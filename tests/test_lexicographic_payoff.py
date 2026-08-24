"""
Suite de pruebas para desempate lexicografico y matriz de pagos eficiente.
Valida resolucion de multiples optimos individuales, eliminacion de extremos dominados,
correcta determinacion de rangos (Delta Z) y barrido ponderado en problemas biobjetivo.
"""

import pytest
import os
from solver_optimizador.lp_models import (
    BiobjectiveProblem,
    LPProblem,
    LinearObjective,
    LinearConstraint,
    Sense,
    Operator,
    SolverStatus,
)
from solver_optimizador.multiobjective import (
    solve_biobjective_weighted,
    solve_lexicographic_extreme,
    generate_weight_combinations,
)
from solver_optimizador.interpretation import interpret_biobjective_solution
from solver_optimizador.model_io import deserialize_model
from solver_optimizador.problem_builder import build_biobjective_problem_from_state

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "hydroelectric_full_24_vars.json")


def _get_hydroelectric_problem():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = deserialize_model(f.read())

    var_names = data["var_names"]
    z1_coeffs = {v: (100.0 if v.startswith("GT") else 0.0) for v in var_names}
    z2_coeffs = {v: (1.0 if v == "V4" else 0.0) for v in var_names}

    return build_biobjective_problem_from_state(
        var_names=var_names,
        obj1_sense="Minimizar",
        obj1_coeffs=z1_coeffs,
        obj2_sense="Maximizar",
        obj2_coeffs=z2_coeffs,
        canonical_constraints=data["constraints_data"],
    )


# ---------------------------------------------------------------------------
# 1. Caso Hidroelectrico: Desempate Lexicografico Individual
# ---------------------------------------------------------------------------
def test_hydroelectric_z2_tie_break_gives_21416_25():
    """
    Verifica que al optimizar Z2 (MAX V4 = 100), el desempate lexicografico
    minimizando Z1 seleccione la solucion eficiente (21416.25, 100) y no la dominada (30000, 100).
    """
    problem = _get_hydroelectric_problem()
    res_z2 = solve_lexicographic_extreme(problem, primary_index=2)

    assert res_z2["status"] == SolverStatus.OPTIMAL
    assert res_z2["primary_optimal_value"] == pytest.approx(100.0, abs=1e-4)
    assert res_z2["Z2"] == pytest.approx(100.0, abs=1e-4)
    assert res_z2["Z1"] == pytest.approx(21416.25, abs=1e-2)
    assert res_z2["has_alternative_optima"] is True


