"""Generación de scripts Gurobi autónomos para los modelos continuos actuales."""

from __future__ import annotations

from pathlib import Path
from pprint import pformat
from typing import Any, Mapping

from .lp_models import BiobjectiveProblem, MultiobjectiveProblem, is_finite_number


class GurobiScriptExportError(RuntimeError):
    """Error específico al construir o guardar un script Gurobi."""


def _objectives(
    problem: BiobjectiveProblem | MultiobjectiveProblem,
) -> list[Any]:
    if isinstance(problem, BiobjectiveProblem):
        return [problem.objective1, problem.objective2]
    return list(problem.objectives)


def _serialize_problem(
    problem: BiobjectiveProblem | MultiobjectiveProblem,
    *,
    method: str,
    model_name: str,
    model_file: Path,
    primary_objective: int | None,
    r_by_objective: Mapping[int, int] | None,
    num_weights: int | None,
    tolerance: float,
) -> dict[str, Any]:
    problem.validate()
    objectives = _objectives(problem)
    if method not in {"epsilon", "weighted"}:
        raise ValueError("method debe ser 'epsilon' o 'weighted'.")
    if not is_finite_number(tolerance) or tolerance <= 0:
        raise ValueError("tolerance debe ser un número finito mayor que cero.")

    configuration: dict[str, Any]
    if method == "weighted":
        if len(objectives) != 2:
            raise ValueError(
                "El método weighted solo admite exactamente dos objetivos."
            )
        if (
            isinstance(num_weights, bool)
            or not isinstance(num_weights, int)
            or num_weights < 2
        ):
            raise ValueError("num_weights debe ser un entero mayor o igual que 2.")
        configuration = {"num_weights": num_weights}
    else:
        if (
            isinstance(primary_objective, bool)
            or not isinstance(primary_objective, int)
            or not 1 <= primary_objective <= len(objectives)
        ):
            raise ValueError(
                f"primary_objective debe estar entre 1 y {len(objectives)}."
            )
        constrained = [
            index
            for index in range(1, len(objectives) + 1)
            if index != primary_objective
        ]
        supplied = dict(r_by_objective or {})
        if set(supplied) != set(constrained):
            expected = ", ".join(f"Z{index}" for index in constrained)
            raise ValueError(f"Debe especificarse r exactamente para: {expected}.")
        normalized_r: dict[int, int] = {}
        for index in constrained:
            value = supplied[index]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"r para Z{index} debe ser un entero >= 1.")
            normalized_r[index] = value
        configuration = {
            "primary_objective": primary_objective,
            "r_by_objective": normalized_r,
        }

    return {
        "model_name": model_name,
        "source_file": model_file.name,
        "method": method,
        "variables": list(problem.variables),
        "variable_type": "continuous",
        "lower_bound": 0.0,
        "upper_bound": None,
        "constraints": [
            {
                "name": constraint.name,
                "coefficients": dict(constraint.coefficients),
                "operator": constraint.operator.value,
                "rhs": constraint.rhs,
            }
            for constraint in problem.constraints
        ],
        "objectives": [
            {
                "name": objective.name,
                "sense": objective.sense.value,
                "coefficients": dict(objective.coefficients),
            }
            for objective in objectives
        ],
        "configuration": configuration,
        "tolerance": tolerance,
    }


