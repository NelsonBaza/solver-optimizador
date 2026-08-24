"""
Modulo de generacion de graficos para el espacio de variables (2D), espacio de objetivos (2D)
y graficos generales de resultados para modelos de dimension arbitraria (n >= 1).
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
    limit_x = max(max_x * 1.25, 10.0)
    limit_y = max(max_y * 1.30, 10.0)

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

    # Crear figura con proporciones legibles
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

    # Dibujar puntos de soluciones con offsets diferenciados
    if solutions:
        for idx, sol in enumerate(solutions):
            sol_id = sol.get("id", f"S{idx+1}")
            x_dict = sol.get("x", sol)
            if isinstance(x_dict, dict) and v1 in x_dict and v2 in x_dict:
                px = x_dict[v1]
                py = x_dict[v2]
                if is_finite_number(px) and is_finite_number(py):
                    ax.scatter(px, py, color="#d62728", s=90, zorder=5, edgecolor="black")
                    
                    # Offset dinamico para evitar solapamientos
                    off_x = 12 if px < limit_x * 0.7 else -70
                    off_y = 12 if py < limit_y * 0.7 else -20
                    
                    ax.annotate(
                        f"{sol_id} ({px:.1f}, {py:.1f})",
                        (px, py), textcoords="offset points", xytext=(off_x, off_y),
                        fontsize=8.5, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#333333", alpha=0.92),
                        arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9),
                    )

    ax.set_xlim(-limit_x * 0.05, limit_x)
    ax.set_ylim(-limit_y * 0.05, limit_y)
    ax.set_xlabel(f"Variable ${v1}$", fontsize=10, fontweight="bold")
    ax.set_ylabel(f"Variable ${v2}$", fontsize=10, fontweight="bold")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=16)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8.0, framealpha=0.9)
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
    Garantiza cajas compactas de texto y amplia separacion con el titulo y la leyenda.
    """
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=150)

    nd_solutions = [s for s in unique_solutions if "no dominada" in s.get("pareto_status", "").lower()]
    d_solutions = [s for s in unique_solutions if "no dominada" not in s.get("pareto_status", "").lower()]
    all_sols = nd_solutions + d_solutions

    # Calcular limites de ejes con margen holgado
    if all_sols:
        z1_vals = [s["Z1"] for s in all_sols if is_finite_number(s.get("Z1"))]
        z2_vals = [s["Z2"] for s in all_sols if is_finite_number(s.get("Z2"))]
        min_z1, max_z1 = min(z1_vals), max(z1_vals)
        min_z2, max_z2 = min(z2_vals), max(z2_vals)
        span_z1 = max_z1 - min_z1 if max_z1 > min_z1 else max(abs(max_z1), 10.0)
        span_z2 = max_z2 - min_z2 if max_z2 > min_z2 else max(abs(max_z2), 10.0)
        
        ax.set_xlim(min_z1 - span_z1 * 0.12, max_z1 + span_z1 * 0.20)
        ax.set_ylim(min_z2 - span_z2 * 0.15, max_z2 + span_z2 * 0.24)

    # Trazar linea conectora entre soluciones no dominadas (ordenadas por Z1)
    if nd_solutions:
        sorted_nd = sorted(nd_solutions, key=lambda s: s["Z1"])
        ax.plot([s["Z1"] for s in sorted_nd], [s["Z2"] for s in sorted_nd],
                color="#1f77b4", linestyle="--", linewidth=1.5,
                label="Aproximacion discreta (no dominadas)", zorder=2)

    # Dibujar puntos no dominados con formato compacto de pesos
    sorted_all_nd = sorted(nd_solutions, key=lambda s: s["Z1"]) if nd_solutions else []
    n_nd = len(sorted_all_nd)

    for idx, s in enumerate(sorted_all_nd):
        if is_finite_number(s.get("Z1")) and is_finite_number(s.get("Z2")):
            ax.scatter(s["Z1"], s["Z2"], color="#d62728", s=100, zorder=4, edgecolor="black")
            
            # Formato compacto de pesos en una sola linea
            weights_list = s.get("generated_by_weights", [])
            w_formatted = ", ".join(f"({w['alpha1']:.2g}, {w['alpha2']:.2g})" for w in weights_list)
            peso_label = "Pesos" if len(weights_list) > 1 else "Peso"
            
            text_label = f"Solucion {s['id']}\nZ = ({s['Z1']:.1f}, {s['Z2']:.1f})\n{peso_label}: {w_formatted}"
            
            # Ubicacion inteligente del offset segun posicion del punto
            if idx == 0 and n_nd > 1:
                # Punto extremo izquierdo (alto Z2, bajo Z1)
                xytext = (15, 12)
            elif idx == n_nd - 1 and n_nd > 1:
                # Punto extremo derecho (alto Z1, bajo Z2)
                xytext = (-130, 12)
            else:
                # Punto intermedio
                xytext = (15, 15)

            ax.annotate(
                text_label,
                (s["Z1"], s["Z2"]), textcoords="offset points", xytext=xytext,
                fontsize=8.0,
                bbox=dict(boxstyle="round,pad=0.35", fc="#ffffff", ec="#999999", alpha=0.93),
                arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.08", color="#555555", lw=0.9),
            )

    # Dibujar puntos dominados si los hubiera
    for s in d_solutions:
        if is_finite_number(s.get("Z1")) and is_finite_number(s.get("Z2")):
            ax.scatter(s["Z1"], s["Z2"], color="#7f7f7f", s=70, zorder=3, marker="s", edgecolor="black")
            ax.annotate(
                f"Solucion {s['id']} (Dominada)\nZ = ({s['Z1']:.1f}, {s['Z2']:.1f})",
                (s["Z1"], s["Z2"]), textcoords="offset points", xytext=(12, -20),
                fontsize=7.5,
                bbox=dict(boxstyle="round,pad=0.25", fc="#eeeeee", ec="#aaaaaa", alpha=0.85),
            )

    s1_str = "MAX" if z1_sense == Sense.MAXIMIZE else "MIN"
    s2_str = "MAX" if z2_sense == Sense.MAXIMIZE else "MIN"

    ax.set_xlabel(f"Objetivo {z1_name} [{s1_str}]", fontsize=10, fontweight="bold")
    ax.set_ylabel(f"Objetivo {z2_name} [{s2_str}]", fontsize=10, fontweight="bold")
    ax.set_title("Espacio de objetivos: Aproximacion discreta de soluciones", fontsize=11, fontweight="bold", pad=16)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower left", fontsize=8.0, framealpha=0.9)
    fig.tight_layout()

    return fig


