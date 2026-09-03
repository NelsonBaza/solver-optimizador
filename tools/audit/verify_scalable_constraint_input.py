"""Verificador reproducible del contrato de entrada dispersa escalable."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solver_optimizador.constraint_import import parse_constraint_text
from solver_optimizador.lp_models import SolverStatus
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.problem_builder import build_lp_problem_from_state


VARIABLE_COUNT = 100
CONSTRAINT_COUNT = 500
EXPECTED_NONZEROS = 900


def build_sparse_input() -> str:
    rows = ["constraint,variable,coefficient,operator,rhs"]
    for index in range(1, VARIABLE_COUNT + 1):
        rows.append(f"UB_{index},x{index},1,<=,10")
    for offset in range(CONSTRAINT_COUNT - VARIABLE_COUNT):
        first = offset % VARIABLE_COUNT + 1
        second = (offset + 1) % VARIABLE_COUNT + 1
        name = f"PAIR_{offset + 1}"
        rows.append(f"{name},x{first},1,<=,20")
        rows.append(f"{name},x{second},1,<=,20")
    return "\n".join(rows)


def main() -> None:
    imported = parse_constraint_text(build_sparse_input(), input_format="sparse")
    assert imported.is_valid, imported.errors
    assert imported.number_of_variables == VARIABLE_COUNT
    assert imported.number_of_constraints == CONSTRAINT_COUNT
    assert imported.nonzero_coefficients == EXPECTED_NONZEROS
    assert max(len(row["coefficients"]) for row in imported.constraints) == 2

    variables = [f"x{index}" for index in range(1, VARIABLE_COUNT + 1)]
    objective = {variable: 1.0 for variable in variables}
    problem = build_lp_problem_from_state(
        variables,
        "Maximizar",
        objective,
        imported.constraints,
    )
    solution = solve_lp(problem)
    assert solution.status == SolverStatus.OPTIMAL
    assert abs(solution.objective_value - 1000.0) <= 1e-6
    assert all(abs(solution.variable_values[variable] - 10.0) <= 1e-6 for variable in variables)
    assert solution.objective_value == problem.objective.evaluate(solution.variable_values)

    print("SCALABLE_CONSTRAINT_INPUT_VERIFICATION")
    print(f"variables={imported.number_of_variables}")
    print(f"constraints={imported.number_of_constraints}")
    print(f"nonzeros={imported.nonzero_coefficients}")
    print(f"input_format={imported.source_format}")
    print(f"solver_status={solution.status.value}")
    print(f"objective_value={solution.objective_value:.12g}")
    print("RESULT: PASS (scalable constraint input contract satisfied)")


if __name__ == "__main__":
    main()
