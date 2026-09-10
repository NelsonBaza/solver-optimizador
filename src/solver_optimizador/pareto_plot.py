"""Gráficos PNG reproducibles para resultados biobjetivo de consola."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402

from .epsilon_constraint import EpsilonConstraintSolution
from .lp_models import (
    BiobjectiveProblem,
    MultiobjectiveProblem,
    MultiobjectiveSolution,
    Sense,
)
from .multiobjective_epsilon import MultiobjectiveEpsilonSolution


def _compact(value: float) -> str:
    return f"{value:.8g}"


def _is_nondominated(solution: dict[str, Any]) -> bool:
    return solution.get("pareto_status") == "No dominada"


def prepare_pareto_plot_data(
    result: EpsilonConstraintSolution | MultiobjectiveSolution,
    method: str,
) -> list[dict[str, Any]]:
    """Convierte soluciones válidas únicas en puntos etiquetados para el gráfico."""

    if method not in ("epsilon", "weighted"):
        raise ValueError("method debe ser 'epsilon' o 'weighted'.")
    points: list[dict[str, Any]] = []
    for solution in result.unique_solutions:
        if solution.get("x") is None or solution.get("Z1") is None or solution.get("Z2") is None:
            continue
        if method == "epsilon":
            levels = solution.get("epsilon_levels", [])
            level_text = ",".join(_compact(float(value)) for value in levels)
            label = f"{solution['id']}\nE={level_text}"
            source = {"epsilon_levels": list(levels)}
        else:
            weights = solution.get("generated_by_weights", [])
            alpha_values = [float(item["alpha1"]) for item in weights]
            alpha_text = ",".join(_compact(value) for value in alpha_values)
            label = f"{solution['id']}\nα1={alpha_text}"
            source = {"alpha1_values": alpha_values}
        points.append(
            {
                "id": solution["id"],
                "Z1": float(solution["Z1"]),
                "Z2": float(solution["Z2"]),
                "label": label,
                "nondominated": _is_nondominated(solution),
                **source,
            }
        )
    return points


def _sense_text(sense: Sense) -> str:
    return "MAX" if sense == Sense.MAXIMIZE else "MIN"


def build_annotation_layout(
    points: list[dict[str, Any]],
    x_key: str,
    y_key: str,
) -> list[dict[str, Any]]:
    """Calcula offsets deterministas orientados hacia el interior del gráfico."""

    if not points:
        return []
    x_values = [float(point[x_key]) for point in points]
    y_values = [float(point[y_key]) for point in points]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    x_range = x_max - x_min
    y_range = y_max - y_min
    repeated_coordinates: dict[tuple[float, float], int] = {}
    layout: list[dict[str, Any]] = []

    for index, point in enumerate(points):
        x_value = float(point[x_key])
        y_value = float(point[y_key])
        x_ratio = 0.5 if x_range == 0.0 else (x_value - x_min) / x_range
        y_ratio = 0.5 if y_range == 0.0 else (y_value - y_min) / y_range

        if x_ratio <= 0.2:
            dx, horizontal_alignment = 10, "left"
        elif x_ratio >= 0.8:
            dx, horizontal_alignment = -10, "right"
        elif index % 2 == 0:
            dx, horizontal_alignment = 10, "left"
        else:
            dx, horizontal_alignment = -10, "right"

        if y_ratio <= 0.2:
            dy, vertical_alignment = 12, "bottom"
        elif y_ratio >= 0.8:
            dy, vertical_alignment = -12, "top"
        elif index % 4 < 2:
            dy, vertical_alignment = 12, "bottom"
        else:
            dy, vertical_alignment = -12, "top"

        coordinate = (round(x_value, 9), round(y_value, 9))
        occurrence = repeated_coordinates.get(coordinate, 0)
        repeated_coordinates[coordinate] = occurrence + 1
        if occurrence:
            dy += (38 * occurrence) if dy > 0 else (-38 * occurrence)

        layout.append(
            {
                "id": point.get("id"),
                "offset": (dx, dy),
                "horizontal_alignment": horizontal_alignment,
                "vertical_alignment": vertical_alignment,
            }
        )
    return layout


def build_biobjective_plot_text(
    problem: BiobjectiveProblem,
    method: str,
    model_name: str,
) -> dict[str, str]:
    """Construye textos académicos sin duplicar identificadores y nombres."""

    if method not in ("epsilon", "weighted"):
        raise ValueError("method debe ser 'epsilon' o 'weighted'.")
    method_name = (
        "Método de las restricciones"
        if method == "epsilon"
        else "Método de ponderaciones normalizadas"
    )
    return {
        "title": (
            f"Frontera de Pareto — {model_name}\n"
            f"{method_name} | "
            f"Z1 {_sense_text(problem.objective1.sense)} · "
            f"Z2 {_sense_text(problem.objective2.sense)}"
        ),
        "xlabel": _objective_axis_label("Z1", problem.objective1.name, problem.objective1.sense),
        "ylabel": _objective_axis_label("Z2", problem.objective2.name, problem.objective2.sense),
        "dominated_legend": "Soluciones dominadas obtenidas",
        "nondominated_legend": "Soluciones no dominadas obtenidas",
    }


def _objective_axis_label(identifier: str, name: str, sense: Sense) -> str:
    clean_name = str(name).strip()
    prefix = identifier
    if clean_name and clean_name.casefold() != identifier.casefold():
        prefix = f"{identifier} — {clean_name}"
    return f"{prefix} ({_sense_text(sense)})"


def save_pareto_plot(
    problem: BiobjectiveProblem,
    result: EpsilonConstraintSolution | MultiobjectiveSolution,
    method: str,
    model_name: str,
    output_path: str | Path,
) -> tuple[Path, list[dict[str, Any]]]:
    """Guarda el espacio Z1-Z2 sin abrir una ventana y devuelve sus puntos."""

    points = prepare_pareto_plot_data(result, method)
    if not points:
        raise ValueError("No hay soluciones válidas para construir el gráfico de Pareto.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 6.5))
    plot_text = build_biobjective_plot_text(problem, method, model_name)

    dominated = [point for point in points if not point["nondominated"]]
    nondominated = [point for point in points if point["nondominated"]]
    if dominated:
        axis.scatter(
            [point["Z1"] for point in dominated],
            [point["Z2"] for point in dominated],
            color="#7f8c8d",
            marker="x",
            s=60,
            label=plot_text["dominated_legend"],
            zorder=3,
        )
    if nondominated:
        ordered = sorted(nondominated, key=lambda point: (point["Z1"], point["Z2"]))
        axis.plot(
            [point["Z1"] for point in ordered],
            [point["Z2"] for point in ordered],
            color="#1f77b4",
            linewidth=1.4,
            alpha=0.75,
            zorder=2,
        )
        axis.scatter(
            [point["Z1"] for point in ordered],
            [point["Z2"] for point in ordered],
            color="#d62728",
            edgecolor="white",
            linewidth=0.8,
            s=72,
            label=plot_text["nondominated_legend"],
            zorder=4,
        )

    annotation_layout = build_annotation_layout(points, "Z1", "Z2")
    for point, position in zip(points, annotation_layout):
        dx, dy = position["offset"]
        axis.annotate(
            point["label"],
            xy=(point["Z1"], point["Z2"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8,
            ha=position["horizontal_alignment"],
            va=position["vertical_alignment"],
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "#bbbbbb", "alpha": 0.9},
            arrowprops={"arrowstyle": "-", "color": "#999999", "lw": 0.6},
            zorder=5,
        )

    axis.set_title(plot_text["title"])
    axis.set_xlabel(plot_text["xlabel"])
    axis.set_ylabel(plot_text["ylabel"])
    axis.margins(x=0.06, y=0.1)
    axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(
        output,
        format="png",
        dpi=160,
        bbox_inches="tight",
        pad_inches=0.2,
    )
    plt.close(figure)
    return output, points


def save_multiobjective_projection_plots(
    problem: MultiobjectiveProblem,
    result: MultiobjectiveEpsilonSolution,
    model_name: str,
    output_directory: str | Path,
    model_stem: str,
) -> list[tuple[Path, list[dict[str, Any]]]]:
    """Guarda proyecciones 2D sin reinterpretar la dominancia global."""

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    primary = result.primary_objective
    generated: list[tuple[Path, list[dict[str, Any]]]] = []
    for constrained in result.constrained_objectives:
        x_label = f"Z{primary}"
        y_label = f"Z{constrained}"
        points = [
            {
                "id": solution["id"],
                "x": float(solution["objective_values"][x_label]),
                "y": float(solution["objective_values"][y_label]),
                "nondominated": _is_nondominated(solution),
            }
            for solution in result.unique_solutions
            if solution.get("objective_values") is not None
        ]
        if not points:
            continue

        figure, axis = plt.subplots(figsize=(10, 6.5))
        dominated = [point for point in points if not point["nondominated"]]
        nondominated = [point for point in points if point["nondominated"]]
        if dominated:
            axis.scatter(
                [point["x"] for point in dominated],
                [point["y"] for point in dominated],
                color="#7f8c8d",
                marker="x",
                s=60,
                label="Soluciones dominadas obtenidas (globalmente)",
                zorder=3,
            )
        if nondominated:
            ordered = sorted(nondominated, key=lambda point: (point["x"], point["y"]))
            axis.scatter(
                [point["x"] for point in ordered],
                [point["y"] for point in ordered],
                color="#d62728",
                edgecolor="white",
                linewidth=0.8,
                s=72,
                label="Soluciones no dominadas obtenidas (globalmente)",
                zorder=4,
            )

        annotation_layout = build_annotation_layout(points, "x", "y")
        for point, position in zip(points, annotation_layout):
            dx, dy = position["offset"]
            axis.annotate(
                point["id"],
                xy=(point["x"], point["y"]),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=8,
                ha=position["horizontal_alignment"],
                va=position["vertical_alignment"],
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "alpha": 0.9},
                zorder=5,
            )

        primary_objective = problem.objectives[primary - 1]
        constrained_objective = problem.objectives[constrained - 1]
        axis.set_title(
            f"Proyección de soluciones multiobjetivo — {model_name}\n"
            f"Dominancia evaluada en {len(problem.objectives)} dimensiones"
        )
        axis.set_xlabel(
            _objective_axis_label(
                x_label, primary_objective.name, primary_objective.sense
            )
        )
        axis.set_ylabel(
            _objective_axis_label(
                y_label, constrained_objective.name, constrained_objective.sense
            )
        )
        axis.margins(x=0.06, y=0.1)
        axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45)
        axis.legend(loc="best")
        figure.tight_layout()
        output = output_dir / (
            f"{model_stem}_epsilon_{x_label}_vs_{y_label}.png"
        )
        figure.savefig(
            output,
            format="png",
            dpi=160,
            bbox_inches="tight",
            pad_inches=0.2,
        )
        plt.close(figure)
        generated.append((output, points))
    return generated
