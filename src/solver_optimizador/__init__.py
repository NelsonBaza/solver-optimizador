"""
solver_optimizador: Suite modular de optimizacion matematica.
Modulo base para LP monoobjetivo y biobjetivo por ponderaciones.
"""

from .lp_models import (
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
    is_finite_number,
)
from .lp_solver import solve_lp
from .multiobjective import solve_biobjective_weighted
from .signature import build_model_signature
from .interpretation import interpret_mono_solution, interpret_biobjective_solution

__all__ = [
    "Sense",
    "Operator",
    "LinearObjective",
    "LinearConstraint",
    "LPProblem",
    "BiobjectiveProblem",
    "SolverStatus",
    "ConstraintResult",
    "LPSolution",
    "MultiobjectiveSolution",
    "is_finite_number",
    "build_model_signature",
    "interpret_mono_solution",
    "interpret_biobjective_solution",
    "solve_lp",
    "solve_biobjective_weighted",
]