def plot_variable_values(
    variable_values: Dict[str, float],
    title: str = "Valores optimos de variables de decision",
) -> plt.Figure:
    """
    Genera un grafico de barras con los valores optimos de las variables de decision.
    Soporta nombres personalizados y escalas dinamicas para cualquier cantidad de variables (1..100).
    """
    vars_list = list(variable_values.keys())
    vals_list = [float(variable_values[v]) for v in vars_list]

    n = len(vars_list)
    # Ancho adaptativo segun cantidad de variables
    fig_w = max(7.5, min(20.0, n * 0.45 + 2.5))
    fig, ax = plt.subplots(figsize=(fig_w, 4.8), dpi=150)

    bars = ax.bar(vars_list, vals_list, color="#1f77b4", edgecolor="#0d47a1", width=0.55, zorder=3)

    max_val = max(vals_list) if vals_list else 1.0
    min_val = min(vals_list) if vals_list else 0.0

    # Margen superior para que el texto encima de las barras no se corte
    top_limit = max(max_val * 1.22, 1.0)
    ax.set_ylim(min(0.0, min_val * 1.1), top_limit)

    # Rotacion y tamaño de fuente adaptativo
    if n <= 8:
        rot = 0
        font_sz = 8.5
    elif n <= 16:
        rot = 35
        font_sz = 7.5
    else:
        rot = 55
        font_sz = 6.8

    for bar, val in zip(bars, vals_list):
        y_pos = bar.get_height()
        if abs(val) < 1e-4:
            txt = "0"
        else:
            txt = f"{val:.4g}"
        y_offset = top_limit * 0.02
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            y_pos + y_offset,
            txt,
            ha="center",
            va="bottom",
            fontsize=font_sz,
            fontweight="bold",
            color="#333333",
            rotation=0 if n <= 14 else 90,
        )

    ax.set_xticks(range(n))
    ax.set_xticklabels(vars_list, rotation=rot, ha="right" if rot > 0 else "center", fontsize=font_sz + 0.5)
    ax.set_xlabel("Variables de Decision", fontsize=10, fontweight="bold")
    ax.set_ylabel("Valor Optimo", fontsize=10, fontweight="bold")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=14)
    ax.grid(axis="y", linestyle=":", alpha=0.6, zorder=0)
    fig.tight_layout()

    return fig


