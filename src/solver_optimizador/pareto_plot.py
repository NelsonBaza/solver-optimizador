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

    dominated = [point for point in points if not point["nondominated"]]
    nondominated = [point for point in points if point["nondominated"]]
    if dominated:
        axis.scatter(
            [point["Z1"] for point in dominated],
            [point["Z2"] for point in dominated],
            color="#7f8c8d",
            marker="x",
            s=60,
            label="Solución dominada",
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
            label="Solución no dominada",
            zorder=4,
        )

    offsets = ((8, 14), (8, -24), (-38, 14), (-38, -24))
    for index, point in enumerate(points):
        dx, dy = offsets[index % len(offsets)]
        dy += 5 * (index // len(offsets))
        axis.annotate(
            point["label"],
            xy=(point["Z1"], point["Z2"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8,
            ha="left" if dx > 0 else "right",
            va="center",
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "#bbbbbb", "alpha": 0.9},
            arrowprops={"arrowstyle": "-", "color": "#999999", "lw": 0.6},
            zorder=5,
        )

    method_name = "ε-constraint" if method == "epsilon" else "ponderaciones normalizadas"
    axis.set_title(
        f"Frontera de Pareto — {model_name}\n"
        f"{method_name} | Z1 ({_sense_text(problem.objective1.sense)}) · "
        f"Z2 ({_sense_text(problem.objective2.sense)})"
    )
    axis.set_xlabel(f"Z1 — {problem.objective1.name} ({_sense_text(problem.objective1.sense)})")
    axis.set_ylabel(f"Z2 — {problem.objective2.name} ({_sense_text(problem.objective2.sense)})")
    axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(output, format="png", dpi=160, bbox_inches="tight")
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
                label="Dominada globalmente",
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
                label="No dominada globalmente",
                zorder=4,
            )

        offsets = ((8, 13), (8, -18), (-12, 13), (-12, -18))
        for index, point in enumerate(points):
            dx, dy = offsets[index % len(offsets)]
            axis.annotate(
                point["id"],
                xy=(point["x"], point["y"]),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=8,
                ha="left" if dx > 0 else "right",
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
            f"{x_label} — {primary_objective.name} "
            f"({_sense_text(primary_objective.sense)})"
        )
        axis.set_ylabel(
            f"{y_label} — {constrained_objective.name} "
            f"({_sense_text(constrained_objective.sense)})"
        )
        axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45)
        axis.legend(loc="best")
        figure.tight_layout()
        output = output_dir / (
            f"{model_stem}_epsilon_{x_label}_vs_{y_label}.png"
        )
        figure.savefig(output, format="png", dpi=160, bbox_inches="tight")
        plt.close(figure)
        generated.append((output, points))
    return generated
