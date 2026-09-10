"""Pruebas del flujo interactivo y del modo avanzado N-objetivo."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "solve_model.py"
MODEL_3 = ROOT / "models" / "ejemplo_tres_objetivos.json"


def _runner_module():
    spec = importlib.util.spec_from_file_location("interactive_runner_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def model2(tmp_path: Path) -> Path:
    document = json.loads(MODEL_3.read_text(encoding="utf-8"))
    document["metadata"]["name"] = "Ejemplo biobjetivo interactivo"
    document["problem"]["type"] = "Biobjetivo"
    document["problem"]["objectives"] = document["problem"]["objectives"][:2]
    path = tmp_path / "biobjetivo.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _answers(*values: str):
    iterator = iter(values)

    def answer(prompt: str) -> str:
        return next(iterator)

    return answer


def test_interactivo_selecciona_epsilon_y_z1(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("2", "1", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "SOLVER MULTIOBJETIVO" in output
    assert "Método: Método de las restricciones" in output
    assert "Objetivo principal: Z1" in output


def test_interactivo_selecciona_z2_como_principal(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("2", "2", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "Objetivo principal: Z2" in output
    assert "Objetivo restringido: Z1" in output


def test_interactivo_selecciona_ponderaciones(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("1", "2", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "Método: Método de ponderaciones" in output
    assert "Tabla completa de las 2 corridas" in output


def test_interactivo_multiobjetivo_fuerza_epsilon_y_admite_z3(capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(MODEL_3), "--no-plot"],
        input_func=_answers("3", "1", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "más de dos objetivos" in output
    assert "Objetivo principal: Z3" in output
    assert "Número total de corridas:" in output


def test_metodo_invalido_reintenta(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("9", "x", "2", "1", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.count("Opción no válida") == 2


def test_objetivo_invalido_reintenta(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("2", "0", "3", "1", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.count("Objetivo no válido") == 2


def test_r_invalido_reintenta(model2, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("2", "1", "0", "-1", "abc", "1", "s"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.count("Valor no válido") == 3


@pytest.mark.parametrize("confirmation", ["S", "s", ""])
def test_confirmaciones_afirmativas(model2, confirmation, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("2", "1", "1", confirmation),
        stdin_is_tty=True,
    )
    assert code == 0
    assert "Iniciando resolución" in capsys.readouterr().out


def test_cancelacion_no_invoca_solver(model2, monkeypatch, capsys) -> None:
    runner = _runner_module()

    def fail(*args, **kwargs):
        raise AssertionError("El solver no debe ejecutarse después de N")

    monkeypatch.setattr(runner, "_solve_weighted", fail)
    code = runner.main(
        [str(model2), "--no-plot"],
        input_func=_answers("1", "2", "n"),
        stdin_is_tty=True,
    )
    assert code == 0
    assert "no se llamó al solver" in capsys.readouterr().out.lower()


def test_configuracion_grande_advierte_y_permite_cancelar(capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(MODEL_3), "--no-plot"],
        input_func=_answers("1", "22", "22", "n"),
        stdin_is_tty=True,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "ADVERTENCIA" in output
    assert "529 resoluciones" in output
    assert "no se llamó al solver" in output.lower()


def test_stdin_no_tty_sin_method_falla_sin_bloquear() -> None:
    process = subprocess.run(
        [sys.executable, str(RUNNER), str(MODEL_3), "--no-plot"],
        cwd=ROOT,
        input="",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 2
    assert "--method es obligatorio" in process.stderr


def test_modo_avanzado_no_pregunta(model2, capsys) -> None:
    runner = _runner_module()

    def fail_input(prompt: str) -> str:
        raise AssertionError("El modo avanzado no debe pedir input")

    code = runner.main(
        [
            str(model2),
            "--method",
            "epsilon",
            "--primary",
            "1",
            "--r",
            "1",
            "--no-plot",
        ],
        input_func=fail_input,
        stdin_is_tty=True,
    )
    assert code == 0
    assert "Tabla completa de las 2 corridas" in capsys.readouterr().out


def test_no_plot_multiobjetivo_no_genera_proyecciones(monkeypatch, capsys) -> None:
    runner = _runner_module()

    def fail(*args, **kwargs):
        raise AssertionError("--no-plot debe omitir todas las proyecciones")

    monkeypatch.setattr(runner, "save_multiobjective_projection_plots", fail)
    code = runner.main(
        [
            str(MODEL_3),
            "--method",
            "epsilon",
            "--primary",
            "1",
            "--r",
            "1",
            "--no-plot",
        ]
    )
    assert code == 0
    assert "Proyecciones de soluciones" not in capsys.readouterr().out


def test_r_global_y_sobrescritura_por_objetivo(capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [
            str(MODEL_3),
            "--method",
            "epsilon",
            "--primary",
            "1",
            "--r",
            "2",
            "--r-objective",
            "2=1",
            "--no-plot",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "Z2: r=1" in output
    assert "Z3: r=2" in output
    assert "Número total de corridas: 6" in output


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--primary", "1", "--r-objective", "1=2"], "objetivo principal Z1"),
        (["--primary", "1", "--r-objective", "4=2"], "Objetivo inexistente"),
        (
            ["--primary", "1", "--r-objective", "2=2", "--r-objective", "2=3"],
            "contradictorios",
        ),
    ],
)
def test_r_objective_invalido(arguments, message, capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(MODEL_3), "--method", "epsilon", *arguments, "--no-plot"]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert message in captured.err


def test_ponderaciones_rechaza_tres_objetivos(capsys) -> None:
    runner = _runner_module()
    code = runner.main(
        [str(MODEL_3), "--method", "weighted", "--no-plot"]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "exactamente dos objetivos" in captured.err
