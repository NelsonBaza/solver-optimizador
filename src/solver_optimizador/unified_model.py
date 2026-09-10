"""Compilador del esquema JSON unificado 1.1 a estado canónico disperso."""

from __future__ import annotations

import itertools
import math
import re
from typing import Any, Mapping

from .constraint_import import (
    RESERVED_VARIABLE_NAMES,
    VARIABLE_NAME_PATTERN,
    validate_variable_names,
)
from .indexed_expression import (
    parse_linear_relation_multi_index,
    parse_numeric_expression_multi_index,
)


UNIFIED_SCHEMA_VERSION = "1.1"
_VARIABLE_REFERENCE = re.compile(
    r"^(?P<family>[A-Za-z_][A-Za-z0-9_]*)\["
    r"(?P<indices>[+-]?\d+(?:\s*,\s*[+-]?\d+)?)\]$"
)


def _finite(value: Any, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context}: se esperaba un número finito.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: se esperaba un número finito.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context}: NaN e Infinity no están permitidos.")
    return result


def _integer(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context}: se esperaba un entero.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: se esperaba un entero.") from exc
    if result != value:
        raise ValueError(f"{context}: se esperaba un entero.")
    return result


def _identifier(value: Any, context: str, *, model_name: bool = False) -> str:
    if value is None:
        raise ValueError(f"{context}: el nombre es obligatorio.")
    result = str(value).strip()
    if not result or not VARIABLE_NAME_PATTERN.fullmatch(result):
        raise ValueError(
            f"{context}: '{result}' no es un identificador válido; "
            "use letras ASCII, números y guion bajo."
        )
    if model_name and result.lower() in RESERVED_VARIABLE_NAMES:
        raise ValueError(f"{context}: '{result}' está reservado por la capa de modelado.")
    return result


