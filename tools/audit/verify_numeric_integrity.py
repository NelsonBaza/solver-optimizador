"""Verifica el contrato corregido de integridad numerica de ``solve_lp``.

Este script sí importa el código de producción porque su objetivo es comprobar
los valores publicados por el adaptador actual con los valores reconstruidos
desde el vector de variables que ese mismo adaptador publica. La evidencia del
defecto anterior permanece en ``docs/audit_evidence/fase1b_validation.txt``.
"""

from __future__ import annotations

import math
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
EXPECTED_X = 1.0 / COEFFICIENT


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

    print("NUMERIC_INTEGRITY_CONTRACT_VERIFICATION")
    print(f"expected_x={EXPECTED_X:.17g}")
    print(f"published_x={published_x:.17g}")
    print(f"published_objective={published_objective:.17g}")
    print(f"reconstructed_objective_from_published_x={reconstructed_objective:.17g}")
    print(f"published_lhs={published_lhs:.17g}")
    print(f"reconstructed_lhs_from_published_x={reconstructed_lhs:.17g}")

    assert math.isclose(published_x, EXPECTED_X, rel_tol=1e-9, abs_tol=1e-18)
    assert math.isclose(published_objective, reconstructed_objective, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(reconstructed_objective, 1.0, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(published_lhs, reconstructed_lhs, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(reconstructed_lhs, 1.0, rel_tol=1e-12, abs_tol=1e-12)

    print("RESULT: PASS (numeric integrity contract satisfied)")


if __name__ == "__main__":
    main()
