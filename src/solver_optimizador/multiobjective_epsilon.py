"""Método epsilon-constraint exacto para LP con dos o más objetivos."""

from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from .epsilon_constraint import generate_epsilon_levels
from .lp_models import (
    LPProblem,
    LinearConstraint,
    MultiobjectiveProblem,
    Operator,
    Sense,
    SolverStatus,
    is_finite_number,
)
from .lp_solver import solve_lp


@dataclass
class MultiobjectiveEpsilonSolution:
    """Resultado del preprocesamiento y barrido epsilon N-dimensional."""

    individual_optima: dict[str, Any]
    payoff_matrix: dict[str, Any]
    objective_ranges: dict[str, float]
    primary_objective: int
    constrained_objectives: list[int]
    r_by_objective: dict[int, int]
    epsilon_levels: dict[str, list[float]]
    total_runs: int
    runs: list[dict[str, Any]]
    unique_solutions: list[dict[str, Any]]
    pareto_classification: dict[str, Any]
    nondominated_solutions: list[dict[str, Any]]
    timing: dict[str, float]
    notes: list[str] = field(default_factory=list)


def _objective_values(
    problem: MultiobjectiveProblem, x_values: Mapping[str, float]
) -> dict[str, float]:
    vector = dict(x_values)
    return {
        f"Z{index}": objective.evaluate(vector)
        for index, objective in enumerate(problem.objectives, start=1)
    }


def _validate_configuration(
    problem: MultiobjectiveProblem,
    primary_objective: int,
    r_by_objective: Mapping[int, int],
    tol: float,
) -> tuple[list[int], dict[int, int]]:
    problem.validate()
    objective_count = len(problem.objectives)
    if (
        isinstance(primary_objective, bool)
        or not isinstance(primary_objective, int)
        or not 1 <= primary_objective <= objective_count
    ):
        raise ValueError(
            f"primary_objective debe estar entre 1 y {objective_count}."
        )
    if not is_finite_number(tol) or tol <= 0:
        raise ValueError("tol debe ser un número finito mayor que cero.")
    if not isinstance(r_by_objective, Mapping):
        raise ValueError("r_by_objective debe ser un mapeo objetivo -> r.")

    constrained = [
        index for index in range(1, objective_count + 1) if index != primary_objective
    ]
    normalized: dict[int, int] = {}
    for raw_index, value in r_by_objective.items():
        if isinstance(raw_index, bool) or not isinstance(raw_index, int):
            raise ValueError("Los índices de r_by_objective deben ser enteros.")
        if raw_index not in constrained:
            if raw_index == primary_objective:
                raise ValueError(
                    f"No se puede asignar r al objetivo principal Z{raw_index}."
                )
            raise ValueError(f"El objetivo Z{raw_index} no existe o no es restringido.")
        generate_epsilon_levels(0.0, 0.0, value)
        normalized[raw_index] = value
    missing = [index for index in constrained if index not in normalized]
    if missing:
        labels = ", ".join(f"Z{index}" for index in missing)
        raise ValueError(f"Falta especificar r para: {labels}.")
    return constrained, normalized


