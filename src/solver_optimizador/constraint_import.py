"""Importacion solver-agnostic de variables, objetivos y restricciones lineales.

El modulo transforma tablas anchas o dispersas en la representacion canonica
que consumen los builders. No importa Streamlit, Pyomo ni ningun solver.
"""

from __future__ import annotations

import csv
import io
import math
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET


ALLOWED_OPERATORS = {"<=", ">=", "="}
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_VARIABLE_NAMES = {
    "active",
    "component",
    "display",
    "index",
    "model",
    "name",
    "parent_component",
    "pprint",
}
MAX_XLSX_COMPRESSED_BYTES = 20 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_XLSX_CELLS = 2_000_000


@dataclass
class ConstraintImportResult:
    constraints: list[dict[str, Any]] = field(default_factory=list)
    detected_variables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_format: str = "unknown"
    source_rows: int = 0

    @property
    def number_of_constraints(self) -> int:
        return len(self.constraints)

    @property
    def number_of_variables(self) -> int:
        return len(self.detected_variables)

    @property
    def nonzero_coefficients(self) -> int:
        return sum(len(row["coefficients"]) for row in self.constraints)

    @property
    def density(self) -> float:
        denominator = self.number_of_constraints * self.number_of_variables
        return self.nonzero_coefficients / denominator if denominator else 0.0

    @property
    def is_valid(self) -> bool:
        return not self.errors and bool(self.constraints)


@dataclass
class VariableImportResult:
    variables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_format: str = "block"

    @property
    def is_valid(self) -> bool:
        return not self.errors and bool(self.variables)


@dataclass
class ObjectiveImportResult:
    problem_type: str
    coefficients: dict[str, float] = field(default_factory=dict)
    coefficients_z1: dict[str, float] = field(default_factory=dict)
    coefficients_z2: dict[str, float] = field(default_factory=dict)
    recognized_variables: list[str] = field(default_factory=list)
    unknown_variables: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_format: str = "delimited"

    @property
    def is_valid(self) -> bool:
        return not self.errors and bool(self.recognized_variables)


def validate_variable_names(variable_names: Sequence[str]) -> list[str]:
    """Devuelve errores deterministas para una lista de nombres de variables."""

    errors: list[str] = []
    seen: set[str] = set()
    for position, raw_name in enumerate(variable_names, start=1):
        name = str(raw_name).strip()
        if not name:
            errors.append(f"Variable #{position}: nombre vacio.")
            continue
        if not VARIABLE_NAME_PATTERN.fullmatch(name):
            errors.append(
                f"Variable '{name}': use letras ASCII, numeros y guion bajo; "
                "el primer caracter no puede ser un numero."
            )
        if name.lower() in RESERVED_VARIABLE_NAMES:
            errors.append(f"Variable '{name}': nombre reservado por la capa de modelado.")
        if name in seen:
            errors.append(f"Variable duplicada: '{name}'.")
        seen.add(name)
    return errors


def parse_variable_names(text: str) -> VariableImportResult:
    """Parsea nombres separados por coma, punto y coma, tabulador o salto."""

    tokens = [token.strip() for token in re.split(r"[,;\t\r\n]+", text or "")]
    variables = [token for token in tokens if token]
    errors = validate_variable_names(variables)
    if not variables:
        errors.append("No se detectaron nombres de variables.")
    return VariableImportResult(variables=variables, errors=errors)


def _normalized_header(value: Any) -> str:
    return str(value if value is not None else "").strip().lstrip("\ufeff").lower()


def _parse_number(value: Any, *, context: str, decimal_separator: str = ".") -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{context}: valor numerico vacio o invalido.")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        raw = str(value).strip()
        if not raw:
            raise ValueError(f"{context}: valor numerico vacio.")
        if decimal_separator == ",":
            raw = raw.replace(".", "").replace(",", ".")
        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError(f"{context}: '{value}' no es numerico.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context}: NaN e Infinity no estan permitidos.")
    return number


