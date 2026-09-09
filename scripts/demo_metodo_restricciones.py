"""Demostracion reproducible del metodo de las restricciones en Benchmark A."""

from __future__ import annotations

import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from solver_optimizador import (  # noqa: E402
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
    solve_biobjective_epsilon_constraint,
)


def build_benchmark_a() -> BiobjectiveProblem:
    """Construye el Benchmark A canonico, sin datos simulados."""

    return BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective(
            "Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}
        ),
        objective2=LinearObjective(
            "Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}
        ),
        constraints=[
            LinearConstraint(
                "c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0
            ),
            LinearConstraint(
                "c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0
            ),
        ],
    )


def _sense_label(sense: Sense) -> str:
    return "MAXIMIZAR" if sense == Sense.MAXIMIZE else "MINIMIZAR"


def _expression(objective: LinearObjective, variables: list[str]) -> str:
    return " + ".join(
        f"{objective.coefficients.get(variable, 0.0):g} {variable}"
        for variable in variables
    )


def _number(value: float | None) -> str:
    if value is None:
        return "-"
    displayed_value = 0.0 if abs(value) < 0.5e-6 else value
    return f"{displayed_value:.6f}"


def _print_run_table(problem: BiobjectiveProblem, runs: list[dict]) -> None:
    columns = ["t", "E", "estado", *problem.variables, "Z1", "Z2", "tiempo_s"]
    widths = {column: max(10, len(column)) for column in columns}
    rows: list[dict[str, str]] = []
    for run in runs:
        row = {
            "t": str(run["t"]),
            "E": _number(run["E"]),
            "estado": run["status"],
            "Z1": _number(run["Z1"]),
            "Z2": _number(run["Z2"]),
            "tiempo_s": _number(run["execution_time_sec"]),
        }
        for variable in problem.variables:
            row[variable] = _number(
                None if run["x"] is None else run["x"][variable]
            )
        rows.append(row)
        for column in columns:
            widths[column] = max(widths[column], len(row[column]))

    header = " | ".join(f"{column:>{widths[column]}}" for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in rows:
        print(" | ".join(f"{row[column]:>{widths[column]}}" for column in columns))


def _print_sweep(problem: BiobjectiveProblem, primary_objective: int, r: int) -> None:
    result = solve_biobjective_epsilon_constraint(
        problem, primary_objective=primary_objective, r=r
    )
    constrained = result.constrained_objective
    constrained_prefix = f"Z{constrained}"

    print("\n" + "=" * 96)
    print(
        f"BARRIDO: objetivo principal Z{primary_objective}; "
        f"objetivo restringido Z{constrained}"
    )
    print("=" * 96)
    print("\n3. Óptimos individuales")
    for objective_name in ("Z1", "Z2"):
        anchor = result.individual_optima[f"{objective_name}_opt"]
        x_text = ", ".join(
            f"{name}={_number(anchor['x'][name])}" for name in problem.variables
        )
        print(
            f"   Óptimo {objective_name}: {x_text}; "
            f"Z1={_number(anchor['Z1'])}; Z2={_number(anchor['Z2'])}; "
            f"estado={anchor['status'].value}"
        )

    print("\n4. Matriz de pagos")
    print("   ancla      |         Z1 |         Z2")
    print("   -----------+------------+-----------")
    for anchor_name in ("opt_Z1", "opt_Z2"):
        anchor = result.payoff_matrix[anchor_name]
        print(
            f"   {anchor_name:<10} | {_number(anchor['Z1']):>10} | "
            f"{_number(anchor['Z2']):>10}"
        )

    print(f"\n5. Objetivo restringido Z{constrained}")
    print(
        f"   {constrained_prefix}_min = "
        f"{_number(result.objective_ranges[f'{constrained_prefix}_min'])}"
    )
    print(
        f"   {constrained_prefix}_max = "
        f"{_number(result.objective_ranges[f'{constrained_prefix}_max'])}"
    )
    print(f"   r = {result.r} (se resuelven {result.r + 1} problemas)")
    print(
        "   Operador = "
        + (">=" if _objective(problem, constrained).sense == Sense.MAXIMIZE else "<=")
    )

    print("\n6. Fórmula utilizada")
    print("   E_k,t = Zk_min + (t/r)(Zk_max - Zk_min), t = 0, ..., r")

    print("\n7. Tabla completa de corridas")
    _print_run_table(problem, result.runs)

    print(f"\n8. Soluciones únicas ({len(result.unique_solutions)})")
    for solution in result.unique_solutions:
        x_text = ", ".join(
            f"{name}={_number(solution['x'][name])}" for name in problem.variables
        )
        print(
            f"   {solution['id']}: {x_text}; Z1={_number(solution['Z1'])}; "
            f"Z2={_number(solution['Z2'])}; t={solution['run_indices']}; "
            f"repeticiones={solution['count']}"
        )

    print(
        f"\n9. Soluciones no dominadas / frontera de Pareto obtenida "
        f"({len(result.nondominated_solutions)})"
    )
    for solution in result.nondominated_solutions:
        print(
            f"   {solution['id']}: (Z1={_number(solution['Z1'])}, "
            f"Z2={_number(solution['Z2'])}) -> {solution['pareto_status']}"
        )

    if len(result.runs) != r + 1:
        raise RuntimeError("El barrido no produjo exactamente r + 1 corridas.")
    if any(run["status"] != "optimal" for run in result.runs):
        raise RuntimeError("Benchmark A produjo una corrida no óptima.")


def _objective(problem: BiobjectiveProblem, index: int) -> LinearObjective:
    return problem.objective1 if index == 1 else problem.objective2


def main() -> None:
    problem = build_benchmark_a()
    print("=" * 96)
    print("MÉTODO DE LAS RESTRICCIONES")
    print("Benchmark A biobjetivo — Pyomo + HiGHS")
    print("=" * 96)
    print("\n1. Funciones objetivo")
    print(f"   Z1 = {_expression(problem.objective1, problem.variables)}")
    print(f"   Z2 = {_expression(problem.objective2, problem.variables)}")
    print("\n2. Sentido de cada objetivo")
    print(f"   Z1: {_sense_label(problem.objective1.sense)}")
    print(f"   Z2: {_sense_label(problem.objective2.sense)}")
    _print_sweep(problem, primary_objective=1, r=5)
    _print_sweep(problem, primary_objective=2, r=5)
    print("\nDEMOSTRACIÓN COMPLETADA: ambos barridos resolvieron 6 problemas cada uno.")


if __name__ == "__main__":
    main()
