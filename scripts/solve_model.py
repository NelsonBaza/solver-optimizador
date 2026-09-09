"""Ejecutor general de modelos biobjetivo JSON desde consola."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from solver_optimizador import (  # noqa: E402
    BiobjectiveProblem,
    EpsilonConstraintSolution,
    MultiobjectiveSolution,
    Sense,
    build_biobjective_problem_from_state,
    deserialize_model,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
)


def _integer_at_least(minimum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("debe ser un número entero") from exc
        if parsed < minimum:
            raise argparse.ArgumentTypeError(f"debe ser mayor o igual que {minimum}")
        return parsed

    return parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Carga un modelo biobjetivo JSON de solver-optimizador y lo resuelve "
            "por epsilon-constraint o ponderaciones normalizadas."
        )
    )
    parser.add_argument("model_file", type=Path, help="ruta del modelo JSON")
    parser.add_argument(
        "--method",
        choices=("epsilon", "weighted"),
        required=True,
        help="método multiobjetivo",
    )
    parser.add_argument(
        "--primary",
        choices=(1, 2),
        type=int,
        default=1,
        help="objetivo principal para epsilon (predeterminado: 1)",
    )
    parser.add_argument(
        "--r",
        type=_integer_at_least(1),
        default=6,
        help="número de intervalos epsilon (predeterminado: 6)",
    )
    parser.add_argument(
        "--num-weights",
        type=_integer_at_least(2),
        default=6,
        help="número de ponderaciones uniformes (predeterminado: 6)",
    )
    return parser


def load_biobjective_model(
    model_file: Path,
) -> tuple[str, dict[str, Any], BiobjectiveProblem]:
    """Carga, deserializa y construye un problema biobjetivo del esquema 1.0."""

    json_text = model_file.read_text(encoding="utf-8")
    loaded = deserialize_model(json_text)
    if loaded["problem_type"] != "Biobjetivo":
        raise ValueError(
            "El ejecutor multiobjetivo requiere problem.type='Biobjetivo'; "
            f"se recibió '{loaded['problem_type']}'."
        )

    problem = build_biobjective_problem_from_state(
        var_names=loaded["var_names"],
        obj1_sense=loaded["obj1_sense"],
        obj1_coeffs=loaded["obj1_coeffs"],
        obj2_sense=loaded["obj2_sense"],
        obj2_coeffs=loaded["obj2_coeffs"],
        canonical_constraints=loaded["constraints_data"],
        obj1_name="Z1",
        obj2_name="Z2",
    )
    model_name = loaded["metadata"]["name"]
    return model_name, loaded, problem


def _number(value: float | None, decimals: int = 6) -> str:
    if value is None:
        return "-"
    displayed = 0.0 if abs(value) < 0.5 * (10 ** -decimals) else value
    return f"{displayed:.{decimals}f}"


def _compact_number(value: float) -> str:
    displayed = 0.0 if abs(value) < 5e-13 else value
    return f"{displayed:.12g}"


def _sense_label(sense: Sense) -> str:
    return "MAXIMIZAR" if sense == Sense.MAXIMIZE else "MINIMIZAR"


def _objective_expression(problem: BiobjectiveProblem, index: int) -> str:
    objective = problem.objective1 if index == 1 else problem.objective2
    terms: list[str] = []
    for variable in problem.variables:
        coefficient = objective.coefficients.get(variable, 0.0)
        if coefficient == 0.0:
            continue
        magnitude = f"{abs(coefficient):g} {variable}"
        if not terms:
            terms.append(magnitude if coefficient > 0 else f"-{magnitude}")
        else:
            terms.append(("+ " if coefficient > 0 else "- ") + magnitude)
    return " ".join(terms) if terms else "0"


def _print_model_header(
    model_file: Path,
    model_name: str,
    problem: BiobjectiveProblem,
    method: str,
) -> None:
    print("=" * 110)
    print("EJECUTOR GENERAL DE MODELOS BIOBJETIVO")
    print("=" * 110)
    print(f"Archivo: {model_file}")
    print(f"Nombre del modelo: {model_name}")
    print(f"Variables: {len(problem.variables)}")
    print(f"Restricciones originales: {len(problem.constraints)}")
    print("\nFunciones objetivo y sentidos")
    print(
        f"  Z1 = {_objective_expression(problem, 1)} "
        f"[{_sense_label(problem.objective1.sense)}]"
    )
    print(
        f"  Z2 = {_objective_expression(problem, 2)} "
        f"[{_sense_label(problem.objective2.sense)}]"
    )
    method_label = (
        "MÉTODO DE LAS RESTRICCIONES (ε-CONSTRAINT)"
        if method == "epsilon"
        else "MÉTODO DE PONDERACIONES NORMALIZADAS"
    )
    print(f"\nMétodo: {method_label}")


def _print_payoff_matrix(payoff_matrix: dict[str, Any]) -> None:
    print("\nMatriz de pagos")
    print("  ancla      | estado      |             Z1 |             Z2")
    print("  -----------+-------------+----------------+---------------")
    for anchor_name in ("opt_Z1", "opt_Z2"):
        anchor = payoff_matrix[anchor_name]
        print(
            f"  {anchor_name:<10} | {str(anchor.get('status', 'optimal')):<11} | "
            f"{_number(anchor['Z1']):>14} | {_number(anchor['Z2']):>14}"
        )


def _print_table(columns: list[str], rows: list[dict[str, str]]) -> None:
    widths = {
        column: max([len(column), *(len(row[column]) for row in rows)])
        for column in columns
    }
    print(" | ".join(f"{column:>{widths[column]}}" for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" | ".join(f"{row[column]:>{widths[column]}}" for column in columns))


def _run_row(
    run: dict[str, Any],
    variables: list[str],
    prefix: dict[str, str],
    suffix: dict[str, str],
) -> dict[str, str]:
    row = dict(prefix)
    for variable in variables:
        row[variable] = _number(
            None if run.get("x") is None else run["x"].get(variable)
        )
    row.update(suffix)
    return row


def _print_epsilon_runs(
    problem: BiobjectiveProblem, result: EpsilonConstraintSolution
) -> None:
    print(f"\nTabla completa de las {len(result.runs)} corridas")
    columns = [
        "t",
        "E",
        "estado",
        *problem.variables,
        "Z1",
        "Z2",
        "tiempo_s",
    ]
    rows = [
        _run_row(
            run,
            problem.variables,
            prefix={
                "t": str(run["t"]),
                "E": _number(run["E"]),
                "estado": run["status"],
            },
            suffix={
                "Z1": _number(run["Z1"]),
                "Z2": _number(run["Z2"]),
                "tiempo_s": _number(run["execution_time_sec"]),
            },
        )
        for run in result.runs
    ]
    _print_table(columns, rows)


def _print_weighted_runs(
    problem: BiobjectiveProblem, result: MultiobjectiveSolution
) -> None:
    print(f"\nTabla completa de las {len(result.weighted_runs)} corridas")
    columns = [
        "run",
        "alpha1",
        "alpha2",
        "estado",
        *problem.variables,
        "Z1",
        "Z2",
        "N1",
        "N2",
        "W",
    ]
    rows = [
        _run_row(
            run,
            problem.variables,
            prefix={
                "run": str(run["run_index"]),
                "alpha1": _number(run["alpha1"]),
                "alpha2": _number(run["alpha2"]),
                "estado": run["status"],
            },
            suffix={
                "Z1": _number(run["Z1"]),
                "Z2": _number(run["Z2"]),
                "N1": _number(run["N1"]),
                "N2": _number(run["N2"]),
                "W": _number(run["W"]),
            },
        )
        for run in result.weighted_runs
    ]
    _print_table(columns, rows)


def _variables_text(variables: list[str], values: dict[str, float]) -> str:
    return ", ".join(f"{name}={_number(values[name])}" for name in variables)


def _print_epsilon_unique(
    problem: BiobjectiveProblem, result: EpsilonConstraintSolution
) -> None:
    print(f"\nSoluciones únicas ({len(result.unique_solutions)})")
    for solution in result.unique_solutions:
        print(
            f"  {solution['id']}: t={solution['run_indices']}; "
            f"repeticiones={solution['count']}; Z1={_number(solution['Z1'])}; "
            f"Z2={_number(solution['Z2'])}; {solution['pareto_status']}"
        )
        print(f"    x = {_variables_text(problem.variables, solution['x'])}")

    print("\nClasificación Pareto")
    for solution_id, classification in result.pareto_classification.items():
        print(
            f"  {solution_id}: Z1={_number(classification['Z1'])}; "
            f"Z2={_number(classification['Z2'])} -> {classification['status']}"
        )


def _print_weighted_unique(
    problem: BiobjectiveProblem, result: MultiobjectiveSolution
) -> None:
    print(f"\nSoluciones únicas ({len(result.unique_solutions)})")
    for solution in result.unique_solutions:
        weights = ", ".join(
            f"({_compact_number(item['alpha1'])},{_compact_number(item['alpha2'])})"
            for item in solution["generated_by_weights"]
        )
        print(
            f"  {solution['id']}: pesos=[{weights}]; repeticiones={solution['count']}; "
            f"Z1={_number(solution['Z1'])}; Z2={_number(solution['Z2'])}; "
            f"{solution['pareto_status']}"
        )
        print(f"    x = {_variables_text(problem.variables, solution['x'])}")

    print("\nClasificación Pareto")
    for solution_id, classification in result.pareto_classification.items():
        print(
            f"  {solution_id}: Z1={_number(classification['Z1'])}; "
            f"Z2={_number(classification['Z2'])} -> {classification['status']}"
        )


def _solve_epsilon(problem: BiobjectiveProblem, primary: int, r: int) -> int:
    result = solve_biobjective_epsilon_constraint(
        problem,
        primary_objective=primary,
        r=r,
    )
    if not result.payoff_matrix:
        for note in result.notes:
            print(f"ERROR: {note}", file=sys.stderr)
        return 1

    _print_payoff_matrix(result.payoff_matrix)
    constrained = result.constrained_objective
    range_prefix = f"Z{constrained}"
    print(f"\nObjetivo principal: Z{primary}")
    print(f"Objetivo restringido: Z{constrained}")
    print(f"{range_prefix}_min = {_number(result.objective_ranges[f'{range_prefix}_min'])}")
    print(f"{range_prefix}_max = {_number(result.objective_ranges[f'{range_prefix}_max'])}")
    print(f"r = {result.r}; corridas = {result.r + 1}")
    print("Fórmula: E_k,t = Zk_min + (t/r)(Zk_max - Zk_min)")
    levels = ", ".join(_compact_number(level) for level in result.epsilon_levels)
    print(f"Niveles E{constrained} = [{levels}]")
    _print_epsilon_runs(problem, result)
    _print_epsilon_unique(problem, result)
    for note in result.notes:
        print(f"NOTA: {note}")
    return 0 if result.runs else 1


def _solve_weighted(problem: BiobjectiveProblem, num_weights: int) -> int:
    result = solve_biobjective_weighted(problem, num_combinations=num_weights)
    if not result.payoff_matrix:
        for note in result.notes:
            print(f"ERROR: {note}", file=sys.stderr)
        return 1

    _print_payoff_matrix(result.payoff_matrix)
    print("\nRangos de normalización")
    for key in ("Z1_min", "Z1_max", "Z1_range", "Z2_min", "Z2_max", "Z2_range"):
        print(f"  {key} = {_number(result.normalization_ranges[key])}")
    print(f"Número de ponderaciones: {num_weights}")
    _print_weighted_runs(problem, result)
    _print_weighted_unique(problem, result)
    for note in result.notes:
        print(f"NOTA: {note}")
    return 0 if result.weighted_runs else 1


def run(args: argparse.Namespace) -> int:
    try:
        model_name, _, problem = load_biobjective_model(args.model_file)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR al cargar '{args.model_file}': {exc}", file=sys.stderr)
        return 2

    _print_model_header(args.model_file, model_name, problem, args.method)
    try:
        if args.method == "epsilon":
            return _solve_epsilon(problem, primary=args.primary, r=args.r)
        return _solve_weighted(problem, num_weights=args.num_weights)
    except Exception as exc:
        print(f"ERROR durante la resolución: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
