"""
Modulo de interpretacion base automatica de resultados de optimizacion matematica.
Construye explicaciones rigurosas y claras a partir de la formulacion matematica y
la solucion obtenida, sin inventar contexto de negocio no provisto por el usuario.
"""

from typing import List, Dict, Any
from .lp_models import (
    LPProblem,
    BiobjectiveProblem,
    LPSolution,
    MultiobjectiveSolution,
    SolverStatus,
    Sense,
    is_finite_number,
)


def interpret_mono_solution(problem: LPProblem, solution: LPSolution) -> List[str]:
    """
    Genera una lista de observaciones interpretativas para un problema lineal monoobjetivo.
    """
    if solution.status == SolverStatus.INFEASIBLE:
        return [
            "El modelo es **infactible**: no existe ninguna asignacion de variables ($x \\ge 0$) que satisfaga simultaneamente todas las restricciones declaradas.",
            "Para resolver este problema, revise las restricciones que puedan ser contradictorias o amplie los limites de los lados derechos (RHS).",
        ]

    if solution.status == SolverStatus.UNBOUNDED:
        return [
            "El modelo **no esta acotado** (no acotamiento): la funcion objetivo puede mejorar indefinidamente en la direccion de optimizacion sin violar ninguna restriccion.",
            "Para corregir este comportamiento, añada restricciones que limiten las variables en la direccion de crecimiento del objetivo.",
        ]

    if solution.status != SolverStatus.OPTIMAL:
        return [
            f"El solver finalizo con estado no optimo: **{solution.status_message}** ({solution.raw_termination}).",
            "No fue posible determinar una solucion optima valida con los datos suministrados.",
        ]

    bullets: List[str] = []

    # 1. Sentido y valor optimo
    sense_str = "maximiza" if problem.objective.sense == Sense.MAXIMIZE else "minimiza"
    bullets.append(
        f"La solucion encontrada **{sense_str}** la funcion objetivo lineal, alcanzando un valor optimo **$Z^* = {solution.objective_value:.4f}$** dentro de la region factible."
    )

    # 2. Desglose de variables de decision
    pos_vars = [f"${v}^* = {val:.4f}$" for v, val in solution.variable_values.items() if abs(val) > 1e-6]
    zero_vars = [f"${v}$" for v, val in solution.variable_values.items() if abs(val) <= 1e-6]

    if pos_vars:
        vars_desc = f"Variables con valor positivo en el optimo: {', '.join(pos_vars)}."
        if zero_vars:
            vars_desc += f" Las variables {', '.join(zero_vars)} toman valor cero, indicando que no participan en la combinacion optima bajo las restricciones actuales."
        bullets.append(vars_desc)

    # 3. Restricciones activas (cuellos de botella)
    active_cons = [cr.name for cr in solution.constraint_results if cr.is_active]
    if active_cons:
        bullets.append(
            f"Restricciones **activas** (holgura nula): **{', '.join(active_cons)}**. Estas restricciones actuan como limites efectivos que determinan directamente el vertice optimo."
        )
    else:
        bullets.append("No se detectaron restricciones activas en el optimo (solucion limitada unicamente por no negatividad o cotas).")

    # 4. Restricciones con holgura (no limitantes)
    slack_cons = [f"**{cr.name}** (holgura = {cr.slack:.4f})" for cr in solution.constraint_results if not cr.is_active]
    if slack_cons:
        bullets.append(
            f"Restricciones **no limitantes** (con holgura): {', '.join(slack_cons)}. Indican margen o capacidad excedente no utilizada en la solucion actual."
        )

    return bullets


def interpret_biobjective_solution(problem: BiobjectiveProblem, solution: MultiobjectiveSolution) -> List[str]:
    """
    Genera una lista de observaciones interpretativas para un problema lineal biobjetivo resuelto por ponderaciones.
    """
    if not solution.unique_solutions:
        return [
            "No fue posible completar el analisis multiobjetivo debido a inconsistencias o infactibilidad en los modelos individuales.",
            "Consulte las notas tecnicas y diagnostico del solver para mas detalles.",
        ]

    bullets: List[str] = []

    # 1. Optimos individuales y compromiso (trade-off)
    pm = solution.payoff_matrix
    if pm and "opt_Z1" in pm and "opt_Z2" in pm:
        z1_opt = pm["opt_Z1"]["Z1"]
        z2_opt = pm["opt_Z2"]["Z2"]
        z1_at_z2 = pm["opt_Z2"]["Z1"]
        z2_at_z1 = pm["opt_Z1"]["Z2"]

        bullets.append(
            f"Los **optimos individuales** indican el mejor valor posible para cada objetivo de forma aislada: "
            f"**$Z_1^* = {z1_opt:.2f}$** y **$Z_2^* = {z2_opt:.2f}$**."
        )

        if abs(z1_opt - z1_at_z2) > 1e-4 or abs(z2_opt - z2_at_z1) > 1e-4:
            bullets.append(
                f"La matriz de pagos evidencia un **compromiso (trade-off)** entre los objetivos: "
                f"priorizar $Z_1$ al maximo reduce $Z_2$ a {z2_at_z1:.2f}, mientras que priorizar $Z_2$ reduce $Z_1$ a {z1_at_z2:.2f}."
            )
        else:
            bullets.append("Ambos objetivos alcanzan su optimo simultaneamente en el mismo punto, sin conflicto evidente.")

    # 2. Soluciones unicas y no dominancia
    n_runs = len(solution.weighted_runs)
    n_unique = len(solution.unique_solutions)
    nd_solutions = [u for u in solution.unique_solutions if "no dominada" in u["pareto_status"].lower()]
    n_nd = len(nd_solutions)

    bullets.append(
        f"Se evaluaron **{n_runs} combinaciones de ponderaciones**, identificando **{n_unique} soluciones unicas**, "
        f"de las cuales **{n_nd} resultaron no dominadas** en el conjunto discreto evaluado."
    )

    # 3. Estabilidad frente a ponderaciones
    multi_weight_sols = [u for u in solution.unique_solutions if u["count"] > 1]
    if multi_weight_sols:
        examples_str = ", ".join(f"Solucion {u['id']} ({u['count']} ponderaciones)" for u in multi_weight_sols[:2])
        bullets.append(
            f"El hecho de que distintas ponderaciones converjan a la misma solucion ({examples_str}) "
            f"indica que dicha alternativa es estable y optima frente a un rango amplio de preferencias relativas."
        )

    # 4. Extremos del compromiso
    if len(nd_solutions) >= 2:
        sorted_nd = sorted(nd_solutions, key=lambda s: s["Z1"])
        sol_left = sorted_nd[0]
        sol_right = sorted_nd[-1]
        bullets.append(
            f"La **Solucion {sol_right['id']}** $Z=({sol_right['Z1']:.1f}, {sol_right['Z2']:.1f})$ favorece prioritariamente $Z_1$, "
            f"mientras que la **Solucion {sol_left['id']}** $Z=({sol_left['Z1']:.1f}, {sol_left['Z2']:.1f})$ favorece prioritariamente $Z_2$."
        )

    # 5. Nota metodologica rigurosa
    bullets.append(
        "**Nota metodologica:** Esta interpretacion describe el conjunto discreto de soluciones no dominadas obtenidas "
        "para los pesos evaluados y no implica la reconstruccion completa de la frontera de Pareto continua."
    )

    return bullets