def _unique(values: list[str], context: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{context}: nombre duplicado '{value}'.")
        seen.add(value)


def _list_of_identifiers(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 2:
        raise ValueError(f"{context}: se requiere una lista de uno o dos nombres.")
    result = tuple(_identifier(item, context) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{context}: los nombres no pueden repetirse.")
    return result


def _sets(document: Mapping[str, Any]) -> dict[str, tuple[int, ...]]:
    raw_sets = document.get("sets", {})
    if raw_sets is None:
        raw_sets = {}
    if not isinstance(raw_sets, Mapping):
        raise ValueError("problem.sets debe ser un objeto JSON.")
    result: dict[str, tuple[int, ...]] = {}
    for raw_name, raw_spec in raw_sets.items():
        name = _identifier(raw_name, "Conjunto")
        if not isinstance(raw_spec, Mapping):
            raise ValueError(f"Conjunto '{name}': la especificación debe ser un objeto.")
        start = _integer(raw_spec.get("start"), f"Conjunto '{name}', start")
        end = _integer(raw_spec.get("end"), f"Conjunto '{name}', end")
        if start > end:
            raise ValueError(f"Conjunto '{name}': start no puede superar end.")
        result[name] = tuple(range(start, end + 1))
    _unique(list(result), "Conjuntos")
    return result


def _domain(
    indices: tuple[str, ...],
    set_names: tuple[str, ...],
    sets: Mapping[str, tuple[int, ...]],
    context: str,
    index_ranges: Any = None,
) -> tuple[tuple[int, ...], ...]:
    if len(indices) != len(set_names):
        raise ValueError(f"{context}: indices y sets deben tener la misma longitud.")
    for set_name in set_names:
        if set_name not in sets:
            raise ValueError(f"{context}: conjunto desconocido '{set_name}'.")
    raw_ranges = {} if index_ranges is None else index_ranges
    if not isinstance(raw_ranges, Mapping):
        raise ValueError(f"{context}: index_ranges debe ser un objeto.")
    unknown = sorted(set(raw_ranges) - set(indices))
    if unknown:
        raise ValueError(f"{context}: rangos para índices desconocidos {unknown}.")

    selected: list[tuple[int, ...]] = []
    for symbol, set_name in zip(indices, set_names):
        values = sets[set_name]
        raw_range = raw_ranges.get(symbol, {})
        if not isinstance(raw_range, Mapping):
            raise ValueError(f"{context}: el rango de '{symbol}' debe ser un objeto.")
        start = _integer(raw_range.get("start", values[0]), f"{context}, inicio de {symbol}")
        end = _integer(raw_range.get("end", values[-1]), f"{context}, fin de {symbol}")
        if start > end or start not in values or end not in values:
            raise ValueError(
                f"{context}: rango {symbol}={start}..{end} fuera de {set_name}."
            )
        selected.append(tuple(value for value in values if start <= value <= end))
    return tuple(itertools.product(*selected))


def _parameter_key(raw_key: Any, dimension: int, context: str) -> tuple[int, ...]:
    parts = [part.strip() for part in str(raw_key).split(",")]
    if len(parts) != dimension or any(not re.fullmatch(r"[+-]?\d+", part) for part in parts):
        raise ValueError(
            f"{context}: la clave '{raw_key}' debe contener {dimension} índice(s) "
            "entero(s) separados por coma."
        )
    return tuple(int(part) for part in parts)


def _parameters(
    document: Mapping[str, Any], sets: Mapping[str, tuple[int, ...]]
) -> tuple[dict[str, float], dict[str, dict[tuple[int, ...], float]], dict[str, Any]]:
    raw_parameters = document.get("parameters", {})
    if raw_parameters is None:
        raw_parameters = {}
    if not isinstance(raw_parameters, Mapping):
        raise ValueError("problem.parameters debe ser un objeto JSON.")
    scalar: dict[str, float] = {}
    indexed: dict[str, dict[tuple[int, ...], float]] = {}
    provenance: dict[str, Any] = {}
    for raw_name, raw_spec in raw_parameters.items():
        name = _identifier(raw_name, "Parámetro")
        if not isinstance(raw_spec, Mapping):
            raise ValueError(f"Parámetro '{name}': la especificación debe ser un objeto.")
        if "value" in raw_spec:
            scalar[name] = _finite(raw_spec["value"], f"Parámetro escalar '{name}'")
            provenance[name] = {"kind": "scalar", "value": scalar[name]}
            continue

        indices = _list_of_identifiers(raw_spec.get("indices"), f"Parámetro '{name}', indices")
        set_names = _list_of_identifiers(raw_spec.get("sets"), f"Parámetro '{name}', sets")
        expected = set(_domain(indices, set_names, sets, f"Parámetro '{name}'"))
        raw_values = raw_spec.get("values")
        if not isinstance(raw_values, Mapping):
            raise ValueError(f"Parámetro '{name}': values debe ser un objeto.")
        supplied: dict[tuple[int, ...], float] = {}
        for raw_key, value in raw_values.items():
            key = _parameter_key(raw_key, len(indices), f"Parámetro '{name}'")
            if key in supplied:
                raise ValueError(f"Parámetro '{name}': índice duplicado {key}.")
            supplied[key] = _finite(value, f"Parámetro '{name}{key}'")
        missing = sorted(expected - set(supplied))
        extra = sorted(set(supplied) - expected)
        if missing:
            raise ValueError(f"Parámetro '{name}': faltan índices {missing}.")
        if extra:
            raise ValueError(f"Parámetro '{name}': índices fuera del dominio {extra}.")
        indexed[name] = supplied
        provenance[name] = {
            "kind": "indexed",
            "indices": list(indices),
            "sets": list(set_names),
        }
    _unique([*scalar, *indexed], "Parámetros")
    return scalar, indexed, provenance


def _variable_reference(
    reference: Any,
    variables: set[str],
    family_domains: Mapping[str, tuple[tuple[str, ...], set[tuple[int, ...]]]],
    context: str,
) -> str:
    rendered = str(reference).strip()
    if rendered in variables:
        return rendered
    match = _VARIABLE_REFERENCE.fullmatch(rendered)
    if not match:
        raise ValueError(f"{context}: variable desconocida '{rendered}'.")
    family = match.group("family")
    if family not in family_domains:
        raise ValueError(f"{context}: familia desconocida '{family}'.")
    indices = tuple(int(item.strip()) for item in match.group("indices").split(","))
    set_names, domain = family_domains[family]
    if len(indices) != len(set_names) or indices not in domain:
        raise ValueError(
            f"{context}: referencia {rendered} fuera de {' x '.join(set_names)}."
        )
    return "_".join((family, *(str(index) for index in indices)))


def _coefficient_map(
    raw: Any,
    variables: set[str],
    family_domains: Mapping[str, tuple[tuple[str, ...], set[tuple[int, ...]]]],
    context: str,
) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{context}: coefficients debe ser un objeto.")
    result: dict[str, float] = {}
    for reference, value in raw.items():
        name = _variable_reference(reference, variables, family_domains, context)
        result[name] = result.get(name, 0.0) + _finite(value, f"{context}, {reference}")
        if result[name] == 0.0:
            del result[name]
    return result


def compile_unified_model_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Valida y expande un documento 1.1 al estado consumido por los builders."""

    if not isinstance(document, Mapping):
        raise ValueError("El archivo JSON debe contener un objeto principal.")
    if str(document.get("schema_version", "")) != UNIFIED_SCHEMA_VERSION:
        raise ValueError("El compilador unificado requiere schema_version '1.1'.")
    problem = document.get("problem")
    if not isinstance(problem, Mapping):
        raise ValueError("El documento debe contener el objeto problem.")
    problem_type = problem.get("type")
    if problem_type not in ("Monoobjetivo", "Biobjetivo", "Multiobjetivo"):
        raise ValueError(
            "problem.type debe ser Monoobjetivo, Biobjetivo o Multiobjetivo."
        )

    sets = _sets(problem)
    scalar_parameters, indexed_parameters, parameter_provenance = _parameters(
        problem, sets
    )

    raw_variables = problem.get("variables", [])
    if not isinstance(raw_variables, list):
        raise ValueError("problem.variables debe ser una lista.")
    explicit_variables = [str(value).strip() for value in raw_variables]
    variable_errors = validate_variable_names(explicit_variables)
    if variable_errors:
        raise ValueError(variable_errors[0])
    collisions = sorted(
        set(explicit_variables) & (set(scalar_parameters) | set(indexed_parameters))
    )
    if collisions:
        raise ValueError(f"Variables explícitas: símbolos ya usados por parámetros {collisions}.")
    variables = list(explicit_variables)
    variable_provenance: dict[str, dict[str, Any]] = {
        name: {"source_type": "explicit", "display_name": name}
        for name in explicit_variables
    }

    raw_families = problem.get("variable_families", [])
    if not isinstance(raw_families, list):
        raise ValueError("problem.variable_families debe ser una lista.")
    family_domains: dict[str, tuple[tuple[str, ...], set[tuple[int, ...]]]] = {}
    family_specs: dict[str, dict[str, tuple[str, ...]]] = {}
    for number, raw_family in enumerate(raw_families, start=1):
        if not isinstance(raw_family, Mapping):
            raise ValueError(f"Familia de variables {number}: se esperaba un objeto.")
        name = _identifier(
            raw_family.get("name"), f"Familia de variables {number}", model_name=True
        )
        if name in scalar_parameters or name in indexed_parameters:
            raise ValueError(f"Familia de variables '{name}': símbolo ya usado por un parámetro.")
        if name in family_domains:
            raise ValueError(f"Familias de variables: nombre duplicado '{name}'.")
        indices = _list_of_identifiers(
            raw_family.get("indices"), f"Familia '{name}', indices"
        )
        collisions = sorted(set(indices) & set(scalar_parameters))
        if collisions:
            raise ValueError(
                f"Familia '{name}': índices en conflicto con parámetros {collisions}."
            )
        set_names = _list_of_identifiers(
            raw_family.get("sets"), f"Familia '{name}', sets"
        )
        domain = _domain(indices, set_names, sets, f"Familia '{name}'")
        family_domains[name] = (set_names, set(domain))
        family_specs[name] = {"indices": indices, "sets": set_names}
        generated = ["_".join((name, *(str(index) for index in key))) for key in domain]
        errors = validate_variable_names(generated)
        if errors:
            raise ValueError(errors[0])
        for key, generated_name in zip(domain, generated):
            if generated_name in variable_provenance:
                raise ValueError(f"Variable expandida duplicada '{generated_name}'.")
            variables.append(generated_name)
            variable_provenance[generated_name] = {
                "source_type": "indexed_family",
                "family_name": name,
                "indices": dict(zip(indices, key)),
                "sets": dict(zip(indices, set_names)),
                "source_reference": f"{name}[{','.join(indices)}]",
            }
    if not variables:
        raise ValueError("El modelo debe producir al menos una variable.")
    _unique(variables, "Variables")
    all_variables = set(variables)

    has_generic_objectives = "objectives" in problem
    has_bi_objectives = "bio_objectives" in problem
    if has_generic_objectives and has_bi_objectives:
        raise ValueError(
            "No defina simultáneamente 'objectives' y 'bio_objectives'."
        )
    if problem_type == "Monoobjetivo":
        if has_generic_objectives:
            raise ValueError(
                "Monoobjetivo conserva el campo 'mono_objective'; "
                "'objectives' se reserva para dos o más objetivos."
            )
        raw_objective_list = [problem.get("mono_objective")]
    elif has_generic_objectives:
        raw_objective_list = problem.get("objectives")
        if not isinstance(raw_objective_list, list):
            raise ValueError("problem.objectives debe ser una lista ordenada.")
        expected_minimum = 3 if problem_type == "Multiobjetivo" else 2
        if problem_type == "Biobjetivo" and len(raw_objective_list) != 2:
            raise ValueError("Biobjetivo requiere exactamente dos objetivos.")
        if problem_type == "Multiobjetivo" and len(raw_objective_list) < expected_minimum:
            raise ValueError("Multiobjetivo requiere al menos tres objetivos.")
    elif problem_type == "Biobjetivo":
        raw_bi_objectives = problem.get("bio_objectives")
        if not isinstance(raw_bi_objectives, Mapping):
            raise ValueError(
                "Biobjetivo requiere 'bio_objectives' o la lista 'objectives'."
            )
        raw_objective_list = [
            raw_bi_objectives.get("obj1"),
            raw_bi_objectives.get("obj2"),
        ]
    else:
        raise ValueError("Multiobjetivo requiere la lista ordenada 'objectives'.")

    compiled_objectives: list[dict[str, Any]] = []
    for objective_number, raw_objective in enumerate(raw_objective_list, start=1):
        if not isinstance(raw_objective, Mapping):
            raise ValueError(f"Falta la configuración del objetivo {objective_number}.")
        sense = raw_objective.get("sense")
        if sense not in ("Maximizar", "Minimizar"):
            raise ValueError(f"Objetivo {objective_number}: sentido inválido '{sense}'.")
        coefficients = _coefficient_map(
            raw_objective.get("coefficients", {}),
            all_variables,
            family_domains,
            f"Objetivo {objective_number}",
        )
        raw_terms = raw_objective.get("indexed_terms", [])
        if not isinstance(raw_terms, list):
            raise ValueError(f"Objetivo {objective_number}: indexed_terms debe ser una lista.")
        for term_number, raw_term in enumerate(raw_terms, start=1):
            if not isinstance(raw_term, Mapping):
                raise ValueError(
                    f"Objetivo {objective_number}, término {term_number}: se esperaba un objeto."
                )
            family = _identifier(
                raw_term.get("variable_family"),
                f"Objetivo {objective_number}, término {term_number}",
            )
            if family not in family_specs:
                raise ValueError(
                    f"Objetivo {objective_number}, término {term_number}: "
                    f"familia desconocida '{family}'."
                )
            expected = family_specs[family]
            indices = tuple(raw_term.get("indices", expected["indices"]))
            set_names = tuple(raw_term.get("sets", expected["sets"]))
            if indices != expected["indices"] or set_names != expected["sets"]:
                raise ValueError(
                    f"Objetivo {objective_number}, término {term_number}: "
                    "indices y sets deben coincidir con la familia."
                )
            domain = _domain(
                indices,
                set_names,
                sets,
                f"Objetivo {objective_number}, término {term_number}",
                raw_term.get("index_ranges"),
            )
            coefficient_source = str(raw_term.get("coefficient", "1"))
            for key_values in domain:
                index_values = dict(zip(indices, key_values))
                coefficient = parse_numeric_expression_multi_index(
                    coefficient_source,
                    scalar_parameters=scalar_parameters,
                    indexed_parameters=indexed_parameters,
                    index_values=index_values,
                    context=f"Objetivo {objective_number}, término {term_number}{key_values}",
                )
                name = "_".join((family, *(str(index) for index in key_values)))
                coefficients[name] = coefficients.get(name, 0.0) + coefficient
                if coefficients[name] == 0.0:
                    del coefficients[name]
        raw_name = str(raw_objective.get("name", "")).strip()
        compiled_objectives.append(
            {
                "name": raw_name or f"Z{objective_number}",
                "sense": sense,
                "coefficients": coefficients,
            }
        )

    raw_constraints = problem.get("constraints", [])
    if not isinstance(raw_constraints, list):
        raise ValueError("problem.constraints debe ser una lista.")
    constraints: list[dict[str, Any]] = []
    constraint_provenance: dict[str, dict[str, Any]] = {}
    used_constraint_names: set[str] = set()
    for number, raw_constraint in enumerate(raw_constraints, start=1):
        if not isinstance(raw_constraint, Mapping):
            raise ValueError(f"Restricción explícita {number}: se esperaba un objeto.")
        name = str(raw_constraint.get("name") or f"Restriccion_{number}").strip()
        if name in used_constraint_names:
            raise ValueError(f"Restricciones: nombre duplicado '{name}'.")
        operator = str(raw_constraint.get("operator", "")).strip()
        if operator not in ("<=", ">=", "="):
            raise ValueError(f"Restricción '{name}': operador inválido '{operator}'.")
        coefficients = _coefficient_map(
            raw_constraint.get("coefficients", {}),
            all_variables,
            family_domains,
            f"Restricción '{name}'",
        )
        constraints.append(
            {
                "name": name,
                "coefficients": coefficients,
                "operator": operator,
                "rhs": _finite(raw_constraint.get("rhs"), f"Restricción '{name}', rhs"),
            }
        )
        used_constraint_names.add(name)
        constraint_provenance[name] = {
            "source_type": "explicit",
            "expanded_name": name,
        }

    raw_constraint_families = problem.get("constraint_families", [])
    if not isinstance(raw_constraint_families, list):
        raise ValueError("problem.constraint_families debe ser una lista.")
    for number, raw_family in enumerate(raw_constraint_families, start=1):
        if not isinstance(raw_family, Mapping):
            raise ValueError(f"Familia de restricciones {number}: se esperaba un objeto.")
        name = _identifier(raw_family.get("name"), f"Familia de restricciones {number}")
        indices = _list_of_identifiers(
            raw_family.get("indices"), f"Familia de restricciones '{name}', indices"
        )
        collisions = sorted(set(indices) & set(scalar_parameters))
        if collisions:
            raise ValueError(
                f"Familia de restricciones '{name}': índices en conflicto "
                f"con parámetros {collisions}."
            )
        set_names = _list_of_identifiers(
            raw_family.get("sets"), f"Familia de restricciones '{name}', sets"
        )
        expression = str(raw_family.get("expression", "")).strip()
        if not expression:
            raise ValueError(f"Familia de restricciones '{name}': falta expression.")
        domain = _domain(
            indices,
            set_names,
            sets,
            f"Familia de restricciones '{name}'",
            raw_family.get("index_ranges"),
        )
        for key_values in domain:
            expanded_name = "_".join((name, *(str(index) for index in key_values)))
            if expanded_name in used_constraint_names:
                raise ValueError(f"Restricciones: nombre duplicado '{expanded_name}'.")
            index_values = dict(zip(indices, key_values))
            coefficients, operator, rhs = parse_linear_relation_multi_index(
                expression,
                scalar_parameters=scalar_parameters,
                indexed_parameters=indexed_parameters,
                variable_domains=family_domains,
                explicit_variables=set(explicit_variables),
                index_values=index_values,
                context=f"{name}{key_values}",
            )
            constraints.append(
                {
                    "name": expanded_name,
                    "coefficients": coefficients,
                    "operator": operator,
                    "rhs": rhs,
                }
            )
            used_constraint_names.add(expanded_name)
            constraint_provenance[expanded_name] = {
                "source_type": "constraint_family",
                "family_name": name,
                "indices": index_values,
                "sets": dict(zip(indices, set_names)),
                "source_expression": expression,
                "expanded_name": expanded_name,
            }
    if not constraints:
        raise ValueError("El modelo debe producir al menos una restricción.")

    metadata = document.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata debe ser un objeto JSON.")
    state: dict[str, Any] = {
        "schema_version": UNIFIED_SCHEMA_VERSION,
        "metadata": {
            "name": str(metadata.get("name", "Modelo unificado")).strip()
            or "Modelo unificado",
            "description": str(metadata.get("description", "")).strip(),
            "plot_title": str(metadata.get("plot_title", "")).strip(),
        },
        "problem_type": problem_type,
        "objectives": compiled_objectives,
        "num_vars": len(variables),
        "var_names": variables,
        "constraints_data": constraints,
        "source_provenance": {
            "variables": variable_provenance,
            "constraints": constraint_provenance,
            "parameters": parameter_provenance,
        },
        "expansion_statistics": {
            "sets": len(sets),
            "scalar_parameters": len(scalar_parameters),
            "indexed_parameters": len(indexed_parameters),
            "explicit_variables": len(explicit_variables),
            "generated_variables": len(variables) - len(explicit_variables),
            "total_variables": len(variables),
            "explicit_constraints": len(raw_constraints),
            "generated_constraints": len(constraints) - len(raw_constraints),
            "total_constraints": len(constraints),
            "nonzero_coefficients": sum(
                len(item["coefficients"]) for item in constraints
            ),
        },
    }
    if problem_type == "Biobjetivo":
        state.update(
            {
                "obj1_sense": compiled_objectives[0]["sense"],
                "obj1_coeffs": compiled_objectives[0]["coefficients"],
                "obj2_sense": compiled_objectives[1]["sense"],
                "obj2_coeffs": compiled_objectives[1]["coefficients"],
            }
        )
    elif problem_type == "Monoobjetivo":
        state.update(
            {
                "obj_sense": compiled_objectives[0]["sense"],
                "obj_coeffs": compiled_objectives[0]["coefficients"],
            }
        )
    return state
