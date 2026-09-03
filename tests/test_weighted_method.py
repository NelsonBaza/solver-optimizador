"""Contrato normativo de la suma ponderada normalizada."""

from __future__ import annotations

import os

import pytest

import solver_optimizador.multiobjective as multiobjective_module
from solver_optimizador.interpretation import interpret_biobjective_solution
from solver_optimizador.lp_models import (
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
)
from solver_optimizador.model_io import deserialize_model
from solver_optimizador.multiobjective import (
    normalize_objective_value,
    solve_biobjective_weighted,
)
from solver_optimizador.problem_builder import build_biobjective_problem_from_state


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "hydroelectric_full_24_vars.json"
)
COURSE_WEIGHTS = [
    (0.0, 1.0),
    (0.2, 0.8),
    (0.4, 0.6),
    (0.6, 0.4),
    (0.8, 0.2),
    (1.0, 0.0),
]
EXPECTED_BENCHMARK = {
    (0.0, 1.0): (0.0, 130.0, 390.0, 169.0),
    (0.2, 0.8): (0.0, 130.0, 390.0, 169.0),
    (0.4, 0.6): (80.0, 50.0, 950.0, 129.0),
    (0.5, 0.5): (80.0, 50.0, 950.0, 129.0),
    (0.6, 0.4): (80.0, 50.0, 950.0, 129.0),
    (0.8, 0.2): (80.0, 50.0, 950.0, 129.0),
    (1.0, 0.0): (100.0, 0.0, 1000.0, 80.0),
}


def _benchmark_a() -> BiobjectiveProblem:
    return BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0),
            LinearConstraint("c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0),
        ],
    )


def _hydroelectric_problem() -> BiobjectiveProblem:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fixture:
        data = deserialize_model(fixture.read())
    variables = data["var_names"]
    return build_biobjective_problem_from_state(
        var_names=variables,
        obj1_sense="Minimizar",
        obj1_coeffs={v: (100.0 if v.startswith("GT") else 0.0) for v in variables},
        obj2_sense="Maximizar",
        obj2_coeffs={v: (1.0 if v == "V4" else 0.0) for v in variables},
        canonical_constraints=data["constraints_data"],
    )


def _assert_feasible(problem: BiobjectiveProblem, x: dict[str, float]) -> None:
    for constraint in problem.constraints:
        lhs = constraint.evaluate_lhs(x)
        if constraint.operator == Operator.LE:
            assert lhs <= constraint.rhs + 1e-6
        elif constraint.operator == Operator.GE:
            assert lhs >= constraint.rhs - 1e-6
        else:
            assert lhs == pytest.approx(constraint.rhs, abs=1e-6)


def test_normalization_max_maps_limits_to_zero_and_one() -> None:
    assert normalize_objective_value(390.0, 390.0, 1000.0, Sense.MAXIMIZE) == 0.0
    assert normalize_objective_value(1000.0, 390.0, 1000.0, Sense.MAXIMIZE) == 1.0


def test_normalization_min_maps_best_to_one_and_worst_to_zero() -> None:
    assert normalize_objective_value(6701.25, 6701.25, 21416.25, Sense.MINIMIZE) == 1.0
    assert normalize_objective_value(21416.25, 6701.25, 21416.25, Sense.MINIMIZE) == 0.0


def test_normalization_rejects_current_zero_range_case() -> None:
    with pytest.raises(ValueError, match="rango"):
        normalize_objective_value(1.0, 1.0, 1.0, Sense.MAXIMIZE)


def test_every_weighted_run_reconstructs_w() -> None:
    solution = solve_biobjective_weighted(
        _benchmark_a(), weights=[*COURSE_WEIGHTS, (0.5, 0.5)]
    )
    for run in solution.weighted_runs:
        assert run["W"] == pytest.approx(
            run["alpha1"] * run["N1"] + run["alpha2"] * run["N2"],
            rel=1e-12,
            abs=1e-12,
        )


@pytest.mark.parametrize("weight", COURSE_WEIGHTS)
def test_benchmark_a_academic_weighted_results(weight: tuple[float, float]) -> None:
    solution = solve_biobjective_weighted(_benchmark_a(), weights=[weight])
    run = solution.weighted_runs[0]
    expected_x1, expected_x2, expected_z1, expected_z2 = EXPECTED_BENCHMARK[weight]
    assert run["status"] == "Optimo"
    assert run["x"]["x1"] == pytest.approx(expected_x1, abs=1e-7)
    assert run["x"]["x2"] == pytest.approx(expected_x2, abs=1e-7)
    assert run["Z1"] == pytest.approx(expected_z1, abs=1e-7)
    assert run["Z2"] == pytest.approx(expected_z2, abs=1e-7)


def test_benchmark_a_half_weight_is_middle_vertex_without_degeneracy_claim() -> None:
    problem = _benchmark_a()
    solution = solve_biobjective_weighted(problem, weights=[(0.5, 0.5)])
    run = solution.weighted_runs[0]
    assert run["x"]["x1"] == pytest.approx(80.0, abs=1e-7)
    assert run["x"]["x2"] == pytest.approx(50.0, abs=1e-7)
    assert run["Z1"] == pytest.approx(950.0, abs=1e-7)
    assert run["Z2"] == pytest.approx(129.0, abs=1e-7)
    interpretation = " ".join(interpret_biobjective_solution(problem, solution)).lower()
    assert "existe degeneración" not in interpretation
    assert "óptimo único" not in interpretation