def _lexicographic_anchor(
    problem: MultiobjectiveProblem,
    primary_index: int,
    tol: float,
) -> dict[str, Any]:
    """Optimiza un objetivo y desempata con los restantes en orden de índice."""

    started = time.perf_counter()
    order = [primary_index] + [
        index
        for index in range(1, len(problem.objectives) + 1)
        if index != primary_index
    ]
    fixed_constraints: list[LinearConstraint] = []
    stages: list[dict[str, Any]] = []
    selected_x: dict[str, float] | None = None
    primary_optimum: float | None = None
    final_status = SolverStatus.ERROR
    error_message: str | None = None

    for stage_number, objective_index in enumerate(order, start=1):
        objective = problem.objectives[objective_index - 1]
        result = solve_lp(
            LPProblem(
                variables=list(problem.variables),
                objective=objective,
                constraints=[*problem.constraints, *fixed_constraints],
            ),
            tol=tol,
        )
        stages.append(
            {
                "stage": stage_number,
                "objective": f"Z{objective_index}",
                "status": result.status.value,
                "value": result.objective_value,
            }
        )
        final_status = result.status
        if result.status != SolverStatus.OPTIMAL:
            error_message = result.status_message
            selected_x = None
            break

        selected_x = dict(result.variable_values)
        optimum = objective.evaluate(selected_x)
        if stage_number == 1:
            primary_optimum = optimum
        fixed_constraints.append(
            LinearConstraint(
                name=f"_payoff_Z{primary_index}_fix_Z{objective_index}",
                coefficients=dict(objective.coefficients),
                operator=Operator.EQ,
                rhs=optimum,
            )
        )

    values = _objective_values(problem, selected_x) if selected_x is not None else None
    return {
        "status": final_status,
        "primary_optimal_value": primary_optimum,
        "x": selected_x,
        "objective_values": values,
        "selection_metadata": {
            "purpose": "payoff_matrix_anchor",
            "rule": "lexicographic_by_objective_index_with_previous_values_fixed",
            "optimization_order": [f"Z{index}" for index in order],
            "stages": stages,
            "completed": len(stages) == len(order)
            and final_status == SolverStatus.OPTIMAL,
            "establishes_uniqueness": False,
        },
        "execution_time_sec": round(time.perf_counter() - started, 6),
        "error_message": error_message,
    }


def _payoff_preprocessing(
    problem: MultiobjectiveProblem,
    tol: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float], list[str]]:
    notes: list[str] = []
    anchors = {
        f"Z{index}_opt": _lexicographic_anchor(problem, index, tol)
        for index in range(1, len(problem.objectives) + 1)
    }
    failed = [
        name.removesuffix("_opt")
        for name, anchor in anchors.items()
        if anchor["status"] != SolverStatus.OPTIMAL or anchor["x"] is None
    ]
    if failed:
        notes.append(
            "No se pudo construir la matriz de pagos; fallaron las anclas de: "
            + ", ".join(failed)
            + "."
        )
        return anchors, {}, {}, notes

    payoff_matrix: dict[str, Any] = {}
    for row_index in range(1, len(problem.objectives) + 1):
        anchor = anchors[f"Z{row_index}_opt"]
        values = dict(anchor["objective_values"])
        payoff_matrix[f"opt_Z{row_index}"] = {
            "x": dict(anchor["x"]),
            "objective_values": values,
            **values,
            "primary_optimal": anchor["primary_optimal_value"],
            "status": anchor["status"].value,
            "selection_metadata": anchor["selection_metadata"],
        }

    ranges: dict[str, float] = {}
    for objective_index in range(1, len(problem.objectives) + 1):
        label = f"Z{objective_index}"
        column = [row[label] for row in payoff_matrix.values()]
        ranges[f"{label}_min"] = min(column)
        ranges[f"{label}_max"] = max(column)
        ranges[f"{label}_range"] = max(column) - min(column)
    notes.append(
        "Los límites epsilon son extremos observados en la matriz de pagos; "
        "no se presentan como un nadir exacto."
    )
    notes.append(
        "Las anclas usan desempate lexicográfico determinista por índice, "
        "respetando el sentido de cada objetivo."
    )
    return anchors, payoff_matrix, ranges, notes


def _solve_run(
    problem: MultiobjectiveProblem,
    primary_objective: int,
    constrained_objectives: list[int],
    run_index: int,
    epsilon_indices: tuple[int, ...],
    epsilon_values: tuple[float, ...],
    tol: float,
) -> dict[str, Any]:
    constraints = list(problem.constraints)
    operators: dict[str, str] = {}
    indices = {
        f"Z{objective_index}": epsilon_index
        for objective_index, epsilon_index in zip(
            constrained_objectives, epsilon_indices
        )
    }
    levels = {
        f"Z{objective_index}": epsilon
        for objective_index, epsilon in zip(
            constrained_objectives, epsilon_values
        )
    }
    for objective_index, epsilon_index, epsilon in zip(
        constrained_objectives, epsilon_indices, epsilon_values
    ):
        objective = problem.objectives[objective_index - 1]
        operator = Operator.GE if objective.sense == Sense.MAXIMIZE else Operator.LE
        operators[f"Z{objective_index}"] = operator.value
        constraints.append(
            LinearConstraint(
                name=f"_epsilon_Z{objective_index}_t_{epsilon_index}",
                coefficients=dict(objective.coefficients),
                operator=operator,
                rhs=epsilon,
            )
        )

    result = solve_lp(
        LPProblem(
            variables=list(problem.variables),
            objective=problem.objectives[primary_objective - 1],
            constraints=constraints,
        ),
        tol=tol,
    )
    run: dict[str, Any] = {
        "run_index": run_index,
        "primary_objective": primary_objective,
        "epsilon_indices": indices,
        "epsilon_levels": levels,
        "constraint_operators": operators,
        "status": result.status.value,
        "status_message": result.status_message,
        "raw_termination": result.raw_termination,
        "x": None,
        "objective_values": None,
        "execution_time_sec": result.execution_time_sec,
    }
    if result.status == SolverStatus.OPTIMAL:
        x_values = dict(result.variable_values)
        objective_values = _objective_values(problem, x_values)
        run["x"] = x_values
        run["objective_values"] = objective_values
        if len(problem.objectives) == 2:
            run["Z1"] = objective_values["Z1"]
            run["Z2"] = objective_values["Z2"]
    return run