def detect_delimiter(text: str) -> str:
    """Detecta tabulador, punto y coma o coma sin ejecutar contenido."""

    sample = "\n".join((text or "").splitlines()[:20])
    if not sample.strip():
        raise ValueError("La tabla esta vacia.")
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t;,").delimiter
    except csv.Error:
        first_line = sample.splitlines()[0]
        counts = {delimiter: first_line.count(delimiter) for delimiter in ("\t", ";", ",")}
        delimiter = max(counts, key=counts.get)
        if counts[delimiter] == 0:
            raise ValueError("No se pudo detectar un delimitador tabular.")
        return delimiter


def _read_delimited_table(text: str, delimiter: str | None) -> tuple[list[str], list[list[str]], str]:
    selected = delimiter or detect_delimiter(text)
    if selected not in {"\t", ";", ","}:
        raise ValueError("Delimitador no soportado. Use tabulador, coma o punto y coma.")
    rows = [row for row in csv.reader(io.StringIO(text), delimiter=selected) if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("La tabla esta vacia.")
    headers = [cell.strip().lstrip("\ufeff") for cell in rows[0]]
    if any(not header for header in headers):
        raise ValueError("La cabecera contiene columnas vacias.")
    normalized = [_normalized_header(header) for header in headers]
    if len(set(normalized)) != len(normalized):
        raise ValueError("La cabecera contiene columnas duplicadas.")
    body: list[list[str]] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(headers):
            raise ValueError(
                f"Fila {row_number}: se esperaban {len(headers)} columnas y se recibieron {len(row)}."
            )
        body.append([cell.strip() for cell in row])
    delimiter_name = {"\t": "tsv", ";": "semicolon", ",": "csv"}[selected]
    return headers, body, delimiter_name


def _find_column(headers: Sequence[str], aliases: set[str]) -> int | None:
    for index, header in enumerate(headers):
        if _normalized_header(header) in aliases:
            return index
    return None


def _validate_declared_variables(
    detected: Sequence[str], declared_variables: Sequence[str] | None, strict_variables: bool
) -> list[str]:
    if not strict_variables or declared_variables is None:
        return []
    declared = set(declared_variables)
    return [
        f"Variable '{variable}' no declarada en el modelo actual."
        for variable in detected
        if variable not in declared
    ]


def import_constraint_table(
    headers: Sequence[Any],
    rows: Iterable[Sequence[Any]],
    *,
    input_format: str = "auto",
    declared_variables: Sequence[str] | None = None,
    strict_variables: bool = False,
    decimal_separator: str = ".",
    source_format: str = "table",
) -> ConstraintImportResult:
    """Punto canonico para tablas explicitas y futuras expansiones indexadas."""

    clean_headers = [str(value if value is not None else "").strip().lstrip("\ufeff") for value in headers]
    normalized_headers = [_normalized_header(value) for value in clean_headers]
    result = ConstraintImportResult(source_format=source_format)
    if not clean_headers or any(not value for value in clean_headers):
        result.errors.append("La cabecera esta vacia o contiene columnas sin nombre.")
        return result
    if len(set(normalized_headers)) != len(normalized_headers):
        result.errors.append("La cabecera contiene columnas duplicadas.")
        return result

    row_list = [list(row) for row in rows]
    result.source_rows = len(row_list)
    for row_number, row in enumerate(row_list, start=2):
        if len(row) != len(clean_headers):
            result.errors.append(
                f"Fila {row_number}: se esperaban {len(clean_headers)} columnas y se recibieron {len(row)}."
            )
    if result.errors:
        return result

    sparse_columns = {"constraint", "variable", "coefficient", "operator", "rhs"}
    format_name = input_format.lower().strip()
    if format_name == "auto":
        format_name = "sparse" if sparse_columns.issubset(set(normalized_headers)) else "wide"
    if format_name not in {"wide", "sparse"}:
        result.errors.append("Formato desconocido. Use 'wide', 'sparse' o 'auto'.")
        return result

    if format_name == "wide":
        name_index = _find_column(clean_headers, {"name", "nombre", "constraint", "restriccion"})
        operator_index = _find_column(clean_headers, {"operator", "operador"})
        rhs_index = _find_column(clean_headers, {"rhs", "lado_derecho"})
        if None in (name_index, operator_index, rhs_index):
            result.errors.append("Formato ancho: se requieren columnas name, operator y rhs.")
            return result
        fixed = {name_index, operator_index, rhs_index}
        variable_indices = [index for index in range(len(clean_headers)) if index not in fixed]
        variables = [clean_headers[index] for index in variable_indices]
        result.detected_variables = variables
        result.errors.extend(validate_variable_names(variables))
        result.errors.extend(
            _validate_declared_variables(variables, declared_variables, strict_variables)
        )
        seen_constraints: set[str] = set()
        for row_number, row in enumerate(row_list, start=2):
            name = str(row[name_index]).strip()
            operator = str(row[operator_index]).strip()
            if not name:
                result.errors.append(f"Fila {row_number}: nombre de restriccion vacio.")
                continue
            if name in seen_constraints:
                result.errors.append(f"Fila {row_number}: restriccion duplicada '{name}'.")
            seen_constraints.add(name)
            if operator not in ALLOWED_OPERATORS:
                result.errors.append(f"Fila {row_number}: operador invalido '{operator}'.")
            try:
                rhs = _parse_number(row[rhs_index], context=f"Fila {row_number}, RHS", decimal_separator=decimal_separator)
            except ValueError as exc:
                result.errors.append(str(exc))
                rhs = 0.0
            coefficients: dict[str, float] = {}
            for variable, index in zip(variables, variable_indices):
                raw_value = row[index]
                if raw_value is None or str(raw_value).strip() == "":
                    continue
                try:
                    coefficient = _parse_number(
                        raw_value,
                        context=f"Fila {row_number}, variable '{variable}'",
                        decimal_separator=decimal_separator,
                    )
                except ValueError as exc:
                    result.errors.append(str(exc))
                    continue
                if coefficient != 0.0:
                    coefficients[variable] = coefficient
            result.constraints.append(
                {"name": name, "coefficients": coefficients, "operator": operator, "rhs": rhs}
            )
    else:
        constraint_index = _find_column(clean_headers, {"constraint", "restriccion"})
        variable_index = _find_column(clean_headers, {"variable"})
        coefficient_index = _find_column(clean_headers, {"coefficient", "coeficiente"})
        operator_index = _find_column(clean_headers, {"operator", "operador"})
        rhs_index = _find_column(clean_headers, {"rhs", "lado_derecho"})
        if None in (constraint_index, variable_index, coefficient_index, operator_index, rhs_index):
            result.errors.append(
                "Formato disperso: se requieren constraint, variable, coefficient, operator y rhs."
            )
            return result
        grouped: dict[str, dict[str, Any]] = {}
        variable_order: list[str] = []
        seen_pairs: set[tuple[str, str]] = set()
        for row_number, row in enumerate(row_list, start=2):
            constraint_name = str(row[constraint_index]).strip()
            variable = str(row[variable_index]).strip()
            operator = str(row[operator_index]).strip()
            if not constraint_name:
                result.errors.append(f"Fila {row_number}: nombre de restriccion vacio.")
            if not variable:
                result.errors.append(f"Fila {row_number}: variable vacia.")
            elif variable not in variable_order:
                variable_order.append(variable)
            if operator not in ALLOWED_OPERATORS:
                result.errors.append(f"Fila {row_number}: operador invalido '{operator}'.")
            try:
                coefficient = _parse_number(
                    row[coefficient_index],
                    context=f"Fila {row_number}, coeficiente",
                    decimal_separator=decimal_separator,
                )
                rhs = _parse_number(
                    row[rhs_index], context=f"Fila {row_number}, RHS", decimal_separator=decimal_separator
                )
            except ValueError as exc:
                result.errors.append(str(exc))
                continue
            pair = (constraint_name, variable)
            is_duplicate = pair in seen_pairs
            if is_duplicate:
                result.errors.append(
                    f"Fila {row_number}: par duplicado constraint-variable {pair}."
                )
            seen_pairs.add(pair)
            current = grouped.get(constraint_name)
            if current is None:
                current = {
                    "name": constraint_name,
                    "coefficients": {},
                    "operator": operator,
                    "rhs": rhs,
                }
                grouped[constraint_name] = current
            else:
                if current["operator"] != operator:
                    result.errors.append(
                        f"Fila {row_number}: '{constraint_name}' tiene operador inconsistente "
                        f"({current['operator']} frente a {operator})."
                    )
                if current["rhs"] != rhs:
                    result.errors.append(
                        f"Fila {row_number}: '{constraint_name}' tiene RHS inconsistente "
                        f"({current['rhs']:g} frente a {rhs:g})."
                    )
            if coefficient != 0.0 and not is_duplicate:
                current["coefficients"][variable] = coefficient
        result.detected_variables = variable_order
        result.errors.extend(validate_variable_names(variable_order))
        result.errors.extend(
            _validate_declared_variables(variable_order, declared_variables, strict_variables)
        )
        result.constraints = list(grouped.values())

    if not result.constraints:
        result.errors.append("No se detectaron restricciones.")
    if any(not row["name"] for row in result.constraints):
        result.errors.append("Existen nombres de restriccion vacios.")
    result.source_format = f"{source_format}_{format_name}"
    return result


def parse_constraint_text(
    text: str,
    *,
    input_format: str = "auto",
    delimiter: str | None = None,
    declared_variables: Sequence[str] | None = None,
    strict_variables: bool = False,
    decimal_separator: str = ".",
) -> ConstraintImportResult:
    """Parsea CSV, TSV o texto separado por punto y coma."""

    try:
        headers, rows, delimiter_name = _read_delimited_table(text, delimiter)
    except ValueError as exc:
        return ConstraintImportResult(errors=[str(exc)], source_format="delimited")
    return import_constraint_table(
        headers,
        rows,
        input_format=input_format,
        declared_variables=declared_variables,
        strict_variables=strict_variables,
        decimal_separator=decimal_separator,
        source_format=delimiter_name,
    )


def parse_objective_text(
    text: str,
    *,
    problem_type: str,
    declared_variables: Sequence[str],
    delimiter: str | None = None,
    decimal_separator: str = ".",
    strict_variables: bool = True,
) -> ObjectiveImportResult:
    """Parsea lotes `variable,coefficient` o `variable,Z1,Z2`."""

    result = ObjectiveImportResult(problem_type=problem_type)
    try:
        headers, rows, delimiter_name = _read_delimited_table(text, delimiter)
    except ValueError as exc:
        result.errors.append(str(exc))
        return result
    result.source_format = delimiter_name
    variable_index = _find_column(headers, {"variable"})
    if problem_type == "Monoobjetivo":
        coefficient_index = _find_column(headers, {"coefficient", "coeficiente", "z"})
        required = (variable_index, coefficient_index)
    elif problem_type == "Biobjetivo":
        z1_index = _find_column(headers, {"z1", "coefficient_z1", "coeficiente_z1"})
        z2_index = _find_column(headers, {"z2", "coefficient_z2", "coeficiente_z2"})
        required = (variable_index, z1_index, z2_index)
    else:
        result.errors.append(f"Tipo de problema no soportado: '{problem_type}'.")
        return result
    if any(index is None for index in required):
        expected = "variable,coefficient" if problem_type == "Monoobjetivo" else "variable,Z1,Z2"
        result.errors.append(f"Cabecera invalida. Se esperaba {expected}.")
        return result

    declared = set(declared_variables)
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        variable = str(row[variable_index]).strip()
        if not variable:
            result.errors.append(f"Fila {row_number}: variable vacia.")
            continue
        if variable in seen:
            result.duplicates.append(variable)
            result.errors.append(f"Fila {row_number}: variable duplicada '{variable}'.")
            continue
        seen.add(variable)
        if variable not in declared:
            result.unknown_variables.append(variable)
            if strict_variables:
                result.errors.append(f"Fila {row_number}: variable desconocida '{variable}'.")
            continue
        result.recognized_variables.append(variable)
        try:
            if problem_type == "Monoobjetivo":
                result.coefficients[variable] = _parse_number(
                    row[coefficient_index],
                    context=f"Fila {row_number}, coeficiente",
                    decimal_separator=decimal_separator,
                )
            else:
                result.coefficients_z1[variable] = _parse_number(
                    row[z1_index],
                    context=f"Fila {row_number}, Z1",
                    decimal_separator=decimal_separator,
                )
                result.coefficients_z2[variable] = _parse_number(
                    row[z2_index],
                    context=f"Fila {row_number}, Z2",
                    decimal_separator=decimal_separator,
                )
        except ValueError as exc:
            result.errors.append(str(exc))
    omitted = [variable for variable in declared_variables if variable not in seen]
    if omitted:
        result.warnings.append(
            f"{len(omitted)} variables omitidas se estableceran en 0 al aplicar el lote."
        )
    return result


def _xlsx_namespace(tag: str) -> str:
    return f"{{http://schemas.openxmlformats.org/spreadsheetml/2006/main}}{tag}"


def _relationship_namespace(tag: str) -> str:
    return f"{{http://schemas.openxmlformats.org/package/2006/relationships}}{tag}"


def _column_index(cell_reference: str) -> int:
    letters = "".join(character for character in cell_reference if character.isalpha())
    value = 0
    for character in letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _load_xlsx_tables(data: bytes) -> dict[str, list[list[Any]]]:
    if not isinstance(data, bytes) or not data:
        raise ValueError("El archivo XLSX esta vacio.")
    if len(data) > MAX_XLSX_COMPRESSED_BYTES:
        raise ValueError("El archivo XLSX supera el limite de 20 MiB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no es un XLSX valido.") from exc
    with archive:
        total_size = sum(info.file_size for info in archive.infolist())
        if total_size > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise ValueError("El contenido XLSX descomprimido supera el limite de seguridad.")
        names = set(archive.namelist())
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise ValueError("Los libros con macros VBA no estan permitidos.")
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise ValueError("El XLSX no contiene una estructura de libro valida.")

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(_xlsx_namespace("si")):
                shared_strings.append(
                    "".join(node.text or "" for node in item.iter(_xlsx_namespace("t")))
                )

        relationships_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            node.attrib["Id"]: node.attrib["Target"]
            for node in relationships_root.findall(_relationship_namespace("Relationship"))
            if node.attrib.get("TargetMode") != "External"
        }
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        relationship_id_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        tables: dict[str, list[list[Any]]] = {}
        cell_count = 0
        for sheet in workbook_root.iter(_xlsx_namespace("sheet")):
            sheet_name = sheet.attrib.get("name", "").strip()
            relationship_id = sheet.attrib.get(relationship_id_key)
            target = relationships.get(relationship_id or "")
            if not sheet_name or not target:
                continue
            target_path = posixpath.normpath(posixpath.join("xl", target.lstrip("/")))
            if target_path.startswith("xl/xl/"):
                target_path = target_path[3:]
            if target_path not in names:
                raise ValueError(f"No se encontro la hoja '{sheet_name}' dentro del XLSX.")
            root = ET.fromstring(archive.read(target_path))
            sheet_rows: list[list[Any]] = []
            for row_node in root.iter(_xlsx_namespace("row")):
                values: dict[int, Any] = {}
                for cell in row_node.findall(_xlsx_namespace("c")):
                    cell_count += 1
                    if cell_count > MAX_XLSX_CELLS:
                        raise ValueError("El XLSX supera el limite de celdas permitido.")
                    index = _column_index(cell.attrib.get("r", "A1"))
                    cell_type = cell.attrib.get("t")
                    formula = cell.find(_xlsx_namespace("f"))
                    value_node = cell.find(_xlsx_namespace("v"))
                    inline = cell.find(_xlsx_namespace("is"))
                    if formula is not None and value_node is None:
                        raise ValueError(
                            f"La hoja '{sheet_name}' contiene una formula sin valor almacenado; "
                            "no se ejecutan formulas durante la importacion."
                        )
                    if cell_type == "inlineStr" and inline is not None:
                        value: Any = "".join(
                            node.text or "" for node in inline.iter(_xlsx_namespace("t"))
                        )
                    elif value_node is None:
                        value = ""
                    elif cell_type == "s":
                        try:
                            value = shared_strings[int(value_node.text or "0")]
                        except (ValueError, IndexError) as exc:
                            raise ValueError("Indice de texto compartido XLSX invalido.") from exc
                    elif cell_type in {"str", "b"}:
                        value = value_node.text or ""
                    else:
                        raw = value_node.text or ""
                        try:
                            value = float(raw)
                        except ValueError:
                            value = raw
                    values[index] = value
                if values:
                    width = max(values) + 1
                    sheet_rows.append([values.get(index, "") for index in range(width)])
            tables[sheet_name] = sheet_rows
        if not tables:
            raise ValueError("El XLSX no contiene hojas legibles.")
        return tables