def test_endpoints_execute_weighted_models_instead_of_copying_payoff(monkeypatch) -> None:
    real_highs = multiobjective_module.Highs
    solved_model_names: list[str] = []

    class RecordingHighs:
        def __init__(self) -> None:
            self._delegate = real_highs()
            self.config = self._delegate.config

        def solve(self, model):
            solved_model_names.append(model.name)
            return self._delegate.solve(model)

    monkeypatch.setattr(multiobjective_module, "Highs", RecordingHighs)
    solution = solve_biobjective_weighted(
        _benchmark_a(), weights=[(0.0, 1.0), (1.0, 0.0)]
    )

    assert {"NormalizedWeightedRun_1", "NormalizedWeightedRun_2"}.issubset(
        set(solved_model_names)
    )
    assert len(solved_model_names) >= 2
    for run in solution.weighted_runs:
        metadata = run["selection_metadata"]
        assert metadata["weighted_problem_solved"] is True
        assert "optimal" in metadata["weighted_solver_termination"].lower()
        assert run["x"] is not solution.payoff_matrix[
            "opt_Z1" if run["alpha1"] == 1.0 else "opt_Z2"
        ]["x"]


def test_max_min_case_with_unique_weighted_optimum() -> None:
    problem = BiobjectiveProblem(
        variables=["x", "y"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x": 1.0}),
        constraints=[LinearConstraint("balance", {"x": 1.0, "y": 1.0}, Operator.EQ, 10.0)],
    )
    solution = solve_biobjective_weighted(problem, weights=[(0.75, 0.25)])
    run = solution.weighted_runs[0]
    assert run["x"]["x"] == pytest.approx(10.0, abs=1e-7)
    assert run["N1"] == pytest.approx(1.0, abs=1e-12)
    assert run["N2"] == pytest.approx(0.0, abs=1e-12)
    assert run["W"] == pytest.approx(0.75, abs=1e-12)


@pytest.mark.parametrize(
    ("weight", "expected_z1", "expected_z2"),
    [
        ((0.2, 0.8), 21416.25, 100.0),
        ((0.4, 0.6), 21416.25, 100.0),
        ((0.6, 0.4), 6701.25, 40.0),
        ((0.8, 0.2), 6701.25, 40.0),
    ],
)
def test_hydroelectric_weighted_extremes(
    weight: tuple[float, float], expected_z1: float, expected_z2: float
) -> None:
    solution = solve_biobjective_weighted(_hydroelectric_problem(), weights=[weight])
    run = solution.weighted_runs[0]
    assert run["Z1"] == pytest.approx(expected_z1, abs=1e-5)
    assert run["Z2"] == pytest.approx(expected_z2, abs=1e-7)


def test_hydroelectric_half_weight_is_feasible_on_documented_frontier() -> None:
    problem = _hydroelectric_problem()
    solution = solve_biobjective_weighted(problem, weights=[(0.5, 0.5)])
    run = solution.weighted_runs[0]
    _assert_feasible(problem, run["x"])
    assert run["Z1"] == pytest.approx(245.25 * run["Z2"] - 3108.75, abs=1e-5)
    assert run["W"] == pytest.approx(0.5, abs=1e-10)


@pytest.mark.parametrize("problem", [_benchmark_a(), _hydroelectric_problem()])
def test_all_published_weighted_values_reconstruct_from_x(
    problem: BiobjectiveProblem,
) -> None:
    solution = solve_biobjective_weighted(problem, weights=[(0.4, 0.6), (0.6, 0.4)])
    ranges = solution.normalization_ranges
    for run in solution.weighted_runs:
        reconstructed_z1 = problem.objective1.evaluate(run["x"])
        reconstructed_z2 = problem.objective2.evaluate(run["x"])
        reconstructed_n1 = normalize_objective_value(
            reconstructed_z1,
            ranges["Z1_min"],
            ranges["Z1_max"],
            problem.objective1.sense,
        )
        reconstructed_n2 = normalize_objective_value(
            reconstructed_z2,
            ranges["Z2_min"],
            ranges["Z2_max"],
            problem.objective2.sense,
        )
        assert run["Z1"] == pytest.approx(reconstructed_z1, rel=1e-12, abs=1e-12)
        assert run["Z2"] == pytest.approx(reconstructed_z2, rel=1e-12, abs=1e-12)
        assert run["N1"] == pytest.approx(reconstructed_n1, rel=1e-12, abs=1e-12)
        assert run["N2"] == pytest.approx(reconstructed_n2, rel=1e-12, abs=1e-12)
        assert run["W"] == pytest.approx(
            run["alpha1"] * reconstructed_n1 + run["alpha2"] * reconstructed_n2,
            rel=1e-12,
            abs=1e-12,
        )
