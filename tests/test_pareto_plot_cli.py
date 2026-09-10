"""Pruebas semánticas del gráfico de Pareto generado por solve_model.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import solver_optimizador.pareto_plot as plot_module

from solver_optimizador import (
    build_annotation_layout,
    build_biobjective_plot_text,
    build_biobjective_problem_from_state,
    deserialize_model,
    prepare_pareto_plot_data,
    save_pareto_plot,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
)


ROOT = Path(__file__).resolve().parents[1]
HYDRO = ROOT / "models" / "hidroelectrica_biobjetivo.json"
RUNNER = ROOT / "scripts" / "solve_model.py"


def _runner_module():
    spec = importlib.util.spec_from_file_location("solve_model_plot_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hydro_problem():
    state = deserialize_model(HYDRO.read_text(encoding="utf-8"))
    return build_biobjective_problem_from_state(
        var_names=state["var_names"],
        obj1_sense=state["obj1_sense"],
        obj1_coeffs=state["obj1_coeffs"],
        obj2_sense=state["obj2_sense"],
        obj2_coeffs=state["obj2_coeffs"],
        canonical_constraints=state["constraints_data"],
        obj1_name=state["objectives"][0]["name"],
        obj2_name=state["objectives"][1]["name"],
    )


def test_datos_epsilon_contienen_siete_puntos_y_etiquetas() -> None:
    result = solve_biobjective_epsilon_constraint(
        _hydro_problem(), primary_objective=1, r=6
    )
    points = prepare_pareto_plot_data(result, "epsilon")
    assert len(points) == 7
    assert [point["Z1"] for point in points] == pytest.approx(
        [6701.25, 9153.75, 11606.25, 14058.75, 16511.25, 18963.75, 21416.25]
    )
    assert [point["Z2"] for point in points] == pytest.approx(
        [40, 50, 60, 70, 80, 90, 100]
    )
    assert [point["label"] for point in points] == [
        f"S{index}\nE={epsilon}"
        for index, epsilon in enumerate(
            (40, 50, 60, 70, 80, 90, 100), start=1
        )
    ]
    assert all(point["nondominated"] for point in points)


def test_textos_descriptivos_titulo_y_leyendas() -> None:
    problem = _hydro_problem()
    text = build_biobjective_plot_text(
        problem, "epsilon", "Generación hidroeléctrica"
    )

    assert problem.objective1.name == "Costo de generación térmica"
    assert problem.objective2.name == "Volumen final del embalse V4 (UH)"
    assert text["xlabel"] == "Z1 — Costo de generación térmica (MIN)"
    assert text["ylabel"] == "Z2 — Volumen final del embalse V4 (UH) (MAX)"
    assert text["title"] == (
        "Frontera de Pareto — Generación hidroeléctrica\n"
        "Método de las restricciones | Z1 MIN · Z2 MAX"
    )
    assert text["nondominated_legend"] == (
        "Soluciones no dominadas obtenidas"
    )
    assert text["dominated_legend"] == "Soluciones dominadas obtenidas"


def test_etiqueta_superior_derecha_se_orienta_hacia_el_interior() -> None:
    result = solve_biobjective_epsilon_constraint(
        _hydro_problem(), primary_objective=1, r=6
    )
    points = prepare_pareto_plot_data(result, "epsilon")
    layout = build_annotation_layout(points, "Z1", "Z2")
    upper_right = layout[-1]

    assert upper_right["id"] == "S7"
    assert upper_right["offset"][0] < 0
    assert upper_right["offset"][1] < 0
    assert upper_right["horizontal_alignment"] == "right"
    assert upper_right["vertical_alignment"] == "top"


def test_png_aplica_textos_y_posicion_semantica(
    tmp_path: Path, monkeypatch
) -> None:
    problem = _hydro_problem()
    result = solve_biobjective_epsilon_constraint(
        problem, primary_objective=1, r=6
    )
    captured = {}
    original_subplots = plot_module.plt.subplots
    original_close = plot_module.plt.close

    def capture_subplots(*args, **kwargs):
        figure, axis = original_subplots(*args, **kwargs)
        captured["figure"] = figure
        captured["axis"] = axis
        return figure, axis

    monkeypatch.setattr(plot_module.plt, "subplots", capture_subplots)
    monkeypatch.setattr(plot_module.plt, "close", lambda figure: None)
    output = tmp_path / "pareto.png"
    plot_module.save_pareto_plot(
        problem, result, "epsilon", "Generación hidroeléctrica", output
    )

    axis = captured["axis"]
    assert axis.get_title().startswith(
        "Frontera de Pareto — Generación hidroeléctrica"
    )
    assert axis.get_xlabel() == "Z1 — Costo de generación térmica (MIN)"
    assert axis.get_ylabel() == "Z2 — Volumen final del embalse V4 (UH) (MAX)"
    assert "Soluciones no dominadas obtenidas" in (
        axis.get_legend_handles_labels()[1]
    )
    s7_annotation = next(text for text in axis.texts if text.get_text() == "S7\nE=100")
    assert s7_annotation.get_position()[0] < 0
    assert s7_annotation.get_position()[1] < 0
    assert output.stat().st_size > 10_000
    original_close(captured["figure"])


def test_png_se_crea_con_nombre_esperado_y_no_esta_vacio(tmp_path: Path) -> None:
    problem = _hydro_problem()
    result = solve_biobjective_epsilon_constraint(problem, primary_objective=1, r=6)
    output = tmp_path / "hidroelectrica_biobjetivo_epsilon_pareto.png"
    saved, points = save_pareto_plot(
        problem,
        result,
        "epsilon",
        "Generación Hidroeléctrica",
        output,
    )
    assert saved.name == "hidroelectrica_biobjetivo_epsilon_pareto.png"
    assert saved.is_file()
    assert saved.stat().st_size > 10_000
    assert len(points) == 7


def test_etiquetas_ponderadas_incluyen_id_y_alpha1() -> None:
    result = solve_biobjective_weighted(_hydro_problem(), num_combinations=6)
    points = prepare_pareto_plot_data(result, "weighted")
    assert points
    assert points[0]["label"].startswith("A\nα1=0")
    assert all("α1=" in point["label"] for point in points)


def test_png_ponderado_tambien_se_genera(tmp_path: Path) -> None:
    problem = _hydro_problem()
    result = solve_biobjective_weighted(problem, num_combinations=6)
    points_before_plot = prepare_pareto_plot_data(result, "weighted")
    layout = build_annotation_layout(points_before_plot, "Z1", "Z2")
    output = tmp_path / "hidroelectrica_biobjetivo_weighted_pareto.png"
    saved, points = save_pareto_plot(
        problem,
        result,
        "weighted",
        "Generación Hidroeléctrica",
        output,
    )
    assert saved == output
    assert saved.stat().st_size > 10_000
    assert len(points) == len(result.unique_solutions)
    assert "Método de ponderaciones normalizadas" in (
        build_biobjective_plot_text(problem, "weighted", "Modelo")["title"]
    )
    repeated_positions = [
        position["offset"]
        for point, position in zip(points_before_plot, layout)
        if point["Z1"] == pytest.approx(21416.25)
        and point["Z2"] == pytest.approx(100.0)
    ]
    assert len(repeated_positions) == len(set(repeated_positions))


def test_runner_usa_titulo_corto_sin_perder_nombre_completo() -> None:
    runner = _runner_module()
    state = deserialize_model(HYDRO.read_text(encoding="utf-8"))
    full_name = state["metadata"]["name"]

    assert "Biobjetivo Corregida" in full_name
    assert runner._plot_display_name(state, full_name) == (
        "Generación hidroeléctrica"
    )


def test_runner_genera_png_por_defecto(tmp_path: Path, monkeypatch, capsys) -> None:
    runner = _runner_module()
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    exit_code = runner.main(
        [str(HYDRO), "--method", "epsilon", "--primary", "1", "--r", "6"]
    )
    output = tmp_path / "results" / "hidroelectrica_biobjetivo_epsilon_pareto.png"
    captured = capsys.readouterr()
    assert exit_code == 0
    assert output.is_file() and output.stat().st_size > 0
    assert "Gráfico de Pareto guardado en:" in captured.out
    assert "Puntos representados: 7" in captured.out


def test_no_plot_evitar_generacion(tmp_path: Path, monkeypatch, capsys) -> None:
    runner = _runner_module()
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("save_pareto_plot no debe ejecutarse con --no-plot")

    monkeypatch.setattr(runner, "save_pareto_plot", fail_if_called)
    exit_code = runner.main(
        [str(HYDRO), "--method", "weighted", "--num-weights", "6", "--no-plot"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    results = tmp_path / "results"
    assert not list(results.glob("*.png"))
    assert (results / "hidroelectrica_biobjetivo_weighted.xlsx").is_file()
    assert "Gráfico de Pareto guardado" not in captured.out
    assert "Libro Excel de resultados guardado en:" in captured.out


def test_help_documenta_no_plot() -> None:
    help_text = _runner_module().build_parser().format_help()
    assert "--no-plot" in help_text
    assert "gráfico PNG" in help_text
