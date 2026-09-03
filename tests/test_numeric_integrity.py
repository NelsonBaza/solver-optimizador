"""Regresiones para el contrato de integridad numerica de resultados."""

import pytest

from solver_optimizador.interpretation import interpret_mono_solution
from solver_optimizador.lp_models import (
    BiobjectiveProblem,
    LPProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted


def test_critical_scaled_equality_preserves_published_vector() -> None:
    coefficient = 1_000_000_000.0
    problem = LPProblem(
        variables=["x"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x": coefficient}),
        constraints=[
            LinearConstraint("scaled_equality", {"x": coefficient}, Operator.EQ, 1.0)
        ],
    )

    solution = solve_lp(problem, tol=1e-7)

    assert solution.status == SolverStatus.OPTIMAL
    assert solution.activity_tolerance == 1e-7
    assert solution.variable_values["x"] != 0.0
    assert solution.variable_values["x"] == pytest.approx(1e-9, rel=1e-9, abs=1e-18)
    reconstructed = coefficient * solution.variable_values["x"]
    assert solution.objective_value == pytest.approx(reconstructed, rel=1e-12, abs=1e-12)
    assert solution.constraint_results[0].lhs == pytest.approx(
        reconstructed, rel=1e-12, abs=1e-12
    )
    assert solution.constraint_results[0].lhs == pytest.approx(1.0, abs=1e-12)
    assert solution.constraint_results[0].slack == pytest.approx(0.0, abs=1e-12)

    interpretation = " ".join(interpret_mono_solution(problem, solution))
    assert "1e-09" in interpretation


def test_published_objective_is_reconstructible_from_published_variables() -> None:
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 3.0, "x2": 2.0}),
        constraints=[
            LinearConstraint("capacity", {"x1": 1.0, "x2": 1.0}, Operator.LE, 4.0),
            LinearConstraint("x1_limit", {"x1": 1.0}, Operator.LE, 2.0),
            LinearConstraint("x2_limit", {"x2": 1.0}, Operator.LE, 3.0),
        ],
    )

    solution = solve_lp(problem)

    assert solution.status == SolverStatus.OPTIMAL
    reconstructed = problem.objective.evaluate(solution.variable_values)
    assert solution.objective_value == pytest.approx(reconstructed, rel=1e-12, abs=1e-12)


def test_published_constraints_and_slacks_use_the_published_vector() -> None:
    problem = LPProblem(
        variables=["x", "y"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x": 2.0, "y": 3.0}),
        constraints=[
            LinearConstraint("capacity", {"x": 1.0, "y": 1.0}, Operator.LE, 10.0),
            LinearConstraint("minimum_x", {"x": 1.0}, Operator.GE, 2.0),
            LinearConstraint("fixed_y", {"y": 1.0}, Operator.EQ, 4.0),
        ],
    )

    solution = solve_lp(problem)

    assert solution.status == SolverStatus.OPTIMAL
    assert len(solution.constraint_results) == len(problem.constraints)
    for constraint, published in zip(problem.constraints, solution.constraint_results):
        reconstructed_lhs = constraint.evaluate_lhs(solution.variable_values)
        reconstructed_slack = constraint.calculate_slack(solution.variable_values)
        assert published.lhs == pytest.approx(reconstructed_lhs, rel=1e-12, abs=1e-12)
        assert published.slack == pytest.approx(reconstructed_slack, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize(
    ("coefficient", "rhs", "expected_x"),
    [
        (1e9, 1.0, 1e-9),
        (1.0, 1.0, 1.0),
        (1.0, 1e9, 1e9),
    ],
)
def test_numeric_scales_remain_reconstructible(
    coefficient: float, rhs: float, expected_x: float
) -> None:
    problem = LPProblem(
        variables=["x"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x": 1.0}),
        constraints=[LinearConstraint("scale", {"x": coefficient}, Operator.EQ, rhs)],
    )

    solution = solve_lp(problem)

    assert solution.status == SolverStatus.OPTIMAL
    assert solution.variable_values["x"] == pytest.approx(
        expected_x, rel=1e-9, abs=max(abs(expected_x) * 1e-12, 1e-18)
    )
    reconstructed_lhs = coefficient * solution.variable_values["x"]
    assert solution.constraint_results[0].lhs == pytest.approx(
        reconstructed_lhs, rel=1e-12, abs=1e-12
    )
    assert reconstructed_lhs == pytest.approx(rhs, rel=1e-9, abs=1e-9)


def test_weighted_run_objectives_and_w_use_the_published_vector() -> None:
    problem = BiobjectiveProblem(
        variables=["x", "y"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x": 1e9}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"y": 1.0}),
        constraints=[
            LinearConstraint("scaled_capacity", {"x": 1e9, "y": 1.0}, Operator.LE, 1.0)
        ],
    )

    solution = solve_biobjective_weighted(problem, weights=[(0.75, 0.25)])

    assert len(solution.weighted_runs) == 1
    z1_extreme = solution.individual_optima["Z1_opt"]
    z2_extreme = solution.individual_optima["Z2_opt"]
    assert z1_extreme["primary_optimal_value"] == pytest.approx(
        problem.objective1.evaluate(z1_extreme["x"]), rel=1e-12, abs=1e-12
    )
    assert z2_extreme["primary_optimal_value"] == pytest.approx(
        problem.objective2.evaluate(z2_extreme["x"]), rel=1e-12, abs=1e-12
    )
    run = solution.weighted_runs[0]
    assert run["status"] == "Optimo"
    assert run["x"]["x"] != 0.0
    reconstructed_z1 = problem.objective1.evaluate(run["x"])
    reconstructed_z2 = problem.objective2.evaluate(run["x"])
    assert run["Z1"] == pytest.approx(reconstructed_z1, rel=1e-12, abs=1e-12)
    assert run["Z2"] == pytest.approx(reconstructed_z2, rel=1e-12, abs=1e-12)

    ranges = solution.normalization_ranges
    reconstructed_w = 0.75 * reconstructed_z1 / ranges["Z1_range"]
    reconstructed_w += 0.25 * reconstructed_z2 / ranges["Z2_range"]
    assert run["W"] == pytest.approx(reconstructed_w, rel=1e-12, abs=1e-12)
