"""Pruebas del generador Gurobi sin requerir una instalación de Gurobi."""

from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from solver_optimizador import export_gurobi_script
import solver_optimizador.gurobi_script_export as generator_module


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "solve_model.py"
PLANNING = ROOT / "models" / "planeacion_agregada_biobjetivo.json"
HYDRO = ROOT / "models" / "hidroelectrica_biobjetivo.json"
MODEL_3 = ROOT / "models" / "ejemplo_tres_objetivos.json"


def _runner_module():
    spec = importlib.util.spec_from_file_location("solve_model_gurobi", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _model_data(source: str) -> dict:
    module = ast.parse(source)
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "MODEL_DATA"
            for target in node.targets
        )
    )
    return ast.literal_eval(assignment.value)


@pytest.fixture(scope="module")
def runner():
    return _runner_module()


@pytest.fixture()
def planning_script(tmp_path, runner):
    name, _, multi = runner.load_multiobjective_model(PLANNING)
    problem = runner._as_biobjective(multi)
    output = tmp_path / "planeacion_agregada_biobjetivo_epsilon_gurobi.py"
    returned = export_gurobi_script(
        problem=problem,
        method="epsilon",
        model_name=name,
        model_file=PLANNING,
        output_path=output,
        primary_objective=1,
        r_by_objective={2: 6},
    )
    source = output.read_text(encoding="utf-8")
    return returned, source, problem


def test_crea_archivo_no_vacio_con_sintaxis_valida(planning_script) -> None:
    output, source, _ = planning_script
    assert output.is_file()
    assert output.stat().st_size > 20_000
    ast.parse(source)
    compile(source, str(output), "exec")


def test_importa_gurobi_y_matplotlib_solo_en_script_generado(planning_script) -> None:
    _, source, _ = planning_script
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom)
    }
    assert "gurobipy" in imports
    assert "matplotlib.pyplot" in imports
    assert "gurobipy" in from_imports
    assert generator_module.__dict__.get("gp") is None
    assert generator_module.__dict__.get("GRB") is None


def test_no_importa_proyecto_ni_lee_json_original(planning_script) -> None:
    _, source, _ = planning_script
    tree = ast.parse(source)
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")
    assert not any(name.startswith("solver_optimizador") for name in imported_modules)
    assert not any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == "open"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in {"read_text", "read_bytes"}
        )
        for node in ast.walk(tree)
    )


def test_embebe_modelo_completo_continuo_y_bounds_actuales(planning_script) -> None:
    _, source, problem = planning_script
    data = _model_data(source)
    assert data["variables"] == problem.variables
    assert data["variable_type"] == "continuous"
    assert data["lower_bound"] == 0.0
    assert data["upper_bound"] is None
    assert data["constraints"] == [
        {
            "name": constraint.name,
            "coefficients": constraint.coefficients,
            "operator": constraint.operator.value,
            "rhs": constraint.rhs,
        }
        for constraint in problem.constraints
    ]
    assert len(data["constraints"]) == 15


def test_embebe_objetivos_y_sentidos_min_min(planning_script) -> None:
    _, source, problem = planning_script
    data = _model_data(source)
    assert [objective["sense"] for objective in data["objectives"]] == ["min", "min"]
    assert data["objectives"][0]["coefficients"] == problem.objective1.coefficients
    assert data["objectives"][1]["coefficients"] == problem.objective2.coefficients


def test_conserva_configuracion_epsilon_y_r(planning_script) -> None:
    _, source, _ = planning_script
    data = _model_data(source)
    assert data["method"] == "epsilon"
    assert data["configuration"] == {
        "primary_objective": 1,
        "r_by_objective": {2: 6},
    }
    assert "range(r_by_objective[index] + 1)" in source
    assert "z_min + (t / r) * difference" in source


def test_reproduce_lexicografia_y_no_usa_multiobjetivo_nativo(planning_script) -> None:
    _, source, _ = planning_script
    assert "def _biobjective_anchor" in source
    assert "def _multiobjective_anchor" in source
    assert '"operator": "="' in source
    assert "setObjectiveN" not in source
    assert "model.setObjective(expression, gurobi_sense)" in source


def test_maneja_estados_sin_leer_x_fuera_de_optimo(planning_script) -> None:
    _, source, _ = planning_script
    for status in ("GRB.OPTIMAL", "GRB.INFEASIBLE", "GRB.UNBOUNDED", "GRB.INF_OR_UNBD"):
        assert status in source
    assert "model.Params.DualReductions = 0" in source
    assert 'if status_code == GRB.OPTIMAL:' in source
    assert "variable.X" in source


def test_rutas_de_graficos_se_basan_en___file__(planning_script) -> None:
    _, source, _ = planning_script
    assert "Path(__file__).resolve()" in source
    assert '"_pareto.png"' in source
    assert '"_region_factible.png"' in source


def test_weighted_embebe_numero_de_pesos_y_formula(tmp_path, runner) -> None:
    name, _, multi = runner.load_multiobjective_model(HYDRO)
    problem = runner._as_biobjective(multi)
    output = tmp_path / "hidroelectrica_biobjetivo_weighted_gurobi.py"
    export_gurobi_script(
        problem=problem,
        method="weighted",
        model_name=name,
        model_file=HYDRO,
        output_path=output,
        num_weights=6,
    )
    source = output.read_text(encoding="utf-8")
    data = _model_data(source)
    assert data["configuration"] == {"num_weights": 6}
    assert "alpha1 * n1 + alpha2 * n2" in source
    assert "round(index / (count - 1), 6)" in source
    assert "_weighted_optimum_run_" in source
    assert [objective["sense"] for objective in data["objectives"]] == ["min", "max"]


