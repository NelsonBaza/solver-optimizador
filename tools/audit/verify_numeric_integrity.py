"""Reproduce el defecto de redondeo del resultado actual de ``solve_lp``.

Este script sí importa el código de producción porque su objetivo es comparar
los valores publicados por el adaptador actual con los valores reconstruidos
desde el vector de variables que ese mismo adaptador publica. No corrige el
defecto; falla si el comportamiento observado deja de reproducirse.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from solver_optimizador.lp_models import (  # noqa: E402
    LPProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp  # noqa: E402


COEFFICIENT = 1_000_000_000.0
EXPECTED_INTERNAL_X = 1.0 / COEFFICIENT


def main() -> None:
    problem = LPProblem(
        variables=["x"],
        objective=LinearObjective(
            name="Z",
            sense=Sense.MAXIMIZE,
            coefficients={"x": COEFFICIENT},
        ),
        constraints=[
            LinearConstraint(
                name="scaled_equality",
                coefficients={"x": COEFFICIENT},
                operator=Operator.EQ,
                rhs=1.0,
            )
        ],
    )

    solution = solve_lp(problem)
    assert solution.status == SolverStatus.OPTIMAL
    assert len(solution.constraint_results) == 1

    published_x = solution.variable_values["x"]
    published_objective = solution.objective_value
    published_lhs = solution.constraint_results[0].lhs
    reconstructed_objective = COEFFICIENT * published_x
    reconstructed_lhs = COEFFICIENT * published_x

    print("NUMERIC_INTEGRITY_DEFECT_REPRODUCTION")
    print(f"expected_internal_x={EXPECTED_INTERNAL_X:.17g}")
    print(f"published_x={published_x:.17g}")
    print(f"published_objective={published_objective:.17g}")
    print(f"reconstructed_objective_from_published_x={reconstructed_objective:.17g}")
    print(f"published_lhs={published_lhs:.17g}")
    print(f"reconstructed_lhs_from_published_x={reconstructed_lhs:.17g}")

    assert EXPECTED_INTERNAL_X == 1e-9
    assert published_x == 0.0
    assert published_objective == 1.0
    assert reconstructed_objective == 0.0
    assert published_lhs == 1.0
    assert reconstructed_lhs == 0.0

    print("RESULT: PASS (current production defect reproduced; no fix applied)")


if __name__ == "__main__":
    main()
