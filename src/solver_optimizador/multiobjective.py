"""Optimizacion biobjetivo mediante suma ponderada normalizada."""

import time
from typing import Any, Dict, List, Optional, Tuple

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

from .lp_models import (
    BiobjectiveProblem,
    LPProblem,
    LinearConstraint,
    MultiobjectiveSolution,
    Operator,
    Sense,
    SolverStatus,
    is_finite_number,
)
from .lp_solver import solve_lp


NORMALIZATION_RANGE_TOL = 1e-7


def generate_weight_combinations(num_combinations: int) -> List[Tuple[float, float]]:
    """Genera N combinaciones uniformes desde (0, 1) hasta (1, 0)."""

    if num_combinations < 2:
        raise ValueError("El numero de combinaciones debe ser al menos 2.")
    weights = []
    for i in range(num_combinations):
        a1 = i / (num_combinations - 1)
        a2 = 1.0 - a1
        weights.append((round(a1, 6), round(a2, 6)))
    return weights


def normalize_objective_value(
    value: float,
    z_min: float,
    z_max: float,
    sense: Sense,
) -> float:
    """Orienta un objetivo a [0, 1] sin redondear el dato canonico.

    La politica general de rango cero permanece fuera de esta fase. Este helper
    conserva el umbral que ya detenia el barrido antes de AUD-HIGH-01.
    """

    if not all(is_finite_number(number) for number in (value, z_min, z_max)):
        raise ValueError("El valor y los limites de normalizacion deben ser finitos.")
    delta = z_max - z_min
    if delta < NORMALIZATION_RANGE_TOL:
        raise ValueError("El rango de normalizacion debe ser positivo y no nulo.")
    if sense == Sense.MAXIMIZE:
        return (value - z_min) / delta
    if sense == Sense.MINIMIZE:
        return (z_max - value) / delta
    raise ValueError(f"Sentido de objetivo no soportado: {sense}")


def _build_payoff_anchor(
    problem: BiobjectiveProblem,
    primary_index: int,
    tol: float = 1e-6,
) -> Dict[str, Any]:
    """Construye una ancla eficiente para la matriz de pagos.

    Primero optimiza el objetivo individual. Luego selecciona un representante
    sobre la misma cara optima fijando exactamente el valor primario y
    optimizando el objetivo restante. Esta seleccion es preprocesamiento de la
    matriz de pagos; no es una corrida del metodo de ponderaciones y no prueba
    unicidad ni multiplicidad.
    """

    if primary_index == 1:
        obj_prim = problem.objective1
        obj_sec = problem.objective2
        prim_name = "Z1"
        sec_name = "Z2"
    elif primary_index == 2:
        obj_prim = problem.objective2
        obj_sec = problem.objective1
        prim_name = "Z2"
        sec_name = "Z1"
    else:
        raise ValueError("primary_index debe ser 1 (Z1) o 2 (Z2).")

    started = time.perf_counter()
    primary_problem = LPProblem(
        variables=problem.variables,
        objective=obj_prim,
        constraints=problem.constraints,
    )
    primary_result = solve_lp(primary_problem, tol=tol)

    empty_metadata = {
        "purpose": "payoff_matrix_anchor",
        "rule": "secondary_objective_with_primary_value_fixed",
        "primary_objective": prim_name,
        "secondary_objective": sec_name,
        "attempted": False,
        "applied": False,
        "primary_value_preserved": False,
        "primary_residual": None,
        "secondary_value_changed": False,
        "establishes_uniqueness": False,
    }

    if primary_result.status != SolverStatus.OPTIMAL:
        return {
            "status": primary_result.status,
            "primary_status": primary_result.status,
            "primary_optimal_value": None,
            "raw_secondary_value": None,
            "x": None,
            "Z1": None,
            "Z2": None,
            "selection_metadata": empty_metadata,
            "execution_time_sec": round(time.perf_counter() - started, 6),
            "error_message": primary_result.status_message,
        }

    primary_optimum = primary_result.objective_value
    raw_secondary = obj_sec.evaluate(primary_result.variable_values)
    exact_primary_constraint = LinearConstraint(
        name=f"_payoff_anchor_{prim_name}",
        coefficients=obj_prim.coefficients,
        operator=Operator.EQ,
        rhs=primary_optimum,
    )
    representative_problem = LPProblem(
        variables=problem.variables,
        objective=obj_sec,
        constraints=problem.constraints + [exact_primary_constraint],
    )
    representative_result = solve_lp(representative_problem, tol=tol)

    metadata = dict(empty_metadata)
    metadata["attempted"] = True
    if representative_result.status == SolverStatus.OPTIMAL:
        candidate_x = representative_result.variable_values
        candidate_primary = obj_prim.evaluate(candidate_x)
        primary_residual = candidate_primary - primary_optimum
        primary_preserved = abs(primary_residual) <= tol
        metadata.update(
            {
                "primary_value_preserved": primary_preserved,
                "primary_residual": primary_residual,
            }
        )
        if primary_preserved:
            selected_x = candidate_x
            metadata["applied"] = True
        else:
            selected_x = primary_result.variable_values
    else:
        selected_x = primary_result.variable_values

    selected_secondary = obj_sec.evaluate(selected_x)
    if obj_sec.sense == Sense.MAXIMIZE:
        metadata["secondary_value_changed"] = selected_secondary > raw_secondary + tol
    else:
        metadata["secondary_value_changed"] = selected_secondary < raw_secondary - tol

    return {
        "status": primary_result.status,
        "primary_status": primary_result.status,
        "primary_optimal_value": primary_optimum,
        "raw_secondary_value": raw_secondary,
        "x": selected_x,
        "Z1": problem.objective1.evaluate(selected_x),
        "Z2": problem.objective2.evaluate(selected_x),
        "selection_metadata": metadata,
        "execution_time_sec": round(time.perf_counter() - started, 6),
    }