def test_hydroelectric_z1_extreme():
    """
    Verifica el extremo para Z1 (MIN Costo): Z1* = 6701.25, Z2 = 40.
    """
    problem = _get_hydroelectric_problem()
    res_z1 = solve_lexicographic_extreme(problem, primary_index=1)

    assert res_z1["status"] == SolverStatus.OPTIMAL
    assert res_z1["primary_optimal_value"] == pytest.approx(6701.25, abs=1e-2)
    assert res_z1["Z1"] == pytest.approx(6701.25, abs=1e-2)
    assert res_z1["Z2"] == pytest.approx(40.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 2. Matriz de Pagos y Rangos de Normalizacion
# ---------------------------------------------------------------------------
def test_hydroelectric_payoff_matrix_and_ranges():
    """
    Valida la matriz de pagos eficiente y los rangos Delta Z1 = 14715, Delta Z2 = 60.
    """
    problem = _get_hydroelectric_problem()
    sol = solve_biobjective_weighted(problem, num_combinations=6)

    # Matriz de pagos
    pm = sol.payoff_matrix
    assert pm["opt_Z1"]["Z1"] == pytest.approx(6701.25, abs=1e-2)
    assert pm["opt_Z1"]["Z2"] == pytest.approx(40.0, abs=1e-4)

    assert pm["opt_Z2"]["Z1"] == pytest.approx(21416.25, abs=1e-2)
    assert pm["opt_Z2"]["Z2"] == pytest.approx(100.0, abs=1e-4)

    # Rangos
    nr = sol.normalization_ranges
    assert nr["Z1_range"] == pytest.approx(14715.0, abs=1e-2)
    assert nr["Z2_range"] == pytest.approx(60.0, abs=1e-4)
    assert nr["Z1_min"] == pytest.approx(6701.25, abs=1e-2)
    assert nr["Z1_max"] == pytest.approx(21416.25, abs=1e-2)
    assert nr["Z2_min"] == pytest.approx(40.0, abs=1e-4)
    assert nr["Z2_max"] == pytest.approx(100.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 3. Barrido de Ponderaciones de Referencia
# ---------------------------------------------------------------------------
def test_hydroelectric_weights_sweep_runs():
    """
    Verifica las 6 corridas ponderadas exactas:
    0.0 / 1.0 -> (21416.25, 100)
    0.2 / 0.8 -> (21416.25, 100)
    0.4 / 0.6 -> (21416.25, 100)
    0.6 / 0.4 -> (6701.25, 40)
    0.8 / 0.2 -> (6701.25, 40)
    1.0 / 0.0 -> (6701.25, 40)
    """
    problem = _get_hydroelectric_problem()
    sol = solve_biobjective_weighted(problem, num_combinations=6)

    assert len(sol.weighted_runs) == 6

    # alpha1 in [0.0, 0.2, 0.4] -> (21416.25, 100)
    for i in range(3):
        r = sol.weighted_runs[i]
        assert r["status"] == "Optimo"
        assert r["Z1"] == pytest.approx(21416.25, abs=1e-2)
        assert r["Z2"] == pytest.approx(100.0, abs=1e-4)

    # alpha1 in [0.6, 0.8, 1.0] -> (6701.25, 40)
    for i in range(3, 6):
        r = sol.weighted_runs[i]
        assert r["status"] == "Optimo"
        assert r["Z1"] == pytest.approx(6701.25, abs=1e-2)
        assert r["Z2"] == pytest.approx(40.0, abs=1e-4)

    # Todos los puntos unicos deben pertenecer a los dos extremos no dominados en espacio de objetivos
    unique_obj_points = {(round(u["Z1"], 2), round(u["Z2"], 2)) for u in sol.unique_solutions}
    assert unique_obj_points == {(21416.25, 100.0), (6701.25, 40.0)}

    for u in sol.unique_solutions:
        assert u["pareto_status"] == "No dominada"


def test_hydroelectric_no_dominated_solutions_in_payoff_or_runs():
    """
    Verifica que la solucion dominada (30000, 100) no aparezca en la matriz de pagos ni en los resultados unicos.
    """
    problem = _get_hydroelectric_problem()
    sol = solve_biobjective_weighted(problem, num_combinations=6)

    for u in sol.unique_solutions:
        assert u["Z1"] < 25000.0

    assert sol.payoff_matrix["opt_Z2"]["Z1"] == pytest.approx(21416.25, abs=1e-2)


# ---------------------------------------------------------------------------
# 4. Caso Especial 0.5 / 0.5
# ---------------------------------------------------------------------------
def test_hydroelectric_single_weight_half_half():
    """
    Verifica la ejecucion con ponderacion unica alpha = (0.5, 0.5).
    """
    problem = _get_hydroelectric_problem()
    sol = solve_biobjective_weighted(problem, weights=[(0.5, 0.5)])

    assert len(sol.weighted_runs) == 1
    r = sol.weighted_runs[0]
    assert r["status"] == "Optimo"
    # El valor obtenido debe pertenecer al segmento entre (6701.25, 40) y (21416.25, 100)
    assert 6700.0 <= r["Z1"] <= 21420.0
    assert 40.0 <= r["Z2"] <= 100.0

    bullets = interpret_biobjective_solution(problem, sol)
    assert any("degeneración de la función ponderada" in b or "múltiples soluciones óptimas" in b for b in bullets)


# ---------------------------------------------------------------------------
# 5. Benchmark A Intacto
# ---------------------------------------------------------------------------
def test_benchmark_a_unaffected_by_lexicographic():
    """
    Verifica que el Benchmark A estandar (MAX/MAX sin empates) mantenga resultados exactos.
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

    assert sol.individual_optima["Z1_opt"]["Z1"] == pytest.approx(1000.0, abs=1e-4)
    assert sol.individual_optima["Z1_opt"]["Z2"] == pytest.approx(80.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z1"] == pytest.approx(390.0, abs=1e-4)
    assert sol.individual_optima["Z2_opt"]["Z2"] == pytest.approx(169.0, abs=1e-4)

    assert sol.normalization_ranges["Z1_range"] == pytest.approx(610.0, abs=1e-4)
    assert sol.normalization_ranges["Z2_range"] == pytest.approx(89.0, abs=1e-4)
    assert len(sol.unique_solutions) == 3


# ---------------------------------------------------------------------------
# 6. Casos Sinteticos de Desempate en las 4 Combinaciones de Sentidos
# ---------------------------------------------------------------------------
def test_synthetic_flat_face_max_max():
    """MAX/MAX con cara plana en Z1."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 1.0, "x2": 0.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 6.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 6.0),
        ],
    )
    res1 = solve_lexicographic_extreme(problem, primary_index=1)
    assert res1["Z1"] == pytest.approx(10.0, abs=1e-4)
    assert res1["Z2"] == pytest.approx(6.0, abs=1e-4)
    assert res1["x"]["x1"] == pytest.approx(6.0, abs=1e-4)
    assert res1["x"]["x2"] == pytest.approx(4.0, abs=1e-4)


