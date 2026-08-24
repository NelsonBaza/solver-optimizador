"""
Suite de pruebas unitarias para el motor matematico de Programacion Lineal (solver_optimizador).
"""

import pytest
from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted, generate_weight_combinations


def test_single_objective_example():
    """
    Test 1: Ejemplo monoobjetivo
    MAX Z = 3*x1 + 2*x2
    s.t.
      x1 + x2 <= 4
      x1 <= 2
      x2 <= 3
      x1, x2 >= 0
    Resultado esperado: x1 = 2, x2 = 2, Z = 10
    """
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective(
            name="Z",
            sense=Sense.MAXIMIZE,
            coefficients={"x1": 3.0, "x2": 2.0},
        ),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 4.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 2.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 3.0),
        ],
    )

    sol = solve_lp(problem)

    assert sol.status == SolverStatus.OPTIMAL
    assert sol.objective_value == pytest.approx(10.0, abs=1e-4)
    assert sol.variable_values["x1"] == pytest.approx(2.0, abs=1e-4)
    assert sol.variable_values["x2"] == pytest.approx(2.0, abs=1e-4)

    # Slacks check
    slacks = {c.name: c.slack for c in sol.constraint_results}
    assert slacks["c1"] == pytest.approx(0.0, abs=1e-4)
    assert slacks["c2"] == pytest.approx(0.0, abs=1e-4)
    assert slacks["c3"] == pytest.approx(1.0, abs=1e-4)


def test_biobjective_benchmark_a():
    """
    Test 2: Benchmark A academico biobjetivo
    MAX Z1 = 10*x1 + 3*x2
    MAX Z2 = 0.8*x1 + 1.3*x2
    s.t.
      x1 + x2 <= 130
      2.5*x1 + x2 <= 250
      x1, x2 >= 0
    """
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0),
            LinearConstraint("c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0),
        ],
    )

    sol = solve_biobjective_weighted(problem, num_combinations=6)

    # 1. Individual optima
    opt1 = sol.individual_optima["Z1_max"]
    assert opt1["x"]["x1"] == pytest.approx(100.0, abs=1e-4)
    assert opt1["x"]["x2"] == pytest.approx(0.0, abs=1e-4)
    assert opt1["Z1"] == pytest.approx(1000.0, abs=1e-4)
    assert opt1["Z2"] == pytest.approx(80.0, abs=1e-4)

    opt2 = sol.individual_optima["Z2_max"]
    assert opt2["x"]["x1"] == pytest.approx(0.0, abs=1e-4)
    assert opt2["x"]["x2"] == pytest.approx(130.0, abs=1e-4)
    assert opt2["Z1"] == pytest.approx(390.0, abs=1e-4)
    assert opt2["Z2"] == pytest.approx(169.0, abs=1e-4)

    # 2. Normalization ranges
    assert sol.normalization_ranges["Z1_range"] == pytest.approx(610.0, abs=1e-4)
    assert sol.normalization_ranges["Z2_range"] == pytest.approx(89.0, abs=1e-4)

    # 3. 6 weighted runs
    assert len(sol.weighted_runs) == 6
    expected_runs = [
        {"x1": 0.0, "x2": 130.0, "Z1": 390.0, "Z2": 169.0},
        {"x1": 0.0, "x2": 130.0, "Z1": 390.0, "Z2": 169.0},
        {"x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"x1": 100.0, "x2": 0.0, "Z1": 1000.0, "Z2": 80.0},
    ]
    for i, exp in enumerate(expected_runs):
        run = sol.weighted_runs[i]
        assert run["x"]["x1"] == pytest.approx(exp["x1"], abs=1e-4)
        assert run["x"]["x2"] == pytest.approx(exp["x2"], abs=1e-4)
        assert run["Z1"] == pytest.approx(exp["Z1"], abs=1e-4)
        assert run["Z2"] == pytest.approx(exp["Z2"], abs=1e-4)

    # 4. Unique solutions
    assert len(sol.unique_solutions) == 3
    for u in sol.unique_solutions:
        assert u["pareto_status"] == "No dominada"


def test_infeasible_problem():
    """
    Test 3: Problema infactible
    x1 + x2 <= 2
    x1 + x2 >= 5
    """
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 2.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 1.0}, Operator.GE, 5.0),
        ],
    )

    sol = solve_lp(problem)
    assert sol.status in (SolverStatus.INFEASIBLE, SolverStatus.INFEASIBLE_OR_UNBOUNDED)
    assert sol.objective_value is None


def test_unbounded_problem():
    """
    Test 4: Problema no acotado
    MAX Z = x1 + x2
    x1 - x2 <= 2
    x1, x2 >= 0 (x2 puede crecer indefinidamente)
    """
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": -1.0}, Operator.LE, 2.0),
        ],
    )

    sol = solve_lp(problem)
    assert sol.status in (SolverStatus.UNBOUNDED, SolverStatus.INFEASIBLE_OR_UNBOUNDED)
    assert sol.objective_value is None


def test_weight_combinations_generator():
    """
    Test 5: Generador de combinaciones de pesos y validacion de entradas incorrectas.
    """
    weights = generate_weight_combinations(6)
    assert len(weights) == 6
    assert weights[0] == (0.0, 1.0)
    assert weights[-1] == (1.0, 0.0)
    assert weights[1] == (0.2, 0.8)

    with pytest.raises(ValueError):
        generate_weight_combinations(1)

    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0, "x2": 0.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.0, "x2": 1.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
        ],
    )

    # Pesos que no suman 1.0
    with pytest.raises(ValueError):
        solve_biobjective_weighted(problem, weights=[(0.5, 0.6)])

    # Pesos negativos
    with pytest.raises(ValueError):
        solve_biobjective_weighted(problem, weights=[(-0.2, 1.2)])


def test_model_validation_errors():
    """
    Test 6: Validaciones de consistencia de modelo.
    """
    with pytest.raises(ValueError):
        LPProblem(
            variables=[],
            objective=LinearObjective("Z", Sense.MAXIMIZE, {}),
            constraints=[LinearConstraint("c1", {}, Operator.LE, 5.0)],
        ).validate()

    with pytest.raises(ValueError):
        LPProblem(
            variables=["x1"],
            objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0}),
            constraints=[],
        ).validate()

    with pytest.raises(ValueError):
        LPProblem(
            variables=["x1"],
            objective=LinearObjective("Z", Sense.MAXIMIZE, {"x2": 1.0}),  # x2 no declarada
            constraints=[LinearConstraint("c1", {"x1": 1.0}, Operator.LE, 5.0)],
        ).validate()