def solve_lexicographic_extreme(
    problem: BiobjectiveProblem,
    primary_index: int = 1,
    tol: float = 1e-6,
) -> Dict[str, Any]:
    """Compatibilidad: devuelve una ancla de matriz de pagos.

    El nombre historico se conserva para consumidores existentes. El resultado
    no representa una alternativa del barrido: es solo el preprocesamiento
    definido por :func:`_build_payoff_anchor`.
    """

    return _build_payoff_anchor(problem, primary_index=primary_index, tol=tol)


def _add_original_model(
    model: pyo.ConcreteModel,
    problem: BiobjectiveProblem,
) -> Dict[str, pyo.Var]:
    var_dict: Dict[str, pyo.Var] = {}
    for variable_name in problem.variables:
        variable = pyo.Var(name=variable_name, within=pyo.NonNegativeReals)
        setattr(model, variable_name, variable)
        var_dict[variable_name] = variable

    for index, constraint in enumerate(problem.constraints):
        expression = sum(
            coefficient * var_dict[variable_name]
            for variable_name, coefficient in constraint.coefficients.items()
        )
        if constraint.operator == Operator.LE:
            pyomo_constraint = pyo.Constraint(expr=expression <= constraint.rhs)
        elif constraint.operator == Operator.GE:
            pyomo_constraint = pyo.Constraint(expr=expression >= constraint.rhs)
        else:
            pyomo_constraint = pyo.Constraint(expr=expression == constraint.rhs)
        setattr(model, f"con_{index}", pyomo_constraint)
    return var_dict


def _objective_expression(
    problem: BiobjectiveProblem,
    objective_index: int,
    var_dict: Dict[str, pyo.Var],
) -> Any:
    objective = problem.objective1 if objective_index == 1 else problem.objective2
    return sum(
        objective.coefficients.get(variable_name, 0.0) * var_dict[variable_name]
        for variable_name in problem.variables
    )


def _normalized_expression(
    expression: Any,
    z_min: float,
    z_max: float,
    sense: Sense,
) -> Any:
    delta = z_max - z_min
    if delta < NORMALIZATION_RANGE_TOL:
        raise ValueError("El rango de normalizacion debe ser positivo y no nulo.")
    if sense == Sense.MAXIMIZE:
        return (expression - z_min) / delta
    return (z_max - expression) / delta


def _is_optimal(termination: Any) -> bool:
    return "optimal" in str(termination).lower()


def _read_variables(
    problem: BiobjectiveProblem,
    var_dict: Dict[str, pyo.Var],
) -> Dict[str, float]:
    return {
        variable_name: float(pyo.value(var_dict[variable_name]))
        for variable_name in problem.variables
    }


def _evaluate_weighted_result(
    problem: BiobjectiveProblem,
    x_values: Dict[str, float],
    alpha1: float,
    alpha2: float,
    ranges: Dict[str, float],
) -> Tuple[float, float, float, float, float]:
    z1_value = problem.objective1.evaluate(x_values)
    z2_value = problem.objective2.evaluate(x_values)
    n1_value = normalize_objective_value(
        z1_value,
        ranges["Z1_min"],
        ranges["Z1_max"],
        problem.objective1.sense,
    )
    n2_value = normalize_objective_value(
        z2_value,
        ranges["Z2_min"],
        ranges["Z2_max"],
        problem.objective2.sense,
    )
    weighted_value = alpha1 * n1_value + alpha2 * n2_value
    return z1_value, z2_value, n1_value, n2_value, weighted_value


