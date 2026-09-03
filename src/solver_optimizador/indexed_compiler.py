"""Validador y compilador solver-agnostic de modelos indexados a forma explicita."""

from __future__ import annotations

import math
from typing import Iterable

from .constraint_import import RESERVED_VARIABLE_NAMES, VARIABLE_NAME_PATTERN, validate_variable_names
from .indexed_expression import parse_linear_relation, parse_numeric_expression
from .indexed_model import ExpandedIndexedModel, IndexedModelSpec


def _finite(value: object, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context}: se esperaba un numero finito.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: se esperaba un numero finito.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context}: NaN e Infinity no estan permitidos.")
    return result


def _identifier(name: object, context: str, *, reject_model_reserved: bool = False) -> str:
    result = str(name).strip()
    if not result or not VARIABLE_NAME_PATTERN.fullmatch(result):
        raise ValueError(
            f"{context}: '{result}' no es un identificador valido; use letras ASCII, numeros y guion bajo."
        )
    if reject_model_reserved and result.lower() in RESERVED_VARIABLE_NAMES:
        raise ValueError(
            f"{context}: '{result}' esta reservado temporalmente por la capa de modelado."
        )
    return result


def _unique(names: Iterable[str], context: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"{context}: nombre duplicado '{name}'.")
        seen.add(name)


def _selected_indices(
    set_values: tuple[int, ...],
    start: int | None,
    end: int | None,
    context: str,
) -> tuple[int, ...]:
    selected_start = set_values[0] if start is None else int(start)
    selected_end = set_values[-1] if end is None else int(end)
    if selected_start > selected_end:
        raise ValueError(f"{context}: el indice inicial no puede superar al final.")
    selected = tuple(index for index in set_values if selected_start <= index <= selected_end)
    expected = selected_end - selected_start + 1
    if len(selected) != expected:
        raise ValueError(
            f"{context}: rango {selected_start}..{selected_end} fuera del conjunto "
            f"{set_values[0]}..{set_values[-1]}."
        )
    return selected


