"""
Modulo de generacion de graficos para el espacio de variables (2D) y espacio de objetivos (2D).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from .lp_models import LPProblem, BiobjectiveProblem, Operator, Sense, is_finite_number


def plot_feasible_region_2d(
    problem: Any,
    solutions: Optional[List[Dict[str, Any]]] = None,
    title: str = "Espacio de variables: Region factible y soluciones",
) -> Optional[plt.Figure]:
    """
    Genera el grafico 2D del espacio de variables (region factible y puntos de solucion).
    Solo disponible cuando el numero de variables es exactamente 2.
    Si la region no es un poligono acotado simple de al menos 3 vertices,
    dibuja las restricciones y puntos sin sombrear un poligono inventado.
    """
    if len(problem.variables) != 2:
        return None

    v1, v2 = problem.variables[0], problem.variables[1]

    # Recopilar lineas de restriccion y ejes
    lines = []
    has_equality = False
    for c in problem.constraints:
        a = c.coefficients.get(v1, 0.0)
        b = c.coefficients.get(v2, 0.0)
        rhs = c.rhs
        op = c.operator
        if op == Operator.EQ:
            has_equality = True
        if is_finite_number(a) and is_finite_number(b) and is_finite_number(rhs):
            lines.append((a, b, rhs, op, c.name))

    # Determinar limites preliminares para el grafico buscando intersecciones
    points = [(0.0, 0.0)]
    for a, b, rhs, _, _ in lines:
        if abs(a) > 1e-7 and is_finite_number(rhs / a) and rhs / a > 0:
            points.append((rhs / a, 0.0))
        if abs(b) > 1e-7 and is_finite_number(rhs / b) and rhs / b > 0:
            points.append((0.0, rhs / b))

    if solutions:
        for s in solutions:
            x_dict = s.get("x", s) if isinstance(s, dict) else {}
            if x_dict and v1 in x_dict and v2 in x_dict:
                px, py = x_dict[v1], x_dict[v2]
                if is_finite_number(px) and is_finite_number(py):
                    points.append((float(px), float(py)))

    max_x = max(p[0] for p in points) if points else 10.0
    max_y = max(p[1] for p in points) if points else 10.0
    limit_x = max(max_x * 1.3, 10.0)
    limit_y = max(max_y * 1.3, 10.0)

    # Hallar intersecciones de todas las lineas (incluyendo x1=0, x2=0)
    all_lines_eq = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]  # x1=0, x2=0
    for a, b, rhs, _, _ in lines:
        all_lines_eq.append((a, b, rhs))

    intersect_pts = []
    for i in range(len(all_lines_eq)):
        for j in range(i + 1, len(all_lines_eq)):
            a1, b1, c1 = all_lines_eq[i]
            a2, b2, c2 = all_lines_eq[j]
            det = a1 * b2 - a2 * b1
            if abs(det) > 1e-7:
                px = (c1 * b2 - c2 * b1) / det
                py = (a1 * c2 - a2 * c1) / det
                if px >= -1e-5 and py >= -1e-5 and px <= limit_x * 2 and py <= limit_y * 2:
                    intersect_pts.append((max(0.0, px), max(0.0, py)))

    # Filtrar puntos que cumplen todas las restricciones
    tol = 1e-4
    feasible_pts = []
    for px, py in intersect_pts:
        is_feas = True
        for a, b, rhs, op, _ in lines:
            val = a * px + b * py
            if op == Operator.LE and val > rhs + tol:
                is_feas = False
                break
            elif op == Operator.GE and val < rhs - tol:
                is_feas = False
                break
            elif op == Operator.EQ and abs(val - rhs) > tol:
                is_feas = False
                break
        if is_feas:
            if not any(abs(px - fx) < tol and abs(py - fy) < tol for fx, fy in feasible_pts):
                feasible_pts.append((px, py))

    # Crear figura con estilo limpio
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=150)

    # Trazar lineas de restriccion
    colors = ["#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
    for idx, (a, b, rhs, op, name) in enumerate(lines):
        color = colors[idx % len(colors)]
        op_sym = r"\leq" if op == Operator.LE else (r"\geq" if op == Operator.GE else "=")
        label = f"{name}: {a:.2g}{v1} + {b:.2g}{v2} ${op_sym}$ {rhs:.2g}"
        if abs(b) > 1e-7:
            x_vals = np.array([0, limit_x])
            y_vals = (rhs - a * x_vals) / b
            ax.plot(x_vals, y_vals, label=label, color=color, linewidth=1.5, linestyle="-")
        elif abs(a) > 1e-7:
            ax.axvline(x=rhs / a, label=label, color=color, linewidth=1.5, linestyle="-")

    # Sombrear poligono SOLO si hay al menos 3 vertices factibles y no hay restricciones de igualdad
    if len(feasible_pts) >= 3 and not has_equality:
        cx = sum(p[0] for p in feasible_pts) / len(feasible_pts)
        cy = sum(p[1] for p in feasible_pts) / len(feasible_pts)
        sorted_pts = sorted(feasible_pts, key=lambda p: np.arctan2(p[1] - cy, p[0] - cx))
        poly = Polygon(sorted_pts, closed=True, facecolor="#e8f4f8", edgecolor="#1f77b4",
                       linewidth=1.5, alpha=0.7, label="Region Factible", zorder=2)
        ax.add_patch(poly)

    # Dibujar puntos de soluciones
    if solutions:
        for idx, sol in enumerate(solutions):
            sol_id = sol.get("id", f"S{idx+1}")
            x_dict = sol.get("x", sol)
            if isinstance(x_dict, dict) and v1 in x_dict and v2 in x_dict:
                px = x_dict[v1]
                py = x_dict[v2]
                if is_finite_number(px) and is_finite_number(py):
                    ax.scatter(px, py, color="#d62728", s=90, zorder=5, edgecolor="black")
                    ax.annotate(
                        f"{sol_id} ({px:.1f}, {py:.1f})",
                        (px, py), textcoords="offset points", xytext=(10, 10),
                        fontsize=8.5, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#333333", alpha=0.9),
                        arrowprops=dict(arrowstyle="->", color="#333333"),
                    )

    ax.set_xlim(-limit_x * 0.05, limit_x)
    ax.set_ylim(-limit_y * 0.05, limit_y)
    ax.set_xlabel(f"Variable ${v1}$", fontsize=10, fontweight="bold")
    ax.set_ylabel(f"Variable ${v2}$", fontsize=10, fontweight="bold")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8.0)
    fig.tight_layout()

    return fig


def plot_objective_space_2d(
    unique_solutions: List[Dict[str, Any]],
    z1_name: str = "Z1",
    z2_name: str = "Z2",
    z1_sense: Sense = Sense.MAXIMIZE,
    z2_sense: Sense = Sense.MAXIMIZE,
) -> plt.Figure:
    """
    Genera el grafico 2D del espacio de objetivos con la aproximacion discreta de soluciones.
    """
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=150)

    nd_solutions = [s for s in unique_solutions if "no dominada" in s.get("pareto_status", "").lower()]
    d_solutions = [s for s in unique_solutions if "no dominada" not in s.get("pareto_status", "").lower()]

    # Trazar linea conectora entre soluciones no dominadas (ordenadas por Z1)
    if nd_solutions:
        sorted_nd = sorted(nd_solutions, key=lambda s: s["Z1"])
        ax.plot([s["Z1"] for s in sorted_nd], [s["Z2"] for s in sorted_nd],
                color="#1f77b4", linestyle="--", linewidth=1.5,
                label="Aproximacion discreta obtenida (no dominadas)", zorder=2)

    # Dibujar puntos no dominados
    for s in nd_solutions:
        if is_finite_number(s.get("Z1")) and is_finite_number(s.get("Z2")):
            ax.scatter(s["Z1"], s["Z2"], color="#d62728", s=100, zorder=4, edgecolor="black")
            weights_str = "\n".join(
                f"a=({w['alpha1']:.2g}, {w['alpha2']:.2g})" for w in s.get("generated_by_weights", [])
            )
            ax.annotate(
                f"Solucion {s['id']}\nZ=({s['Z1']:.1f}, {s['Z2']:.1f})\n{weights_str}",
                (s["Z1"], s["Z2"]), textcoords="offset points", xytext=(12, 10),
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.3", fc="#f8f9fa", ec="#cccccc", alpha=0.9),
                arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#666666"),
            )

    # Dibujar puntos dominados si los hubiera
    for s in d_solutions:
        if is_finite_number(s.get("Z1")) and is_finite_number(s.get("Z2")):
            ax.scatter(s["Z1"], s["Z2"], color="#7f7f7f", s=70, zorder=3, marker="s", edgecolor="black")
            ax.annotate(
                f"Solucion {s['id']} (Dominada)\nZ=({s['Z1']:.1f}, {s['Z2']:.1f})",
                (s["Z1"], s["Z2"]), textcoords="offset points", xytext=(12, -15),
                fontsize=8.0,
                bbox=dict(boxstyle="round,pad=0.2", fc="#eeeeee", ec="#aaaaaa", alpha=0.8),
            )

    s1_str = "MAX" if z1_sense == Sense.MAXIMIZE else "MIN"
    s2_str = "MAX" if z2_sense == Sense.MAXIMIZE else "MIN"

    ax.set_xlabel(f"Objetivo {z1_name} [{s1_str}]", fontsize=10, fontweight="bold")
    ax.set_ylabel(f"Objetivo {z2_name} [{s2_str}]", fontsize=10, fontweight="bold")
    ax.set_title("Espacio de objetivos: Aproximacion discreta de soluciones", fontsize=11, fontweight="bold", pad=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="best", fontsize=8.0)
    fig.tight_layout()

    return fig
