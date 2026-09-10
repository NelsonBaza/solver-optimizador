"""Pruebas estructurales del exportador académico Gurobi autocontenido."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from solver_optimizador import (
    build_biobjective_problem_from_state,
    deserialize_model,
    solve_biobjective_epsilon_constraint,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = PROJECT_ROOT / "scripts" / "export_gurobi.py"
HYDRO_PATH = PROJECT_ROOT / "models" / "hidroelectrica_biobjetivo.json"
UNIFIED_PATH = PROJECT_ROOT / "models" / "ejemplo_familias_2d.json"
DELIVERABLE_PATH = (
    PROJECT_ROOT / "entregas" / "hidroelectrica_restricciones_gurobi.py"
)


def _exporter_module():
    spec = importlib.util.spec_from_file_location("export_gurobi", EXPORTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assignment(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"No se encontró la asignación {name}.")


@pytest.fixture(scope="module")
def exporter():
    return _exporter_module()


@pytest.fixture()
def generated(tmp_path: Path, exporter):
    output = tmp_path / "hidroelectrica_restricciones_gurobi.py"
    exporter.export_gurobi_script(HYDRO_PATH, output, primary=1, r=6)
    return output, output.read_text(encoding="utf-8")


def test_genera_archivo_hidroelectrico_no_vacio_y_compilable(generated) -> None:
    output, source = generated

    assert output.is_file()
    assert output.stat().st_size > 0
    assert len(source.splitlines()) <= 300
    ast.parse(source)
    compile(source, str(output), "exec")


def test_entregable_versionado_es_reproducible(exporter) -> None:
    canonical = exporter.load_canonical_biobjective(HYDRO_PATH)
    expected = exporter.render_gurobi_script(
        canonical,
        primary=1,
        r=6,
        output_name=DELIVERABLE_PATH.name,
    )

    assert DELIVERABLE_PATH.read_text(encoding="utf-8") == expected


def test_imports_generados_son_solo_gurobi_matplotlib_y_estandar(generated) -> None:
    _, source = generated
    imported_roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_roots.add((node.module or "").split(".")[0])

    assert "gurobipy" in imported_roots
    assert "matplotlib" in imported_roots
    assert imported_roots <= {
        "__future__",
        "pathlib",
        "sys",
        "time",
        "gurobipy",
        "matplotlib",
    }
    assert "solver_optimizador" not in imported_roots
    assert "pyomo" not in imported_roots
    assert "highspy" not in imported_roots


def test_archivo_generado_no_necesita_json_ni_repositorio(
    generated, tmp_path: Path
) -> None:
    output, source = generated
    portable_dir = tmp_path / "entrega_profesor"
    portable_dir.mkdir()
    portable_file = portable_dir / output.name
    shutil.copy2(output, portable_file)

    assert ".json" not in source
    assert "import json" not in source
    assert "scripts.solve_model" not in source
    assert "from solver_optimizador" not in source
    compile(portable_file.read_text(encoding="utf-8"), str(portable_file), "exec")


def test_plan_directo_conserva_todo_el_modelo_canonico(generated, exporter) -> None:
    _, source = generated
    canonical = exporter.load_canonical_biobjective(HYDRO_PATH)
    plan = exporter.build_render_plan(canonical)

    assert len(canonical["variables"]) == 24
    assert len(canonical["constraints"]) == 28
    assert plan["folded_bounds"] == 12
    assert plan["direct_constraints"] == 16
    assert "28 restricciones canónicas" in source
    assert "CONSTRAINTS =" not in source
    assert "OBJECTIVES =" not in source
    assert "VARIABLES =" not in source


def test_objetivos_hidroelectricos_embebidos_son_exactos(generated) -> None:
    _, source = generated

    assert _assignment(source, "SENSES") == ("MIN", "MAX")
    assert _assignment(source, "OBJECTIVE_NAMES") == (
        "Costo de generación térmica",
        "Volumen final del embalse V4 (UH)",
    )
    assert "Z1 = 100 * gp.quicksum(GT[t] for t in periodos)" in source
    assert "Z2 = V[4]" in source
    assert "def valor(expresion)" in source
    assert "isinstance(expresion, gp.Var)" in source
    assert "Z1=valor(Z1), Z2=valor(Z2)" in source


def test_formulacion_hidroelectrica_usa_gurobi_natural(generated) -> None:
    _, source = generated

    assert "periodos = range(1, 5)" in source
    assert "T = m.addVars(periodos, lb=0, ub=70, name='T')" in source
    assert "V = m.addVars(periodos, lb=40, ub=100, name='V')" in source
    assert "m.addConstrs((PH[t] - 2.4525 * T[t] == 0" in source
    assert "m.addConstrs((GH[t] - PH[t] == 0" in source
    assert "m.addConstrs((GH[t] + GT[t] == demanda_p_rhs[t]" in source


def test_configuracion_epsilon_es_editable_y_exacta(generated) -> None:
    _, source = generated

    assert _assignment(source, "PRIMARY_OBJECTIVE") == 1
    assert _assignment(source, "R") == 6
    assert "E_t = Z_min + (t/r)(Z_max - Z_min)" in source
    assert "range(r + 1)" in source
    assert "for t, E in enumerate(niveles)" in source


def test_barrido_maneja_max_min_y_no_acumula_epsilon(generated) -> None:
    _, source = generated

    assert 'SENSES[indice - 1] == "MAX"' in source
    assert "objetivos[indice - 1] >= nivel" in source
    assert "objetivos[indice - 1] <= nivel" in source
    assert "m, x, Z1, Z2 = construir_modelo()" in source
    assert "las restricciones no se acumulan" in source


def test_matriz_de_pagos_se_resuelve_y_no_usa_set_objective_n(generated) -> None:
    _, source = generated

    assert "for indice in (1, 2):" in source
    assert "primera = optimizar(indice)" in source
    assert 'fila = optimizar(otro, fijar=(indice, primera[f"Z{indice}"]))' in source
    assert 'matriz[f"opt_Z{indice}"]' in source
    assert ".setObjective(" in source
    assert "setObjectiveN" not in source
    assert "m.optimize()" in source


def test_estados_pareto_y_grafico_estan_incluidos(generated) -> None:
    _, source = generated

    for status in ("GRB.OPTIMAL", "GRB.INFEASIBLE", "GRB.UNBOUNDED", "GRB.INF_OR_UNBD"):
        assert status in source
    assert "def resumir_soluciones" in source
    assert "Soluciones no dominadas obtenidas por el barrido" in source
    assert "matplotlib.use(\"Agg\")" in source
    assert "fig.savefig(PLOT_FILE" in source
    assert "Soluciones no dominadas obtenidas" in source


def test_grafico_contiene_textos_descriptivos_aprobados(generated) -> None:
    _, source = generated

    assert _assignment(source, "PLOT_TITLE") == "Generación hidroeléctrica"
    assert "Frontera de Pareto — {PLOT_TITLE}" in source
    assert "Método de las restricciones | Z1 {SENSES[0]} · Z2 {SENSES[1]}" in source
    assert "Z1 — {OBJECTIVE_NAMES[0]} ({SENSES[0]})" in source
    assert "Z2 — {OBJECTIVE_NAMES[1]} ({SENSES[1]})" in source


def test_cli_exporta_sin_importar_gurobipy(tmp_path: Path) -> None:
    output = tmp_path / "modelo_gurobi.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORTER_PATH),
            str(HYDRO_PATH),
            "--method",
            "epsilon",
            "--primary",
            "1",
            "--r",
            "6",
            "--output",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert "no necesita el JSON original" in completed.stdout
    exporter_source = EXPORTER_PATH.read_text(encoding="utf-8")
    exporter_imports = {
        (node.module or "").split(".")[0]
        for node in ast.walk(ast.parse(exporter_source))
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(exporter_source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "gurobipy" not in exporter_imports


def test_cli_rechaza_metodo_weighted(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORTER_PATH),
            str(HYDRO_PATH),
            "--method",
            "weighted",
            "--output",
            str(tmp_path / "invalid.py"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr


def test_json_11_indexado_se_expande_y_exporta(tmp_path: Path, exporter) -> None:
    output = tmp_path / "familias_2d_gurobi.py"
    exporter.export_gurobi_script(UNIFIED_PATH, output, primary=2, r=4)
    source = output.read_text(encoding="utf-8")
    state = deserialize_model(UNIFIED_PATH.read_text(encoding="utf-8"))
    canonical = exporter.load_canonical_biobjective(UNIFIED_PATH)
    plan = exporter.build_render_plan(canonical)

    assert canonical["variables"] == state["var_names"]
    assert plan["folded_bounds"] + plan["direct_constraints"] == len(
        state["constraints_data"]
    )
    assert "CONSTRAINTS =" not in source
    assert "OBJECTIVES =" not in source
    assert _assignment(source, "PRIMARY_OBJECTIVE") == 2
    assert _assignment(source, "R") == 4
    compile(source, str(output), "exec")


@pytest.mark.parametrize(
    ("sense1", "sense2"),
    [
        ("Maximizar", "Maximizar"),
        ("Minimizar", "Maximizar"),
        ("Maximizar", "Minimizar"),
        ("Minimizar", "Minimizar"),
    ],
)
def test_preserva_las_cuatro_combinaciones_de_sentidos(
    tmp_path: Path, exporter, sense1: str, sense2: str
) -> None:
    document = json.loads(HYDRO_PATH.read_text(encoding="utf-8"))
    document["problem"]["bio_objectives"]["obj1"]["sense"] = sense1
    document["problem"]["bio_objectives"]["obj2"]["sense"] = sense2
    model_file = tmp_path / f"{sense1}_{sense2}.json"
    model_file.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / f"{sense1}_{sense2}.py"

    exporter.export_gurobi_script(model_file, output, primary=1, r=2)
    senses = list(_assignment(output.read_text(encoding="utf-8"), "SENSES"))

    assert senses == [
        "MAX" if sense1 == "Maximizar" else "MIN",
        "MAX" if sense2 == "Maximizar" else "MIN",
    ]


def test_regresion_hidroelectrica_coincide_con_backend_oficial(exporter) -> None:
    canonical = exporter.load_canonical_biobjective(HYDRO_PATH)
    loaded = deserialize_model(HYDRO_PATH.read_text(encoding="utf-8"))
    problem = build_biobjective_problem_from_state(
        var_names=loaded["var_names"],
        obj1_sense=loaded["objectives"][0]["sense"],
        obj1_coeffs=loaded["objectives"][0]["coefficients"],
        obj2_sense=loaded["objectives"][1]["sense"],
        obj2_coeffs=loaded["objectives"][1]["coefficients"],
        canonical_constraints=loaded["constraints_data"],
    )
    result = solve_biobjective_epsilon_constraint(problem, 1, 6)

    assert canonical["variables"] == problem.variables
    assert result.payoff_matrix["opt_Z1"]["Z1"] == pytest.approx(6701.25)
    assert result.payoff_matrix["opt_Z1"]["Z2"] == pytest.approx(40.0)
    assert result.payoff_matrix["opt_Z2"]["Z1"] == pytest.approx(21416.25)
    assert result.payoff_matrix["opt_Z2"]["Z2"] == pytest.approx(100.0)
    assert result.epsilon_levels == pytest.approx([40, 50, 60, 70, 80, 90, 100])
    assert [run["Z1"] for run in result.runs] == pytest.approx(
        [6701.25, 9153.75, 11606.25, 14058.75, 16511.25, 18963.75, 21416.25]
    )
    assert [run["Z2"] for run in result.runs] == pytest.approx(
        [40, 50, 60, 70, 80, 90, 100]
    )
    assert all(
        solution["pareto_status"] == "No dominada"
        for solution in result.unique_solutions
    )


def test_validaciones_de_salida_primary_y_r(tmp_path: Path, exporter) -> None:
    output = tmp_path / "modelo.txt"
    with pytest.raises(ValueError, match="extensión .py"):
        exporter.export_gurobi_script(HYDRO_PATH, output, primary=1, r=6)
    with pytest.raises(ValueError, match="primary debe ser 1 o 2"):
        exporter.export_gurobi_script(HYDRO_PATH, tmp_path / "x.py", primary=3, r=6)
    with pytest.raises(ValueError, match="r debe ser un entero"):
        exporter.export_gurobi_script(HYDRO_PATH, tmp_path / "x.py", primary=1, r=0)


@pytest.mark.skipif(
    importlib.util.find_spec("gurobipy") is None,
    reason="gurobipy no está instalado en este entorno",
)
def test_ejecucion_real_si_gurobi_esta_disponible(generated) -> None:
    output, _ = generated
    completed = subprocess.run(
        [sys.executable, str(output)],
        cwd=output.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    license_error = "license" in (completed.stdout + completed.stderr).lower()
    if license_error:
        pytest.skip("gurobipy está instalado, pero no hay licencia funcional")
    assert completed.returncode == 0, completed.stderr
    assert "Niveles E = [40, 50, 60, 70, 80, 90, 100]" in completed.stdout
    assert output.with_name(output.stem + "_pareto.png").is_file()
