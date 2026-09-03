"""Verifica restricciones constantes y la salvaguarda temporal de nombres."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solver_optimizador.constraint_import import parse_variable_names
from solver_optimizador.input_application import apply_variable_import
from solver_optimizador.lp_models import (
    LinearConstraint,
    LinearObjective,
    LPProblem,
    Operator,
    Sense,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.problem_builder import build_lp_problem_from_state


def _solve_constant(operator: Operator, rhs: float):
    problem = LPProblem(
        variables=["x1"],
        objective=LinearObjective("Z", Sense.MAXIMIZE, {"x1": 0.0}),
        constraints=[LinearConstraint("constant", {}, operator, rhs)],
    )
    return solve_lp(problem)


def _projection_state() -> dict[str, object]:
    return {
        "editor_version": 0,
        "problem_type": "Monoobjetivo",
        "num_vars": 2,
        "var_names": ["x1", "x2"],
        "obj_coeffs": {"x1": 0.0, "x2": 0.0},
        "obj1_coeffs": {"x1": 0.0, "x2": 0.0},
        "obj2_coeffs": {"x1": 0.0, "x2": 0.0},
        "constraints_data": [
            {
                "name": "R1",
                "coefficients": {"x1": 1.0},
                "operator": "<=",
                "rhs": 10.0,
            }
        ],
    }


def main() -> None:
    cases = [
        ("0 <= 10", Operator.LE, 10.0, SolverStatus.OPTIMAL),
        ("0 >= 10", Operator.GE, 10.0, SolverStatus.INFEASIBLE),
        ("0 = 0", Operator.EQ, 0.0, SolverStatus.OPTIMAL),
        ("0 = 10", Operator.EQ, 10.0, SolverStatus.INFEASIBLE),
    ]
    results = []
    for label, operator, rhs, expected in cases:
        solution = _solve_constant(operator, rhs)
        assert solution.status == expected
        results.append((label, solution.status.value))

    state = _projection_state()
    apply_variable_import(state, ["x2"])
    assert state["constraints_data"][0]["coefficients"] == {}
    projected_problem = build_lp_problem_from_state(
        state["var_names"],
        "Maximizar",
        state["obj_coeffs"],
        state["constraints_data"],
    )
    projected_solution = solve_lp(projected_problem)
    assert projected_solution.status == SolverStatus.OPTIMAL

    for reserved_name in ("obj", "component_map", "name"):
        parsed = parse_variable_names(f"x1,{reserved_name}")
        assert not parsed.is_valid
        assert any("nombre reservado" in error for error in parsed.errors)

    valid = parse_variable_names("x1")
    assert valid.is_valid and valid.variables == ["x1"]

    print("SCALABLE_INPUT_HARDENING_VERIFICATION")
    for label, status in results:
        print(f"constant_constraint={label} status={status}")
    print(
        "projection=PASS coefficients={} "
        f"status={projected_solution.status.value}"
    )
    print("reserved_names_rejected=obj,component_map,name")
    print("valid_name_accepted=x1")
    print("RESULT: PASS (scalable input hardening contract satisfied)")


if __name__ == "__main__":
    main()
