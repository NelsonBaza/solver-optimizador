"""Metodo de las restricciones (epsilon-constraint) para LP biobjetivo."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .lp_models import (
    BiobjectiveProblem,
    LPProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
    SolverStatus,
    is_finite_number,
)
from .lp_solver import solve_lp
from .multiobjective import solve_lexicographic_extreme


@dataclass
class EpsilonConstraintSolution:
    """Resultado completo del preprocesamiento y del barrido epsilon."""

    individual_optima: Dict[str, Any]
    payoff_matrix: Dict[str, Any]
    objective_ranges: Dict[str, float]
    primary_objective: int
    constrained_objective: int
    r: int
    epsilon_levels: List[float]
    runs: List[Dict[str, Any]]
    unique_solutions: List[Dict[str, Any]]
    pareto_classification: Dict[str, Any]
    nondominated_solutions: List[Dict[str, Any]]
    timing: Dict[str, float]
    notes: List[str] = field(default_factory=list)


def generate_epsilon_levels(z_min: float, z_max: float, r: int) -> List[float]:
    """Genera ``r + 1`` niveles mediante la formula academica indicada.

    Para cada ``t = 0, ..., r`` se calcula sin redondeo interno::

        E_t = z_min + (t / r) * (z_max - z_min)

    Los extremos se asignan directamente para conservar exactamente los
    valores de entrada en ``t=0`` y ``t=r``.
    """

    if isinstance(r, bool) or not isinstance(r, int) or r < 1:
        raise ValueError("r debe ser un entero mayor o igual que 1.")
    if not is_finite_number(z_min) or not is_finite_number(z_max):
        raise ValueError("z_min y z_max deben ser numeros finitos.")
    if z_min > z_max:
        raise ValueError("z_min no puede ser mayor que z_max.")

    difference = z_max - z_min
    levels = [z_min + (t / r) * difference for t in range(r + 1)]
    levels[0] = z_min
    levels[-1] = z_max
    return levels


def _objective_for_index(
    problem: BiobjectiveProblem, objective_index: int
) -> LinearObjective:
    return problem.objective1 if objective_index == 1 else problem.objective2


def _payoff_preprocessing(
    problem: BiobjectiveProblem, tol: float
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, float], List[str]]:
    """Reutiliza las anclas vigentes y construye matriz y extremos numericos."""

    notes: List[str] = []
    anchor_z1 = solve_lexicographic_extreme(problem, primary_index=1, tol=tol)
    anchor_z2 = solve_lexicographic_extreme(problem, primary_index=2, tol=tol)
    individual_optima = {"Z1_opt": anchor_z1, "Z2_opt": anchor_z2}

    failed_anchors = [
        name
        for name, anchor in (("Z1", anchor_z1), ("Z2", anchor_z2))
        if anchor["status"] != SolverStatus.OPTIMAL or anchor["x"] is None
    ]
    if failed_anchors:
        notes.append(
            "No se pudo construir la matriz de pagos; fallaron los optimos "
            f"individuales de: {', '.join(failed_anchors)}."
        )
        return individual_optima, {}, {}, notes

    payoff_matrix = {
        "opt_Z1": {
            "x": anchor_z1["x"],
            "Z1": anchor_z1["Z1"],
            "Z2": anchor_z1["Z2"],
            "primary_optimal": anchor_z1["primary_optimal_value"],
            "status": anchor_z1["status"].value,
            "selection_metadata": anchor_z1["selection_metadata"],
        },
        "opt_Z2": {
            "x": anchor_z2["x"],
            "Z1": anchor_z2["Z1"],
            "Z2": anchor_z2["Z2"],
            "primary_optimal": anchor_z2["primary_optimal_value"],
            "status": anchor_z2["status"].value,
            "selection_metadata": anchor_z2["selection_metadata"],
        },
    }
    z1_values = [anchor_z1["Z1"], anchor_z2["Z1"]]
    z2_values = [anchor_z1["Z2"], anchor_z2["Z2"]]
    objective_ranges = {
        "Z1_min": min(z1_values),
        "Z1_max": max(z1_values),
        "Z2_min": min(z2_values),
        "Z2_max": max(z2_values),
    }
    objective_ranges["Z1_range"] = (
        objective_ranges["Z1_max"] - objective_ranges["Z1_min"]
    )
    objective_ranges["Z2_range"] = (
        objective_ranges["Z2_max"] - objective_ranges["Z2_min"]
    )
    return individual_optima, payoff_matrix, objective_ranges, notes


def _solve_epsilon_run(
    problem: BiobjectiveProblem,
    primary_objective: int,
    constrained_objective: int,
    t: int,
    epsilon: float,
    tol: float,
) -> Dict[str, Any]:
    primary = _objective_for_index(problem, primary_objective)
    constrained = _objective_for_index(problem, constrained_objective)
    epsilon_operator = (
        Operator.GE if constrained.sense == Sense.MAXIMIZE else Operator.LE
    )
    epsilon_constraint = LinearConstraint(
        name=f"_epsilon_Z{constrained_objective}_t_{t}",
        coefficients=dict(constrained.coefficients),
        operator=epsilon_operator,
        rhs=epsilon,
    )
    run_problem = LPProblem(
        variables=list(problem.variables),
        objective=primary,
        constraints=[*problem.constraints, epsilon_constraint],
    )
    result = solve_lp(run_problem, tol=tol)

    run: Dict[str, Any] = {
        "run_index": t,
        "t": t,
        "primary_objective": primary_objective,
        "constrained_objective": constrained_objective,
        "E": epsilon,
        "constraint_operator": epsilon_operator.value,
        "status": result.status.value,
        "status_message": result.status_message,
        "raw_termination": result.raw_termination,
        "x": None,
        "Z1": None,
        "Z2": None,
        "execution_time_sec": result.execution_time_sec,
    }
    if result.status == SolverStatus.OPTIMAL:
        x_values = dict(result.variable_values)
        run["x"] = x_values
        run["Z1"] = problem.objective1.evaluate(x_values)
        run["Z2"] = problem.objective2.evaluate(x_values)
    return run


def _same_solution(
    first: Dict[str, Any],
    second: Dict[str, Any],
    variables: List[str],
    tol: float,
) -> bool:
    return (
        all(abs(first["x"][name] - second["x"][name]) <= tol for name in variables)
        and abs(first["Z1"] - second["Z1"]) <= tol
        and abs(first["Z2"] - second["Z2"]) <= tol
    )


def _deduplicate_runs(
    runs: List[Dict[str, Any]], variables: List[str], tol: float
) -> List[Dict[str, Any]]:
    unique_solutions: List[Dict[str, Any]] = []
    for run in runs:
        if run["status"] != SolverStatus.OPTIMAL.value or run["x"] is None:
            continue
        matched = next(
            (
                solution
                for solution in unique_solutions
                if _same_solution(run, solution, variables, tol)
            ),
            None,
        )
        if matched is not None:
            matched["run_indices"].append(run["run_index"])
            matched["epsilon_levels"].append(run["E"])
            matched["count"] += 1
            continue

        unique_solutions.append(
            {
                "id": f"S{len(unique_solutions) + 1}",
                "x": dict(run["x"]),
                "Z1": run["Z1"],
                "Z2": run["Z2"],
                "count": 1,
                "run_indices": [run["run_index"]],
                "epsilon_levels": [run["E"]],
                "pareto_status": "No evaluada",
            }
        )
    return unique_solutions


def _is_no_worse(candidate: float, reference: float, sense: Sense, tol: float) -> bool:
    if sense == Sense.MAXIMIZE:
        return candidate >= reference - tol
    return candidate <= reference + tol


def _is_strictly_better(
    candidate: float, reference: float, sense: Sense, tol: float
) -> bool:
    if sense == Sense.MAXIMIZE:
        return candidate > reference + tol
    return candidate < reference - tol


def _classify_pareto(
    problem: BiobjectiveProblem,
    unique_solutions: List[Dict[str, Any]],
    tol: float,
) -> Dict[str, Any]:
    for solution in unique_solutions:
        solution["pareto_status"] = "No dominada"
        for candidate in unique_solutions:
            if candidate is solution:
                continue
            no_worse_z1 = _is_no_worse(
                candidate["Z1"], solution["Z1"], problem.objective1.sense, tol
            )
            no_worse_z2 = _is_no_worse(
                candidate["Z2"], solution["Z2"], problem.objective2.sense, tol
            )
            better_z1 = _is_strictly_better(
                candidate["Z1"], solution["Z1"], problem.objective1.sense, tol
            )
            better_z2 = _is_strictly_better(
                candidate["Z2"], solution["Z2"], problem.objective2.sense, tol
            )
            if no_worse_z1 and no_worse_z2 and (better_z1 or better_z2):
                solution["pareto_status"] = f"Dominada (por {candidate['id']})"
                break

    return {
        solution["id"]: {
            "x": solution["x"],
            "Z1": solution["Z1"],
            "Z2": solution["Z2"],
            "status": solution["pareto_status"],
            "run_indices": solution["run_indices"],
            "epsilon_levels": solution["epsilon_levels"],
        }
        for solution in unique_solutions
    }


def solve_biobjective_epsilon_constraint(
    problem: BiobjectiveProblem,
    primary_objective: int,
    r: int,
    tol: float = 1e-6,
) -> EpsilonConstraintSolution:
    """Resuelve un LP biobjetivo mediante el metodo de las restricciones.

    Si ``Zk`` es el objetivo restringido, cada corrida optimiza el objetivo
    principal sobre todas las restricciones originales y agrega exactamente
    ``Zk(x) >= E_k,t`` para MAX o ``Zk(x) <= E_k,t`` para MIN. No se emplean
    pesos ni normalizacion de objetivos.
    """

    if (
        isinstance(primary_objective, bool)
        or not isinstance(primary_objective, int)
        or primary_objective not in (1, 2)
    ):
        raise ValueError("primary_objective debe ser 1 (Z1) o 2 (Z2).")
    if not is_finite_number(tol) or tol <= 0:
        raise ValueError("tol debe ser un numero finito mayor que cero.")
    # Valida r incluso si el preprocesamiento no puede producir extremos.
    generate_epsilon_levels(0.0, 0.0, r)
    problem.validate()

    started = time.perf_counter()
    constrained_objective = 2 if primary_objective == 1 else 1
    preprocessing_started = time.perf_counter()
    individual_optima, payoff_matrix, objective_ranges, notes = _payoff_preprocessing(
        problem, tol
    )
    preprocessing_time = time.perf_counter() - preprocessing_started

    if not payoff_matrix:
        return EpsilonConstraintSolution(
            individual_optima=individual_optima,
            payoff_matrix={},
            objective_ranges={},
            primary_objective=primary_objective,
            constrained_objective=constrained_objective,
            r=r,
            epsilon_levels=[],
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

    range_prefix = f"Z{constrained_objective}"
    epsilon_levels = generate_epsilon_levels(
        objective_ranges[f"{range_prefix}_min"],
        objective_ranges[f"{range_prefix}_max"],
        r,
    )

    sweep_started = time.perf_counter()
    runs = [
        _solve_epsilon_run(
            problem=problem,
            primary_objective=primary_objective,
            constrained_objective=constrained_objective,
            t=t,
            epsilon=epsilon,
            tol=tol,
        )
        for t, epsilon in enumerate(epsilon_levels)
    ]
    sweep_time = time.perf_counter() - sweep_started

    unique_solutions = _deduplicate_runs(runs, list(problem.variables), tol)
    pareto_classification = _classify_pareto(problem, unique_solutions, tol)
    nondominated_solutions = [
        solution
        for solution in unique_solutions
        if solution["pareto_status"] == "No dominada"
    ]
    infeasible_count = sum(
        run["status"] == SolverStatus.INFEASIBLE.value for run in runs
    )
    if infeasible_count:
        notes.append(
            f"Se registraron {infeasible_count} corridas infactibles sin detener el barrido."
        )

    return EpsilonConstraintSolution(
        individual_optima=individual_optima,
        payoff_matrix=payoff_matrix,
        objective_ranges=objective_ranges,
        primary_objective=primary_objective,
        constrained_objective=constrained_objective,
        r=r,
        epsilon_levels=epsilon_levels,
        runs=runs,
        unique_solutions=unique_solutions,
        pareto_classification=pareto_classification,
        nondominated_solutions=nondominated_solutions,
        timing={
            "preprocessing_sec": round(preprocessing_time, 6),
            "sweep_sec": round(sweep_time, 6),
            "total_sec": round(time.perf_counter() - started, 6),
        },
        notes=notes,
    )