def _same_solution(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    variables: list[str],
    objective_labels: list[str],
    tol: float,
) -> bool:
    return all(
        abs(first["x"][variable] - second["x"][variable]) <= tol
        for variable in variables
    ) and all(
        abs(
            first["objective_values"][label]
            - second["objective_values"][label]
        )
        <= tol
        for label in objective_labels
    )


def _deduplicate_runs(
    problem: MultiobjectiveProblem,
    runs: list[dict[str, Any]],
    tol: float,
) -> list[dict[str, Any]]:
    labels = [f"Z{index}" for index in range(1, len(problem.objectives) + 1)]
    unique: list[dict[str, Any]] = []
    for run in runs:
        if run["status"] != SolverStatus.OPTIMAL.value or run["x"] is None:
            continue
        matched = next(
            (
                solution
                for solution in unique
                if _same_solution(run, solution, problem.variables, labels, tol)
            ),
            None,
        )
        if matched is not None:
            matched["run_indices"].append(run["run_index"])
            matched["epsilon_indices"].append(dict(run["epsilon_indices"]))
            matched["epsilon_levels"].append(dict(run["epsilon_levels"]))
            matched["count"] += 1
            continue
        solution: dict[str, Any] = {
            "id": f"S{len(unique) + 1}",
            "x": dict(run["x"]),
            "objective_values": dict(run["objective_values"]),
            "count": 1,
            "run_indices": [run["run_index"]],
            "epsilon_indices": [dict(run["epsilon_indices"])],
            "epsilon_levels": [dict(run["epsilon_levels"])],
            "pareto_status": "No evaluada",
        }
        if len(problem.objectives) == 2:
            solution["Z1"] = run["objective_values"]["Z1"]
            solution["Z2"] = run["objective_values"]["Z2"]
        unique.append(solution)
    return unique


def _is_no_worse(
    candidate: float, reference: float, sense: Sense, tol: float
) -> bool:
    if sense == Sense.MAXIMIZE:
        return candidate >= reference - tol
    return candidate <= reference + tol


def _is_strictly_better(
    candidate: float, reference: float, sense: Sense, tol: float
) -> bool:
    if sense == Sense.MAXIMIZE:
        return candidate > reference + tol
    return candidate < reference - tol


def classify_pareto_multiobjective(
    problem: MultiobjectiveProblem,
    unique_solutions: list[dict[str, Any]],
    tol: float = 1e-6,
) -> dict[str, Any]:
    """Clasifica dominancia usando todos los objetivos y sus sentidos."""

    labels = [f"Z{index}" for index in range(1, len(problem.objectives) + 1)]
    for solution in unique_solutions:
        solution["pareto_status"] = "No dominada"
        for candidate in unique_solutions:
            if candidate is solution:
                continue
            no_worse = all(
                _is_no_worse(
                    candidate["objective_values"][label],
                    solution["objective_values"][label],
                    problem.objectives[index].sense,
                    tol,
                )
                for index, label in enumerate(labels)
            )
            strictly_better = any(
                _is_strictly_better(
                    candidate["objective_values"][label],
                    solution["objective_values"][label],
                    problem.objectives[index].sense,
                    tol,
                )
                for index, label in enumerate(labels)
            )
            if no_worse and strictly_better:
                solution["pareto_status"] = f"Dominada (por {candidate['id']})"
                break

    return {
        solution["id"]: {
            "x": solution["x"],
            "objective_values": solution["objective_values"],
            "status": solution["pareto_status"],
            "run_indices": solution["run_indices"],
            "epsilon_indices": solution["epsilon_indices"],
            "epsilon_levels": solution["epsilon_levels"],
        }
        for solution in unique_solutions
    }