def list_xlsx_sheets(data: bytes) -> list[str]:
    """Lista hojas disponibles sin ejecutar macros ni formulas."""

    return list(_load_xlsx_tables(data))


def parse_xlsx_constraints(
    data: bytes,
    *,
    sheet_name: str,
    input_format: str = "auto",
    declared_variables: Sequence[str] | None = None,
    strict_variables: bool = False,
    decimal_separator: str = ".",
) -> ConstraintImportResult:
    """Importa una hoja XLSX OOXML como datos tabulares."""

    try:
        tables = _load_xlsx_tables(data)
    except ValueError as exc:
        return ConstraintImportResult(errors=[str(exc)], source_format="xlsx")
    if sheet_name not in tables:
        return ConstraintImportResult(
            errors=[f"La hoja '{sheet_name}' no existe en el libro."], source_format="xlsx"
        )
    matrix = tables[sheet_name]
    if not matrix:
        return ConstraintImportResult(errors=[f"La hoja '{sheet_name}' esta vacia."], source_format="xlsx")
    width = len(matrix[0])
    rows = [row + [""] * (width - len(row)) for row in matrix[1:]]
    return import_constraint_table(
        matrix[0],
        rows,
        input_format=input_format,
        declared_variables=declared_variables,
        strict_variables=strict_variables,
        decimal_separator=decimal_separator,
        source_format="xlsx",
    )