def compile_indexed_model(spec: IndexedModelSpec) -> ExpandedIndexedModel:
    """Valida y expande familias a las estructuras canonicas dispersas vigentes."""

    if spec.indexed_schema_version != "1.0":
        raise ValueError(f"Version indexada no soportada: '{spec.indexed_schema_version}'.")
    if not spec.sets:
        raise ValueError("El modelo indexado debe declarar al menos un conjunto.")
    if not spec.variable_families:
        raise ValueError("El modelo indexado debe declarar al menos una familia de variables.")
    if len(spec.objectives) not in (1, 2):
        raise ValueError("El modelo indexado debe declarar uno o dos objetivos.")
    if not spec.constraint_families:
        raise ValueError("El modelo indexado debe declarar al menos una familia de restricciones.")

    set_names = [_identifier(item.name, "Conjunto") for item in spec.sets]
    _unique(set_names, "Conjuntos")
    sets: dict[str, tuple[int, ...]] = {}
    for item in spec.sets:
        if isinstance(item.start, bool) or isinstance(item.end, bool):
            raise ValueError(f"Conjunto '{item.name}': los limites deben ser enteros.")
        start, end = int(item.start), int(item.end)
        if start != item.start or end != item.end or start > end:
            raise ValueError(f"Conjunto '{item.name}': se requiere start <= end con enteros.")
        sets[item.name] = tuple(range(start, end + 1))

    scalar_names = [_identifier(item.name, "Parametro escalar") for item in spec.scalar_parameters]
    indexed_names = [_identifier(item.name, "Parametro indexado") for item in spec.indexed_parameters]
    family_names = [
        _identifier(item.name, "Familia de variables", reject_model_reserved=True)
        for item in spec.variable_families
    ]
    _unique(scalar_names, "Parametros escalares")
    _unique(indexed_names, "Parametros indexados")
    _unique(family_names, "Familias de variables")
    _unique([*scalar_names, *indexed_names, *family_names], "Simbolos del modelo")

    scalar_parameters = {
        item.name: _finite(item.value, f"Parametro escalar '{item.name}'")
        for item in spec.scalar_parameters
    }
    indexed_parameters: dict[str, dict[int, float]] = {}
    for item in spec.indexed_parameters:
        if item.index_set not in sets:
            raise ValueError(
                f"Parametro '{item.name}': conjunto desconocido '{item.index_set}'."
            )
        required = set(sets[item.index_set])
        supplied = set(item.values)
        missing = sorted(required - supplied)
        extra = sorted(supplied - required)
        if missing:
            raise ValueError(f"Parametro '{item.name}': faltan indices {missing}.")
        if extra:
            raise ValueError(f"Parametro '{item.name}': indices fuera del conjunto {extra}.")
        indexed_parameters[item.name] = {
            int(index): _finite(value, f"Parametro '{item.name}[{index}]'")
            for index, value in item.values.items()
        }

    variables: list[str] = []
    variable_provenance: dict[str, dict[str, object]] = {}
    variable_sets: dict[str, tuple[str, set[int]]] = {}
    for family in spec.variable_families:
        if family.index_set not in sets:
            raise ValueError(
                f"Familia '{family.name}': conjunto desconocido '{family.index_set}'."
            )
        family_indices = sets[family.index_set]
        variable_sets[family.name] = (family.index_set, set(family_indices))
        generated = [f"{family.name}_{index}" for index in family_indices]
        errors = validate_variable_names(generated)
        if errors:
            raise ValueError("; ".join(errors))
        for index, name in zip(family_indices, generated):
            variables.append(name)
            variable_provenance[name] = {
                "display_name": name,
                "family_name": family.name,
                "index": index,
                "index_set": family.index_set,
            }

    objective_names = [_identifier(item.name, "Objetivo") for item in spec.objectives]
    _unique(objective_names, "Objetivos")
    compiled_objectives: list[dict[str, object]] = []
    for objective in spec.objectives:
        if objective.sense not in ("Maximizar", "Minimizar"):
            raise ValueError(
                f"Objetivo '{objective.name}': sentido invalido '{objective.sense}'."
            )
        if not objective.terms:
            raise ValueError(f"Objetivo '{objective.name}': debe contener al menos un termino.")
        coefficients: dict[str, float] = {}
        for term_number, term in enumerate(objective.terms, start=1):
            if term.variable_family not in variable_sets:
                raise ValueError(
                    f"Objetivo '{objective.name}', termino {term_number}: familia desconocida "
                    f"'{term.variable_family}'."
                )
            family_set_name, family_indices_set = variable_sets[term.variable_family]
            if term.index_set != family_set_name or term.index_set not in sets:
                raise ValueError(
                    f"Objetivo '{objective.name}', termino {term_number}: el conjunto "
                    f"'{term.index_set}' no corresponde a la familia '{term.variable_family}'."
                )
            indices = _selected_indices(
                sets[term.index_set], term.start_index, term.end_index,
                f"Objetivo '{objective.name}', termino {term_number}",
            )
            for index in indices:
                if index not in family_indices_set:
                    raise ValueError(f"Objetivo '{objective.name}': indice {index} no disponible.")
                coefficient = parse_numeric_expression(
                    term.coefficient,
                    scalar_parameters=scalar_parameters,
                    indexed_parameters=indexed_parameters,
                    index_symbol="t",
                    index_value=index,
                    context=f"Objetivo {objective.name}[{index}]",
                )
                name = f"{term.variable_family}_{index}"
                coefficients[name] = coefficients.get(name, 0.0) + coefficient
                if coefficients[name] == 0.0:
                    del coefficients[name]
        compiled_objectives.append(
            {"name": objective.name, "sense": objective.sense, "coefficients": coefficients}
        )

    family_names_constraints = [
        _identifier(item.name, "Familia de restricciones") for item in spec.constraint_families
    ]
    _unique(family_names_constraints, "Familias de restricciones")
    constraints: list[dict[str, object]] = []
    constraint_provenance: dict[str, dict[str, object]] = {}
    for family in spec.constraint_families:
        if family.index_set not in sets:
            raise ValueError(
                f"Familia '{family.name}': conjunto desconocido '{family.index_set}'."
            )
        index_symbol = _identifier(family.index_symbol, f"Familia '{family.name}', simbolo")
        indices = _selected_indices(
            sets[family.index_set], family.start_index, family.end_index,
            f"Familia '{family.name}'",
        )
        for index in indices:
            generated_name = f"{family.name}_{index}"
            coefficients, operator, rhs = parse_linear_relation(
                family.expression,
                scalar_parameters=scalar_parameters,
                indexed_parameters=indexed_parameters,
                variable_sets=variable_sets,
                index_symbol=index_symbol,
                index_value=index,
                context=f"{family.name}[{index}]",
            )
            constraints.append(
                {
                    "name": generated_name,
                    "coefficients": coefficients,
                    "operator": operator,
                    "rhs": rhs,
                }
            )
            constraint_provenance[generated_name] = {
                "family_name": family.name,
                "index_symbol": index_symbol,
                "index": index,
                "index_set": family.index_set,
                "source_expression": family.expression,
            }

    nonzeros = sum(len(item["coefficients"]) for item in constraints)
    denominator = len(variables) * len(constraints)
    statistics: dict[str, int | float] = {
        "sets": len(sets),
        "scalar_parameters": len(scalar_parameters),
        "indexed_parameters": len(indexed_parameters),
        "parameters": len(scalar_parameters) + len(indexed_parameters),
        "variable_families": len(spec.variable_families),
        "generated_variables": len(variables),
        "constraint_families": len(spec.constraint_families),
        "generated_constraints": len(constraints),
        "nonzero_coefficients": nonzeros,
        "density": nonzeros / denominator if denominator else 0.0,
    }
    if len(compiled_objectives) == 1:
        mono = compiled_objectives[0]
        bio = None
        problem_type = "Monoobjetivo"
    else:
        mono = None
        bio = {"obj1": compiled_objectives[0], "obj2": compiled_objectives[1]}
        problem_type = "Biobjetivo"
    return ExpandedIndexedModel(
        name=spec.name,
        description=spec.description,
        problem_type=problem_type,
        variables=tuple(variables),
        constraints=tuple(constraints),
        mono_objective=mono,
        bio_objectives=bio,
        variable_provenance=variable_provenance,
        generated_constraint_provenance=constraint_provenance,
        statistics=statistics,
        source_spec=spec,
    )
