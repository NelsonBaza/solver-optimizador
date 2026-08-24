"""
Suite de pruebas unitarias para la interpretacion base automatica de resultados (Mono y Biobjetivo).
Valida que la interpretacion sea rigurosamente consciente del sentido MAX/MIN en todas las combinaciones.
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
    ConstraintResult,
    LPSolution,
    MultiobjectiveSolution,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.interpretation import (
    interpret_mono_solution,
    interpret_biobjective_solution,
)


def test_interpret_mono_optimal():
    """Valida la interpretacion de una solucion lineal monoobjetivo optima."""
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 3.0, "x2": 2.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 4.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.LE, 2.0),
            LinearConstraint("c3", {"x1": 0.0, "x2": 1.0}, Operator.LE, 3.0),
        ],
    )
    solution = solve_lp(problem)
    bullets = interpret_mono_solution(problem, solution)

    assert len(bullets) >= 3
    assert any("10.00" in b for b in bullets)
    assert any("x1" in b and "x2" in b for b in bullets)
    assert any("c1" in b and "c2" in b for b in bullets)
    assert any("c3" in b and "holgura" in b for b in bullets)


def test_interpret_mono_infeasible():
    """Valida la interpretacion de un problema infactible."""
    problem = LPProblem(
        variables=["x1"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0}, Operator.LE, 2.0),
            LinearConstraint("c2", {"x1": 1.0}, Operator.GE, 5.0),
        ],
    )
    solution = solve_lp(problem)
    bullets = interpret_mono_solution(problem, solution)

    assert len(bullets) >= 1
    assert any("infactible" in b.lower() for b in bullets)


def test_interpret_mono_unbounded():
    """Valida la interpretacion de un problema no acotado."""
    problem = LPProblem(
        variables=["x1", "x2"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 1.0, "x2": 1.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": -1.0}, Operator.LE, 1.0),
        ],
    )
    solution = solve_lp(problem)
    bullets = interpret_mono_solution(problem, solution)

    assert len(bullets) >= 1
    assert any("no esta acotado" in b.lower() or "no acotamiento" in b.lower() for b in bullets)


def test_interpret_biobjective_max_max():
    """Valida la interpretacion para biobjetivo MAX/MAX (Benchmark A)."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0),
            LinearConstraint("c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0),
        ],
    )
    solution = solve_biobjective_weighted(problem, num_combinations=6)
    bullets = interpret_biobjective_solution(problem, solution)

    assert len(bullets) >= 4
    assert any("1000.00" in b and "169.00" in b and "maximizar" in b for b in bullets)
    assert any("trade-off" in b.lower() or "compromiso" in b.lower() for b in bullets)
    assert any("favorece a $z_1$ segun su sentido de optimizacion (max)" in b.lower() for b in bullets)
    assert any("favorece a $z_2$ segun su sentido de optimizacion (max)" in b.lower() for b in bullets)
    full_text = " ".join(bullets).lower()
    assert "rango amplio" not in full_text
    assert "intervalo completo" not in full_text


def test_interpret_biobjective_max_min():
    """Valida la interpretacion para biobjetivo MAX/MIN."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 2.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 3.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.GE, 2.0),
        ],
    )
    solution = solve_biobjective_weighted(problem, num_combinations=5)
    bullets = interpret_biobjective_solution(problem, solution)

    assert len(bullets) >= 4
    assert any("maximizar $z_1$" in b.lower() and "minimizar $z_2$" in b.lower() for b in bullets)
    assert any("favorece a $z_1$ segun su sentido de optimizacion (max)" in b.lower() for b in bullets)
    assert any("favorece a $z_2$ segun su sentido de optimizacion (min)" in b.lower() for b in bullets)


def test_interpret_biobjective_min_max():
    """Valida la interpretacion para biobjetivo MIN/MAX."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MINIMIZE, {"x1": 2.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 1.0, "x2": 3.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 0.0}, Operator.GE, 2.0),
        ],
    )
    solution = solve_biobjective_weighted(problem, num_combinations=5)
    bullets = interpret_biobjective_solution(problem, solution)

    assert len(bullets) >= 4
    assert any("minimizar $z_1$" in b.lower() and "maximizar $z_2$" in b.lower() for b in bullets)
    assert any("favorece a $z_1$ segun su sentido de optimizacion (min)" in b.lower() for b in bullets)
    assert any("favorece a $z_2$ segun su sentido de optimizacion (max)" in b.lower() for b in bullets)


def test_interpret_biobjective_min_min():
    """Valida la interpretacion para biobjetivo MIN/MIN con conflicto."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MINIMIZE, {"x1": 2.0, "x2": 1.0}),
        objective2=LinearObjective("Z2", Sense.MINIMIZE, {"x1": 1.0, "x2": 3.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.GE, 10.0),
            LinearConstraint("c2", {"x1": 1.0, "x2": 2.0}, Operator.LE, 20.0),
        ],
    )
    solution = solve_biobjective_weighted(problem, num_combinations=5)
    bullets = interpret_biobjective_solution(problem, solution)

    assert len(bullets) >= 4
    assert any("minimizar $z_1$" in b.lower() and "minimizar $z_2$" in b.lower() for b in bullets)
    assert any("favorece a $z_1$ segun su sentido de optimizacion (min)" in b.lower() for b in bullets)
    assert any("favorece a $z_2$ segun su sentido de optimizacion (min)" in b.lower() for b in bullets)


def test_interpret_biobjective_stability_phrasing():
    """Valida que la frase de estabilidad no afirme rango amplio ni intervalos completos."""
    problem = BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0),
            LinearConstraint("c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0),
        ],
    )
    solution = solve_biobjective_weighted(problem, num_combinations=6)
    bullets = interpret_biobjective_solution(problem, solution)

    assert any("preferencias discretas analizadas" in b for b in bullets)
    full_text = " ".join(bullets).lower()
    assert "rango amplio" not in full_text
    assert "intervalo completo" not in full_text
    assert "estabilidad global" not in full_text