def _solve_weighted_run(
    problem: BiobjectiveProblem,
    run_index: int,
    alpha1: float,
    alpha2: float,
    ranges: Dict[str, float],
    tol: float,
) -> Dict[str, Any]:
    """Resuelve una funcion W y devuelve valores reconstruidos desde el mismo x."""

    model = pyo.ConcreteModel(name=f"NormalizedWeightedRun_{run_index}")
    var_dict = _add_original_model(model, problem)
    z1_expression = _objective_expression(problem, 1, var_dict)
    z2_expression = _objective_expression(problem, 2, var_dict)
    n1_expression = _normalized_expression(
        z1_expression,
        ranges["Z1_min"],
        ranges["Z1_max"],
        problem.objective1.sense,
    )
    n2_expression = _normalized_expression(
        z2_expression,
        ranges["Z2_min"],
        ranges["Z2_max"],
        problem.objective2.sense,
    )
    weighted_expression = alpha1 * n1_expression + alpha2 * n2_expression
    model.weighted_objective = pyo.Objective(expr=weighted_expression, sense=pyo.maximize)

    solver = Highs()
    solver.config.load_solution = False
    result = solver.solve(model)
    termination = str(result.termination_condition)
    selection_metadata: Dict[str, Any] = {
        "method": "normalized_weighted_sum",
        "weighted_problem_solved": True,
        "weighted_solver_termination": termination,
        "representative_selection_applied": False,
        "representative_selection_rule": None,
        "w_optimum_before_selection": None,
        "w_after_selection": None,
        "establishes_uniqueness": False,
    }

    if not _is_optimal(result.termination_condition):
        return {
            "run_index": run_index,
            "alpha1": alpha1,
            "alpha2": alpha2,
            "x": None,
            "Z1": None,
            "Z2": None,
            "N1": None,
            "N2": None,
            "W": None,
            "status": termination,
            "selection_metadata": selection_metadata,
        }

    if result.solution_loader:
        result.solution_loader.load_vars()
    x_values = _read_variables(problem, var_dict)
    z1_value, z2_value, n1_value, n2_value, weighted_value = _evaluate_weighted_result(
        problem, x_values, alpha1, alpha2, ranges
    )
    selection_metadata["w_optimum_before_selection"] = weighted_value
    selection_metadata["w_after_selection"] = weighted_value

    # Un peso extremo puede ignorar por completo un objetivo. Se resuelve W en
    # todos los casos y solo despues se selecciona un representante eficiente
    # sobre la misma cara W*, conservando el valor ponderado.
    ignored_objective = None
    ignored_name = None
    ignored_expression = None
    if alpha1 == 0.0:
        ignored_objective = problem.objective1
        ignored_name = "Z1"
        ignored_expression = z1_expression
    elif alpha2 == 0.0:
        ignored_objective = problem.objective2
        ignored_name = "Z2"
        ignored_expression = z2_expression

    if ignored_objective is not None:
        model.weighted_optimum = pyo.Constraint(expr=weighted_expression == weighted_value)
        model.weighted_objective.deactivate()
        secondary_sense = (
            pyo.maximize if ignored_objective.sense == Sense.MAXIMIZE else pyo.minimize
        )
        model.representative_objective = pyo.Objective(
            expr=ignored_expression,
            sense=secondary_sense,
        )
        selection_result = Highs().solve(model)
        selection_termination = str(selection_result.termination_condition)
        selection_metadata.update(
            {
                "representative_selection_rule": (
                    f"optimize_{ignored_name}_with_weighted_optimum_fixed"
                ),
                "representative_selection_termination": selection_termination,
            }
        )
        if _is_optimal(selection_result.termination_condition):
            if selection_result.solution_loader:
                selection_result.solution_loader.load_vars()
            candidate_x = _read_variables(problem, var_dict)
            candidate_values = _evaluate_weighted_result(
                problem, candidate_x, alpha1, alpha2, ranges
            )
            candidate_w = candidate_values[4]
            if abs(candidate_w - weighted_value) <= tol:
                x_values = candidate_x
                z1_value, z2_value, n1_value, n2_value, weighted_value = candidate_values
                selection_metadata["representative_selection_applied"] = True
                selection_metadata["w_after_selection"] = candidate_w

    return {
        "run_index": run_index,
        "alpha1": alpha1,
        "alpha2": alpha2,
        "x": x_values,
        "Z1": z1_value,
        "Z2": z2_value,
        "N1": n1_value,
        "N2": n2_value,
        "W": weighted_value,
        "status": "Optimo",
        "selection_metadata": selection_metadata,
    }


