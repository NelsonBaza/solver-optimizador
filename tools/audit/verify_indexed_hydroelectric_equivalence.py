"""Compara el fixture hidro explicito con su expansion indexada equivalente."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_examples import hydroelectric_fixture_indexed_spec
from solver_optimizador.lp_models import SolverStatus
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.model_io import deserialize_model
from solver_optimizador.problem_builder import build_lp_problem_from_state


def _explicit_variable(generated: str) -> str:
    family, index = generated.rsplit("_", 1)
    return f"{family}{index}"


def _explicit_constraint(generated: str) -> str:
    if generated == "Balance_H_Inicial_1":
        return "Balance_H1"
    if generated.startswith("Balance_H_"):
        return generated.replace("Balance_H_", "Balance_H", 1)
    if generated.startswith("Demanda_P_"):
        return generated.replace("Demanda_P_", "Demanda_P", 1)
    return generated


def _residual(constraint, values) -> float:
    return constraint.evaluate_lhs(values) - constraint.rhs


def main() -> None:
    loaded = deserialize_model(
        (ROOT / "tests/fixtures/hydroelectric_full_24_vars.json").read_text(encoding="utf-8")
    )
    explicit_problem = build_lp_problem_from_state(
        loaded["var_names"], loaded["obj_sense"], loaded["obj_coeffs"], loaded["constraints_data"]
    )
    expanded = compile_indexed_model(hydroelectric_fixture_indexed_spec())
    state = expanded.to_builder_state()
    indexed_problem = build_lp_problem_from_state(
        state["var_names"], state["obj_sense"], state["obj_coeffs"], state["constraints_data"]
    )
    explicit_solution = solve_lp(explicit_problem)
    indexed_solution = solve_lp(indexed_problem)
    assert explicit_solution.status == indexed_solution.status == SolverStatus.OPTIMAL
    assert abs(explicit_solution.objective_value - indexed_solution.objective_value) <= 1e-7
    assert abs(indexed_solution.objective_value - 6701.25) <= 1e-7
    for generated in expanded.variables:
        original = _explicit_variable(generated)
        assert abs(indexed_solution.variable_values[generated] - explicit_solution.variable_values[original]) <= 1e-7
    explicit_constraints = {constraint.name: constraint for constraint in explicit_problem.constraints}
    max_residual_difference = 0.0
    for constraint in indexed_problem.constraints:
        original = explicit_constraints[_explicit_constraint(constraint.name)]
        difference = abs(
            _residual(constraint, indexed_solution.variable_values)
            - _residual(original, explicit_solution.variable_values)
        )
        max_residual_difference = max(max_residual_difference, difference)
        assert difference <= 1e-7
    print(f"explicit_status={explicit_solution.status.value}")
    print(f"indexed_status={indexed_solution.status.value}")
    print(f"explicit_objective={explicit_solution.objective_value:.12g}")
    print(f"indexed_objective={indexed_solution.objective_value:.12g}")
    print(f"generated_variables={expanded.statistics['generated_variables']}")
    print(f"generated_constraints={expanded.statistics['generated_constraints']}")
    print(f"nonzeros={expanded.statistics['nonzero_coefficients']}")
    print(f"max_residual_difference={max_residual_difference:.3g}")
    print("NOTE: Equivalencia con fixture vigente; no certifica fidelidad fisica al enunciado fuente.")
    print("RESULT: PASS (indexed hydroelectric fixture equivalence satisfied)")


if __name__ == "__main__":
    main()