_STANDALONE_RUNTIME = r'''

import itertools
import math
import time
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt


TOLERANCE = float(MODEL_DATA["tolerance"])
NORMALIZATION_RANGE_TOL = 1e-7
WEIGHTED_COMPARISON_TOL = 1e-4


def _linear_expression(coefficients, variables):
    expression = gp.LinExpr()
    for name, coefficient in coefficients.items():
        expression.addTerms(float(coefficient), variables[name])
    return expression


def _add_constraint(model, variables, specification):
    expression = _linear_expression(specification["coefficients"], variables)
    operator = specification["operator"]
    rhs = float(specification["rhs"])
    if operator == "<=":
        model.addConstr(expression <= rhs, name=specification["name"])
    elif operator == ">=":
        model.addConstr(expression >= rhs, name=specification["name"])
    elif operator == "=":
        model.addConstr(expression == rhs, name=specification["name"])
    else:
        raise ValueError(f"Operador no soportado: {operator}")


def _build_model(extra_constraints=()):
    model = gp.Model("standalone_multiobjective_lp")
    model.Params.OutputFlag = 0
    variables = {
        name: model.addVar(
            lb=float(MODEL_DATA["lower_bound"]),
            ub=GRB.INFINITY,
            vtype=GRB.CONTINUOUS,
            name=name,
        )
        for name in MODEL_DATA["variables"]
    }
    model.update()
    for specification in [*MODEL_DATA["constraints"], *extra_constraints]:
        _add_constraint(model, variables, specification)
    return model, variables


def _status_text(status):
    mapping = {
        GRB.OPTIMAL: "optimal",
        GRB.INFEASIBLE: "infeasible",
        GRB.UNBOUNDED: "unbounded",
        GRB.INF_OR_UNBD: "infeasibleOrUnbounded",
    }
    return mapping.get(status, f"gurobi_status_{status}")


def _evaluate(coefficients, vector):
    return sum(
        float(coefficient) * float(vector.get(name, 0.0))
        for name, coefficient in coefficients.items()
    )


def _objective_values(vector):
    return {
        f"Z{index}": _evaluate(objective["coefficients"], vector)
        for index, objective in enumerate(MODEL_DATA["objectives"], start=1)
    }


def _solve_coefficients(
    coefficients,
    sense,
    *,
    constant=0.0,
    extra_constraints=(),
):
    model, variables = _build_model(extra_constraints)
    expression = _linear_expression(coefficients, variables) + float(constant)
    gurobi_sense = GRB.MAXIMIZE if sense == "max" else GRB.MINIMIZE
    model.setObjective(expression, gurobi_sense)
    started = time.perf_counter()
    model.optimize()
    if model.Status == GRB.INF_OR_UNBD:
        model.Params.DualReductions = 0
        model.reset()
        model.optimize()
    elapsed = time.perf_counter() - started
    status_code = model.Status
    result = {
        "status": _status_text(status_code),
        "status_code": status_code,
        "x": None,
        "objective_values": None,
        "optimized_value": None,
        "execution_time_sec": elapsed,
        "gurobi_runtime_sec": float(model.Runtime),
    }
    if status_code == GRB.OPTIMAL:
        vector = {name: float(variable.X) for name, variable in variables.items()}
        result["x"] = vector
        result["objective_values"] = _objective_values(vector)
        result["optimized_value"] = _evaluate(coefficients, vector) + float(constant)
    model.dispose()
    return result


def _solve_objective(objective_index, *, extra_constraints=()):
    objective = MODEL_DATA["objectives"][objective_index - 1]
    return _solve_coefficients(
        objective["coefficients"],
        objective["sense"],
        extra_constraints=extra_constraints,
    )


def _fixed_objective_constraint(objective_index, value, name):
    return {
        "name": name,
        "coefficients": dict(MODEL_DATA["objectives"][objective_index - 1]["coefficients"]),
        "operator": "=",
        "rhs": value,
    }


def _biobjective_anchor(primary_index):
    started = time.perf_counter()
    secondary_index = 2 if primary_index == 1 else 1
    primary = _solve_objective(primary_index)
    if primary["status"] != "optimal":
        return {
            "status": primary["status"],
            "primary_optimal_value": None,
            "x": None,
            "objective_values": None,
            "execution_time_sec": time.perf_counter() - started,
        }
    primary_optimum = primary["optimized_value"]
    fixed = _fixed_objective_constraint(
        primary_index,
        primary_optimum,
        f"_payoff_anchor_Z{primary_index}",
    )
    representative = _solve_objective(
        secondary_index,
        extra_constraints=[fixed],
    )
    selected = primary
    if representative["status"] == "optimal":
        residual = (
            representative["objective_values"][f"Z{primary_index}"]
            - primary_optimum
        )
        if abs(residual) <= TOLERANCE:
            selected = representative
    return {
        "status": primary["status"],
        "primary_optimal_value": primary_optimum,
        "x": dict(selected["x"]),
        "objective_values": dict(selected["objective_values"]),
        "execution_time_sec": time.perf_counter() - started,
    }


def _multiobjective_anchor(primary_index):
    started = time.perf_counter()
    objective_count = len(MODEL_DATA["objectives"])
    order = [primary_index] + [
        index for index in range(1, objective_count + 1) if index != primary_index
    ]
    fixed_constraints = []
    selected = None
    primary_optimum = None
    for stage, objective_index in enumerate(order, start=1):
        selected = _solve_objective(
            objective_index,
            extra_constraints=fixed_constraints,
        )
        if selected["status"] != "optimal":
            return {
                "status": selected["status"],
                "primary_optimal_value": primary_optimum,
                "x": None,
                "objective_values": None,
                "execution_time_sec": time.perf_counter() - started,
            }
        optimum = selected["objective_values"][f"Z{objective_index}"]
        if stage == 1:
            primary_optimum = optimum
        fixed_constraints.append(
            _fixed_objective_constraint(
                objective_index,
                optimum,
                f"_payoff_Z{primary_index}_fix_Z{objective_index}",
            )
        )
    return {
        "status": "optimal",
        "primary_optimal_value": primary_optimum,
        "x": dict(selected["x"]),
        "objective_values": dict(selected["objective_values"]),
        "execution_time_sec": time.perf_counter() - started,
    }


def _payoff_preprocessing():
    started = time.perf_counter()
    objective_count = len(MODEL_DATA["objectives"])
    anchor_function = (
        _biobjective_anchor if objective_count == 2 else _multiobjective_anchor
    )
    anchors = {
        f"Z{index}_opt": anchor_function(index)
        for index in range(1, objective_count + 1)
    }
    failed = [
        label
        for label, anchor in anchors.items()
        if anchor["status"] != "optimal" or anchor["x"] is None
    ]
    if failed:
        raise RuntimeError(
            "No se pudo construir la matriz de pagos; fallaron: "
            + ", ".join(failed)
        )
    payoff = {}
    for index in range(1, objective_count + 1):
        anchor = anchors[f"Z{index}_opt"]
        payoff[f"opt_Z{index}"] = {
            "status": anchor["status"],
            "x": dict(anchor["x"]),
            "objective_values": dict(anchor["objective_values"]),
            **anchor["objective_values"],
        }
    ranges = {}
    for index in range(1, objective_count + 1):
        label = f"Z{index}"
        values = [row[label] for row in payoff.values()]
        ranges[f"{label}_min"] = min(values)
        ranges[f"{label}_max"] = max(values)
        ranges[f"{label}_range"] = max(values) - min(values)
    return anchors, payoff, ranges, time.perf_counter() - started


def _generate_epsilon_levels(z_min, z_max, r):
    difference = z_max - z_min
    levels = [z_min + (t / r) * difference for t in range(r + 1)]
    levels[0] = z_min
    levels[-1] = z_max
    return levels


def _epsilon_constraint(objective_index, t, epsilon):
    objective = MODEL_DATA["objectives"][objective_index - 1]
    return {
        "name": f"_epsilon_Z{objective_index}_t_{t}",
        "coefficients": dict(objective["coefficients"]),
        "operator": ">=" if objective["sense"] == "max" else "<=",
        "rhs": epsilon,
    }


def _same_epsilon_solution(first, second):
    return all(
        abs(first["x"][name] - second["x"][name]) <= TOLERANCE
        for name in MODEL_DATA["variables"]
    ) and all(
        abs(first["objective_values"][label] - second["objective_values"][label])
        <= TOLERANCE
        for label in first["objective_values"]
    )


def _deduplicate_epsilon(runs):
    unique = []
    for run in runs:
        if run["status"] != "optimal" or run["x"] is None:
            continue
        matched = next(
            (
                solution
                for solution in unique
                if _same_epsilon_solution(run, solution)
            ),
            None,
        )
        if matched is not None:
            matched["run_indices"].append(run["run_index"])
            matched["epsilon_indices"].append(dict(run["epsilon_indices"]))
            matched["epsilon_levels"].append(dict(run["epsilon_levels"]))
            matched["count"] += 1
            continue
        unique.append(
            {
                "id": f"S{len(unique) + 1}",
                "x": dict(run["x"]),
                "objective_values": dict(run["objective_values"]),
                "count": 1,
                "run_indices": [run["run_index"]],
                "epsilon_indices": [dict(run["epsilon_indices"])],
                "epsilon_levels": [dict(run["epsilon_levels"])],
                "pareto_status": "No evaluada",
            }
        )
    return unique


def _is_no_worse(candidate, reference, sense, tolerance):
    if sense == "max":
        return candidate >= reference - tolerance
    return candidate <= reference + tolerance


def _is_strictly_better(candidate, reference, sense, tolerance):
    if sense == "max":
        return candidate > reference + tolerance
    return candidate < reference - tolerance


def _classify_pareto(unique, tolerance):
    labels = [f"Z{index}" for index in range(1, len(MODEL_DATA["objectives"]) + 1)]
    for solution in unique:
        solution["pareto_status"] = "No dominada"
        for candidate in unique:
            if candidate is solution:
                continue
            no_worse = all(
                _is_no_worse(
                    candidate["objective_values"][label],
                    solution["objective_values"][label],
                    MODEL_DATA["objectives"][index]["sense"],
                    tolerance,
                )
                for index, label in enumerate(labels)
            )
            strictly_better = any(
                _is_strictly_better(
                    candidate["objective_values"][label],
                    solution["objective_values"][label],
                    MODEL_DATA["objectives"][index]["sense"],
                    tolerance,
                )
                for index, label in enumerate(labels)
            )
            if no_worse and strictly_better:
                solution["pareto_status"] = f"Dominada (por {candidate['id']})"
                break
    return [solution for solution in unique if solution["pareto_status"] == "No dominada"]


def _solve_epsilon(payoff, ranges, preprocessing_time):
    configuration = MODEL_DATA["configuration"]
    primary = configuration["primary_objective"]
    constrained = [
        index
        for index in range(1, len(MODEL_DATA["objectives"]) + 1)
        if index != primary
    ]
    r_by_objective = configuration["r_by_objective"]
    levels = {
        f"Z{index}": _generate_epsilon_levels(
            ranges[f"Z{index}_min"],
            ranges[f"Z{index}_max"],
            r_by_objective[index],
        )
        for index in constrained
    }
    index_products = itertools.product(
        *(range(r_by_objective[index] + 1) for index in constrained)
    )
    sweep_started = time.perf_counter()
    runs = []
    for run_index, indices in enumerate(index_products):
        index_map = {
            f"Z{objective_index}": level_index
            for objective_index, level_index in zip(constrained, indices)
        }
        level_map = {
            f"Z{objective_index}": levels[f"Z{objective_index}"][level_index]
            for objective_index, level_index in zip(constrained, indices)
        }
        epsilon_constraints = [
            _epsilon_constraint(
                objective_index,
                level_index,
                level_map[f"Z{objective_index}"],
            )
            for objective_index, level_index in zip(constrained, indices)
        ]
        solved = _solve_objective(
            primary,
            extra_constraints=epsilon_constraints,
        )
        runs.append(
            {
                "run_index": run_index,
                "epsilon_indices": index_map,
                "epsilon_levels": level_map,
                "status": solved["status"],
                "x": solved["x"],
                "objective_values": solved["objective_values"],
                "execution_time_sec": solved["execution_time_sec"],
            }
        )
    sweep_time = time.perf_counter() - sweep_started
    unique = _deduplicate_epsilon(runs)
    nondominated = _classify_pareto(unique, TOLERANCE)
    return {
        "method": "epsilon",
        "payoff_matrix": payoff,
        "objective_ranges": ranges,
        "primary_objective": primary,
        "constrained_objectives": constrained,
        "r_by_objective": r_by_objective,
        "epsilon_levels": levels,
        "runs": runs,
        "unique_solutions": unique,
        "nondominated_solutions": nondominated,
        "timing": {
            "preprocessing_sec": preprocessing_time,
            "sweep_sec": sweep_time,
            "total_sec": preprocessing_time + sweep_time,
        },
    }


def _generate_weights(count):
    return [
        (round(index / (count - 1), 6), round(1.0 - index / (count - 1), 6))
        for index in range(count)
    ]


def _normalized_coefficients(objective_index, ranges):
    objective = MODEL_DATA["objectives"][objective_index - 1]
    label = f"Z{objective_index}"
    z_min = ranges[f"{label}_min"]
    z_max = ranges[f"{label}_max"]
    delta = z_max - z_min
    if delta < NORMALIZATION_RANGE_TOL:
        raise RuntimeError(f"El rango de normalización de {label} es nulo.")
    if objective["sense"] == "max":
        return (
            {name: coefficient / delta for name, coefficient in objective["coefficients"].items()},
            -z_min / delta,
        )
    return (
        {name: -coefficient / delta for name, coefficient in objective["coefficients"].items()},
        z_max / delta,
    )


def _combine_weighted_coefficients(alpha1, alpha2, ranges):
    n1_coefficients, n1_constant = _normalized_coefficients(1, ranges)
    n2_coefficients, n2_constant = _normalized_coefficients(2, ranges)
    coefficients = {}
    for name in MODEL_DATA["variables"]:
        coefficients[name] = (
            alpha1 * n1_coefficients.get(name, 0.0)
            + alpha2 * n2_coefficients.get(name, 0.0)
        )
    return coefficients, alpha1 * n1_constant + alpha2 * n2_constant


def _normalized_value(value, z_min, z_max, sense):
    delta = z_max - z_min
    if sense == "max":
        return (value - z_min) / delta
    return (z_max - value) / delta


def _weighted_values(vector, alpha1, alpha2, ranges):
    objective_values = _objective_values(vector)
    n1 = _normalized_value(
        objective_values["Z1"],
        ranges["Z1_min"],
        ranges["Z1_max"],
        MODEL_DATA["objectives"][0]["sense"],
    )
    n2 = _normalized_value(
        objective_values["Z2"],
        ranges["Z2_min"],
        ranges["Z2_max"],
        MODEL_DATA["objectives"][1]["sense"],
    )
    return objective_values, n1, n2, alpha1 * n1 + alpha2 * n2


def _solve_weighted_run(run_index, alpha1, alpha2, ranges):
    coefficients, constant = _combine_weighted_coefficients(alpha1, alpha2, ranges)
    solved = _solve_coefficients(coefficients, "max", constant=constant)
    run = {
        "run_index": run_index,
        "alpha1": alpha1,
        "alpha2": alpha2,
        "status": solved["status"],
        "x": None,
        "objective_values": None,
        "Z1": None,
        "Z2": None,
        "N1": None,
        "N2": None,
        "W": None,
        "execution_time_sec": solved["execution_time_sec"],
    }
    if solved["status"] != "optimal":
        return run
    vector = solved["x"]
    objective_values, n1, n2, weighted_value = _weighted_values(
        vector, alpha1, alpha2, ranges
    )

    ignored_index = 1 if alpha1 == 0.0 else (2 if alpha2 == 0.0 else None)
    if ignored_index is not None:
        fixed_weighted = {
            "name": f"_weighted_optimum_run_{run_index}",
            "coefficients": coefficients,
            "operator": "=",
            "rhs": weighted_value - constant,
        }
        candidate = _solve_objective(
            ignored_index,
            extra_constraints=[fixed_weighted],
        )
        if candidate["status"] == "optimal":
            candidate_values, candidate_n1, candidate_n2, candidate_w = _weighted_values(
                candidate["x"], alpha1, alpha2, ranges
            )
            if abs(candidate_w - weighted_value) <= TOLERANCE:
                vector = candidate["x"]
                objective_values = candidate_values
                n1, n2, weighted_value = candidate_n1, candidate_n2, candidate_w
                run["execution_time_sec"] += candidate["execution_time_sec"]

    run.update(
        {
            "status": "Optimo",
            "x": vector,
            "objective_values": objective_values,
            "Z1": objective_values["Z1"],
            "Z2": objective_values["Z2"],
            "N1": n1,
            "N2": n2,
            "W": weighted_value,
        }
    )
    return run


def _deduplicate_weighted(runs):
    unique = []
    for run in runs:
        if run["status"] != "Optimo" or run["x"] is None:
            continue
        matched = next(
            (
                solution
                for solution in unique
                if all(
                    abs(run["x"][name] - solution["x"][name])
                    < WEIGHTED_COMPARISON_TOL
                    for name in MODEL_DATA["variables"]
                )
                and abs(run["Z1"] - solution["objective_values"]["Z1"])
                < WEIGHTED_COMPARISON_TOL
                and abs(run["Z2"] - solution["objective_values"]["Z2"])
                < WEIGHTED_COMPARISON_TOL
            ),
            None,
        )
        generator = {"alpha1": run["alpha1"], "alpha2": run["alpha2"]}
        if matched is not None:
            matched["generated_by_weights"].append(generator)
            matched["count"] += 1
            continue
        unique.append(
            {
                "id": chr(ord("A") + len(unique)),
                "x": dict(run["x"]),
                "objective_values": dict(run["objective_values"]),
                "count": 1,
                "generated_by_weights": [generator],
                "pareto_status": "No evaluado",
            }
        )
    return unique


def _solve_weighted(payoff, ranges, preprocessing_time):
    started = time.perf_counter()
    count = MODEL_DATA["configuration"]["num_weights"]
    weights = _generate_weights(count)
    runs = [
        _solve_weighted_run(index, alpha1, alpha2, ranges)
        for index, (alpha1, alpha2) in enumerate(weights, start=1)
    ]
    sweep_time = time.perf_counter() - started
    unique = _deduplicate_weighted(runs)
    nondominated = _classify_pareto(unique, WEIGHTED_COMPARISON_TOL)
    return {
        "method": "weighted",
        "payoff_matrix": payoff,
        "normalization_ranges": ranges,
        "weights": weights,
        "runs": runs,
        "unique_solutions": unique,
        "nondominated_solutions": nondominated,
        "timing": {
            "preprocessing_sec": preprocessing_time,
            "sweep_sec": sweep_time,
            "total_sec": preprocessing_time + sweep_time,
        },
    }


def solve_model():
    _, payoff, ranges, preprocessing_time = _payoff_preprocessing()
    if MODEL_DATA["method"] == "epsilon":
        return _solve_epsilon(payoff, ranges, preprocessing_time)
    return _solve_weighted(payoff, ranges, preprocessing_time)


def _number(value):
    return "-" if value is None else f"{value:.12g}"


def _objective_expression_text(objective):
    terms = []
    for name in MODEL_DATA["variables"]:
        coefficient = objective["coefficients"].get(name, 0.0)
        if coefficient:
            terms.append(f"{coefficient:g} {name}")
    return " + ".join(terms).replace("+ -", "- ") or "0"


def _print_results(result):
    print("=" * 90)
    print("SCRIPT GUROBI AUTÓNOMO — MODELO MULTIOBJETIVO CONTINUO")
    print("=" * 90)
    print(f"Modelo: {MODEL_DATA['model_name']}")
    print(f"Archivo fuente informativo: {MODEL_DATA['source_file']}")
    print(f"Variables continuas no negativas: {len(MODEL_DATA['variables'])}")
    print(f"Restricciones originales: {len(MODEL_DATA['constraints'])}")
    print("Objetivos:")
    for index, objective in enumerate(MODEL_DATA["objectives"], start=1):
        print(
            f"  Z{index} = {_objective_expression_text(objective)} "
            f"[{objective['sense'].upper()}] — {objective['name']}"
        )
    print(f"Método: {result['method']}")
    print("\nMatriz de pagos:")
    for anchor, row in result["payoff_matrix"].items():
        values = "; ".join(
            f"Z{index}={_number(row[f'Z{index}'])}"
            for index in range(1, len(MODEL_DATA["objectives"]) + 1)
        )
        print(f"  {anchor}: estado={row['status']}; {values}")

    if result["method"] == "epsilon":
        print(f"\nObjetivo principal: Z{result['primary_objective']}")
        for index in result["constrained_objectives"]:
            label = f"Z{index}"
            print(
                f"  {label}: r={result['r_by_objective'][index]}; "
                f"niveles={result['epsilon_levels'][label]}"
            )
        print(f"Corridas: {len(result['runs'])}")
    else:
        print(f"\nPonderaciones: {len(result['weights'])}")

    print("\nTodas las corridas:")
    for run in result["runs"]:
        if result["method"] == "epsilon":
            configuration = ", ".join(
                f"{label}[t={run['epsilon_indices'][label]}]="
                f"{_number(run['epsilon_levels'][label])}"
                for label in run["epsilon_indices"]
            )
        else:
            configuration = (
                f"alpha1={_number(run['alpha1'])}; alpha2={_number(run['alpha2'])}; "
                f"N1={_number(run['N1'])}; N2={_number(run['N2'])}; "
                f"W={_number(run['W'])}"
            )
        print(
            f"  Corrida {run['run_index'] + (1 if result['method'] == 'epsilon' else 0)}: "
            f"{configuration}; estado={run['status']}; "
            f"tiempo_s={_number(run['execution_time_sec'])}"
        )
        if run["x"] is None:
            print("    objetivos: -")
            print("    variables: -")
            continue
        print(
            "    objetivos: "
            + "; ".join(
                f"{label}={_number(value)}"
                for label, value in run["objective_values"].items()
            )
        )
        print(
            "    x: "
            + ", ".join(
                f"{name}={_number(run['x'][name])}"
                for name in MODEL_DATA["variables"]
            )
        )

    print(f"\nSoluciones únicas: {len(result['unique_solutions'])}")
    for solution in result["unique_solutions"]:
        values = "; ".join(
            f"{label}={_number(value)}"
            for label, value in solution["objective_values"].items()
        )
        print(
            f"  {solution['id']}: {values}; repeticiones={solution['count']}; "
            f"{solution['pareto_status']}"
        )
    print(
        "Soluciones no dominadas obtenidas: "
        + str(len(result["nondominated_solutions"]))
    )
    for solution in result["nondominated_solutions"]:
        values = "; ".join(
            f"{label}={_number(value)}"
            for label, value in solution["objective_values"].items()
        )
        print(f"  {solution['id']}: {values}")
    print("Tiempos:")
    for name, value in result["timing"].items():
        print(f"  {name}={_number(value)}")


def _annotate_points(axis, solutions, x_label, y_label):
    offsets = [(7, 8), (7, -14), (-18, 8), (-18, -14)]
    for index, solution in enumerate(solutions):
        axis.annotate(
            solution["id"],
            (solution["objective_values"][x_label], solution["objective_values"][y_label]),
            xytext=offsets[index % len(offsets)],
            textcoords="offset points",
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.15", "fc": "white", "alpha": 0.8},
        )


def _objective_axis_label(index):
    objective = MODEL_DATA["objectives"][index - 1]
    return f"Z{index}: {objective['name']} ({objective['sense'].upper()})"


def _save_objective_plots(result):
    outputs = []
    solutions = result["nondominated_solutions"]
    if not solutions:
        print("No hay soluciones no dominadas para graficar.")
        return outputs
    script_path = Path(__file__).resolve()
    primary = result.get("primary_objective", 1)
    pairs = (
        [(1, 2)]
        if len(MODEL_DATA["objectives"]) == 2
        else [(primary, index) for index in result["constrained_objectives"]]
    )
    for first, second in pairs:
        first_label, second_label = f"Z{first}", f"Z{second}"
        figure, axis = plt.subplots(figsize=(9, 6))
        ordered = sorted(solutions, key=lambda item: item["objective_values"][first_label])
        x_values = [item["objective_values"][first_label] for item in ordered]
        y_values = [item["objective_values"][second_label] for item in ordered]
        if len(MODEL_DATA["objectives"]) == 2:
            axis.plot(x_values, y_values, color="#2C6EBA", linewidth=1.2, alpha=0.75)
        axis.scatter(x_values, y_values, color="#C43D3D", s=42, zorder=3)
        _annotate_points(axis, ordered, first_label, second_label)
        axis.set_xlabel(_objective_axis_label(first))
        axis.set_ylabel(_objective_axis_label(second))
        axis.set_title(f"{MODEL_DATA['model_name']} — soluciones no dominadas")
        axis.grid(True, alpha=0.25)
        figure.tight_layout()
        suffix = (
            "_pareto.png"
            if len(MODEL_DATA["objectives"]) == 2
            else f"_Z{first}_vs_Z{second}.png"
        )
        output = script_path.with_name(script_path.stem + suffix)
        figure.savefig(output, dpi=160, bbox_inches="tight")
        plt.close(figure)
        outputs.append(output)
    return outputs


def _constraint_satisfied(specification, x_value, y_value, first, second):
    lhs = (
        specification["coefficients"].get(first, 0.0) * x_value
        + specification["coefficients"].get(second, 0.0) * y_value
    )
    rhs = specification["rhs"]
    if specification["operator"] == "<=":
        return lhs <= rhs + TOLERANCE
    if specification["operator"] == ">=":
        return lhs >= rhs - TOLERANCE
    return abs(lhs - rhs) <= TOLERANCE


def _save_feasible_region_2d():
    if len(MODEL_DATA["variables"]) != 2:
        print(
            "Región factible: no se representa porque el modelo tiene "
            f"{len(MODEL_DATA['variables'])} variables de decisión."
        )
        return None
    first, second = MODEL_DATA["variables"]
    for variable in (first, second):
        bound = _solve_coefficients({variable: 1.0}, "max")
        if bound["status"] != "optimal":
            print("Región factible 2D: no se grafica porque no es acotada o no es factible.")
            return None

    boundaries = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for constraint in MODEL_DATA["constraints"]:
        a = float(constraint["coefficients"].get(first, 0.0))
        b = float(constraint["coefficients"].get(second, 0.0))
        if abs(a) > TOLERANCE or abs(b) > TOLERANCE:
            boundaries.append((a, b, float(constraint["rhs"])))
    vertices = []
    for index, (a1, b1, c1) in enumerate(boundaries):
        for a2, b2, c2 in boundaries[index + 1:]:
            determinant = a1 * b2 - a2 * b1
            if abs(determinant) <= TOLERANCE:
                continue
            x_value = (c1 * b2 - c2 * b1) / determinant
            y_value = (a1 * c2 - a2 * c1) / determinant
            if x_value < -TOLERANCE or y_value < -TOLERANCE:
                continue
            if not all(
                _constraint_satisfied(c, x_value, y_value, first, second)
                for c in MODEL_DATA["constraints"]
            ):
                continue
            if not any(
                abs(x_value - x) <= TOLERANCE and abs(y_value - y) <= TOLERANCE
                for x, y in vertices
            ):
                vertices.append((max(0.0, x_value), max(0.0, y_value)))
    if not vertices:
        print("Región factible 2D: no se encontraron vértices representables.")
        return None
    center_x = sum(x for x, _ in vertices) / len(vertices)
    center_y = sum(y for _, y in vertices) / len(vertices)
    vertices.sort(key=lambda point: math.atan2(point[1] - center_y, point[0] - center_x))
    figure, axis = plt.subplots(figsize=(7, 6))
    x_values = [point[0] for point in vertices]
    y_values = [point[1] for point in vertices]
    if len(vertices) >= 3:
        axis.fill(x_values, y_values, color="#80B1D3", alpha=0.35)
        axis.plot(x_values + [x_values[0]], y_values + [y_values[0]], color="#2C6EBA")
    elif len(vertices) == 2:
        axis.plot(x_values, y_values, color="#2C6EBA", linewidth=2)
    else:
        axis.scatter(x_values, y_values, color="#2C6EBA")
    axis.set_xlabel(first)
    axis.set_ylabel(second)
    axis.set_title(f"{MODEL_DATA['model_name']} — región factible 2D")
    axis.grid(True, alpha=0.25)
    figure.tight_layout()
    script_path = Path(__file__).resolve()
    output = script_path.with_name(script_path.stem + "_region_factible.png")
    figure.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output


def main():
    result = solve_model()
    _print_results(result)
    objective_plots = _save_objective_plots(result)
    for output in objective_plots:
        print(f"Gráfico de objetivos guardado en: {output}")
    feasible_output = _save_feasible_region_2d()
    if feasible_output is not None:
        print(f"Región factible 2D guardada en: {feasible_output}")


if __name__ == "__main__":
    main()
'''