def solve_biobjective_weighted(
    problem: BiobjectiveProblem,
    weights: Optional[List[Tuple[float, float]]] = None,
    num_combinations: Optional[int] = 6,
    tol: float = 1e-6,
) -> MultiobjectiveSolution:
    """Resuelve un problema biobjetivo por suma ponderada normalizada."""

    problem.validate()
    notes: List[str] = []
    started = time.perf_counter()

    anchor_z1 = _build_payoff_anchor(problem, primary_index=1, tol=tol)
    if anchor_z1["status"] != SolverStatus.OPTIMAL or anchor_z1["x"] is None:
        return MultiobjectiveSolution(
            individual_optima={"Z1_opt": anchor_z1, "Z2_opt": None},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={"total_sec": anchor_z1["execution_time_sec"]},
            notes=[
                "No se pudo obtener el optimo individual para Z1: "
                f"{anchor_z1.get('error_message', anchor_z1['status'].value)}"
            ],
        )

    anchor_z2 = _build_payoff_anchor(problem, primary_index=2, tol=tol)
    if anchor_z2["status"] != SolverStatus.OPTIMAL or anchor_z2["x"] is None:
        return MultiobjectiveSolution(
            individual_optima={"Z1_opt": anchor_z1, "Z2_opt": anchor_z2},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={
                "total_sec": (
                    anchor_z1["execution_time_sec"] + anchor_z2["execution_time_sec"]
                )
            },
            notes=[
                "No se pudo obtener el optimo individual para Z2: "
                f"{anchor_z2.get('error_message', anchor_z2['status'].value)}"
            ],
        )

    individual_time = (
        anchor_z1["execution_time_sec"] + anchor_z2["execution_time_sec"]
    )
    for anchor_name, anchor in (("Z1", anchor_z1), ("Z2", anchor_z2)):
        metadata = anchor["selection_metadata"]
        if metadata["applied"]:
            notes.append(
                f"Para el ancla {anchor_name} se selecciono un representante eficiente "
                "conservando el optimo primario. Esta regla estabiliza la matriz de "
                "pagos y no establece unicidad ni multiplicidad."
            )

    payoff_matrix = {
        "opt_Z1": {
            "x": anchor_z1["x"],
            "Z1": anchor_z1["Z1"],
            "Z2": anchor_z1["Z2"],
            "primary_optimal": anchor_z1["primary_optimal_value"],
            "selection_metadata": anchor_z1["selection_metadata"],
        },
        "opt_Z2": {
            "x": anchor_z2["x"],
            "Z1": anchor_z2["Z1"],
            "Z2": anchor_z2["Z2"],
            "primary_optimal": anchor_z2["primary_optimal_value"],
            "selection_metadata": anchor_z2["selection_metadata"],
        },
    }

    z1_values = [anchor_z1["Z1"], anchor_z2["Z1"]]
    z2_values = [anchor_z1["Z2"], anchor_z2["Z2"]]
    normalization_ranges = {
        "Z1_max": max(z1_values),
        "Z1_min": min(z1_values),
        "Z1_range": max(z1_values) - min(z1_values),
        "Z2_max": max(z2_values),
        "Z2_min": min(z2_values),
        "Z2_range": max(z2_values) - min(z2_values),
    }

    if (
        normalization_ranges["Z1_range"] < NORMALIZATION_RANGE_TOL
        or normalization_ranges["Z2_range"] < NORMALIZATION_RANGE_TOL
    ):
        notes.append(
            "No es posible aplicar la normalizacion por rangos porque al menos "
            "uno de los objetivos tiene rango nulo (Delta Z ~= 0)."
        )
        return MultiobjectiveSolution(
            individual_optima={"Z1_opt": anchor_z1, "Z2_opt": anchor_z2},
            payoff_matrix=payoff_matrix,
            normalization_ranges=normalization_ranges,
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={
                "individual_optima_sec": round(individual_time, 6),
                "total_sec": round(time.perf_counter() - started, 6),
            },
            notes=notes,
        )

    if weights is None:
        weights_list = generate_weight_combinations(num_combinations or 6)
    else:
        for alpha1, alpha2 in weights:
            if not is_finite_number(alpha1) or not is_finite_number(alpha2):
                raise ValueError(
                    f"Los pesos deben ser numeros finitos: ({alpha1}, {alpha2})"
                )
            if alpha1 < -1e-6 or alpha2 < -1e-6:
                raise ValueError(
                    f"Los pesos deben ser no negativos: ({alpha1}, {alpha2})"
                )
            if abs(alpha1 + alpha2 - 1.0) > 1e-3:
                raise ValueError(
                    "Los pesos deben sumar 1.0: "
                    f"({alpha1} + {alpha2} = {alpha1 + alpha2})"
                )
        weights_list = [(round(a1, 6), round(a2, 6)) for a1, a2 in weights]

    sweep_started = time.perf_counter()
    weighted_runs = [
        _solve_weighted_run(
            problem,
            run_index=index,
            alpha1=alpha1,
            alpha2=alpha2,
            ranges=normalization_ranges,
            tol=tol,
        )
        for index, (alpha1, alpha2) in enumerate(weights_list, start=1)
    ]
    sweep_time = time.perf_counter() - sweep_started

    # Agrupacion y Pareto conservan la politica de tolerancias preexistente.
    unique_solutions: List[Dict[str, Any]] = []
    for run in weighted_runs:
        if run["status"] != "Optimo" or run["x"] is None:
            continue
        matched = False
        for unique in unique_solutions:
            same_x = all(
                abs(run["x"].get(v, 0.0) - unique["x"].get(v, 0.0)) < 1e-4
                for v in problem.variables
            )
            same_z1 = abs(run["Z1"] - unique["Z1"]) < 1e-4
            same_z2 = abs(run["Z2"] - unique["Z2"]) < 1e-4
            if same_x and same_z1 and same_z2:
                unique["generated_by_weights"].append(
                    {"alpha1": run["alpha1"], "alpha2": run["alpha2"]}
                )
                unique["count"] += 1
                matched = True
                break
        if not matched:
            solution_id = chr(ord("A") + len(unique_solutions))
            unique_solutions.append(
                {
                    "id": solution_id,
                    "x": run["x"],
                    "Z1": run["Z1"],
                    "Z2": run["Z2"],
                    "count": 1,
                    "generated_by_weights": [
                        {"alpha1": run["alpha1"], "alpha2": run["alpha2"]}
                    ],
                    "pareto_status": "No evaluado",
                }
            )

    for index_a, solution_a in enumerate(unique_solutions):
        dominated = False
        for index_b, solution_b in enumerate(unique_solutions):
            if index_a == index_b:
                continue

            if problem.objective1.sense == Sense.MAXIMIZE:
                no_worse_1 = solution_b["Z1"] >= solution_a["Z1"] - 1e-4
                better_1 = solution_b["Z1"] > solution_a["Z1"] + 1e-4
            else:
                no_worse_1 = solution_b["Z1"] <= solution_a["Z1"] + 1e-4
                better_1 = solution_b["Z1"] < solution_a["Z1"] - 1e-4

            if problem.objective2.sense == Sense.MAXIMIZE:
                no_worse_2 = solution_b["Z2"] >= solution_a["Z2"] - 1e-4
                better_2 = solution_b["Z2"] > solution_a["Z2"] + 1e-4
            else:
                no_worse_2 = solution_b["Z2"] <= solution_a["Z2"] + 1e-4
                better_2 = solution_b["Z2"] < solution_a["Z2"] - 1e-4

            if no_worse_1 and no_worse_2 and (better_1 or better_2):
                dominated = True
                solution_a["pareto_status"] = f"Dominada (por {solution_b['id']})"
                break
        if not dominated:
            solution_a["pareto_status"] = "No dominada"

    pareto_classification = {
        solution["id"]: {
            "x": solution["x"],
            "Z1": solution["Z1"],
            "Z2": solution["Z2"],
            "status": solution["pareto_status"],
            "generated_by_weights": solution["generated_by_weights"],
        }
        for solution in unique_solutions
    }

    return MultiobjectiveSolution(
        individual_optima={"Z1_opt": anchor_z1, "Z2_opt": anchor_z2},
        payoff_matrix=payoff_matrix,
        normalization_ranges=normalization_ranges,
        weighted_runs=weighted_runs,
        unique_solutions=unique_solutions,
        pareto_classification=pareto_classification,
        timing={
            "individual_optima_sec": round(individual_time, 6),
            "weighted_sweep_sec": round(sweep_time, 6),
            "total_sec": round(time.perf_counter() - started, 6),
        },
        notes=notes,
    )
