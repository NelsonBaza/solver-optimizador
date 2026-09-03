"""Aplicacion atomica de una especificacion indexada al estado explicito vigente."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping

from .indexed_compiler import compile_indexed_model
from .indexed_model import (
    ExpandedIndexedModel,
    IndexedModelSpec,
    build_indexed_spec_signature,
    indexed_model_spec_to_dict,
)


class IndexedPreviewSynchronizationError(ValueError):
    """La vista previa no corresponde a la especificacion indexada actual."""


def _set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, MutableMapping):
        state[key] = value
    else:
        setattr(state, key, value)


def _get(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, Mapping):
        return state.get(key, default)
    return getattr(state, key, default)


def mark_indexed_source_stale(state: Any, reason: str) -> None:
    """Marca la fuente generativa como desincronizada tras una edicion explicita."""

    if _get(state, "indexed_source_status") == "synchronized":
        _set(state, "indexed_source_status", "stale")
        metadata = dict(_get(state, "indexed_model_metadata", {}) or {})
        metadata["stale_reason"] = reason
        metadata["stale_at"] = datetime.now(timezone.utc).isoformat()
        _set(state, "indexed_model_metadata", metadata)


def apply_indexed_model(
    state: Any,
    model: IndexedModelSpec | ExpandedIndexedModel,
) -> ExpandedIndexedModel:
    """Compila por completo y solo entonces reemplaza el modelo explicito."""

    expanded = compile_indexed_model(model) if isinstance(model, IndexedModelSpec) else model
    builder_state = expanded.to_builder_state()

    _set(state, "model_name", expanded.name)
    _set(state, "model_desc", expanded.description)
    _set(state, "problem_type", expanded.problem_type)
    _set(state, "var_names", list(expanded.variables))
    _set(state, "num_vars", len(expanded.variables))
    _set(state, "constraints_data", [dict(row) for row in expanded.constraints])
    if expanded.problem_type == "Monoobjetivo":
        _set(state, "obj_sense", builder_state["obj_sense"])
        _set(state, "obj_coeffs", dict(builder_state["obj_coeffs"]))
        _set(state, "obj1_coeffs", {name: 0.0 for name in expanded.variables})
        _set(state, "obj2_coeffs", {name: 0.0 for name in expanded.variables})
    else:
        _set(state, "obj1_sense", builder_state["obj1_sense"])
        _set(state, "obj1_coeffs", dict(builder_state["obj1_coeffs"]))
        _set(state, "obj2_sense", builder_state["obj2_sense"])
        _set(state, "obj2_coeffs", dict(builder_state["obj2_coeffs"]))
        _set(state, "obj_coeffs", {name: 0.0 for name in expanded.variables})
    for key in (
        "last_solution",
        "last_solution_type",
        "last_solution_problem",
        "last_solution_signature",
    ):
        _set(state, key, None)
    _set(state, "editor_version", int(_get(state, "editor_version", 0)) + 1)
    _set(state, "indexed_source_spec", indexed_model_spec_to_dict(expanded.source_spec))
    _set(state, "indexed_source_status", "synchronized")
    _set(
        state,
        "indexed_model_metadata",
        {
            "source_type": "indexed_model",
            "indexed_schema_version": expanded.source_spec.indexed_schema_version,
            "sets_count": expanded.statistics["sets"],
            "variable_families_count": expanded.statistics["variable_families"],
            "constraint_families_count": expanded.statistics["constraint_families"],
            "generated_variables": expanded.statistics["generated_variables"],
            "generated_constraints": expanded.statistics["generated_constraints"],
            "nonzero_coefficients": expanded.statistics["nonzero_coefficients"],
            "compiled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return expanded


def apply_indexed_preview_if_current(
    state: Any,
    preview: ExpandedIndexedModel,
    current_spec: IndexedModelSpec,
    preview_signature: str | None,
) -> ExpandedIndexedModel:
    """Aplica una preview solo si ambas fuentes coinciden con su firma guardada."""

    if not preview_signature:
        raise IndexedPreviewSynchronizationError(
            "No existe una firma de compilacion vigente. Valide y compile nuevamente."
        )
    signed_preview = build_indexed_spec_signature(preview.source_spec)
    if signed_preview != preview_signature:
        raise IndexedPreviewSynchronizationError(
            "La vista previa almacenada no coincide con su firma. Valide y compile nuevamente."
        )
    current_signature = build_indexed_spec_signature(current_spec)
    if current_signature != preview_signature:
        raise IndexedPreviewSynchronizationError(
            "La especificacion cambio despues de la ultima compilacion. "
            "Debe validar y compilar nuevamente antes de aplicar."
        )
    return apply_indexed_model(state, preview)