def solve_multiobjective_epsilon_constraint(
    problem: MultiobjectiveProblem,
    primary_objective: int,
    r_by_objective: Mapping[int, int],
    tol: float = 1e-6,
) -> MultiobjectiveEpsilonSolution:
    """Resuelve el producto cartesiano exacto de los niveles epsilon."""

    constrained, normalized_r = _validate_configuration(
        problem, primary_objective, r_by_objective, tol
    )
    total_runs = math.prod(normalized_r[index] + 1 for index in constrained)
    started = time.perf_counter()
    preprocessing_started = time.perf_counter()
    individual_optima, payoff_matrix, ranges, notes = _payoff_preprocessing(
        problem, tol
    )
    preprocessing_time = time.perf_counter() - preprocessing_started

    if not payoff_matrix:
        return MultiobjectiveEpsilonSolution(
            individual_optima=individual_optima,
            payoff_matrix={},
            objective_ranges={},
            primary_objective=primary_objective,
            constrained_objectives=constrained,
            r_by_objective=normalized_r,
            epsilon_levels={},
            total_runs=total_runs,
            runs=[],
            unique_solutions=[],
            pareto_classification={},
            nondominated_solutions=[],
            timing={
                "preprocessing_sec": round(preprocessing_time, 6),
                "sweep_sec": 0.0,
                "total_sec": round(time.perf_counter() - started, 6),
            },
            notes=notes,
        )

    levels = {
        f"Z{index}": generate_epsilon_levels(
            ranges[f"Z{index}_min"],
            ranges[f"Z{index}_max"],
            normalized_r[index],
        )
        for index in constrained
    }
    index_products = itertools.product(
        *(range(normalized_r[index] + 1) for index in constrained)
    )
    sweep_started = time.perf_counter()
    runs: list[dict[str, Any]] = []
    for run_index, epsilon_indices in enumerate(index_products):
        epsilon_values = tuple(
            levels[f"Z{objective_index}"][level_index]
            for objective_index, level_index in zip(
                constrained, epsilon_indices
            )
        )
        runs.append(
            _solve_run(
                problem=problem,
                primary_objective=primary_objective,
                constrained_objectives=constrained,
                run_index=run_index,
                epsilon_indices=epsilon_indices,
                epsilon_values=epsilon_values,
                tol=tol,
            )
        )
    sweep_time = time.perf_counter() - sweep_started

    unique = _deduplicate_runs(problem, runs, tol)
    classification = classify_pareto_multiobjective(problem, unique, tol)
    nondominated = [
        solution
        for solution in unique
        if solution["pareto_status"] == "No dominada"
    ]
    infeasible_count = sum(
        run["status"] == SolverStatus.INFEASIBLE.value for run in runs
    )
    if infeasible_count:
        notes.append(
            f"Se registraron {infeasible_count} corridas infactibles sin "
            "detener el barrido."
        )
    if total_runs > 500:
        notes.append(
            f"El producto cartesiano requirió {total_runs} resoluciones; "
            "el costo computacional crece multiplicativamente."
        )

    return MultiobjectiveEpsilonSolution(
        individual_optima=individual_optima,
        payoff_matrix=payoff_matrix,
        objective_ranges=ranges,
        primary_objective=primary_objective,
        constrained_objectives=constrained,
        r_by_objective=normalized_r,
        epsilon_levels=levels,
        total_runs=total_runs,
        runs=runs,
        unique_solutions=unique,
        pareto_classification=classification,
        nondominated_solutions=nondominated,
        timing={
            "preprocessing_sec": round(preprocessing_time, 6),
            "sweep_sec": round(sweep_time, 6),
            "total_sec": round(time.perf_counter() - started, 6),
        },
        notes=notes,
    )