def export_gurobi_script(
    *,
    problem: BiobjectiveProblem | MultiobjectiveProblem,
    method: str,
    model_name: str,
    model_file: str | Path,
    output_path: str | Path,
    primary_objective: int | None = None,
    r_by_objective: Mapping[int, int] | None = None,
    num_weights: int | None = None,
    tolerance: float = 1e-6,
) -> Path:
    """Escribe código Gurobi autónomo sin importar ni ejecutar ``gurobipy``."""

    source = Path(model_file)
    destination = Path(output_path)
    if destination.suffix.lower() != ".py":
        raise ValueError("output_path debe tener extensión .py.")
    payload = _serialize_problem(
        problem,
        method=method,
        model_name=model_name,
        model_file=source,
        primary_objective=primary_objective,
        r_by_objective=r_by_objective,
        num_weights=num_weights,
        tolerance=tolerance,
    )
    source_code = (
        "# -*- coding: utf-8 -*-\n"
        '"""Script autónomo generado para resolver el modelo con Gurobi."""\n\n'
        "from __future__ import annotations\n\n"
        "MODEL_DATA = "
        + pformat(payload, width=100, sort_dicts=False)
        + "\n"
        + _STANDALONE_RUNTIME
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source_code, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise GurobiScriptExportError(
            f"No se pudo guardar el script Gurobi en '{destination}': {exc}"
        ) from exc
    return destination.resolve()


__all__ = [
    "GurobiScriptExportError",
    "export_gurobi_script",
]
