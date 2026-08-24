"""
Modulo de optimizacion multiobjetivo (Biobjetivo mediante suma ponderada normalizada).
"""

import time
from typing import List, Tuple, Dict, Any, Optional

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

from .lp_models import (
    BiobjectiveProblem,
    LPProblem,
    MultiobjectiveSolution,
    SolverStatus,
    Sense,
    Operator,
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


def solve_biobjective_weighted(
    problem: BiobjectiveProblem,
    weights: Optional[List[Tuple[float, float]]] = None,
    num_combinations: Optional[int] = 6,
    tol: float = 1e-4,
) -> MultiobjectiveSolution:
    """
    Ejecuta el flujo biobjetivo completo con el metodo de ponderaciones normalizadas.
    """
    problem.validate()
    notes = []
    t_start = time.perf_counter()

    # 1. Optimizar Z1 individualmente
    t_z1_0 = time.perf_counter()
    p1 = LPProblem(
        variables=problem.variables,
        objective=problem.objective1,
        constraints=problem.constraints,
    )
    res_z1 = solve_lp(p1)
    t_z1_1 = time.perf_counter()

    if res_z1.status != SolverStatus.OPTIMAL:
        return MultiobjectiveSolution(
            individual_optima={"Z1": res_z1, "Z2": None},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={"total_sec": t_z1_1 - t_z1_0},
            notes=[f"No se pudo obtener optimo individual para Z1: {res_z1.status_message}"],
        )

    # 2. Optimizar Z2 individualmente
    t_z2_0 = time.perf_counter()
    p2 = LPProblem(
        variables=problem.variables,
        objective=problem.objective2,
        constraints=problem.constraints,
    )
    res_z2 = solve_lp(p2)
    t_z2_1 = time.perf_counter()

    if res_z2.status != SolverStatus.OPTIMAL:
        return MultiobjectiveSolution(
            individual_optima={"Z1": res_z1, "Z2": res_z2},
            payoff_matrix={},
            normalization_ranges={},
            weighted_runs=[],
            unique_solutions=[],
            pareto_classification={},
            timing={"total_sec": (t_z1_1 - t_z1_0) + (t_z2_1 - t_z2_0)},
            notes=[f"No se pudo obtener optimo individual para Z2: {res_z2.status_message}"],
        )

    t_individual = (t_z1_1 - t_z1_0) + (t_z2_1 - t_z2_0)

    # 3. Matriz de pagos
    x_at_z1 = res_z1.variable_values
    x_at_z2 = res_z2.variable_values

    z1_val_at_z1 = problem.objective1.evaluate(x_at_z1)
    z2_val_at_z1 = problem.objective2.evaluate(x_at_z1)

    z1_val_at_z2 = problem.objective1.evaluate(x_at_z2)
    z2_val_at_z2 = problem.objective2.evaluate(x_at_z2)

    payoff_matrix = {
        "opt_Z1": {
            "x": x_at_z1,
            "Z1": round(z1_val_at_z1, 6),
            "Z2": round(z2_val_at_z1, 6),
        },
        "opt_Z2": {
            "x": x_at_z2,
            "Z1": round(z1_val_at_z2, 6),
            "Z2": round(z2_val_at_z2, 6),
        },
    }

    # 4. Rangos de normalizacion
    z1_max = max(z1_val_at_z1, z1_val_at_z2)
    z1_min = min(z1_val_at_z1, z1_val_at_z2)
    z1_range = z1_max - z1_min

    z2_max = max(z2_val_at_z1, z2_val_at_z2)
    z2_min = min(z2_val_at_z1, z2_val_at_z2)
    z2_range = z2_max - z2_min

    # Gestion de rango nulo
    r1_effective = z1_range
    if z1_range < 1e-7:
        r1_effective = 1.0
        notes.append("El rango de Z1 es nulo (Z1 no varia entre optimos individuales). Se fija factor 1.0.")

    r2_effective = z2_range
    if z2_range < 1e-7:
        r2_effective = 1.0
        notes.append("El rango de Z2 es nulo (Z2 no varia entre optimos individuales). Se fija factor 1.0.")

    normalization_ranges = {
        "Z1_max": round(z1_max, 6),
        "Z1_min": round(z1_min, 6),
        "Z1_range": round(z1_range, 6),
        "Z2_max": round(z2_max, 6),
        "Z2_min": round(z2_min, 6),
        "Z2_range": round(z2_range, 6),
    }

    # 5. Determinar lista de pesos
    if weights is None:
        weights_list = generate_weight_combinations(num_combinations or 6)
    else:
        for a1, a2 in weights:
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
            setattr(mw, f"c_{i}_{c.name}", con_obj)

        # Expresiones de Z1 y Z2
        z1_expr = sum(problem.objective1.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)
        z2_expr = sum(problem.objective2.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)

        # Normalizacion segun sentido:
        # Para MAX Z: maximizar + Z / range
        # Para MIN Z: maximizar - Z / range
        term1 = (z1_expr / r1_effective) if problem.objective1.sense == Sense.MAXIMIZE else (-z1_expr / r1_effective)
        term2 = (z2_expr / r2_effective) if problem.objective2.sense == Sense.MAXIMIZE else (-z2_expr / r2_effective)

        mw.obj = pyo.Objective(expr=a1 * term1 + a2 * term2, sense=pyo.maximize)

        res_w = solver.solve(mw)
        term_str = str(res_w.termination_condition)

        if "optimal" in term_str.lower():
            if res_w.solution_loader:
                res_w.solution_loader.load_vars()
            x_vals = {v: round(float(pyo.value(var_dict[v])), 6) for v in problem.variables}
            z1_val = round(problem.objective1.evaluate(x_vals), 6)
            z2_val = round(problem.objective2.evaluate(x_vals), 6)
            w_val = round(float(pyo.value(mw.obj.expr)), 6)
        else:
            x_vals = {}
            z1_val = 0.0
            z2_val = 0.0
            w_val = 0.0

        weighted_runs.append({
            "run_index": idx + 1,
            "alpha1": a1,
            "alpha2": a2,
            "x": x_vals,
            "Z1": z1_val,
            "Z2": z2_val,
            "W": w_val,
            "status": "Optimo" if "optimal" in term_str.lower() else term_str,
        })

    t_sweep_1 = time.perf_counter()
    t_sweep = t_sweep_1 - t_sweep_0

    # 7. Agrupar soluciones unicas
    unique_solutions: List[Dict[str, Any]] = []
    for run in weighted_runs:
        if run["status"] != "Optimo":
            continue
        matched = False
        for u in unique_solutions:
            same_x = all(abs(run["x"].get(v, 0.0) - u["x"].get(v, 0.0)) < tol for v in problem.variables)
            same_z1 = abs(run["Z1"] - u["Z1"]) < tol
            same_z2 = abs(run["Z2"] - u["Z2"]) < tol
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

    # 8. Clasificar dominancia de Pareto en el conjunto discreto
    for i, sa in enumerate(unique_solutions):
        dominated = False
        for j, sb in enumerate(unique_solutions):
            if i == j:
                continue

            # Mejor o igual segun sentido
            if problem.objective1.sense == Sense.MAXIMIZE:
                ge1 = sb["Z1"] >= sa["Z1"] - tol
                gt1 = sb["Z1"] > sa["Z1"] + tol
            else:
                ge1 = sb["Z1"] <= sa["Z1"] + tol
                gt1 = sb["Z1"] < sa["Z1"] - tol

            if problem.objective2.sense == Sense.MAXIMIZE:
                ge2 = sb["Z2"] >= sa["Z2"] - tol
                gt2 = sb["Z2"] > sa["Z2"] + tol
            else:
                ge2 = sb["Z2"] <= sa["Z2"] + tol
                gt2 = sb["Z2"] < sa["Z2"] - tol

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
            "Z1_max": {
                "x": x_at_z1,
                "Z1": round(z1_val_at_z1, 6),
                "Z2": round(z2_val_at_z1, 6),
                "status": res_z1.status.value,
            },
            "Z2_max": {
                "x": x_at_z2,
                "Z1": round(z1_val_at_z2, 6),
                "Z2": round(z2_val_at_z2, 6),
                "status": res_z2.status.value,
            },
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
