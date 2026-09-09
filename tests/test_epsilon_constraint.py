"""Contrato matematico del metodo de las restricciones epsilon."""

from __future__ import annotations

from copy import deepcopy

import pytest

import solver_optimizador.epsilon_constraint as epsilon_module
from solver_optimizador import (
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
    generate_epsilon_levels,
    solve_biobjective_epsilon_constraint,
)
from solver_optimizador.lp_models import LPSolution, SolverStatus


def _benchmark_a() -> BiobjectiveProblem:
    return BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective(
            "Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}
        ),
        objective2=LinearObjective(
            "Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}
        ),
        constraints=[
            LinearConstraint(
                "c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0
            ),
            LinearConstraint(
                "c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0
            ),
        ],
    )


def _max_min_problem() -> BiobjectiveProblem:
    return BiobjectiveProblem(
        variables=["x", "y"],
        objective1=LinearObjective("beneficio", Sense.MAXIMIZE, {"x": 1.0}),
        objective2=LinearObjective("costo", Sense.MINIMIZE, {"y": 1.0}),
        constraints=[
            LinearConstraint(
                "demanda", {"x": 1.0, "y": 1.0}, Operator.GE, 10.0
            ),
            LinearConstraint("limite_x", {"x": 1.0}, Operator.LE, 10.0),
            LinearConstraint("limite_y", {"y": 1.0}, Operator.LE, 10.0),
        ],
    )


def test_generate_epsilon_levels_returns_r_plus_one_values() -> None:
    assert len(generate_epsilon_levels(2.0, 17.0, 5)) == 6


def test_generate_epsilon_levels_preserves_exact_first_endpoint() -> None:
    z_min = 0.1
    assert generate_epsilon_levels(z_min, 9.7, 7)[0] == z_min


def test_generate_epsilon_levels_preserves_exact_last_endpoint() -> None:
    z_max = 9.7
    assert generate_epsilon_levels(0.1, z_max, 7)[-1] == z_max


def test_generate_epsilon_levels_uses_exact_academic_expression() -> None:
    z_min, z_max, r = -3.5, 8.75, 4
    levels = generate_epsilon_levels(z_min, z_max, r)
    assert levels == [
        z_min if t == 0 else z_max if t == r else z_min + (t / r) * (z_max - z_min)
        for t in range(r + 1)
    ]


@pytest.mark.parametrize("invalid_r", [True, 0, -1, 2.5])
def test_generate_epsilon_levels_rejects_invalid_r(invalid_r: object) -> None:
    with pytest.raises(ValueError, match="r debe ser un entero"):
        generate_epsilon_levels(0.0, 1.0, invalid_r)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_bound", [float("nan"), float("inf"), None])
def test_generate_epsilon_levels_rejects_non_finite_bounds(
    invalid_bound: object,
) -> None:
    with pytest.raises(ValueError, match="finitos"):
        generate_epsilon_levels(invalid_bound, 1.0, 2)  # type: ignore[arg-type]


def test_max_constrained_objective_uses_greater_than_or_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_solve_lp = epsilon_module.solve_lp
    observed_operators: list[Operator] = []

    def recording_solve_lp(problem, tol=1e-6):
        observed_operators.append(problem.constraints[-1].operator)
        return real_solve_lp(problem, tol=tol)

    monkeypatch.setattr(epsilon_module, "solve_lp", recording_solve_lp)
    result = solve_biobjective_epsilon_constraint(
        _benchmark_a(), primary_objective=1, r=2
    )

    assert len(result.runs) == 3
    assert observed_operators == [Operator.GE] * 3
    assert {run["constraint_operator"] for run in result.runs} == {">="}


def test_min_constrained_objective_uses_less_than_or_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_solve_lp = epsilon_module.solve_lp
    observed_operators: list[Operator] = []

    def recording_solve_lp(problem, tol=1e-6):
        observed_operators.append(problem.constraints[-1].operator)
        return real_solve_lp(problem, tol=tol)

    monkeypatch.setattr(epsilon_module, "solve_lp", recording_solve_lp)
    result = solve_biobjective_epsilon_constraint(
        _max_min_problem(), primary_objective=1, r=2
    )

    assert len(result.runs) == 3
    assert observed_operators == [Operator.LE] * 3
    assert {run["constraint_operator"] for run in result.runs} == {"<="}


def test_every_run_keeps_all_original_constraints_and_calls_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _benchmark_a()
    original_snapshot = deepcopy(problem.constraints)
    real_solve_lp = epsilon_module.solve_lp
    submitted_problems = []

    def recording_solve_lp(run_problem, tol=1e-6):
        submitted_problems.append(run_problem)
        return real_solve_lp(run_problem, tol=tol)

    monkeypatch.setattr(epsilon_module, "solve_lp", recording_solve_lp)
    result = solve_biobjective_epsilon_constraint(problem, primary_objective=1, r=5)

    assert len(submitted_problems) == 6
    assert len(result.runs) == 6
    for submitted, run in zip(submitted_problems, result.runs):
        assert submitted.constraints[:-1] == original_snapshot
        assert len(submitted.constraints) == len(problem.constraints) + 1
        assert submitted.objective is problem.objective1
        assert submitted.constraints[-1].coefficients == problem.objective2.coefficients
        assert submitted.constraints[-1].rhs == run["E"]
    assert problem.constraints == original_snapshot


