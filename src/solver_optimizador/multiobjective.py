"""
Modulo de optimizacion multiobjetivo (Biobjetivo mediante suma ponderada normalizada con extremos lexicograficos).
"""

import time
from typing import List, Tuple, Dict, Any, Optional

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

from .lp_models import (
    BiobjectiveProblem,
    LPProblem,
    LinearConstraint,
    MultiobjectiveSolution,
    SolverStatus,
    Sense,
    Operator,
    is_finite_number,
)
from .lp_solver import solve_lp


def generate_weight_combinations(num_combinations: int) -> List[Tuple[float, float]]:
    """Genera N combinaciones de pesos uniformes desde (0.0, 1.0) hasta (1.0, 0.0)."""
    if num_combinations < 2:
        raise ValueError("El numero de combinaciones debe ser al menos 2.")
    weights = []
    for i in range(num_combinations):
        a1 = i / (num_combinations - 1)
        a2 = 1.0 - a1
        weights.append((round(a1, 6), round(a2, 6)))
    return weights


def solve_lexicographic_extreme(
    problem: BiobjectiveProblem,
    primary_index: int = 1,
    tol: float = 1e-6,
) -> Dict[str, Any]:
    """
    Resuelve el extremo eficiente lexicografico para un objetivo primario (1 para Z1, 2 para Z2),
    desempatando con el objetivo secundario si existen multiples optimos.

    1. Optimiza el objetivo primario Z_prim segun su sentido -> Z_prim*.
    2. Fija Z_prim = Z_prim* mediante restriccion exacta (con fallback acotado por tolerancia).
    3. Optimiza el objetivo secundario Z_sec segun su propio sentido.
    4. Garantiza que el extremo resultante sea Pareto-eficiente (no dominado).
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

    t_0 = time.perf_counter()

    # Paso 1: Optimizacion individual del objetivo primario
    p_prim = LPProblem(
        variables=problem.variables,
        objective=obj_prim,
        constraints=problem.constraints,
    )
    res_prim = solve_lp(p_prim)

    if res_prim.status != SolverStatus.OPTIMAL:
        return {
            "status": res_prim.status,
            "primary_status": res_prim.status,
            "primary_optimal_value": None,
            "raw_secondary_value": None,
            "x": None,
            "Z1": None,
            "Z2": None,
            "has_alternative_optima": False,
            "execution_time_sec": round(time.perf_counter() - t_0, 6),
            "error_message": res_prim.status_message,
        }

    prim_val = res_prim.objective_value
    sec_prim_val = obj_sec.evaluate(res_prim.variable_values)

    # Paso 2: Fijar objetivo primario e intentar resolucion lexicografica exacta
    lex_con_eq = LinearConstraint(
        name=f"_lex_bound_{prim_name}",
        coefficients=obj_prim.coefficients,
        operator=Operator.EQ,
        rhs=prim_val,
    )
    p_lex_eq = LPProblem(
        variables=problem.variables,
        objective=obj_sec,
        constraints=problem.constraints + [lex_con_eq],
    )
    res_lex = solve_lp(p_lex_eq)

    # Fallback con tolerancia si la igualdad exacta falla por condicionamiento numerico
    if res_lex.status != SolverStatus.OPTIMAL and tol > 0:
        op = Operator.LE if obj_prim.sense == Sense.MINIMIZE else Operator.GE
        bound = prim_val + tol if obj_prim.sense == Sense.MINIMIZE else prim_val - tol
        lex_con_ineq = LinearConstraint(
            name=f"_lex_bound_{prim_name}",
            coefficients=obj_prim.coefficients,
            operator=op,
            rhs=bound,
        )
        p_lex_ineq = LPProblem(
            variables=problem.variables,
            objective=obj_sec,
            constraints=problem.constraints + [lex_con_ineq],
        )
        res_lex = solve_lp(p_lex_ineq)

    if res_lex.status == SolverStatus.OPTIMAL:
        x_final = res_lex.variable_values
        final_status = res_lex.status
    else:
        x_final = res_prim.variable_values
        final_status = res_prim.status

    z1_final = problem.objective1.evaluate(x_final)
    z2_final = problem.objective2.evaluate(x_final)
    sec_final_val = obj_sec.evaluate(x_final)

    # Detectar si el desempate mejoro el objetivo secundario
    if obj_sec.sense == Sense.MAXIMIZE:
        has_alt = (sec_final_val - sec_prim_val) > 1e-4
    else:
        has_alt = (sec_prim_val - sec_final_val) > 1e-4

    t_total = time.perf_counter() - t_0

    return {
        "status": final_status,
        "primary_status": res_prim.status,
        "primary_optimal_value": prim_val,
        "raw_secondary_value": sec_prim_val,
        "x": x_final,
        "Z1": z1_final,
        "Z2": z2_final,
        "has_alternative_optima": has_alt,
        "execution_time_sec": round(t_total, 6),
    }


def solve_biobjective_weighted(
    problem: BiobjectiveProblem,
    weights: Optional[List[Tuple[float, float]]] = None,
    num_combinations: Optional[int] = 6,
    tol: float = 1e-6,
) -> MultiobjectiveSolution:
    """
    Ejecuta el flujo biobjetivo completo con el metodo de ponderaciones normalizadas
    y extremos lexicograficamente eficientes para la matriz de pagos.
    """
    problem.validate()
    notes = []
    t_start = time.perf_counter()

    # 1. Extremo lexicografico para Z1
    opt_z1 = solve_lexicographic_extreme(problem, primary_index=1, tol=tol)
    if opt_z1["status"] != SolverStatus.OPTIMAL or opt_z1["x"] is None:
        return MultiobjectiveSolution(
            individual_optima={"Z1_opt": opt_z1, "Z2_opt": None},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={"total_sec": opt_z1["execution_time_sec"]},
            notes=[f"No se pudo obtener optimo individual lexicografico para Z1: {opt_z1.get('error_message', opt_z1['status'].value)}"],
        )

    # 2. Extremo lexicografico para Z2
    opt_z2 = solve_lexicographic_extreme(problem, primary_index=2, tol=tol)
    if opt_z2["status"] != SolverStatus.OPTIMAL or opt_z2["x"] is None:
        return MultiobjectiveSolution(
            individual_optima={"Z1_opt": opt_z1, "Z2_opt": opt_z2},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={"total_sec": opt_z1["execution_time_sec"] + opt_z2["execution_time_sec"]},
            notes=[f"No se pudo obtener optimo individual lexicografico para Z2: {opt_z2.get('error_message', opt_z2['status'].value)}"],
        )

    t_individual = opt_z1["execution_time_sec"] + opt_z2["execution_time_sec"]

    if opt_z1["has_alternative_optima"]:
        notes.append("El objetivo Z1 presento multiples optimos individuales; se aplico desempate lexicografico optimizando Z2.")
    if opt_z2["has_alternative_optima"]:
        notes.append("El objetivo Z2 presento multiples optimos individuales; se aplico desempate lexicografico optimizando Z1.")

    # 3. Matriz de pagos eficiente
    payoff_matrix = {
        "opt_Z1": {
            "x": opt_z1["x"],
            "Z1": opt_z1["Z1"],
            "Z2": opt_z1["Z2"],
            "has_tie_break": opt_z1["has_alternative_optima"],
            "primary_optimal": opt_z1["primary_optimal_value"],
        },
        "opt_Z2": {
            "x": opt_z2["x"],
            "Z1": opt_z2["Z1"],
            "Z2": opt_z2["Z2"],
            "has_tie_break": opt_z2["has_alternative_optima"],
            "primary_optimal": opt_z2["primary_optimal_value"],
        },
    }

    # 4. Rangos de normalizacion
    z1_vals = [opt_z1["Z1"], opt_z2["Z1"]]
    z2_vals = [opt_z1["Z2"], opt_z2["Z2"]]

    z1_max = max(z1_vals)
    z1_min = min(z1_vals)
    z1_range = z1_max - z1_min

    z2_max = max(z2_vals)
    z2_min = min(z2_vals)
    z2_range = z2_max - z2_min

    normalization_ranges = {
        "Z1_max": z1_max,
        "Z1_min": z1_min,
        "Z1_range": z1_range,
        "Z2_max": z2_max,
        "Z2_min": z2_min,
        "Z2_range": z2_range,
    }

    if z1_range < 1e-7 or z2_range < 1e-7:
        msg = (
            "No es posible aplicar la normalizacion por rangos porque al menos uno de los objetivos tiene rango nulo (Delta Z ~= 0). "
            "Esto indica que el objetivo es constante o que ambos extremos lexicograficos coinciden."
        )
        notes.append(msg)
        return MultiobjectiveSolution(
            individual_optima={
                "Z1_opt": opt_z1,
                "Z2_opt": opt_z2,
            },
            payoff_matrix=payoff_matrix,
            normalization_ranges=normalization_ranges,
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={
                "individual_optima_sec": round(t_individual, 6),
                "total_sec": round(time.perf_counter() - t_start, 6),
            },
            notes=notes,
        )

    # 5. Lista de pesos
    if weights is None:
        weights_list = generate_weight_combinations(num_combinations or 6)
    else:
        for a1, a2 in weights:
            if not is_finite_number(a1) or not is_finite_number(a2):
                raise ValueError(f"Los pesos deben ser numeros finitos: ({a1}, {a2})")
            if a1 < -1e-6 or a2 < -1e-6:
                raise ValueError(f"Los pesos deben ser no negativos: ({a1}, {a2})")
            if abs(a1 + a2 - 1.0) > 1e-3:
                raise ValueError(f"Los pesos deben sumar 1.0: ({a1} + {a2} = {a1+a2})")
        weights_list = [(round(a1, 6), round(a2, 6)) for a1, a2 in weights]

    # 6. Barrido de ponderaciones
    weighted_runs: List[Dict[str, Any]] = []
    solver = Highs()
    solver.config.load_solution = False

    t_sweep_0 = time.perf_counter()

    for idx, (a1, a2) in enumerate(weights_list):
        if abs(a1 - 1.0) < 1e-6 and abs(a2 - 0.0) < 1e-6:
            # Extremo Z1 eficiente directamente
            x_vals = opt_z1["x"]
            z1_val = opt_z1["Z1"]
            z2_val = opt_z1["Z2"]
            term1 = (z1_val / z1_range) if problem.objective1.sense == Sense.MAXIMIZE else (-z1_val / z1_range)
            term2 = (z2_val / z2_range) if problem.objective2.sense == Sense.MAXIMIZE else (-z2_val / z2_range)
            w_val = a1 * term1 + a2 * term2
            status_str = "Optimo"
        elif abs(a1 - 0.0) < 1e-6 and abs(a2 - 1.0) < 1e-6:
            # Extremo Z2 eficiente directamente
            x_vals = opt_z2["x"]
            z1_val = opt_z2["Z1"]
            z2_val = opt_z2["Z2"]
            term1 = (z1_val / z1_range) if problem.objective1.sense == Sense.MAXIMIZE else (-z1_val / z1_range)
            term2 = (z2_val / z2_range) if problem.objective2.sense == Sense.MAXIMIZE else (-z2_val / z2_range)
            w_val = a1 * term1 + a2 * term2
            status_str = "Optimo"
        else:
            mw = pyo.ConcreteModel(name=f"Weighted_{idx}")
            var_dict = {}
            for v in problem.variables:
                var_obj = pyo.Var(name=v, within=pyo.NonNegativeReals)
                setattr(mw, v, var_obj)
                var_dict[v] = var_obj

            for i, c in enumerate(problem.constraints):
                expr = sum(c.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)
                if c.operator == Operator.LE:
                    con_obj = pyo.Constraint(expr=expr <= c.rhs)
                elif c.operator == Operator.GE:
                    con_obj = pyo.Constraint(expr=expr >= c.rhs)
                else:
                    con_obj = pyo.Constraint(expr=expr == c.rhs)
                setattr(mw, f"con_{i}", con_obj)

            z1_expr = sum(problem.objective1.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)
            z2_expr = sum(problem.objective2.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)

            term1 = (z1_expr / z1_range) if problem.objective1.sense == Sense.MAXIMIZE else (-z1_expr / z1_range)
            term2 = (z2_expr / z2_range) if problem.objective2.sense == Sense.MAXIMIZE else (-z2_expr / z2_range)

            mw.obj = pyo.Objective(expr=a1 * term1 + a2 * term2, sense=pyo.maximize)

            res_w = solver.solve(mw)
            term_str = str(res_w.termination_condition)

            if "optimal" in term_str.lower():
                if res_w.solution_loader:
                    res_w.solution_loader.load_vars()
                x_vals = {v: float(pyo.value(var_dict[v])) for v in problem.variables}
                z1_val = problem.objective1.evaluate(x_vals)
                z2_val = problem.objective2.evaluate(x_vals)
                z1_term = (z1_val / z1_range) if problem.objective1.sense == Sense.MAXIMIZE else (-z1_val / z1_range)
                z2_term = (z2_val / z2_range) if problem.objective2.sense == Sense.MAXIMIZE else (-z2_val / z2_range)
                w_val = a1 * z1_term + a2 * z2_term
                status_str = "Optimo"
            else:
                x_vals = None
                z1_val = None
                z2_val = None
                w_val = None
                status_str = term_str

        weighted_runs.append({
            "run_index": idx + 1,
            "alpha1": a1,
            "alpha2": a2,
            "x": x_vals,
            "Z1": z1_val,
            "Z2": z2_val,
            "W": w_val,
            "status": status_str,
        })

    t_sweep_1 = time.perf_counter()
    t_sweep = t_sweep_1 - t_sweep_0

    # 7. Agrupar soluciones unicas
    unique_solutions: List[Dict[str, Any]] = []
    for run in weighted_runs:
        if run["status"] != "Optimo" or run["x"] is None:
            continue
        matched = False
        for u in unique_solutions:
            same_x = all(abs(run["x"].get(v, 0.0) - u["x"].get(v, 0.0)) < 1e-4 for v in problem.variables)
            same_z1 = abs(run["Z1"] - u["Z1"]) < 1e-4
            same_z2 = abs(run["Z2"] - u["Z2"]) < 1e-4
            if same_x and same_z1 and same_z2:
                u["generated_by_weights"].append({"alpha1": run["alpha1"], "alpha2": run["alpha2"]})
                u["count"] += 1
                matched = True
                break
        if not matched:
            sol_id = chr(ord('A') + len(unique_solutions))
            unique_solutions.append({
                "id": sol_id,
                "x": run["x"],
                "Z1": run["Z1"],
                "Z2": run["Z2"],
                "count": 1,
                "generated_by_weights": [{"alpha1": run["alpha1"], "alpha2": run["alpha2"]}],
                "pareto_status": "No evaluado",
            })

    # 8. Clasificar dominancia de Pareto
    for i, sa in enumerate(unique_solutions):
        dominated = False
        for j, sb in enumerate(unique_solutions):
            if i == j:
                continue

            if problem.objective1.sense == Sense.MAXIMIZE:
                ge1 = sb["Z1"] >= sa["Z1"] - 1e-4
                gt1 = sb["Z1"] > sa["Z1"] + 1e-4
            else:
                ge1 = sb["Z1"] <= sa["Z1"] + 1e-4
                gt1 = sb["Z1"] < sa["Z1"] - 1e-4

            if problem.objective2.sense == Sense.MAXIMIZE:
                ge2 = sb["Z2"] >= sa["Z2"] - 1e-4
                gt2 = sb["Z2"] > sa["Z2"] + 1e-4
            else:
                ge2 = sb["Z2"] <= sa["Z2"] + 1e-4
                gt2 = sb["Z2"] < sa["Z2"] - 1e-4

            if ge1 and ge2 and (gt1 or gt2):
                dominated = True
                sa["pareto_status"] = f"Dominada (por {sb['id']})"
                break
        if not dominated:
            sa["pareto_status"] = "No dominada"

    pareto_classification = {
        sol["id"]: {
            "x": sol["x"],
            "Z1": sol["Z1"],
            "Z2": sol["Z2"],
            "status": sol["pareto_status"],
            "generated_by_weights": sol["generated_by_weights"],
        }
        for sol in unique_solutions
    }

    t_total = time.perf_counter() - t_start

    return MultiobjectiveSolution(
        individual_optima={
            "Z1_opt": opt_z1,
            "Z2_opt": opt_z2,
        },
        payoff_matrix=payoff_matrix,
        normalization_ranges=normalization_ranges,
        weighted_runs=weighted_runs,
        unique_solutions=unique_solutions,
        pareto_classification=pareto_classification,
        timing={
            "individual_optima_sec": round(t_individual, 6),
            "weighted_sweep_sec": round(t_sweep, 6),
            "total_sec": round(t_total, 6),
        },
        notes=notes,
    )
