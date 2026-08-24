"""
Motor de resolucion para Programacion Lineal Continua con Pyomo + HiGHS.
"""

import time
from typing import Dict, Any

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

from .lp_models import (
    LPProblem,
    LPSolution,
    SolverStatus,
    ConstraintResult,
    Sense,
    Operator,
)


def _map_termination_condition(term_cond: Any) -> SolverStatus:
    s = str(term_cond).lower()
    if "optimal" in s:
        return SolverStatus.OPTIMAL
    elif "infeasible" in s and "unbounded" in s:
        return SolverStatus.INFEASIBLE_OR_UNBOUNDED
    elif "infeasible" in s:
        return SolverStatus.INFEASIBLE
    elif "unbounded" in s:
        return SolverStatus.UNBOUNDED
    else:
        return SolverStatus.ERROR


def solve_lp(problem: LPProblem, tol: float = 1e-6) -> LPSolution:
    """
    Resuelve un problema de programacion lineal continua mediante Pyomo + HiGHS (APPSI).
    """
    problem.validate()

    t_start = time.perf_counter()

    # 1. Construir modelo Pyomo
    model = pyo.ConcreteModel(name="LP_Problem")

    # Variables (continuas >= 0)
    var_dict = {}
    for v in problem.variables:
        var_obj = pyo.Var(name=v, within=pyo.NonNegativeReals)
        setattr(model, v, var_obj)
        var_dict[v] = var_obj

    # Restricciones
    for i, c in enumerate(problem.constraints):
        expr = sum(c.coefficients.get(v, 0.0) * var_dict[v] for v in problem.variables)
        if c.operator == Operator.LE:
            con_obj = pyo.Constraint(expr=expr <= c.rhs)
        elif c.operator == Operator.GE:
            con_obj = pyo.Constraint(expr=expr >= c.rhs)
        else:  # EQ
            con_obj = pyo.Constraint(expr=expr == c.rhs)
        setattr(model, f"c_{i}_{c.name}", con_obj)

    # Objetivo
    obj_expr = sum(
        problem.objective.coefficients.get(v, 0.0) * var_dict[v]
        for v in problem.variables
    )
    sense = pyo.maximize if problem.objective.sense == Sense.MAXIMIZE else pyo.minimize
    model.obj = pyo.Objective(expr=obj_expr, sense=sense)

    # 2. Resolver con APPSI HiGHS
    solver = Highs()
    solver.config.load_solution = False
    try:
        results = solver.solve(model)
        raw_term = str(results.termination_condition)
        status = _map_termination_condition(results.termination_condition)
    except Exception as exc:
        t_end = time.perf_counter()
        return LPSolution(
            status=SolverStatus.ERROR,
            status_message=f"Error al ejecutar HiGHS: {str(exc)}",
            raw_termination="Exception",
            execution_time_sec=t_end - t_start,
        )

    t_end = time.perf_counter()
    exec_time = t_end - t_start

    # 3. Procesar resultados si es optimo
    if status == SolverStatus.OPTIMAL:
        if results.solution_loader:
            results.solution_loader.load_vars()
        var_values = {v: float(pyo.value(var_dict[v])) for v in problem.variables}
        obj_val = float(pyo.value(model.obj))

        con_results = []
        for c in problem.constraints:
            lhs_val = c.evaluate_lhs(var_values)
            slack = c.calculate_slack(var_values)
            is_active = abs(slack) < tol
            con_results.append(
                ConstraintResult(
                    name=c.name,
                    lhs=round(lhs_val, 6),
                    operator=c.operator.value,
                    rhs=c.rhs,
                    slack=round(slack, 6),
                    is_active=is_active,
                )
            )

        return LPSolution(
            status=status,
            status_message=status.user_friendly_message,
            raw_termination=raw_term,
            objective_value=round(obj_val, 6),
            variable_values={v: round(val, 6) for v, val in var_values.items()},
            constraint_results=con_results,
            execution_time_sec=round(exec_time, 6),
        )
    else:
        return LPSolution(
            status=status,
            status_message=status.user_friendly_message,
            raw_termination=raw_term,
            execution_time_sec=round(exec_time, 6),
        )
