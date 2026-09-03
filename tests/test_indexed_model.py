"""Contratos de especificacion, serializacion y aplicacion de modelos indexados."""

from __future__ import annotations

import pytest

from solver_optimizador.indexed_application import apply_indexed_model, mark_indexed_source_stale
from solver_optimizador.input_application import apply_variable_import
from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_examples import production_planning_example_spec
from solver_optimizador.indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    VariableFamilySpec,
    deserialize_indexed_model_spec,
    serialize_indexed_model_spec,
)
from solver_optimizador.indexed_text_io import indexed_spec_to_table_texts, parse_indexed_tables


def _basic_spec(**changes) -> IndexedModelSpec:
    data = {
        "name": "Basico",
        "sets": (IndexSetSpec("T", 1, 4),),
        "indexed_parameters": (
            IndexedParameterSpec("cap", "T", {1: 2.0, 2: 3.0, 3: 4.0, 4: 5.0}),
        ),
        "variable_families": (VariableFamilySpec("X", "T"),),
        "objectives": (
            IndexedObjectiveSpec("Z", "Maximizar", (ObjectiveTermSpec("X", "T"),)),
        ),
        "constraint_families": (
            ConstraintFamilySpec("Cap", "T", "t", "X[t] <= cap[t]"),
        ),
    }
    data.update(changes)
    return IndexedModelSpec(**data)


def test_i1_integer_set_generates_inclusive_values():
    assert IndexSetSpec("T", 1, 4).values == [1, 2, 3, 4]


def test_i2_set_start_after_end_fails():
    with pytest.raises(ValueError, match="start <= end"):
        compile_indexed_model(_basic_spec(sets=(IndexSetSpec("T", 4, 1),)))


def test_i3_complete_indexed_parameter_compiles():
    assert compile_indexed_model(_basic_spec()).statistics["indexed_parameters"] == 1


def test_i4_missing_indexed_parameter_value_fails():
    parameter = IndexedParameterSpec("cap", "T", {1: 2.0, 2: 3.0, 4: 5.0})
    with pytest.raises(ValueError, match="faltan indices.*3"):
        compile_indexed_model(_basic_spec(indexed_parameters=(parameter,)))


def test_i5_extra_indexed_parameter_value_fails():
    parameter = IndexedParameterSpec("cap", "T", {1: 2, 2: 3, 3: 4, 4: 5, 5: 6})
    with pytest.raises(ValueError, match="fuera del conjunto.*5"):
        compile_indexed_model(_basic_spec(indexed_parameters=(parameter,)))


def test_i6_variable_family_generates_stable_names():
    assert compile_indexed_model(_basic_spec()).variables == ("X_1", "X_2", "X_3", "X_4")


def test_i7_two_variable_families_generate_expected_count():
    spec = _basic_spec(
        variable_families=(VariableFamilySpec("X", "T"), VariableFamilySpec("Y", "T"))
    )
    assert compile_indexed_model(spec).statistics["generated_variables"] == 8


def test_i19_invalid_spec_does_not_modify_state():
    state = {"var_names": ["old"], "editor_version": 4, "last_solution": object()}
    before = dict(state)
    invalid = _basic_spec(sets=(IndexSetSpec("T", 3, 1),))
    with pytest.raises(ValueError):
        apply_indexed_model(state, invalid)
    assert state.keys() == before.keys()
    assert state["var_names"] == before["var_names"]
    assert state["editor_version"] == before["editor_version"]
    assert state["last_solution"] is before["last_solution"]


def test_i20_valid_application_replaces_model_and_invalidates_solution():
    state = {"var_names": ["old"], "editor_version": 4, "last_solution": object()}
    expanded = apply_indexed_model(state, _basic_spec())
    assert state["var_names"] == list(expanded.variables)
    assert len(state["constraints_data"]) == 4
    assert state["last_solution"] is None
    assert state["editor_version"] == 5
    assert state["indexed_source_status"] == "synchronized"


def test_explicit_edit_marks_indexed_source_stale():
    state = {"indexed_source_status": "synchronized", "indexed_model_metadata": {}}
    mark_indexed_source_stale(state, "prueba")
    assert state["indexed_source_status"] == "stale"
    assert state["indexed_model_metadata"]["stale_reason"] == "prueba"


def test_explicit_import_after_indexed_application_marks_source_stale():
    state = {"editor_version": 0, "last_solution": object()}
    apply_indexed_model(state, _basic_spec())
    apply_variable_import(state, ["X_1"])
    assert state["indexed_source_status"] == "stale"
    assert state["indexed_model_metadata"]["stale_reason"] == "variables explicitas modificadas"


def test_i21_variable_provenance_is_complete():
    provenance = compile_indexed_model(_basic_spec()).variable_provenance["X_3"]
    assert provenance == {
        "display_name": "X_3", "family_name": "X", "index": 3, "index_set": "T"
    }


def test_i22_constraint_provenance_is_complete():
    provenance = compile_indexed_model(_basic_spec()).generated_constraint_provenance["Cap_2"]
    assert provenance["family_name"] == "Cap"
    assert provenance["index"] == 2
    assert provenance["source_expression"] == "X[t] <= cap[t]"


def test_i23_indexed_spec_json_round_trip():
    original = production_planning_example_spec()
    restored = deserialize_indexed_model_spec(serialize_indexed_model_spec(original))
    assert restored == original


def test_reserved_variable_family_base_is_rejected():
    with pytest.raises(ValueError, match="reservado temporalmente"):
        compile_indexed_model(_basic_spec(variable_families=(VariableFamilySpec("obj", "T"),)))


def test_tabular_source_round_trip_compiles_equivalently():
    original = production_planning_example_spec()
    tables = indexed_spec_to_table_texts(original)
    restored = parse_indexed_tables(
        name=original.name,
        description=original.description,
        sets_text=tables["sets"],
        scalar_parameters_text=tables["scalars"],
        indexed_parameters_text=tables["indexed"],
        variable_families_text=tables["variables"],
        objectives_text=tables["objectives"],
        constraint_families_text=tables["constraints"],
    )
    assert compile_indexed_model(restored).to_builder_state() == compile_indexed_model(original).to_builder_state()
