"""Regresiones de restricciones constantes y nombres reservados temporales."""

from __future__ import annotations

import json

import pytest

from solver_optimizador.constraint_import import (
    RESERVED_VARIABLE_NAMES,
    constraints_to_sparse_csv,
    parse_constraint_text,
    parse_variable_names,
)
from solver_optimizador.input_application import (
    apply_manual_variable_rename,
    apply_variable_import,
)
from solver_optimizador.lp_models import (
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    LPProblem,
    Operator,
    Sense,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.model_io import deserialize_model, validate_model_dict
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.problem_builder import build_lp_problem_from_state


def _constant_problem(operator: Operator, rhs: float) -> LPProblem:
    return LPProblem(
        variables=["x1"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 0.0}),
        constraints=[LinearConstraint("constant", {}, operator, rhs)],
    )


@pytest.mark.parametrize(
    ("operator", "rhs", "expected_status"),
    [
        pytest.param(Operator.LE, 10.0, SolverStatus.OPTIMAL, id="zero_le_ten"),
        pytest.param(Operator.GE, 10.0, SolverStatus.INFEASIBLE, id="zero_ge_ten"),
        pytest.param(Operator.EQ, 0.0, SolverStatus.OPTIMAL, id="zero_eq_zero"),
        pytest.param(Operator.EQ, 10.0, SolverStatus.INFEASIBLE, id="zero_eq_ten"),
    ],
)
def test_constant_constraint_semantics(operator, rhs, expected_status):
    solution = solve_lp(_constant_problem(operator, rhs))
    assert solution.status == expected_status
    if expected_status == SolverStatus.OPTIMAL:
        result = solution.constraint_results[0]
        assert result.lhs == 0.0
        assert result.slack == pytest.approx(10.0 if operator == Operator.LE else 0.0)
        assert result.is_active is (operator == Operator.EQ)


def _projection_state(operator: str) -> dict[str, object]:
    return {
        "editor_version": 0,
        "problem_type": "Monoobjetivo",
        "num_vars": 2,
        "var_names": ["x1", "x2"],
        "obj_coeffs": {"x1": 0.0, "x2": 0.0},
        "obj1_coeffs": {"x1": 0.0, "x2": 0.0},
        "obj2_coeffs": {"x1": 0.0, "x2": 0.0},
        "constraints_data": [
            {
                "name": "R1",
                "coefficients": {"x1": 1.0},
                "operator": operator,
                "rhs": 10.0,
            }
        ],
        "last_solution": object(),
        "last_solution_type": "Monoobjetivo",
        "last_solution_problem": object(),
        "last_solution_signature": "old",
    }


def test_variable_projection_can_leave_feasible_constant_constraint():
    state = _projection_state("<=")
    apply_variable_import(state, ["x2"])
    assert state["constraints_data"][0]["coefficients"] == {}
    problem = build_lp_problem_from_state(
        state["var_names"],
        "Maximizar",
        state["obj_coeffs"],
        state["constraints_data"],
    )
    assert solve_lp(problem).status == SolverStatus.OPTIMAL


def test_variable_projection_can_leave_infeasible_constant_constraint():
    state = _projection_state(">=")
    apply_variable_import(state, ["x2"])
    assert state["constraints_data"][0]["coefficients"] == {}
    problem = build_lp_problem_from_state(
        state["var_names"],
        "Maximizar",
        state["obj_coeffs"],
        state["constraints_data"],
    )
    assert solve_lp(problem).status == SolverStatus.INFEASIBLE


def _biobjective_with_constant(operator: Operator, rhs: float) -> BiobjectiveProblem:
    return BiobjectiveProblem(
        variables=["x1"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0}),
        constraints=[
            LinearConstraint("constant", {}, operator, rhs),
            LinearConstraint("upper", {"x1": 1.0}, Operator.LE, 10.0),
        ],
    )


def test_biobjective_accepts_feasible_constant_constraint():
    solution = solve_biobjective_weighted(
        _biobjective_with_constant(Operator.LE, 10.0),
        weights=[(0.25, 0.75), (0.75, 0.25)],
    )
    assert len(solution.weighted_runs) == 2
    assert all(run["status"] == "Optimo" for run in solution.weighted_runs)


def test_biobjective_reports_infeasible_constant_without_construction_crash():
    solution = solve_biobjective_weighted(
        _biobjective_with_constant(Operator.GE, 10.0),
        weights=[(0.5, 0.5)],
    )
    assert solution.individual_optima["Z1_opt"]["status"] == SolverStatus.INFEASIBLE
    assert solution.weighted_runs == []
    assert any("Z1" in note for note in solution.notes)