def constraints_to_sparse_csv(
    constraints: Sequence[Mapping[str, Any]],
    variable_names: Sequence[str] | None = None,
) -> str:
    """Exporta restricciones canonicas a formato long sin densificar."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["constraint", "variable", "coefficient", "operator", "rhs"])
    for constraint in constraints:
        coefficients = constraint.get("coefficients", {})
        if not isinstance(coefficients, Mapping):
            coefficients = {
                key: value
                for key, value in constraint.items()
                if key not in {"name", "Nombre", "operator", "Operador", "rhs", "RHS"}
                and value not in (0, 0.0, None, "")
            }
        written = False
        for variable, coefficient in coefficients.items():
            if float(coefficient) != 0.0:
                writer.writerow(
                    [
                        constraint.get("name", constraint.get("Nombre", "")),
                        variable,
                        format(float(coefficient), ".17g"),
                        constraint.get("operator", constraint.get("Operador", "")),
                        format(float(constraint.get("rhs", constraint.get("RHS", 0.0))), ".17g"),
                    ]
                )
                written = True
        if not written:
            if not variable_names:
                raise ValueError(
                    "Se requieren variables declaradas para exportar una restriccion sin terminos."
                )
            writer.writerow(
                [
                    constraint.get("name", constraint.get("Nombre", "")),
                    variable_names[0],
                    "0",
                    constraint.get("operator", constraint.get("Operador", "")),
                    format(float(constraint.get("rhs", constraint.get("RHS", 0.0))), ".17g"),
                ]
            )
    return output.getvalue()


def constraint_template_wide() -> str:
    return "name,x1,x2,x3,operator,rhs\nR1,2,3,0,<=,20\nR2,0,1,4,>=,15\n"


def constraint_template_sparse() -> str:
    return (
        "constraint,variable,coefficient,operator,rhs\n"
        "R1,x1,2,<=,20\nR1,x7,5,<=,20\nR2,x4,3,>=,15\n"
    )


def objective_template_mono() -> str:
    return "variable,coefficient\nx1,10\nx2,5\nx50,-2\n"


def objective_template_bi() -> str:
    return "variable,Z1,Z2\nx1,10,0.8\nx2,3,1.3\nx50,-2,5\n"
