"""
Suite exhaustiva de pruebas unitarias para el motor matematico de Programacion Lineal.
Cubre casos monoobjetivo (MAX/MIN), biobjetivo (MAX/MAX, MAX/MIN, MIN/MIN),
infactibilidad, no acotamiento, validacion de pesos, rango nulo, nombres especiales,
entradas no finitas y robustez grafica.
"""

import pytest
import math
from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
    is_finite_number,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted, generate_weight_combinations
from solver_optimizador.plotting import plot_feasible_region_2d, plot_objective_space_2d


# ---------------------------------------------------------------------------
# 1. Monoobjetivo MAX
# ---------------------------------------------------------------------------
def test_single_objective_max():
    """
    Test 1: Ejemplo monoobjetivo MAX
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
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 3.0, "x2": 2.0}),
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

    slacks = {c.name: c.slack for c in sol.constraint_results}
    assert slacks["c1"] == pytest.approx(0.0, abs=1e-4)
    assert slacks["c2"] == pytest.approx(0.0, abs=1e-4)
    assert slacks["c3"] == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 2. Monoobjetivo MIN
# ---------------------------------------------------------------------------
def test_single_objective_min():
    """
    Test 2: Caso A — Monoobjetivo MIN
    MIN Z = x1 + 2*x2
    s.t.
      x1 + x2 >= 4
      x1 >= 1
      x2 >= 1
      x1, x2 >= 0
    Vértices factibles: (3, 1) -> Z = 3 + 2 = 5; (1, 3) -> Z = 1 + 6 = 7.
    Resultado esperado: x1 = 3, x2 = 1, Z = 5.0
    """
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MINIMIZE, {"x1": 1.0, "x2": 2.0}),
        constraints=[
            LinearConstraint("demanda_total", {"x1": 1.0, "x2": 1.0}, Operator.GE, 4.0),
            LinearConstraint("min_x1", {"x1": 1.0, "x2": 0.0}, Operator.GE, 1.0),
            LinearConstraint("min_x2", {"x1": 0.0, "x2": 1.0}, Operator.GE, 1.0),
        ],
    )

    sol = solve_lp(problem)

    assert sol.status == SolverStatus.OPTIMAL
    assert sol.objective_value == pytest.approx(5.0, abs=1e-4)
    assert sol.variable_values["x1"] == pytest.approx(3.0, abs=1e-4)
    assert sol.variable_values["x2"] == pytest.approx(1.0, abs=1e-4)

    slacks = {c.name: c.slack for c in sol.constraint_results}
    assert slacks["demanda_total"] == pytest.approx(0.0, abs=1e-4)
    assert slacks["min_x1"] == pytest.approx(2.0, abs=1e-4)
    assert slacks["min_x2"] == pytest.approx(0.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 3. Biobjetivo MAX/MAX (Benchmark A)
# ---------------------------------------------------------------------------
def test_biobjective_benchmark_a():
    """
    Test 3: Benchmark A academico biobjetivo MAX/MAX
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

    # Optimos individuales
    opt1 = sol.individual_optima["Z1_opt"]
    assert opt1["x"]["x1"] == pytest.approx(100.0, abs=1e-4)
    assert opt1["x"]["x2"] == pytest.approx(0.0, abs=1e-4)
    assert opt1["Z1"] == pytest.approx(1000.0, abs=1e-4)
    assert opt1["Z2"] == pytest.approx(80.0, abs=1e-4)

    opt2 = sol.individual_optima["Z2_opt"]
    assert opt2["x"]["x1"] == pytest.approx(0.0, abs=1e-4)
    assert opt2["x"]["x2"] == pytest.approx(130.0, abs=1e-4)
    assert opt2["Z1"] == pytest.approx(390.0, abs=1e-4)
    assert opt2["Z2"] == pytest.approx(169.0, abs=1e-4)

    # Rangos
    assert sol.normalization_ranges["Z1_range"] == pytest.approx(610.0, abs=1e-4)
    assert sol.normalization_ranges["Z2_range"] == pytest.approx(89.0, abs=1e-4)

    # 6 corridas
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

    assert len(sol.unique_solutions) == 3
    for u in sol.unique_solutions:
        assert u["pareto_status"] == "No dominada"


