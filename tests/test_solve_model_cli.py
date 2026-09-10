"""Validación del modelo hidroeléctrico biobjetivo y su runner de consola."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from solver_optimizador import (
    BiobjectiveProblem,
    Sense,
    build_biobjective_problem_from_state,
    deserialize_model,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "hidroelectrica_biobjetivo.json"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "solve_model.py"


@pytest.fixture(scope="module")
def raw_model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def loaded_model() -> dict:
    return deserialize_model(MODEL_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hydro_problem(loaded_model: dict) -> BiobjectiveProblem:
    return build_biobjective_problem_from_state(
        var_names=loaded_model["var_names"],
        obj1_sense=loaded_model["obj1_sense"],
        obj1_coeffs=loaded_model["obj1_coeffs"],
        obj2_sense=loaded_model["obj2_sense"],
        obj2_coeffs=loaded_model["obj2_coeffs"],
        canonical_constraints=loaded_model["constraints_data"],
    )


@pytest.fixture(scope="module")
def epsilon_solution(hydro_problem: BiobjectiveProblem):
    return solve_biobjective_epsilon_constraint(
        hydro_problem,
        primary_objective=1,
        r=6,
    )


def test_hydroelectric_json_loads_with_expected_shape(loaded_model: dict) -> None:
    assert loaded_model["problem_type"] == "Biobjetivo"
    assert loaded_model["num_vars"] == 24
    assert len(loaded_model["var_names"]) == 24
    assert len(loaded_model["constraints_data"]) == 28
    assert loaded_model["metadata"]["plot_title"] == "Generación hidroeléctrica"
    assert [objective["name"] for objective in loaded_model["objectives"]] == [
        "Costo de generación térmica",
        "Volumen final del embalse V4 (UH)",
    ]


def test_hydroelectric_json_is_sparse(raw_model: dict) -> None:
    problem = raw_model["problem"]
    objective_coefficients = [
        problem["bio_objectives"]["obj1"]["coefficients"],
        problem["bio_objectives"]["obj2"]["coefficients"],
    ]
    constraint_coefficients = [
        constraint["coefficients"] for constraint in problem["constraints"]
    ]

    assert set(objective_coefficients[0]) == {"GT1", "GT2", "GT3", "GT4"}
    assert objective_coefficients[1] == {"V4": 1.0}
    for coefficients in [*objective_coefficients, *constraint_coefficients]:
        assert coefficients
        assert all(value != 0.0 for value in coefficients.values())


def test_hydroelectric_problem_has_exact_variables_and_constraints(
    hydro_problem: BiobjectiveProblem,
) -> None:
    expected_variables = [
        *(f"T{period}" for period in range(1, 5)),
        *(f"V{period}" for period in range(1, 5)),
        *(f"S{period}" for period in range(1, 5)),
        *(f"PH{period}" for period in range(1, 5)),
        *(f"GH{period}" for period in range(1, 5)),
        *(f"GT{period}" for period in range(1, 5)),
    ]
    expected_constraint_names = {
        *(f"Balance_H{period}" for period in range(1, 5)),
        *(f"Turb_Pot_{period}" for period in range(1, 5)),
        *(f"Pot_Ene_{period}" for period in range(1, 5)),
        *(f"Demanda_P{period}" for period in range(1, 5)),
        *(f"V_Min_{period}" for period in range(1, 5)),
        *(f"V_Max_{period}" for period in range(1, 5)),
        *(f"T_Max_{period}" for period in range(1, 5)),
    }

    assert hydro_problem.variables == expected_variables
    assert len(hydro_problem.constraints) == 28
    assert {constraint.name for constraint in hydro_problem.constraints} == (
        expected_constraint_names
    )


def test_hydroelectric_all_original_constraints_are_exact(
    hydro_problem: BiobjectiveProblem,
) -> None:
    constraints = {constraint.name: constraint for constraint in hydro_problem.constraints}
    expected_balances = {
        1: ({"V1": 1.0, "T1": 1.0, "S1": 1.0}, 90.0),
        2: ({"V2": 1.0, "V1": -1.0, "T2": 1.0, "S2": 1.0}, 20.0),
        3: ({"V3": 1.0, "V2": -1.0, "T3": 1.0, "S3": 1.0}, 15.0),
        4: ({"V4": 1.0, "V3": -1.0, "T4": 1.0, "S4": 1.0}, 10.0),
    }
    expected_demand = {1: 60.0, 2: 80.0, 3: 70.0, 4: 90.0}

    for period in range(1, 5):
        balance_coefficients, balance_rhs = expected_balances[period]
        balance = constraints[f"Balance_H{period}"]
        assert balance.coefficients == balance_coefficients
        assert balance.operator.value == "="
        assert balance.rhs == balance_rhs

        power = constraints[f"Turb_Pot_{period}"]
        assert power.coefficients == {f"PH{period}": 1.0, f"T{period}": -2.4525}
        assert power.operator.value == "="
        assert power.rhs == 0.0

        conversion = constraints[f"Pot_Ene_{period}"]
        assert conversion.coefficients == {f"GH{period}": 1.0, f"PH{period}": -1.0}
        assert conversion.operator.value == "="
        assert conversion.rhs == 0.0

        demand = constraints[f"Demanda_P{period}"]
        assert demand.coefficients == {f"GH{period}": 1.0, f"GT{period}": 1.0}
        assert demand.operator.value == "="
        assert demand.rhs == expected_demand[period]

        minimum_volume = constraints[f"V_Min_{period}"]
        assert minimum_volume.coefficients == {f"V{period}": 1.0}
        assert minimum_volume.operator.value == ">="
        assert minimum_volume.rhs == 40.0

        maximum_volume = constraints[f"V_Max_{period}"]
        assert maximum_volume.coefficients == {f"V{period}": 1.0}
        assert maximum_volume.operator.value == "<="
        assert maximum_volume.rhs == 100.0

        maximum_turbining = constraints[f"T_Max_{period}"]
        assert maximum_turbining.coefficients == {f"T{period}": 1.0}
        assert maximum_turbining.operator.value == "<="
        assert maximum_turbining.rhs == 70.0


def test_hydroelectric_objective_senses_and_coefficients(
    hydro_problem: BiobjectiveProblem,
) -> None:
    assert hydro_problem.objective1.sense == Sense.MINIMIZE
    assert hydro_problem.objective2.sense == Sense.MAXIMIZE
    for variable in hydro_problem.variables:
        expected_z1 = 100.0 if variable in {"GT1", "GT2", "GT3", "GT4"} else 0.0
        expected_z2 = 1.0 if variable == "V4" else 0.0
        assert hydro_problem.objective1.coefficients[variable] == expected_z1
        assert hydro_problem.objective2.coefficients[variable] == expected_z2


def test_hydroelectric_known_efficient_extremes(epsilon_solution) -> None:
    payoff = epsilon_solution.payoff_matrix
    assert payoff["opt_Z1"]["Z1"] == pytest.approx(6701.25, abs=1e-6)
    assert payoff["opt_Z1"]["Z2"] == pytest.approx(40.0, abs=1e-7)
    assert payoff["opt_Z2"]["Z1"] == pytest.approx(21416.25, abs=1e-6)
    assert payoff["opt_Z2"]["Z2"] == pytest.approx(100.0, abs=1e-7)


def test_hydroelectric_r6_has_expected_levels_and_seven_runs(
    epsilon_solution,
) -> None:
    assert len(epsilon_solution.runs) == 7
    assert epsilon_solution.epsilon_levels == pytest.approx(
        [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        abs=1e-12,
    )


def test_hydroelectric_epsilon_runs_follow_known_frontier(
    epsilon_solution,
) -> None:
    expected_costs = [
        6701.25,
        9153.75,
        11606.25,
        14058.75,
        16511.25,
        18963.75,
        21416.25,
    ]
    for run, expected_v4, expected_cost in zip(
        epsilon_solution.runs,
        epsilon_solution.epsilon_levels,
        expected_costs,
    ):
        assert run["status"] == "optimal"
        assert run["x"]["V4"] == pytest.approx(expected_v4, abs=1e-7)
        assert run["Z2"] == pytest.approx(expected_v4, abs=1e-7)
        assert run["Z1"] == pytest.approx(expected_cost, abs=1e-6)
        assert run["Z1"] == pytest.approx(
            245.25 * run["x"]["V4"] - 3108.75,
            abs=1e-6,
        )
    assert len(epsilon_solution.unique_solutions) == 7
    assert len(epsilon_solution.nondominated_solutions) == 7


def test_loaded_model_preserves_weighted_and_epsilon_results(
    hydro_problem: BiobjectiveProblem,
    epsilon_solution,
) -> None:
    weighted = solve_biobjective_weighted(hydro_problem, num_combinations=6)

    assert len(weighted.weighted_runs) == 6
    assert all(run["status"] == "Optimo" for run in weighted.weighted_runs)
    assert weighted.payoff_matrix["opt_Z1"]["Z1"] == pytest.approx(6701.25)
    assert weighted.payoff_matrix["opt_Z2"]["Z2"] == pytest.approx(100.0)
    assert {round(run["Z1"], 2) for run in weighted.weighted_runs} == {
        6701.25,
        21416.25,
    }
    assert len(epsilon_solution.runs) == 7


def _execute_runner(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(RUNNER_PATH), str(MODEL_PATH), *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        timeout=30,
    )


def test_console_runner_executes_epsilon_and_prints_full_result() -> None:
    completed = _execute_runner("--method", "epsilon", "--primary", "1", "--r", "6")
    output = completed.stdout.decode("utf-8")
    error = completed.stderr.decode("utf-8")

    assert completed.returncode == 0, error
    assert "Generación Hidroeléctrica Biobjetivo Corregida" in output
    assert "MÉTODO DE LAS RESTRICCIONES" in output
    assert "Z2_min = 40.000000" in output
    assert "Z2_max = 100.000000" in output
    assert "Niveles E2 = [40, 50, 60, 70, 80, 90, 100]" in output
    assert "Tabla completa de las 7 corridas" in output
    assert "Soluciones únicas (7)" in output
    assert "Clasificación Pareto" in output
    for variable in (
        "T1",
        "T4",
        "V1",
        "V4",
        "S1",
        "S4",
        "PH1",
        "PH4",
        "GH1",
        "GH4",
        "GT1",
        "GT4",
    ):
        assert variable in output
    for expected_cost in (
        "6701.250000",
        "9153.750000",
        "11606.250000",
        "14058.750000",
        "16511.250000",
        "18963.750000",
        "21416.250000",
    ):
        assert expected_cost in output


def test_console_runner_executes_weighted_method() -> None:
    completed = _execute_runner("--method", "weighted", "--num-weights", "6")
    output = completed.stdout.decode("utf-8")
    error = completed.stderr.decode("utf-8")

    assert completed.returncode == 0, error
    assert "MÉTODO DE PONDERACIONES NORMALIZADAS" in output
    assert "Número de ponderaciones: 6" in output
    assert "Tabla completa de las 6 corridas" in output
    assert "6701.250000" in output
    assert "21416.250000" in output
    assert "Clasificación Pareto" in output
