"""Contratos de firma y aplicacion segura de previews indexadas."""

from __future__ import annotations

from dataclasses import replace

import pytest

from solver_optimizador.indexed_application import (
    IndexedPreviewSynchronizationError,
    apply_indexed_preview_if_current,
)
from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    VariableFamilySpec,
    build_indexed_spec_signature,
)
from solver_optimizador.indexed_text_io import parse_indexed_tables


def _spec(cap_values=None) -> IndexedModelSpec:
    return IndexedModelSpec(
        name="Sincronizacion",
        description="Modelo para prueba",
        sets=(IndexSetSpec("T", 1, 3),),
        indexed_parameters=(
            IndexedParameterSpec("cap", "T", cap_values or {1: 10.0, 2: 10.0, 3: 10.0}),
        ),
        variable_families=(VariableFamilySpec("X", "T"),),
        objectives=(
            IndexedObjectiveSpec("Z", "Maximizar", (ObjectiveTermSpec("X", "T", "1"),)),
        ),
        constraint_families=(
            ConstraintFamilySpec("Cap", "T", "t", "X[t] <= cap[t]"),
        ),
    )


def _state():
    return {
        "var_names": ["old"],
        "constraints_data": [{"name": "old", "coefficients": {"old": 1}, "operator": "<=", "rhs": 1}],
        "last_solution": object(),
        "editor_version": 7,
    }


def test_s1_same_spec_has_same_signature():
    assert build_indexed_spec_signature(_spec()) == build_indexed_spec_signature(_spec())


def test_s2_parameter_change_changes_signature():
    assert build_indexed_spec_signature(_spec()) != build_indexed_spec_signature(
        _spec({1: 10.0, 2: 99.0, 3: 10.0})
    )


def test_s3_constraint_change_changes_signature():
    changed = replace(
        _spec(),
        constraint_families=(
            ConstraintFamilySpec("Cap", "T", "t", "2*X[t] <= cap[t]"),
        ),
    )
    assert build_indexed_spec_signature(_spec()) != build_indexed_spec_signature(changed)


def test_s4_objective_change_changes_signature():
    changed = replace(
        _spec(),
        objectives=(
            IndexedObjectiveSpec("Z", "Maximizar", (ObjectiveTermSpec("X", "T", "2"),)),
        ),
    )
    assert build_indexed_spec_signature(_spec()) != build_indexed_spec_signature(changed)


def test_s5_set_change_changes_signature():
    changed = replace(_spec(), sets=(IndexSetSpec("T", 1, 4),))
    assert build_indexed_spec_signature(_spec()) != build_indexed_spec_signature(changed)


def test_s6_parameter_dict_order_does_not_change_signature():
    ordered_a = _spec({1: 10.0, 2: 20.0, 3: 30.0})
    ordered_b = _spec({3: 30.0, 1: 10.0, 2: 20.0})
    assert build_indexed_spec_signature(ordered_a) == build_indexed_spec_signature(ordered_b)


def test_name_and_description_are_part_of_signature():
    original = _spec()
    assert build_indexed_spec_signature(original) != build_indexed_spec_signature(
        replace(original, name="Otro nombre")
    )
    assert build_indexed_spec_signature(original) != build_indexed_spec_signature(
        replace(original, description="Otra descripcion")
    )


def test_s7_current_preview_is_applied():
    spec = _spec()
    preview = compile_indexed_model(spec)
    state = _state()
    result = apply_indexed_preview_if_current(
        state, preview, spec, build_indexed_spec_signature(spec)
    )
    assert result is preview
    assert state["var_names"] == ["X_1", "X_2", "X_3"]
    assert state["indexed_source_status"] == "synchronized"


def test_s8_modified_spec_blocks_old_preview():
    original = _spec()
    changed = _spec({1: 10.0, 2: 99.0, 3: 10.0})
    with pytest.raises(IndexedPreviewSynchronizationError, match="cambio despues"):
        apply_indexed_preview_if_current(
            _state(),
            compile_indexed_model(original),
            changed,
            build_indexed_spec_signature(original),
        )


def test_s9_blocked_application_does_not_mutate_explicit_state():
    original = _spec()
    changed = _spec({1: 10.0, 2: 99.0, 3: 10.0})
    state = _state()
    variables_before = list(state["var_names"])
    constraints_before = [dict(row) for row in state["constraints_data"]]
    solution_before = state["last_solution"]
    version_before = state["editor_version"]
    with pytest.raises(IndexedPreviewSynchronizationError):
        apply_indexed_preview_if_current(
            state,
            compile_indexed_model(original),
            changed,
            build_indexed_spec_signature(original),
        )
    assert state["var_names"] == variables_before
    assert state["constraints_data"] == constraints_before
    assert state["last_solution"] is solution_before
    assert state["editor_version"] == version_before
    assert state.get("indexed_source_status") is None


def test_s10_recompiled_modified_spec_can_be_applied():
    changed = _spec({1: 10.0, 2: 99.0, 3: 10.0})
    preview = compile_indexed_model(changed)
    state = _state()
    apply_indexed_preview_if_current(
        state, preview, changed, build_indexed_spec_signature(changed)
    )
    constraints = {row["name"]: row for row in state["constraints_data"]}
    assert constraints["Cap_2"]["rhs"] == 99.0


def test_preview_source_is_checked_against_stored_signature():
    original = _spec()
    preview = compile_indexed_model(original)
    wrong_signature = build_indexed_spec_signature(
        _spec({1: 10.0, 2: 99.0, 3: 10.0})
    )
    state = _state()
    with pytest.raises(IndexedPreviewSynchronizationError, match="vista previa almacenada"):
        apply_indexed_preview_if_current(state, preview, original, wrong_signature)
    assert state["var_names"] == ["old"]


def test_csv_parameter_source_change_blocks_old_preview():
    def parsed(value: float):
        return parse_indexed_tables(
            name="CSV",
            description="",
            sets_text="name,start,end\nT,1,1",
            scalar_parameters_text="name,value",
            indexed_parameters_text=(
                "parameter,index_set,index,value\n" f"cap,T,1,{value}"
            ),
            variable_families_text="family,index_set\nX,T",
            objectives_text=(
                "objective,sense,variable_family,index_set,start_index,end_index,coefficient\n"
                "Z,Maximizar,X,T,1,1,1"
            ),
            constraint_families_text=(
                "name,index_set,index_symbol,start_index,end_index,expression\n"
                "Cap,T,t,1,1,X[t] <= cap[t]"
            ),
        )

    spec_a, spec_b = parsed(10), parsed(999)
    with pytest.raises(IndexedPreviewSynchronizationError):
        apply_indexed_preview_if_current(
            _state(),
            compile_indexed_model(spec_a),
            spec_b,
            build_indexed_spec_signature(spec_a),
        )
