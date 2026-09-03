"""Regresiones matematicas, de seguridad y escala del compilador indexado."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_examples import (
    biobjective_indexed_example_spec,
    hydroelectric_fixture_indexed_spec,
)
from solver_optimizador.indexed_expression import IndexedExpressionError, parse_linear_relation
from solver_optimizador.indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    VariableFamilySpec,
)
from solver_optimizador.lp_models import SolverStatus
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.model_io import deserialize_model
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.problem_builder import (
    build_biobjective_problem_from_state,
    build_lp_problem_from_state,
)


def _spec(expression="X[t] <= cap[t]", *, start=None, end=None, objective_coefficient="1"):
    return IndexedModelSpec(
        name="Compilador",
        sets=(IndexSetSpec("T", 1, 4),),
        indexed_parameters=(IndexedParameterSpec("cap", "T", {1: 2, 2: 3, 3: 4, 4: 5}),),
        variable_families=(VariableFamilySpec("X", "T"), VariableFamilySpec("Y", "T")),
        objectives=(IndexedObjectiveSpec(
            "Z", "Maximizar", (ObjectiveTermSpec("X", "T", objective_coefficient),)
        ),),
        constraint_families=(ConstraintFamilySpec("R", "T", "t", expression, start, end),),
    )


def test_i8_family_generates_four_correct_constraints():
    constraints = compile_indexed_model(_spec()).constraints
    assert len(constraints) == 4
    assert constraints[2] == {
        "name": "R_3", "coefficients": {"X_3": 1.0}, "operator": "<=", "rhs": 4.0
    }


def test_i9_shifted_index_from_two_compiles():
    constraints = compile_indexed_model(
        _spec("X[t] - X[t-1] + Y[t] = cap[t]", start=2, end=4)
    ).constraints
    assert constraints[0]["coefficients"] == {"X_2": 1.0, "X_1": -1.0, "Y_2": 1.0}


def test_positive_shift_compiles_when_target_exists():
    constraints = compile_indexed_model(
        _spec("X[t+1] - X[t] = 0", start=1, end=3)
    ).constraints
    assert constraints[-1]["coefficients"] == {"X_4": 1.0, "X_3": -1.0}


def test_i10_shifted_index_out_of_range_has_clear_error():
    with pytest.raises(IndexedExpressionError, match=r"R\[1\] referencia X\[0\].*T"):
        compile_indexed_model(_spec("X[t] - X[t-1] = 0"))


def test_i11_parameter_coefficient_compiles():
    expanded = compile_indexed_model(_spec(objective_coefficient="cap[t]"))
    assert expanded.mono_objective["coefficients"] == {
        "X_1": 2.0, "X_2": 3.0, "X_3": 4.0, "X_4": 5.0
    }


@pytest.mark.parametrize("expression", ["X[t] * Y[t] <= 1", "X[t] ** 2 <= 1", "X[t] / Y[t] <= 1"])
def test_i12_to_i14_nonlinear_expressions_are_rejected(expression):
    with pytest.raises(IndexedExpressionError):
        compile_indexed_model(_spec(expression))


@pytest.mark.parametrize("expression", ["sin(X[t]) <= 1", "open(X[t]) <= 1", "X[t].real <= 1"])
def test_i15_calls_and_attribute_access_are_rejected(expression):
    with pytest.raises(IndexedExpressionError, match="no permitida"):
        compile_indexed_model(_spec(expression))


def test_i16_compiler_source_has_no_dynamic_execution_calls():
    import solver_optimizador.indexed_compiler as compiler
    import solver_optimizador.indexed_expression as expression

    source = inspect.getsource(compiler) + inspect.getsource(expression)
    assert "ev" + "al(" not in source
    assert "ex" + "ec(" not in source
    tree = ast.parse(source)
    forbidden = {"ev" + "al", "ex" + "ec", "com" + "pile"}
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(forbidden)


def test_i17_objective_sum_has_correct_coefficients():
    coefficients = compile_indexed_model(_spec()).mono_objective["coefficients"]
    assert coefficients == {f"X_{index}": 1.0 for index in range(1, 5)}


def test_i18_objective_single_index():
    spec = _spec()
    objective = IndexedObjectiveSpec(
        "Z", "Maximizar", (ObjectiveTermSpec("X", "T", "1", 4, 4),)
    )
    expanded = compile_indexed_model(
        IndexedModelSpec(**{**spec.__dict__, "objectives": (objective,)})
    )
    assert expanded.mono_objective["coefficients"] == {"X_4": 1.0}


def test_i24_hydroelectric_explicit_and_indexed_have_same_optimum_and_variables():
    root = Path(__file__).resolve().parents[1]
    explicit = deserialize_model((root / "tests/fixtures/hydroelectric_full_24_vars.json").read_text("utf-8"))
    explicit_problem = build_lp_problem_from_state(
        explicit["var_names"], explicit["obj_sense"], explicit["obj_coeffs"], explicit["constraints_data"]
    )
    expanded = compile_indexed_model(hydroelectric_fixture_indexed_spec())
    state = expanded.to_builder_state()
    indexed_problem = build_lp_problem_from_state(
        state["var_names"], state["obj_sense"], state["obj_coeffs"], state["constraints_data"]
    )
    explicit_solution, indexed_solution = solve_lp(explicit_problem), solve_lp(indexed_problem)
    assert explicit_solution.status == indexed_solution.status == SolverStatus.OPTIMAL
    assert indexed_solution.objective_value == pytest.approx(explicit_solution.objective_value, abs=1e-7)
    assert indexed_solution.objective_value == pytest.approx(6701.25, abs=1e-7)
    for family in ("T", "V", "S", "PH", "GH", "GT"):
        for index in range(1, 5):
            assert indexed_solution.variable_values[f"{family}_{index}"] == pytest.approx(
                explicit_solution.variable_values[f"{family}{index}"], abs=1e-7
            )


def test_i25_biobjective_indexed_model_uses_existing_weighted_solver():
    expanded = compile_indexed_model(biobjective_indexed_example_spec())
    state = expanded.to_builder_state()
    problem = build_biobjective_problem_from_state(
        state["var_names"], state["obj1_sense"], state["obj1_coeffs"],
        state["obj2_sense"], state["obj2_coeffs"], state["constraints_data"],
    )
    solution = solve_biobjective_weighted(problem, [(0.25, 0.75), (0.75, 0.25)])
    for run in solution.weighted_runs:
        assert run["status"] == "Optimo"
        assert run["Z1"] == pytest.approx(problem.objective1.evaluate(run["x"]))
        assert run["Z2"] == pytest.approx(problem.objective2.evaluate(run["x"]))
        assert run["W"] == pytest.approx(run["alpha1"] * run["N1"] + run["alpha2"] * run["N2"])


def test_i26_expansion_is_sparse():
    expanded = compile_indexed_model(_spec("X[t] + Y[t] <= cap[t]"))
    assert all(len(row["coefficients"]) == 2 for row in expanded.constraints)
    assert expanded.statistics["nonzero_coefficients"] == 8


def _large_spec(size: int, families: int) -> IndexedModelSpec:
    return IndexedModelSpec(
        name="Escala",
        sets=(IndexSetSpec("T", 1, size),),
        indexed_parameters=(IndexedParameterSpec("cap", "T", {i: 10.0 for i in range(1, size + 1)}),),
        variable_families=(VariableFamilySpec("X", "T"),),
        objectives=(IndexedObjectiveSpec("Z", "Maximizar", (ObjectiveTermSpec("X", "T"),)),),
        constraint_families=tuple(
            ConstraintFamilySpec(f"R{k}", "T", "t", "X[t] <= cap[t]")
            for k in range(1, families + 1)
        ),
    )


def test_i27_one_family_generates_one_thousand_constraints():
    assert compile_indexed_model(_large_spec(1000, 1)).statistics["generated_constraints"] == 1000


def test_i28_ten_families_generate_ten_thousand_without_density():
    expanded = compile_indexed_model(_large_spec(1000, 10))
    assert expanded.statistics["generated_constraints"] == 10_000
    assert expanded.statistics["nonzero_coefficients"] == 10_000


def test_linear_division_by_numeric_constant_is_supported():
    row = compile_indexed_model(_spec("X[t] / 3600 <= cap[t]")).constraints[0]
    assert row["coefficients"] == {"X_1": pytest.approx(1 / 3600)}


def test_no_zero_coefficients_are_stored_after_cancellation():
    row = compile_indexed_model(_spec("X[t] - X[t] + Y[t] <= cap[t]")).constraints[0]
    assert row["coefficients"] == {"Y_1": 1.0}


def test_nonfinite_parameter_is_rejected():
    bad = IndexedParameterSpec("cap", "T", {1: 2, 2: 3, 3: float("nan"), 4: 5})
    with pytest.raises(ValueError, match="NaN e Infinity"):
        compile_indexed_model(IndexedModelSpec(**{**_spec().__dict__, "indexed_parameters": (bad,)}))
