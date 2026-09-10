"""Pruebas semánticas del gráfico de Pareto generado por solve_model.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from solver_optimizador import (
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
    assert points[0]["label"] == "S1\nE=40"
    assert points[-1]["label"] == "S7\nE=100"
    assert all(point["nondominated"] for point in points)


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
    assert not (tmp_path / "results").exists()
    assert "Gráfico de Pareto guardado" not in captured.out


def test_help_documenta_no_plot() -> None:
    help_text = _runner_module().build_parser().format_help()
    assert "--no-plot" in help_text
    assert "gráfico PNG" in help_text
