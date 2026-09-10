"""Ejecutor interactivo y reproducible de modelos multiobjetivo JSON."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


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
    MultiobjectiveEpsilonSolution,
    MultiobjectiveProblem,
    MultiobjectiveSolution,
    Sense,
    build_biobjective_problem_from_state,
    build_multiobjective_problem_from_state,
    deserialize_model,
    save_multiobjective_projection_plots,
    save_pareto_plot,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
    solve_multiobjective_epsilon_constraint,
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
            "Carga un modelo multiobjetivo JSON. Sin --method inicia el modo "
            "interactivo; con --method realiza una ejecución reproducible."
        )
    )
    parser.add_argument("model_file", type=Path, help="ruta del modelo JSON")
    parser.add_argument(
        "--method",
        choices=("epsilon", "weighted"),
        help="método multiobjetivo",
    )
    parser.add_argument(
        "--primary",
        type=_integer_at_least(1),
        default=1,
        help="índice del objetivo principal para epsilon (predeterminado: 1)",
    )
    parser.add_argument(
        "--r-objective",
        action="append",
        default=[],
        metavar="K=R",
        help="sobrescribe r para ZK, por ejemplo 2=4 (opción repetible)",
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
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="no generar el gráfico PNG ni las proyecciones de resultados",
    )
    return parser


def load_biobjective_model(
    model_file: Path,
) -> tuple[str, dict[str, Any], BiobjectiveProblem]:
    """Carga y construye un problema biobjetivo de los esquemas 1.0 o 1.1."""

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


def load_multiobjective_model(
    model_file: Path,
) -> tuple[str, dict[str, Any], MultiobjectiveProblem]:
    """Carga un problema de dos o más objetivos de los esquemas compatibles."""

    loaded = deserialize_model(model_file.read_text(encoding="utf-8"))
    if loaded["problem_type"] not in ("Biobjetivo", "Multiobjetivo"):
        raise ValueError(
            "El ejecutor requiere un problema Biobjetivo o Multiobjetivo; "
            f"se recibió '{loaded['problem_type']}'."
        )
    objectives = loaded.get("objectives")
    if not isinstance(objectives, list):
        raise ValueError("El modelo cargado no contiene una lista de objetivos.")
    problem = build_multiobjective_problem_from_state(
        var_names=loaded["var_names"],
        objectives=objectives,
        canonical_constraints=loaded["constraints_data"],
    )
    return loaded["metadata"]["name"], loaded, problem


def _as_biobjective(problem: MultiobjectiveProblem) -> BiobjectiveProblem:
    if len(problem.objectives) != 2:
        raise ValueError(
            "El método de ponderaciones implementado actualmente admite "
            "exactamente dos objetivos. Para este modelo utilice el método "
            "de las restricciones."
        )
    return BiobjectiveProblem(
        variables=list(problem.variables),
        objective1=problem.objectives[0],
        objective2=problem.objectives[1],
        constraints=list(problem.constraints),
    )


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


def _objective_expression_general(
    problem: MultiobjectiveProblem, index: int
) -> str:
    objective = problem.objectives[index - 1]
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


def _print_objectives(problem: MultiobjectiveProblem) -> None:
    print("\nFunciones objetivo encontradas:\n")
    for index, objective in enumerate(problem.objectives, start=1):
        descriptive = (
            "" if objective.name == f"Z{index}" else f" ({objective.name})"
        )
        print(
            f"[{index}] Z{index}{descriptive} = "
            f"{_objective_expression_general(problem, index)}"
        )
        print(f"    Sentido: {_sense_label(objective.sense)}\n")


def _print_interactive_header(
    model_name: str, problem: MultiobjectiveProblem
) -> None:
    print("=" * 52)
    print("SOLVER MULTIOBJETIVO")
    print("=" * 52)
    print(f"\nModelo: {model_name}")
    print(f"Variables: {len(problem.variables)}")
    print(f"Restricciones originales: {len(problem.constraints)}")
    print(f"Objetivos: {len(problem.objectives)}")
    _print_objectives(problem)


def _prompt_choice(
    prompt: str,
    valid: set[int],
    input_func: Callable[[str], str],
    error_message: str,
) -> int:
    while True:
        try:
            raw = input_func(prompt).strip()
            value = int(raw)
        except (ValueError, EOFError):
            print(error_message)
            continue
        if value in valid:
            return value
        print(error_message)


def _prompt_integer(
    prompt: str,
    minimum: int,
    input_func: Callable[[str], str],
) -> int:
    while True:
        try:
            value = int(input_func(prompt).strip())
        except (ValueError, EOFError):
            print(f"Valor no válido. Ingrese un entero mayor o igual que {minimum}.")
            continue
        if value >= minimum:
            return value
        print(f"Valor no válido. Ingrese un entero mayor o igual que {minimum}.")


def _prompt_confirmation(input_func: Callable[[str], str]) -> bool:
    while True:
        try:
            answer = input_func("¿Desea continuar? [S/n]: ").strip().lower()
        except EOFError:
            return False
        if answer in ("", "s"):
            return True
        if answer == "n":
            return False
        print("Respuesta no válida. Escriba S o N.")


def _parse_r_overrides(values: list[str]) -> dict[int, int]:
    overrides: dict[int, int] = {}
    for raw in values:
        parts = raw.split("=", maxsplit=1)
        if len(parts) != 2:
            raise ValueError(
                f"--r-objective '{raw}' debe usar el formato K=R, por ejemplo 2=4."
            )
        try:
            objective_index = int(parts[0])
            r_value = int(parts[1])
        except ValueError as exc:
            raise ValueError(
                f"--r-objective '{raw}' requiere dos enteros K=R."
            ) from exc
        if objective_index < 1 or r_value < 1:
            raise ValueError(
                f"--r-objective '{raw}' requiere K >= 1 y R >= 1."
            )
        if objective_index in overrides:
            previous = overrides[objective_index]
            if previous != r_value:
                raise ValueError(
                    f"Valores contradictorios para Z{objective_index}: "
                    f"r={previous} y r={r_value}."
                )
            raise ValueError(f"--r-objective para Z{objective_index} está duplicado.")
        overrides[objective_index] = r_value
    return overrides


def _r_configuration(
    objective_count: int,
    primary: int,
    default_r: int,
    overrides: dict[int, int],
) -> dict[int, int]:
    if not 1 <= primary <= objective_count:
        raise ValueError(
            f"El objetivo principal debe estar entre 1 y {objective_count}."
        )
    if primary in overrides:
        raise ValueError(f"No se puede asignar r al objetivo principal Z{primary}.")
    unknown = sorted(index for index in overrides if index > objective_count)
    if unknown:
        raise ValueError(
            "Objetivo inexistente en --r-objective: "
            + ", ".join(f"Z{index}" for index in unknown)
            + "."
        )
    return {
        index: overrides.get(index, default_r)
        for index in range(1, objective_count + 1)
        if index != primary
    }


def _print_configuration(
    problem: MultiobjectiveProblem,
    method: str,
    primary: int,
    r_by_objective: dict[int, int],
    num_weights: int,
) -> int:
    print("-" * 52)
    print("CONFIGURACIÓN")
    print("-" * 52)
    if method == "weighted":
        print("\nMétodo: Método de ponderaciones")
        print(f"Número de ponderaciones: {num_weights}")
        print(f"Número total de corridas: {num_weights}\n")
        return num_weights

    print("\nMétodo: Método de las restricciones")
    print(f"Objetivo principal: Z{primary}")
    print("\nObjetivos restringidos:\n")
    factors: list[str] = []
    for index, r_value in r_by_objective.items():
        objective = problem.objectives[index - 1]
        print(f"Z{index}")
        print(f"    sentido: {_sense_label(objective.sense).replace('IMIZAR', '')}")
        print(f"    r = {r_value}")
        print(f"    niveles = {r_value + 1}\n")
        factors.append(str(r_value + 1))
    total = math.prod(value + 1 for value in r_by_objective.values())
    print("Número total de corridas:")
    print(f"    {' × '.join(factors)} = {total}\n")
    if total > 500:
        print("ADVERTENCIA:")
        print(f"Esta configuración requiere {total} resoluciones del modelo.")
        print("El proceso puede tardar considerablemente.\n")
    return total


def _interactive_configuration(
    model_name: str,
    problem: MultiobjectiveProblem,
    input_func: Callable[[str], str],
) -> dict[str, Any] | None:
    _print_interactive_header(model_name, problem)
    objective_count = len(problem.objectives)
    if objective_count > 2:
        print(
            "Actualmente los modelos con más de dos objetivos se resuelven\n"
            "mediante el método de las restricciones.\n"
        )
        method = "epsilon"
    else:
        print("Seleccione el método:\n")
        print("[1] Método de ponderaciones")
        print("[2] Método de las restricciones\n")
        selection = _prompt_choice(
            "Opción: ",
            {1, 2},
            input_func,
            "Opción no válida.\nSeleccione 1 o 2.",
        )
        method = "weighted" if selection == 1 else "epsilon"

    if method == "weighted":
        print("\n¿Cuántas combinaciones de pesos desea utilizar?\n")
        num_weights = _prompt_integer(
            "Número de ponderaciones: ", 2, input_func
        )
        primary = 1
        r_by_objective: dict[int, int] = {}
    else:
        print("\nOBJETIVO PRINCIPAL\n")
        print("Es la función objetivo que continuará optimizándose.")
        print(
            "Las demás funciones objetivo se convertirán en restricciones\n"
            "mediante niveles E."
        )
        _print_objectives(problem)
        primary = _prompt_choice(
            "Seleccione el objetivo principal: ",
            set(range(1, objective_count + 1)),
            input_func,
            f"Objetivo no válido. Seleccione un número entre 1 y {objective_count}.",
        )
        r_by_objective = {}
        for index in range(1, objective_count + 1):
            if index == primary:
                continue
            print(f"\nIngrese el valor de r para Z{index}.")
            print("r representa el número de intervalos.")
            print("Con r = 6 se generan 7 niveles E.\n")
            r_by_objective[index] = _prompt_integer("r: ", 1, input_func)
        num_weights = 6

    _print_configuration(
        problem, method, primary, r_by_objective, num_weights
    )
    if not _prompt_confirmation(input_func):
        print("Ejecución cancelada. No se llamó al solver.")
        return None
    return {
        "method": method,
        "primary": primary,
        "r_by_objective": r_by_objective,
        "num_weights": num_weights,
    }


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


def _print_expansion_summary(loaded: dict[str, Any]) -> None:
    statistics = loaded.get("expansion_statistics")
    if not statistics:
        print("Esquema JSON: 1.0 explícito")
        return
    print("Esquema JSON: 1.1 unificado")
    print(
        "Expansión: "
        f"{statistics['explicit_variables']} variables explícitas + "
        f"{statistics['generated_variables']} indexadas; "
        f"{statistics['explicit_constraints']} restricciones explícitas + "
        f"{statistics['generated_constraints']} generadas"
    )


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


def _print_general_payoff_matrix(
    problem: MultiobjectiveProblem, result: MultiobjectiveEpsilonSolution
) -> None:
    labels = [f"Z{index}" for index in range(1, len(problem.objectives) + 1)]
    columns = ["ancla", "estado", *labels]
    rows = []
    for index in range(1, len(problem.objectives) + 1):
        anchor = result.payoff_matrix[f"opt_Z{index}"]
        rows.append(
            {
                "ancla": f"opt_Z{index}",
                "estado": anchor["status"],
                **{label: _number(anchor[label]) for label in labels},
            }
        )
    print("\nMatriz de pagos")
    _print_table(columns, rows)


def _objective_values_text(values: Mapping[str, float] | None) -> str:
    if values is None:
        return "-"
    return "; ".join(
        f"{label}={_number(value)}" for label, value in values.items()
    )


def _print_general_epsilon_result(
    problem: MultiobjectiveProblem, result: MultiobjectiveEpsilonSolution
) -> None:
    _print_general_payoff_matrix(problem, result)
    print(f"\nObjetivo principal: Z{result.primary_objective}")
    print("Objetivos restringidos:")
    for index in result.constrained_objectives:
        label = f"Z{index}"
        print(
            f"  {label}: r={result.r_by_objective[index]}; "
            f"{label}_min={_number(result.objective_ranges[label + '_min'])}; "
            f"{label}_max={_number(result.objective_ranges[label + '_max'])}"
        )
        levels = ", ".join(
            _compact_number(level) for level in result.epsilon_levels[label]
        )
        print(f"    niveles E = [{levels}]")
    print(
        "Fórmula: E_k,t = Zk_min + (t/r_k)(Zk_max - Zk_min), "
        "t=0,...,r_k"
    )
    print(f"Número total de corridas: {result.total_runs}")
    print(f"\nCorridas ({len(result.runs)})")
    for run in result.runs:
        epsilon_text = ", ".join(
            f"{label}[t={run['epsilon_indices'][label]}]="
            f"{_number(level)}"
            for label, level in run["epsilon_levels"].items()
        )
        print(
            f"  Corrida {run['run_index'] + 1}: {epsilon_text}; "
            f"estado={run['status']}; tiempo_s={_number(run['execution_time_sec'])}"
        )
        print(f"    objetivos: {_objective_values_text(run['objective_values'])}")
        if run["x"] is not None:
            print(f"    x = {_variables_text(problem.variables, run['x'])}")

    print(f"\nSoluciones únicas ({len(result.unique_solutions)})")
    for solution in result.unique_solutions:
        print(
            f"  {solution['id']}: corridas={solution['run_indices']}; "
            f"repeticiones={solution['count']}; "
            f"{_objective_values_text(solution['objective_values'])}; "
            f"{solution['pareto_status']}"
        )
        print(f"    x = {_variables_text(problem.variables, solution['x'])}")

    print("\nClasificación Pareto N-dimensional")
    print("Soluciones no dominadas obtenidas por el barrido epsilon:")
    for solution_id, classification in result.pareto_classification.items():
        print(
            f"  {solution_id}: "
            f"{_objective_values_text(classification['objective_values'])} "
            f"-> {classification['status']}"
        )
    for note in result.notes:
        print(f"NOTA: {note}")


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


def _solve_epsilon(
    problem: BiobjectiveProblem, primary: int, r: int
) -> tuple[int, EpsilonConstraintSolution]:
    result = solve_biobjective_epsilon_constraint(
        problem,
        primary_objective=primary,
        r=r,
    )
    if not result.payoff_matrix:
        for note in result.notes:
            print(f"ERROR: {note}", file=sys.stderr)
        return 1, result

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
    return (0 if result.runs else 1), result


def _solve_weighted(
    problem: BiobjectiveProblem, num_weights: int
) -> tuple[int, MultiobjectiveSolution]:
    result = solve_biobjective_weighted(problem, num_combinations=num_weights)
    if not result.payoff_matrix:
        for note in result.notes:
            print(f"ERROR: {note}", file=sys.stderr)
        return 1, result

    _print_payoff_matrix(result.payoff_matrix)
    print("\nRangos de normalización")
    for key in ("Z1_min", "Z1_max", "Z1_range", "Z2_min", "Z2_max", "Z2_range"):
        print(f"  {key} = {_number(result.normalization_ranges[key])}")
    print(f"Número de ponderaciones: {num_weights}")
    _print_weighted_runs(problem, result)
    _print_weighted_unique(problem, result)
    for note in result.notes:
        print(f"NOTA: {note}")
    return (0 if result.weighted_runs else 1), result


def _solve_general_epsilon(
    problem: MultiobjectiveProblem,
    primary: int,
    r_by_objective: dict[int, int],
) -> tuple[int, MultiobjectiveEpsilonSolution]:
    result = solve_multiobjective_epsilon_constraint(
        problem,
        primary_objective=primary,
        r_by_objective=r_by_objective,
    )
    if not result.payoff_matrix:
        for note in result.notes:
            print(f"ERROR: {note}", file=sys.stderr)
        return 1, result
    _print_general_epsilon_result(problem, result)
    return (0 if result.runs else 1), result


def _print_general_model_header(
    model_file: Path,
    model_name: str,
    problem: MultiobjectiveProblem,
    method: str,
) -> None:
    print("=" * 110)
    print("EJECUTOR GENERAL DE MODELOS MULTIOBJETIVO")
    print("=" * 110)
    print(f"Archivo: {model_file}")
    print(f"Nombre del modelo: {model_name}")
    print(f"Variables: {len(problem.variables)}")
    print(f"Restricciones originales: {len(problem.constraints)}")
    print(f"Objetivos: {len(problem.objectives)}")
    _print_objectives(problem)
    print("Método: MÉTODO DE LAS RESTRICCIONES (ε-CONSTRAINT)")


def _plot_path(model_file: Path, method: str) -> Path:
    return PROJECT_ROOT / "results" / f"{model_file.stem}_{method}_pareto.png"


def run(
    args: argparse.Namespace,
    input_func: Callable[[str], str] | None = None,
    stdin_is_tty: bool | None = None,
) -> int:
    try:
        model_name, loaded, problem = load_multiobjective_model(args.model_file)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR al cargar '{args.model_file}': {exc}", file=sys.stderr)
        return 2

    interactive = args.method is None
    if interactive:
        is_tty = sys.stdin.isatty() if stdin_is_tty is None else stdin_is_tty
        if not is_tty:
            print(
                "ERROR: --method es obligatorio en ejecución no interactiva.",
                file=sys.stderr,
            )
            return 2
        configuration = _interactive_configuration(
            model_name, problem, input_func or input
        )
        if configuration is None:
            return 0
        method = configuration["method"]
        primary = configuration["primary"]
        r_by_objective = configuration["r_by_objective"]
        num_weights = configuration["num_weights"]
        print("\nIniciando resolución...\n")
    else:
        method = args.method
        primary = args.primary
        num_weights = args.num_weights
        try:
            overrides = _parse_r_overrides(args.r_objective)
            if method == "weighted" and overrides:
                raise ValueError("--r-objective solo se aplica al método epsilon.")
            r_by_objective = _r_configuration(
                len(problem.objectives), primary, args.r, overrides
            ) if method == "epsilon" else {}
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    if method == "weighted" and len(problem.objectives) != 2:
        print(
            "ERROR: El método de ponderaciones implementado actualmente admite\n"
            "exactamente dos objetivos.\n\n"
            "Para este modelo utilice el método de las restricciones.",
            file=sys.stderr,
        )
        return 2

    biobjective = _as_biobjective(problem) if len(problem.objectives) == 2 else None
    if not interactive:
        if biobjective is not None:
            _print_model_header(args.model_file, model_name, biobjective, method)
        else:
            _print_general_model_header(args.model_file, model_name, problem, method)
    _print_expansion_summary(loaded)

    try:
        if method == "weighted":
            exit_code, result = _solve_weighted(
                biobjective, num_weights=num_weights
            )
        elif biobjective is not None:
            constrained = 2 if primary == 1 else 1
            exit_code, result = _solve_epsilon(
                biobjective, primary=primary, r=r_by_objective[constrained]
            )
        else:
            exit_code, result = _solve_general_epsilon(
                problem, primary=primary, r_by_objective=r_by_objective
            )
        if exit_code != 0 or args.no_plot:
            return exit_code
        if biobjective is not None:
            output, points = save_pareto_plot(
                problem=biobjective,
                result=result,
                method=method,
                model_name=model_name,
                output_path=_plot_path(args.model_file, method),
            )
            print(f"\nGráfico de Pareto guardado en:\n{output}")
            print(f"Puntos representados: {len(points)}")
        else:
            projections = save_multiobjective_projection_plots(
                problem=problem,
                result=result,
                model_name=model_name,
                output_directory=PROJECT_ROOT / "results",
                model_stem=args.model_file.stem,
            )
            print("\nProyecciones de soluciones multiobjetivo guardadas en:")
            for output, points in projections:
                print(f"  {output} ({len(points)} puntos)")
        return exit_code
    except Exception as exc:
        print(
            f"ERROR durante la resolución: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def main(
    argv: Sequence[str] | None = None,
    input_func: Callable[[str], str] | None = None,
    stdin_is_tty: bool | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    return run(args, input_func=input_func, stdin_is_tty=stdin_is_tty)


if __name__ == "__main__":
    raise SystemExit(main())
