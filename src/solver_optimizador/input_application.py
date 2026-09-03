"""Aplicacion atomica de lotes validados a un estado tipo mapping/Session State."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Sequence

from .constraint_import import (
    ConstraintImportResult,
    ObjectiveImportResult,
    VariableImportResult,
    validate_variable_names,
)
from .model_io import normalize_constraints


def _get(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, Mapping):
        return state.get(key, default)
    return getattr(state, key, default)


def _set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, MutableMapping):
        state[key] = value
    else:
        setattr(state, key, value)


def _invalidate_solution(state: Any) -> None:
    for key in (
        "last_solution",
        "last_solution_type",
        "last_solution_problem",
        "last_solution_signature",
    ):
        _set(state, key, None)


def _next_editor_version(state: Any) -> None:
    _set(state, "editor_version", int(_get(state, "editor_version", 0)) + 1)


def _metadata(source_type: str, details: Mapping[str, Any] | None, **counts: Any) -> dict[str, Any]:
    result = {
        "source_type": source_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **counts,
    }
    if details:
        result.update({key: value for key, value in details.items() if value is not None})
    return result


def _project_objectives(state: Any, variable_names: Sequence[str]) -> dict[str, dict[str, float]]:
    return {
        key: {name: float(_get(state, key, {}).get(name, 0.0)) for name in variable_names}
        for key in ("obj_coeffs", "obj1_coeffs", "obj2_coeffs")
    }


def _project_constraints(state: Any, variable_names: Sequence[str]) -> list[dict[str, Any]]:
    current_variables = list(_get(state, "var_names", []))
    normalized = normalize_constraints(list(_get(state, "constraints_data", [])), current_variables)
    allowed = set(variable_names)
    return [
        {
            "name": row["name"],
            "coefficients": {
                name: value
                for name, value in row["coefficients"].items()
                if name in allowed and value != 0.0
            },
            "operator": row["operator"],
            "rhs": row["rhs"],
        }
        for row in normalized
    ]


def apply_variable_import(
    state: Any,
    result: VariableImportResult | Sequence[str],
    *,
    source_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Reemplaza variables atomicamente, preservando coeficientes por nombre."""

    if isinstance(result, VariableImportResult):
        if not result.is_valid:
            raise ValueError("No se puede aplicar el lote: " + "; ".join(result.errors))
        variables = list(result.variables)
        source_type = result.source_format
    else:
        variables = list(result)
        source_type = "programmatic"
        if not variables:
            raise ValueError("El lote de variables esta vacio.")
        errors = validate_variable_names(variables)
        if errors:
            raise ValueError("No se puede aplicar el lote: " + "; ".join(errors))
    projected_objectives = _project_objectives(state, variables)
    projected_constraints = _project_constraints(state, variables)
    _set(state, "var_names", variables)
    _set(state, "num_vars", len(variables))
    for key, coefficients in projected_objectives.items():
        _set(state, key, coefficients)
    _set(state, "constraints_data", projected_constraints)
    _set(
        state,
        "variable_import_metadata",
        _metadata(source_type, source_metadata, variable_count=len(variables)),
    )
    _invalidate_solution(state)
    _next_editor_version(state)


def apply_constraint_import(
    state: Any,
    result: ConstraintImportResult,
    *,
    use_detected_variables: bool,
    source_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Aplica un lote completo o no aplica nada si existe algun error."""

    if not result.is_valid:
        raise ValueError("No se puede aplicar la importacion: " + "; ".join(result.errors))
    current_variables = list(_get(state, "var_names", []))
    target_variables = list(result.detected_variables) if use_detected_variables else current_variables
    unknown = [name for name in result.detected_variables if name not in current_variables]
    if not use_detected_variables and unknown:
        raise ValueError("Variables no declaradas: " + ", ".join(unknown))

    projected_objectives = _project_objectives(state, target_variables)
    allowed = set(target_variables)
    constraints = [
        {
            "name": row["name"],
            "coefficients": {
                name: float(value)
                for name, value in row["coefficients"].items()
                if name in allowed and float(value) != 0.0
            },
            "operator": row["operator"],
            "rhs": float(row["rhs"]),
        }
        for row in result.constraints
    ]

    _set(state, "var_names", target_variables)
    _set(state, "num_vars", len(target_variables))
    for key, coefficients in projected_objectives.items():
        _set(state, key, coefficients)
    _set(state, "constraints_data", constraints)
    _set(
        state,
        "constraint_import_metadata",
        _metadata(
            result.source_format,
            source_metadata,
            format=result.source_format,
            row_count=result.source_rows,
            constraint_count=result.number_of_constraints,
            variable_count=len(target_variables),
            detected_variable_count=result.number_of_variables,
            nonzero_count=result.nonzero_coefficients,
        ),
    )
    _invalidate_solution(state)
    _next_editor_version(state)


def apply_objective_import(
    state: Any,
    result: ObjectiveImportResult,
    *,
    source_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Aplica todos los coeficientes de objetivo; los omitidos pasan a cero."""

    if not result.is_valid:
        raise ValueError("No se puede aplicar el objetivo: " + "; ".join(result.errors))
    current_type = str(_get(state, "problem_type", ""))
    if current_type != result.problem_type:
        raise ValueError(
            f"El lote es {result.problem_type} pero el modelo actual es {current_type}."
        )
    variables = list(_get(state, "var_names", []))
    if result.problem_type == "Monoobjetivo":
        _set(state, "obj_coeffs", {name: result.coefficients.get(name, 0.0) for name in variables})
    else:
        _set(state, "obj1_coeffs", {name: result.coefficients_z1.get(name, 0.0) for name in variables})
        _set(state, "obj2_coeffs", {name: result.coefficients_z2.get(name, 0.0) for name in variables})
    _set(
        state,
        "objective_import_metadata",
        _metadata(
            result.source_format,
            source_metadata,
            variable_count=len(variables),
            recognized_count=len(result.recognized_variables),
        ),
    )
    _invalidate_solution(state)
    _next_editor_version(state)
