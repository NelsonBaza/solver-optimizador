"""
Suite de pruebas unitarias para la interpretacion base automatica de resultados.
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
    # Debe mencionar optimo Z
    assert any("10.00" in b for b in bullets)
    # Debe mencionar variables positivas
    assert any("x1" in b and "x2" in b for b in bullets)
    # Debe mencionar restricciones activas
    assert any("c1" in b and "c2" in b for b in bullets)
    # Debe mencionar restricciones con holgura
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


def test_interpret_biobjective_optimal():
    """Valida la interpretacion de un problema biobjetivo resuelto por ponderaciones."""
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
    # Debe mencionar optimos individuales
    assert any("1000.00" in b and "169.00" in b for b in bullets)
    # Debe mencionar compromiso / trade-off
    assert any("trade-off" in b.lower() or "compromiso" in b.lower() for b in bullets)
    # Debe mencionar conteo de no dominadas
    assert any("3 resultaron no dominadas" in b for b in bullets)
    # Debe incluir aviso metodologico de frontera discreta
    assert any("frontera de pareto" in b.lower() for b in bullets)


def test_interpret_biobjective_empty():
    """Valida la interpretacion cuando no hay soluciones unicas calculadas."""
    problem = BiobjectiveProblem(
        variables=["x1"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 2.0}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0}, Operator.LE, 10.0),
        ],
    )
    empty_solution = MultiobjectiveSolution(
        individual_optima={},
        payoff_matrix={},
        normalization_ranges={},
        weighted_runs=[],
        unique_solutions=[],
        pareto_classification={},
        timing={},
        notes=["Error de prueba"],
    )
    bullets = interpret_biobjective_solution(problem, empty_solution)
    assert len(bullets) >= 1
    assert any("no fue posible" in b.lower() for b in bullets)