# ---------------------------------------------------------------------------
# 4. Biobjetivo MAX / MIN
# ---------------------------------------------------------------------------
def test_biobjective_max_min():
    """
    Test 4: Caso B — Biobjetivo MAX / MIN
    MAX Z1 = 2*x1 + x2
    MIN Z2 = x1 + 3*x2
    s.t.
      x1 + x2 <= 4
      x1, x2 >= 0
    Vertices factibles: (0,0), (4,0), (0,4).
    Para Z1 (MAX): optimo en (4,0) -> Z1 = 8, Z2 = 4
    Para Z2 (MIN): optimo en (0,0) -> Z1 = 0, Z2 = 0
    Rangos: Delta Z1 = 8 - 0 = 8, Delta Z2 = 4 - 0 = 4
    """
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 2.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 3.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 4.0),
        ],
    )

    sol = solve_biobjective_weighted(problem, num_combinations=5)

    # Optimos individuales
    assert sol.individual_optima["Z1_opt"]["x"]["x1"] == pytest.approx(4.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["x"]["x2"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["Z1"] == pytest.approx(8.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["Z2"] == pytest.approx(4.0, abs=1e-4)

    assert sol.individual_optima["Z2_opt"]["x"]["x1"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["x"]["x2"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z1"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z2"] == pytest.approx(0.0, abs=1e-4)

    assert sol.normalization_ranges["Z1_range"] == pytest.approx(8.0, abs=1e-4)
    assert sol.normalization_ranges["Z2_range"] == pytest.approx(4.0, abs=1e-4)

    # Todas las soluciones optimas del barrido estan en el eje x2=0 entre x1=0 y x1=4
    for run in sol.weighted_runs:
        assert run["status"] == "Optimo"
        assert run["x"]["x2"] == pytest.approx(0.0, abs=1e-4)

    assert len(sol.unique_solutions) >= 1
    for u in sol.unique_solutions:
        assert u["pareto_status"] == "No dominada"


# ---------------------------------------------------------------------------
# 5. Biobjetivo MIN / MIN
# ---------------------------------------------------------------------------
def test_biobjective_min_min():
    """
    Test 5: Caso C — Biobjetivo MIN / MIN
    MIN Z1 = 2*x1 + x2
    MIN Z2 = x1 + 2*x2
    s.t.
      x1 + x2 >= 4
      x1, x2 >= 0
    Vertices factibles de borde: (0, 4) y (4, 0).
    Para Z1 (MIN): optimo en (0, 4) -> Z1 = 4, Z2 = 8
    Para Z2 (MIN): optimo en (4, 0) -> Z1 = 8, Z2 = 4
    Rangos: Delta Z1 = 4, Delta Z2 = 4
    """
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MINIMIZE, {"x1": 2.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 2.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.GE, 4.0),
        ],
    )

    sol = solve_biobjective_weighted(problem, num_combinations=3)

    assert sol.individual_optima["Z1_opt"]["x"]["x1"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["x"]["x2"] == pytest.approx(4.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["Z1"] == pytest.approx(4.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["Z2"] == pytest.approx(8.0, abs=1e-4)

    assert sol.individual_optima["Z2_opt"]["x"]["x1"] == pytest.approx(4.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["x"]["x2"] == pytest.approx(0.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z1"] == pytest.approx(8.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z2"] == pytest.approx(4.0, abs=1e-4)

    assert sol.normalization_ranges["Z1_range"] == pytest.approx(4.0, abs=1e-4)
    assert sol.normalization_ranges["Z2_range"] == pytest.approx(4.0, abs=1e-4)

    assert len(sol.weighted_runs) == 3
    for run in sol.weighted_runs:
        assert run["status"] == "Optimo"

    assert len(sol.unique_solutions) >= 2
    for u in sol.unique_solutions:
        assert u["pareto_status"] == "No dominada"


# ---------------------------------------------------------------------------
# 6. Infactibilidad y No Acotamiento
# ---------------------------------------------------------------------------
def test_infeasible_problem():
    """Test 6: Problema infactible detectado limpiamente."""
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
    """Test 7: Problema no acotado detectado limpiamente."""
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


# ---------------------------------------------------------------------------
# 8. Validacion de Pesos
# ---------------------------------------------------------------------------
def test_invalid_weights_validation():
    """Test 8: Validacion de combinaciones de pesos."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0, "x2": 0.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.0, "x2": 1.0}),
        constraints=[LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0)],
    )

    with pytest.raises(ValueError):
        generate_weight_combinations(1)

    with pytest.raises(ValueError):
        solve_biobjective_weighted(problem, weights=[(0.4, 0.4)])  # Suma 0.8 != 1.0

    with pytest.raises(ValueError):
        solve_biobjective_weighted(problem, weights=[(-0.1, 1.1)])  # Peso negativo


# ---------------------------------------------------------------------------
# 9. Tratamiento de Rango Cero (Delta Z = 0)
# ---------------------------------------------------------------------------
def test_zero_range_handling():
    """
    Test 9: Cuando un objetivo no presenta variacion entre optimos individuales (Delta Z = 0).
    Debe detener el barrido de forma controlada sin division por cero ni presentar W falso.
    """
    # Z2 es constante (0*x1 + 0*x2 + 5 -> 0x1 + 0x2)
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.0, "x2": 0.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 5.0),
        ],
    )

    sol = solve_biobjective_weighted(problem, num_combinations=5)

    assert sol.normalization_ranges["Z2_range"] == pytest.approx(0.0, abs=1e-7)
    assert len(sol.weighted_runs) == 0
    assert len(sol.unique_solutions) == 0
    assert any("rango nulo" in note.lower() for note in sol.notes)


# ---------------------------------------------------------------------------
# 10. Nombres de Restricciones Especiales
# ---------------------------------------------------------------------------
def test_special_constraint_names():
    """
    Test 10: Nombres de restricciones con caracteres especiales, simbolos y espacios.
    """
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 2.0, "x2": 3.0}),
        constraints=[
            LinearConstraint("Capacidad total (A + B)", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
            LinearConstraint("Demanda ≥ mínima #1", {"x1": 1.0, "x2": 0.0}, Operator.GE, 2.0),
            LinearConstraint("Límite superior %", {"x1": 0.0, "x2": 1.0}, Operator.LE, 6.0),
        ],
    )

    sol = solve_lp(problem)
    assert sol.status == SolverStatus.OPTIMAL
    assert sol.objective_value == pytest.approx(26.0, abs=1e-4)
    assert sol.variable_values["x1"] == pytest.approx(4.0, abs=1e-4)
    assert sol.variable_values["x2"] == pytest.approx(6.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 11. Validacion de Entradas No Finitas
# ---------------------------------------------------------------------------
def test_non_finite_inputs_validation():
    """
    Test 11: Validacion de entradas NaN, inf, -inf.
    """
    assert is_finite_number(5.0) is True
    assert is_finite_number(0) is True
    assert is_finite_number(float("nan")) is False
    assert is_finite_number(float("inf")) is False
    assert is_finite_number(float("-inf")) is False
    assert is_finite_number(None) is False
    assert is_finite_number("texto") is False

    # NaN en objetivo
    with pytest.raises(ValueError):
        LPProblem(
            variables=["x1"],
            objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": float("nan")}),
            constraints=[LinearConstraint("c1", {"x1": 1.0}, Operator.LE, 5.0)],
        ).validate()

    # Infinito en RHS
    with pytest.raises(ValueError):
        LPProblem(
            variables=["x1"],
            objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0}),
            constraints=[LinearConstraint("c1", {"x1": 1.0}, Operator.LE, float("inf"))],
        ).validate()


# ---------------------------------------------------------------------------
# 12. Robustez de Graficos
# ---------------------------------------------------------------------------
def test_plotting_functions():
    """
    Test 12: Pruebas estructurales de los graficos 2D.
    """
    # Caso 1: Problema 2D valido -> devuelve Figure
    p2d = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        constraints=[LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 4.0)],
    )
    fig_feas = plot_feasible_region_2d(p2d, solutions=[{"x": {"x1": 2.0, "x2": 2.0}}])
    assert fig_feas is not None

    # Caso 2: Problema > 2 variables -> devuelve None
    p3d = LPProblem(
        variables=["x1", "x2", "x3"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0, "x3": 1.0}),
        constraints=[LinearConstraint("c1", {"x1": 1.0, "x2": 1.0, "x3": 1.0}, Operator.LE, 4.0)],
    )
    assert plot_feasible_region_2d(p3d) is None

    # Caso 3: Grafico de espacio de objetivos
    unique_sols = [
        {"id": "A", "Z1": 10.0, "Z2": 2.0, "pareto_status": "No dominada", "generated_by_weights": [{"alpha1": 0.0, "alpha2": 1.0}]},
        {"id": "B", "Z1": 5.0, "Z2": 8.0, "pareto_status": "No dominada", "generated_by_weights": [{"alpha1": 1.0, "alpha2": 0.0}]},
    ]
    fig_obj = plot_objective_space_2d(unique_sols, z1_name="Z1", z2_name="Z2")
    assert fig_obj is not None