def test_published_objectives_are_reconstructed_from_same_vector() -> None:
    problem = _benchmark_a()
    result = solve_biobjective_epsilon_constraint(problem, primary_objective=1, r=5)

    for run in result.runs:
        assert run["status"] == SolverStatus.OPTIMAL.value
        assert set(run["x"]) == set(problem.variables)
        assert run["Z1"] == pytest.approx(
            problem.objective1.evaluate(run["x"]), rel=1e-12, abs=1e-12
        )
        assert run["Z2"] == pytest.approx(
            problem.objective2.evaluate(run["x"]), rel=1e-12, abs=1e-12
        )


def test_infeasible_run_is_recorded_and_sweep_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_solve_lp = epsilon_module.solve_lp

    def one_infeasible_run(problem, tol=1e-6):
        if problem.constraints[-1].name.endswith("_t_2"):
            return LPSolution(
                status=SolverStatus.INFEASIBLE,
                status_message=SolverStatus.INFEASIBLE.user_friendly_message,
                raw_termination="infeasible",
                execution_time_sec=0.001,
            )
        return real_solve_lp(problem, tol=tol)

    monkeypatch.setattr(epsilon_module, "solve_lp", one_infeasible_run)
    result = solve_biobjective_epsilon_constraint(
        _benchmark_a(), primary_objective=1, r=3
    )

    assert len(result.runs) == 4
    assert result.runs[2]["status"] == SolverStatus.INFEASIBLE.value
    assert result.runs[2]["x"] is None
    assert result.runs[3]["status"] == SolverStatus.OPTIMAL.value
    assert any("1 corridas infactibles" in note for note in result.notes)


def test_repeated_solutions_are_detected_without_removing_runs() -> None:
    problem = BiobjectiveProblem(
        variables=["x"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x": 0.0}),
        constraints=[LinearConstraint("limite", {"x": 1.0}, Operator.LE, 10.0)],
    )
    result = solve_biobjective_epsilon_constraint(problem, primary_objective=1, r=5)

    assert len(result.runs) == 6
    assert result.epsilon_levels == [0.0] * 6
    assert len(result.unique_solutions) == 1
    assert result.unique_solutions[0]["count"] == 6
    assert result.unique_solutions[0]["run_indices"] == list(range(6))


def test_pareto_classification_honors_max_min_senses() -> None:
    problem = _max_min_problem()
    unique = [
        {
            "id": "S1",
            "x": {},
            "Z1": 10.0,
            "Z2": 5.0,
            "run_indices": [0],
            "epsilon_levels": [0.0],
        },
        {
            "id": "S2",
            "x": {},
            "Z1": 11.0,
            "Z2": 4.0,
            "run_indices": [1],
            "epsilon_levels": [1.0],
        },
        {
            "id": "S3",
            "x": {},
            "Z1": 12.0,
            "Z2": 6.0,
            "run_indices": [2],
            "epsilon_levels": [2.0],
        },
    ]

    classification = epsilon_module._classify_pareto(problem, unique, tol=1e-6)

    assert classification["S1"]["status"] == "Dominada (por S2)"
    assert classification["S2"]["status"] == "No dominada"
    assert classification["S3"]["status"] == "No dominada"


def test_benchmark_a_with_z1_as_primary_objective() -> None:
    result = solve_biobjective_epsilon_constraint(
        _benchmark_a(), primary_objective=1, r=5
    )

    assert result.primary_objective == 1
    assert result.constrained_objective == 2
    assert result.epsilon_levels == pytest.approx(
        [80.0, 97.8, 115.6, 133.4, 151.2, 169.0]
    )
    assert result.runs[0]["x"] == pytest.approx({"x1": 100.0, "x2": 0.0})
    assert result.runs[-1]["x"] == pytest.approx({"x1": 0.0, "x2": 130.0})
    assert len(result.nondominated_solutions) == 6


def test_benchmark_a_with_z2_as_primary_objective() -> None:
    result = solve_biobjective_epsilon_constraint(
        _benchmark_a(), primary_objective=2, r=5
    )

    assert result.primary_objective == 2
    assert result.constrained_objective == 1
    assert result.epsilon_levels == pytest.approx(
        [390.0, 512.0, 634.0, 756.0, 878.0, 1000.0]
    )
    assert result.runs[0]["x"] == pytest.approx({"x1": 0.0, "x2": 130.0})
    assert result.runs[-1]["x"] == pytest.approx({"x1": 100.0, "x2": 0.0})
    assert len(result.nondominated_solutions) == 6


@pytest.mark.parametrize("invalid_primary", [0, 3, True, 1.0, "1"])
def test_primary_objective_must_be_one_or_two(invalid_primary: object) -> None:
    with pytest.raises(ValueError, match="primary_objective"):
        solve_biobjective_epsilon_constraint(
            _benchmark_a(), primary_objective=invalid_primary, r=2  # type: ignore[arg-type]
        )