def plot_constraint_slacks(
    constraint_results: List[Any],
    title: str = "Analisis de holguras por restriccion",
) -> plt.Figure:
    """
    Genera un grafico de barras horizontal con las holguras de cada restriccion.
    Distingue visualmente las restricciones activas (holgura = 0) de las no activas.
    Soporta dinamicamente desde 1 hasta 50+ restricciones.
    """
    names = []
    slacks = []
    is_actives = []
    for i, cr in enumerate(constraint_results):
        if isinstance(cr, dict):
            n = str(cr.get("name", f"R_{i+1}"))
            s = float(cr.get("slack", 0.0))
            act = bool(cr.get("is_active", abs(s) < 1e-5))
        else:
            n = str(getattr(cr, "name", f"R_{i+1}"))
            s = float(getattr(cr, "slack", 0.0))
            act = bool(getattr(cr, "is_active", abs(s) < 1e-5))
        names.append(n)
        slacks.append(s)
        is_actives.append(act)

    n = len(names)
    fig_h = max(4.5, min(22.0, n * 0.38 + 1.8))
    fig, ax = plt.subplots(figsize=(8.0, fig_h), dpi=150)

    y_pos = np.arange(len(names))
    colors = ["#d62728" if act else "#2ca02c" for act in is_actives]

    bars = ax.barh(y_pos, slacks, color=colors, edgecolor="#333333", height=0.60, zorder=3)
    
    # Tamaño de fuente adaptativo para nombres de restricciones
    font_sz = max(6.5, min(8.5, 160.0 / max(n, 1)))
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=font_sz)
    ax.invert_yaxis()  # Primera restriccion arriba

    max_slack = max(slacks) if slacks else 1.0
    ax.set_xlim(0, max(max_slack * 1.30, 1.0))

    for bar, slack, act in zip(bars, slacks, is_actives):
        w = bar.get_width()
        if act:
            lbl = "Activa (holgura = 0)"
            col = "#b71c1c"
        else:
            lbl = f"Holgura: {slack:.4g}"
            col = "#1b5e20"
        ax.text(
            w + max_slack * 0.02,
            bar.get_y() + bar.get_height() / 2.0,
            lbl,
            va="center",
            ha="left",
            fontsize=font_sz,
            fontweight="bold",
            color=col,
        )

    # Leyenda indicativa
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#d62728", edgecolor="#333333", label="Restriccion Activa (Limite efectivo)"),
        Patch(facecolor="#2ca02c", edgecolor="#333333", label="Con Holgura (Capacidad excedente)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8.0, framealpha=0.9)

    ax.set_xlabel("Holgura Calculada (Slack)", fontsize=10, fontweight="bold")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=14)
    ax.grid(axis="x", linestyle=":", alpha=0.6, zorder=0)
    fig.tight_layout()

    return fig


def plot_multiobjective_runs(
    weighted_runs: List[Dict[str, Any]],
    z1_name: str = "Z1",
    z2_name: str = "Z2",
) -> plt.Figure:
    """
    Genera dos subgraficos verticales mostrando la evolucion de Z1 y Z2 frente al peso alpha1.
    Evita problemas de escalas dispares manteniendo cada objetivo en su propio eje.
    """
    valid_runs = [r for r in weighted_runs if r.get("Z1") is not None and r.get("Z2") is not None]
    if not valid_runs:
        fig, ax = plt.subplots(figsize=(7.0, 4.0), dpi=150)
        ax.text(0.5, 0.5, "No hay corridas validas para graficar", ha="center", va="center")
        return fig

    a1_vals = [r["alpha1"] for r in valid_runs]
    z1_vals = [r["Z1"] for r in valid_runs]
    z2_vals = [r["Z2"] for r in valid_runs]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 6.0), dpi=150, sharex=True)

    # Grafico Z1
    ax1.plot(a1_vals, z1_vals, marker="o", color="#1f77b4", linewidth=1.8, markersize=6, label=f"Objetivo {z1_name}")
    for a1, z1 in zip(a1_vals, z1_vals):
        ax1.annotate(f"{z1:.1f}", (a1, z1), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5)
    ax1.set_ylabel(f"Valor {z1_name}", fontsize=9.5, fontweight="bold")
    ax1.set_title(f"Sensibilidad de {z1_name} y {z2_name} frente a la ponderacion $\\alpha_1$", fontsize=11, fontweight="bold", pad=12)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="best", fontsize=8.0)

    # Grafico Z2
    ax2.plot(a1_vals, z2_vals, marker="s", color="#ff7f0e", linewidth=1.8, markersize=6, label=f"Objetivo {z2_name}")
    for a1, z2 in zip(a1_vals, z2_vals):
        ax2.annotate(f"{z2:.1f}", (a1, z2), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5)
    ax2.set_xlabel("Ponderacion $\\alpha_1$ (Peso de $Z_1$)", fontsize=9.5, fontweight="bold")
    ax2.set_ylabel(f"Valor {z2_name}", fontsize=9.5, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="best", fontsize=8.0)

    fig.tight_layout()
    return fig
