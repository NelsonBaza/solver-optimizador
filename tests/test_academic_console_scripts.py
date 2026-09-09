"""Comparación y portabilidad de los dos scripts académicos autónomos."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from solver_optimizador import (
    build_biobjective_problem_from_state,
    deserialize_model,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
)


ROOT = Path(__file__).resolve().parents[1]
EPSILON_SCRIPT = ROOT / "exports" / "metodo_restricciones.py"
WEIGHTED_SCRIPT = ROOT / "exports" / "metodo_ponderaciones.py"
HYDRO_MODEL = ROOT / "models" / "hidroelectrica_biobjetivo.json"


def _importar_script(ruta: Path, nombre: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


EPSILON = _importar_script(EPSILON_SCRIPT, "metodo_restricciones_academico")
WEIGHTED = _importar_script(WEIGHTED_SCRIPT, "metodo_ponderaciones_academico")


def _documento(
    nombre: str,
    variables: list[str],
    sentido1: str,
    coeficientes1: dict[str, float],
    sentido2: str,
    coeficientes2: dict[str, float],
    restricciones: list[dict],
) -> dict:
    return {
        "schema_version": "1.0",
        "metadata": {"name": nombre, "description": "Fixture versionado en tests"},
        "problem": {
            "type": "Biobjetivo",
            "num_vars": len(variables),
            "variables": variables,
            "bio_objectives": {
                "obj1": {"sense": sentido1, "coefficients": coeficientes1},
                "obj2": {"sense": sentido2, "coefficients": coeficientes2},
            },
            "constraints": restricciones,
        },
    }


MODELOS = {
    "benchmark_a": _documento(
        "Benchmark A",
        ["X1", "X2"],
        "Maximizar",
        {"X1": 10.0, "X2": 3.0},
        "Maximizar",
        {"X1": 0.8, "X2": 1.3},
        [
            {"name": "R1", "coefficients": {"X1": 1.0, "X2": 1.0}, "operator": "<=", "rhs": 130.0},
            {"name": "R2", "coefficients": {"X1": 2.5, "X2": 1.0}, "operator": "<=", "rhs": 250.0},
        ],
    ),
    "artificial_max_max": _documento(
        "Artificial MAX MAX",
        ["x", "y"],
        "Maximizar",
        {"x": 1.0},
        "Maximizar",
        {"y": 1.0},
        [
            {"name": "R1", "coefficients": {"x": 2.0, "y": 1.0}, "operator": "<=", "rhs": 12.0},
            {"name": "R2", "coefficients": {"x": 1.0, "y": 2.0}, "operator": "<=", "rhs": 12.0},
        ],
    ),
    "artificial_max_min": _documento(
        "Artificial MAX MIN",
        ["x"],
        "Maximizar",
        {"x": 1.0},
        "Minimizar",
        {"x": 1.0},
        [
            {"name": "Cota", "coefficients": {"x": 1.0}, "operator": "<=", "rhs": 10.0},
        ],
    ),
}


def _guardar(documento: dict, ruta: Path) -> Path:
    ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def _problema_oficial(ruta: Path):
    estado = deserialize_model(ruta.read_text(encoding="utf-8"))
    return build_biobjective_problem_from_state(
        var_names=estado["var_names"],
        obj1_sense=estado["obj1_sense"],
        obj1_coeffs=estado["obj1_coeffs"],
        obj2_sense=estado["obj2_sense"],
        obj2_coeffs=estado["obj2_coeffs"],
        canonical_constraints=estado["constraints_data"],
    )


def _rutas_modelos(tmp_path: Path) -> list[tuple[str, Path]]:
    rutas = [("hidroelectrica", HYDRO_MODEL)]
    for nombre, documento in MODELOS.items():
        rutas.append((nombre, _guardar(documento, tmp_path / f"{nombre}.json")))
    return rutas


def _comparar_vectores(actual: dict[str, float], esperado: dict[str, float]) -> None:
    assert actual.keys() == esperado.keys()
    for variable in actual:
        assert actual[variable] == pytest.approx(esperado[variable], abs=1e-6)


def _comparar_matriz(actual: dict, esperada: dict) -> None:
    assert actual.keys() == esperada.keys()
    for ancla in actual:
        assert actual[ancla]["Z1"] == pytest.approx(esperada[ancla]["Z1"], abs=1e-6)
        assert actual[ancla]["Z2"] == pytest.approx(esperada[ancla]["Z2"], abs=1e-6)
        _comparar_vectores(actual[ancla]["x"], esperada[ancla]["x"])


def test_scripts_no_importan_modulos_internos() -> None:
    for ruta in (EPSILON_SCRIPT, WEIGHTED_SCRIPT):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        importados = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados.extend(alias.name for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                importados.append(nodo.module)
        assert not any(
            nombre == "solver_optimizador"
            or nombre.startswith("solver_optimizador.")
            or nombre == "src"
            or nombre.startswith("src.solver_optimizador")
            for nombre in importados
        )


def test_carga_portable_completa_coeficientes_dispersos(tmp_path: Path) -> None:
    ruta = _guardar(MODELOS["artificial_max_max"], tmp_path / "disperso.json")
    for modulo in (EPSILON, WEIGHTED):
        problema = modulo.cargar_problema(ruta)
        assert problema["objectives"][0]["coefficients"] == {"x": 1.0, "y": 0.0}
        assert problema["objectives"][1]["coefficients"] == {"x": 0.0, "y": 1.0}
        assert len(problema["constraints"]) == 2


@pytest.mark.parametrize("primary", [1, 2])
def test_restricciones_coincide_con_backend_en_cuatro_modelos(
    tmp_path: Path, primary: int
) -> None:
    for _, ruta in _rutas_modelos(tmp_path):
        oficial = solve_biobjective_epsilon_constraint(
            _problema_oficial(ruta), primary_objective=primary, r=4
        )
        problema = EPSILON.cargar_problema(ruta)
        academico = EPSILON.resolver_metodo_restricciones(
            problema, primary=primary, r=4
        )

        _comparar_matriz(academico["payoff_matrix"], oficial.payoff_matrix)
        assert academico["epsilon_levels"] == pytest.approx(oficial.epsilon_levels, abs=1e-8)
        assert len(academico["runs"]) == len(oficial.runs) == 5
        for actual, esperado in zip(academico["runs"], oficial.runs):
            assert actual["E"] == pytest.approx(esperado["E"], abs=1e-8)
            assert actual["constraint_operator"] == esperado["constraint_operator"]
            assert actual["status"] == esperado["status"]
            assert actual["Z1"] == pytest.approx(esperado["Z1"], abs=1e-6)
            assert actual["Z2"] == pytest.approx(esperado["Z2"], abs=1e-6)
            _comparar_vectores(actual["x"], esperado["x"])

        assert len(academico["unique_solutions"]) == len(oficial.unique_solutions)
        for actual, esperado in zip(academico["unique_solutions"], oficial.unique_solutions):
            assert actual["run_indices"] == esperado["run_indices"]
            assert actual["epsilon_levels"] == pytest.approx(esperado["epsilon_levels"], abs=1e-8)
            assert actual["pareto_status"] == esperado["pareto_status"]
            _comparar_vectores(actual["x"], esperado["x"])
        assert {
            clave: valor["status"] for clave, valor in academico["pareto_classification"].items()
        } == {
            clave: valor["status"] for clave, valor in oficial.pareto_classification.items()
        }


def test_ponderaciones_coincide_con_backend_en_cuatro_modelos(tmp_path: Path) -> None:
    for nombre, ruta in _rutas_modelos(tmp_path):
        numero_pesos = 4 if nombre == "artificial_max_min" else 6
        oficial = solve_biobjective_weighted(
            _problema_oficial(ruta), num_combinations=numero_pesos
        )
        problema = WEIGHTED.cargar_problema(ruta)
        academico = WEIGHTED.resolver_metodo_ponderaciones(
            problema, num_weights=numero_pesos
        )

        _comparar_matriz(academico["payoff_matrix"], oficial.payoff_matrix)
        assert academico["normalization_ranges"] == pytest.approx(
            oficial.normalization_ranges, abs=1e-8
        )
        pesos_oficiales = [(r["alpha1"], r["alpha2"]) for r in oficial.weighted_runs]
        assert academico["weights"] == pesos_oficiales
        assert len(academico["weighted_runs"]) == len(oficial.weighted_runs)
        for actual, esperado in zip(academico["weighted_runs"], oficial.weighted_runs):
            for clave in ("Z1", "Z2", "N1", "N2", "W"):
                assert actual[clave] == pytest.approx(esperado[clave], abs=1e-6)
            _comparar_vectores(actual["x"], esperado["x"])

        assert len(academico["unique_solutions"]) == len(oficial.unique_solutions)
        for actual, esperado in zip(academico["unique_solutions"], oficial.unique_solutions):
            assert actual["generated_by_weights"] == esperado["generated_by_weights"]
            assert actual["pareto_status"] == esperado["pareto_status"]
            _comparar_vectores(actual["x"], esperado["x"])
        assert {
            clave: valor["status"] for clave, valor in academico["pareto_classification"].items()
        } == {
            clave: valor["status"] for clave, valor in oficial.pareto_classification.items()
        }


def test_hidroelectrica_reproduce_frontera_conocida() -> None:
    problema = EPSILON.cargar_problema(HYDRO_MODEL)
    resultado = EPSILON.resolver_metodo_restricciones(problema, primary=1, r=6)
    assert resultado["epsilon_levels"] == pytest.approx(
        [40, 50, 60, 70, 80, 90, 100], abs=1e-8
    )
    assert [c["x"]["V4"] for c in resultado["runs"]] == pytest.approx(
        [40, 50, 60, 70, 80, 90, 100], abs=1e-6
    )
    for corrida in resultado["runs"]:
        assert corrida["Z1"] == pytest.approx(
            245.25 * corrida["x"]["V4"] - 3108.75, abs=1e-6
        )


@pytest.mark.parametrize(
    ("script", "argumentos", "encabezado"),
    [
        (EPSILON_SCRIPT, ["--primary", "1", "--r", "6"], "METODO DE LAS RESTRICCIONES"),
        (WEIGHTED_SCRIPT, ["--num-weights", "6"], "METODO DE PONDERACIONES NORMALIZADAS"),
    ],
)
def test_portabilidad_real_solo_script_y_json(
    tmp_path: Path, script: Path, argumentos: list[str], encabezado: str
) -> None:
    script_copiado = tmp_path / script.name
    modelo_copiado = tmp_path / "problema.json"
    shutil.copy2(script, script_copiado)
    shutil.copy2(HYDRO_MODEL, modelo_copiado)
    assert sorted(ruta.name for ruta in tmp_path.iterdir()) == [script.name, "problema.json"]

    entorno = os.environ.copy()
    entorno.pop("PYTHONPATH", None)
    comprobacion = subprocess.run(
        [sys.executable, "-c", "import importlib.util; print(importlib.util.find_spec('solver_optimizador'))"],
        cwd=tmp_path,
        env=entorno,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    assert comprobacion.stdout.strip() == "None"

    proceso = subprocess.run(
        [sys.executable, script_copiado.name, modelo_copiado.name, *argumentos],
        cwd=tmp_path,
        env=entorno,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proceso.returncode == 0, proceso.stderr
    assert encabezado in proceso.stdout
    assert "Generación Hidroeléctrica" in proceso.stdout
    assert "Matriz de pagos" in proceso.stdout
    assert "Clasificacion Pareto" in proceso.stdout


def test_salidas_cli_contienen_trazabilidad_matematica() -> None:
    epsilon = subprocess.run(
        [sys.executable, str(EPSILON_SCRIPT), str(HYDRO_MODEL), "--primary", "1", "--r", "6"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout
    assert "Niveles E2 = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]" in epsilon
    assert "21416.250000 | 100.000000" in epsilon

    weighted = subprocess.run(
        [sys.executable, str(WEIGHTED_SCRIPT), str(HYDRO_MODEL), "--num-weights", "6"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout
    assert "Pesos: [(0.0, 1.0), (0.2, 0.8)" in weighted
    assert "N1 | N2 | W" in weighted