def test_constant_constraint_sparse_csv_roundtrip_preserves_semantics():
    constraint = {
        "name": "constant",
        "coefficients": {},
        "operator": "<=",
        "rhs": 10.0,
    }
    exported = constraints_to_sparse_csv([constraint], ["x1"])
    imported = parse_constraint_text(exported, input_format="sparse")
    assert imported.is_valid
    assert imported.constraints == [constraint]
    problem = build_lp_problem_from_state(
        ["x1"], "Maximizar", {"x1": 0.0}, imported.constraints
    )
    solution = solve_lp(problem)
    assert solution.status == SolverStatus.OPTIMAL
    assert solution.constraint_results[0].slack == pytest.approx(10.0)


@pytest.mark.parametrize(
    "reserved_name",
    ["obj", "Obj", "OBJ", "name", "Name", "component_map", "COMPONENT_MAP"],
)
def test_variable_block_rejects_reserved_names_case_insensitively(reserved_name):
    result = parse_variable_names(f"x1,{reserved_name}")
    assert not result.is_valid
    assert any("nombre reservado" in error for error in result.errors)


@pytest.mark.parametrize("reserved_name", ["obj", "component_map"])
def test_wide_format_rejects_reserved_variable_columns(reserved_name):
    result = parse_constraint_text(
        f"name,{reserved_name},operator,rhs\nR1,1,<=,10\n",
        input_format="wide",
    )
    assert not result.is_valid
    assert any("nombre reservado" in error for error in result.errors)


def test_wide_format_rejects_name_as_variable_column():
    result = parse_constraint_text(
        "constraint,name,operator,rhs\nR1,1,<=,10\n",
        input_format="wide",
    )
    assert not result.is_valid
    assert any("nombre reservado" in error for error in result.errors)


@pytest.mark.parametrize("reserved_name", ["obj", "name", "component_map"])
def test_sparse_format_rejects_reserved_variable_values(reserved_name):
    result = parse_constraint_text(
        "constraint,variable,coefficient,operator,rhs\n"
        f"R1,{reserved_name},1,<=,10\n",
        input_format="sparse",
    )
    assert not result.is_valid
    assert any("nombre reservado" in error for error in result.errors)


def _json_model(variable: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata": {},
        "problem": {
            "type": "Monoobjetivo",
            "variables": [variable],
            "mono_objective": {
                "sense": "Maximizar",
                "coefficients": {variable: 1.0},
            },
            "constraints": [
                {
                    "name": "R1",
                    "coefficients": {variable: 1.0},
                    "operator": "<=",
                    "rhs": 10.0,
                }
            ],
        },
    }


@pytest.mark.parametrize("reserved_name", ["obj", "name", "component_map"])
def test_json_validation_and_deserialization_reject_reserved_names(reserved_name):
    data = _json_model(reserved_name)
    is_valid, error = validate_model_dict(data)
    assert not is_valid
    assert "nombre reservado" in error
    with pytest.raises(ValueError, match="nombre reservado"):
        deserialize_model(json.dumps(data))


@pytest.mark.parametrize("reserved_name", ["obj", "name", "component_map"])
def test_manual_editor_controller_rejects_reserved_names_atomically(
    reserved_name,
):
    state = _projection_state("<=")
    before_variables = list(state["var_names"])
    before_constraints = list(state["constraints_data"])
    with pytest.raises(ValueError, match="nombre reservado"):
        apply_manual_variable_rename(state, ["x1", reserved_name])
    assert state["var_names"] == before_variables
    assert state["constraints_data"] == before_constraints


def test_manual_editor_controller_preserves_valid_positional_rename():
    state = _projection_state("<=")
    state["obj_coeffs"] = {"x1": 3.0, "x2": 5.0}
    apply_manual_variable_rename(state, ["T1", "GT_12"])
    assert state["var_names"] == ["T1", "GT_12"]
    assert state["obj_coeffs"] == {"T1": 3.0, "GT_12": 5.0}
    assert state["constraints_data"][0]["coefficients"] == {"T1": 1.0}
    assert state["last_solution"] is None


def test_normal_variable_names_remain_valid():
    expected = ["x1", "T1", "V4", "GT_12", "demanda_aux", "variable2026"]
    parsed = parse_variable_names("\n".join(expected))
    assert parsed.is_valid
    assert parsed.variables == expected
    assert {"name", "component_map", "obj"}.issubset(RESERVED_VARIABLE_NAMES)
