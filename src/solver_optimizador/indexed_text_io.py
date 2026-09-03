"""Adaptador tabular puro entre la UI y la especificacion indexada tipada."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any, Iterable

from .indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    ScalarParameterSpec,
    VariableFamilySpec,
)


def _rows(text: str, required: set[str], label: str) -> list[dict[str, str]]:
    source = (text or "").strip()
    if not source:
        return []
    reader = csv.DictReader(io.StringIO(source))
    headers = {str(name).strip() for name in (reader.fieldnames or [])}
    missing = sorted(required - headers)
    if missing:
        raise ValueError(f"{label}: faltan columnas {missing}.")
    result = []
    for number, row in enumerate(reader, start=2):
        normalized = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
        if any(normalized.values()):
            normalized["__row__"] = str(number)
            result.append(normalized)
    return result


def _optional_int(value: str, context: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{context}: '{value}' no es entero.") from exc


def parse_indexed_tables(
    *,
    name: str,
    description: str,
    sets_text: str,
    scalar_parameters_text: str,
    indexed_parameters_text: str,
    variable_families_text: str,
    objectives_text: str,
    constraint_families_text: str,
) -> IndexedModelSpec:
    """Construye la fuente tipada; la validacion matematica ocurre al compilar."""

    sets = tuple(
        IndexSetSpec(row["name"], int(row["start"]), int(row["end"]))
        for row in _rows(sets_text, {"name", "start", "end"}, "Conjuntos")
    )
    scalars = tuple(
        ScalarParameterSpec(row["name"], float(row["value"]))
        for row in _rows(
            scalar_parameters_text, {"name", "value"}, "Parametros escalares"
        )
    )
    parameter_rows = _rows(
        indexed_parameters_text,
        {"parameter", "index_set", "index", "value"},
        "Parametros indexados",
    )
    grouped_parameters: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in parameter_rows:
        key = (row["parameter"], row["index_set"])
        index = int(row["index"])
        if index in grouped_parameters[key]:
            raise ValueError(
                f"Parametros indexados, fila {row['__row__']}: duplicado {row['parameter']}[{index}]."
            )
        grouped_parameters[key][index] = float(row["value"])
    indexed = tuple(
        IndexedParameterSpec(parameter, index_set, values)
        for (parameter, index_set), values in grouped_parameters.items()
    )
    variables = tuple(
        VariableFamilySpec(row["family"], row["index_set"])
        for row in _rows(
            variable_families_text, {"family", "index_set"}, "Familias de variables"
        )
    )
    objective_rows = _rows(
        objectives_text,
        {
            "objective", "sense", "variable_family", "index_set",
            "start_index", "end_index", "coefficient",
        },
        "Objetivos",
    )
    grouped_objectives: dict[tuple[str, str], list[ObjectiveTermSpec]] = defaultdict(list)
    for row in objective_rows:
        grouped_objectives[(row["objective"], row["sense"])].append(
            ObjectiveTermSpec(
                row["variable_family"],
                row["index_set"],
                row["coefficient"] or "1",
                _optional_int(row["start_index"], f"Objetivos, fila {row['__row__']}"),
                _optional_int(row["end_index"], f"Objetivos, fila {row['__row__']}"),
            )
        )
    objectives = tuple(
        IndexedObjectiveSpec(objective, sense, tuple(terms))
        for (objective, sense), terms in grouped_objectives.items()
    )
    constraints = tuple(
        ConstraintFamilySpec(
            row["name"], row["index_set"], row["index_symbol"], row["expression"],
            _optional_int(row["start_index"], f"Restricciones, fila {row['__row__']}"),
            _optional_int(row["end_index"], f"Restricciones, fila {row['__row__']}"),
        )
        for row in _rows(
            constraint_families_text,
            {
                "name", "index_set", "index_symbol", "start_index", "end_index", "expression"
            },
            "Familias de restricciones",
        )
    )
    return IndexedModelSpec(
        name=name.strip() or "Modelo indexado",
        description=description.strip(),
        sets=sets,
        scalar_parameters=scalars,
        indexed_parameters=indexed,
        variable_families=variables,
        objectives=objectives,
        constraint_families=constraints,
    )


def indexed_spec_to_table_texts(spec: IndexedModelSpec) -> dict[str, str]:
    def render(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue().rstrip()

    objective_rows = []
    for objective in spec.objectives:
        for term in objective.terms:
            objective_rows.append(
                (
                    objective.name, objective.sense, term.variable_family, term.index_set,
                    "" if term.start_index is None else term.start_index,
                    "" if term.end_index is None else term.end_index,
                    term.coefficient,
                )
            )
    return {
        "sets": render(["name", "start", "end"], ((item.name, item.start, item.end) for item in spec.sets)),
        "scalars": render(["name", "value"], ((item.name, item.value) for item in spec.scalar_parameters)),
        "indexed": render(
            ["parameter", "index_set", "index", "value"],
            (
                (item.name, item.index_set, index, value)
                for item in spec.indexed_parameters for index, value in item.values.items()
            ),
        ),
        "variables": render(
            ["family", "index_set"], ((item.name, item.index_set) for item in spec.variable_families)
        ),
        "objectives": render(
            [
                "objective", "sense", "variable_family", "index_set",
                "start_index", "end_index", "coefficient",
            ],
            objective_rows,
        ),
        "constraints": render(
            ["name", "index_set", "index_symbol", "start_index", "end_index", "expression"],
            (
                (
                    item.name, item.index_set, item.index_symbol,
                    "" if item.start_index is None else item.start_index,
                    "" if item.end_index is None else item.end_index,
                    item.expression,
                )
                for item in spec.constraint_families
            ),
        ),
    }