def test_synthetic_flat_face_max_min():
    """MAX/MIN con cara plana en Z1."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 0.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 6.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 6.0),
        ],
    )
    res1 = solve_lexicographic_extreme(problem, primary_index=1)
    assert res1["Z1"] == pytest.approx(10.0, abs=1e-4)
    assert res1["Z2"] == pytest.approx(4.0, abs=1e-4)
    assert res1["x"]["x1"] == pytest.approx(4.0, abs=1e-4)
    assert res1["x"]["x2"] == pytest.approx(6.0, abs=1e-4)


def test_synthetic_flat_face_min_max():
    """MIN/MAX con cara plana en Z1."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MINIMIZE, {"x1": 1.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 1.0, "x2": 0.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.GE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 6.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 6.0),
        ],
    )
    res1 = solve_lexicographic_extreme(problem, primary_index=1)
    assert res1["Z1"] == pytest.approx(10.0, abs=1e-4)
    assert res1["Z2"] == pytest.approx(6.0, abs=1e-4)
    assert res1["x"]["x1"] == pytest.approx(6.0, abs=1e-4)
    assert res1["x"]["x2"] == pytest.approx(4.0, abs=1e-4)


def test_synthetic_flat_face_min_min():
    """MIN/MIN con cara plana en Z1."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MINIMIZE, {"x1": 1.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 0.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.GE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 6.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 6.0),
        ],
    )
    res1 = solve_lexicographic_extreme(problem, primary_index=1)
    assert res1["Z1"] == pytest.approx(10.0, abs=1e-4)
    assert res1["Z2"] == pytest.approx(4.0, abs=1e-4)
    assert res1["x"]["x1"] == pytest.approx(4.0, abs=1e-4)
    assert res1["x"]["x2"] == pytest.approx(6.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 7. Interpretacion de Extremos Lexicograficos
# ---------------------------------------------------------------------------
def test_interpretation_lexicographic_notes():
    """
    Verifica que la interpretacion reporte la construccion de extremos lexicograficos
    y el desempate especifico para Z2 en el problema hidroelectrico.
    """
    problem = _get_hydroelectric_problem()
    sol = solve_biobjective_weighted(problem, num_combinations=6)
    bullets = interpret_biobjective_solution(problem, sol)

    assert any("extremos lexicográficamente eficientes" in b for b in bullets)
    assert any("Z_2" in b and "criterio secundario de desempate" in b for b in bullets)