def test_epsilon_tres_objetivos_embebe_producto_cartesiano(tmp_path, runner) -> None:
    name, _, problem = runner.load_multiobjective_model(MODEL_3)
    output = tmp_path / "ejemplo_tres_objetivos_epsilon_gurobi.py"
    export_gurobi_script(
        problem=problem,
        method="epsilon",
        model_name=name,
        model_file=MODEL_3,
        output_path=output,
        primary_objective=1,
        r_by_objective={2: 2, 3: 2},
    )
    source = output.read_text(encoding="utf-8")
    data = _model_data(source)
    assert len(data["objectives"]) == 3
    assert data["configuration"]["r_by_objective"] == {2: 2, 3: 2}
    assert "itertools.product" in source
    assert "[(primary, index) for index in result[\"constrained_objectives\"]]" in source
    compile(source, str(output), "exec")


def test_generador_no_modifica_problema_ni_llama_solver(
    tmp_path, runner, monkeypatch
) -> None:
    name, _, multi = runner.load_multiobjective_model(HYDRO)
    problem = runner._as_biobjective(multi)
    snapshot = deepcopy(problem)

    def forbidden(*args, **kwargs):
        raise AssertionError("El generador no debe llamar al solver")

    monkeypatch.setattr("solver_optimizador.solve_lp", forbidden)
    monkeypatch.setattr("solver_optimizador.solve_biobjective_weighted", forbidden)
    monkeypatch.setattr(
        "solver_optimizador.solve_biobjective_epsilon_constraint", forbidden
    )
    export_gurobi_script(
        problem=problem,
        method="epsilon",
        model_name=name,
        model_file=HYDRO,
        output_path=tmp_path / "model_gurobi.py",
        primary_objective=1,
        r_by_objective={2: 1},
    )
    assert problem == snapshot


def test_cli_genera_nombre_esperado_sin_resolucion_adicional(
    tmp_path, runner, monkeypatch
) -> None:
    name, loaded, multi = runner.load_multiobjective_model(HYDRO)
    problem = runner._as_biobjective(multi)
    actual_solver = runner.solve_biobjective_epsilon_constraint
    expected_result = actual_solver(problem, primary_objective=1, r=1)
    calls = 0

    def counted_solver(*args, **kwargs):
        nonlocal calls
        calls += 1
        return expected_result

    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "solve_biobjective_epsilon_constraint", counted_solver)
    code = runner.main(
        [
            str(HYDRO),
            "--method", "epsilon",
            "--primary", "1",
            "--r", "1",
            "--no-plot",
            "--no-excel",
        ]
    )
    output = tmp_path / "results" / "hidroelectrica_biobjetivo_epsilon_gurobi.py"
    assert code == 0
    assert calls == 1
    assert output.is_file()
    compile(output.read_text(encoding="utf-8"), str(output), "exec")


def test_no_gurobi_script_desactiva_solo_generador(
    tmp_path, runner, monkeypatch
) -> None:
    calls = 0
    actual_solver = runner.solve_biobjective_epsilon_constraint

    def counted_solver(*args, **kwargs):
        nonlocal calls
        calls += 1
        return actual_solver(*args, **kwargs)

    def forbidden(**kwargs):
        raise AssertionError("--no-gurobi-script debe omitir el generador")

    monkeypatch.setattr(runner, "solve_biobjective_epsilon_constraint", counted_solver)
    monkeypatch.setattr(runner, "export_gurobi_script", forbidden)
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    code = runner.main(
        [
            str(HYDRO),
            "--method", "epsilon",
            "--primary", "1",
            "--r", "1",
            "--no-gurobi-script",
        ]
    )
    assert code == 0
    assert calls == 1
    results = tmp_path / "results"
    assert (results / "hidroelectrica_biobjetivo_epsilon_pareto.png").is_file()
    assert (results / "hidroelectrica_biobjetivo_epsilon.xlsx").is_file()
    assert not list(results.glob("*_gurobi.py"))


def test_help_documenta_no_gurobi_script(runner) -> None:
    help_text = runner.build_parser().format_help()
    assert "--no-gurobi-script" in help_text
    assert "Gurobi" in help_text


def test_no_agrega_gurobipy_como_dependencia() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "gurobipy" not in pyproject


@pytest.mark.parametrize(
    ("method", "arguments", "filename"),
    [
        (
            "epsilon",
            {"primary_objective": 1, "r_by_objective": {2: 6}},
            "modelo_epsilon_gurobi.py",
        ),
        (
            "weighted",
            {"num_weights": 6},
            "modelo_weighted_gurobi.py",
        ),
    ],
)
def test_nombres_de_archivo_finales(
    tmp_path, runner, method, arguments, filename
) -> None:
    name, _, multi = runner.load_multiobjective_model(HYDRO)
    problem = runner._as_biobjective(multi)
    output = tmp_path / filename
    returned = export_gurobi_script(
        problem=problem,
        method=method,
        model_name=name,
        model_file=HYDRO,
        output_path=output,
        **arguments,
    )
    assert returned.name == filename
