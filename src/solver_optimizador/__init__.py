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
from .multiobjective import (
    generate_weight_combinations,
    normalize_objective_value,
    solve_biobjective_weighted,
    solve_lexicographic_extreme,
)
from .signature import build_model_signature
from .interpretation import interpret_mono_solution, interpret_biobjective_solution
from .model_io import (
    serialize_model,
    deserialize_model,
    validate_model_dict,
    normalize_constraints,
    is_empty_constraint_row,
    sanitize_filename,
    SCHEMA_VERSION,
)
from .problem_builder import (
    build_lp_problem_from_state,
    build_biobjective_problem_from_state,
)
from .plotting import (
    plot_feasible_region_2d,
    plot_objective_space_2d,
    plot_variable_values,
    plot_constraint_slacks,
    plot_multiobjective_runs,
)

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
    "serialize_model",
    "deserialize_model",
    "validate_model_dict",
    "normalize_constraints",
    "is_empty_constraint_row",
    "sanitize_filename",
    "SCHEMA_VERSION",
    "plot_feasible_region_2d",
    "plot_objective_space_2d",
    "plot_variable_values",
    "plot_constraint_slacks",
    "plot_multiobjective_runs",
    "build_lp_problem_from_state",
    "build_biobjective_problem_from_state",
    "solve_lp",
    "solve_biobjective_weighted",
    "solve_lexicographic_extreme",
    "generate_weight_combinations",
    "normalize_objective_value",
]
