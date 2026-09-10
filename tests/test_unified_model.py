"""Validación del JSON unificado 1.1 y su expansión canónica."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from solver_optimizador import (
    build_biobjective_problem_from_state,
    deserialize_model,
    solve_biobjective_epsilon_constraint,
    solve_biobjective_weighted,
    validate_model_dict,
)


ROOT = Path(__file__).resolve().parents[1]
HYDRO = ROOT / "models" / "hidroelectrica_biobjetivo.json"
MODEL_1D = ROOT / "models" / "ejemplo_familias_1d.json"
MODEL_2D = ROOT / "models" / "ejemplo_familias_2d.json"
RUNNER = ROOT / "scripts" / "solve_model.py"


def _explicit_11() -> dict:
    return {
        "schema_version": "1.1",
        "metadata": {"name": "Explícito 1.1"},
        "problem": {
            "type": "Biobjetivo",
            "variables": ["x", "y"],
            "bio_objectives": {
                "obj1": {
                    "sense": "Maximizar",
                    "coefficients": {"x": 3.0, "y": 1.0},
                },
                "obj2": {
                    "sense": "Maximizar",
                    "coefficients": {"x": 1.0, "y": 3.0},
                },
            },
            "constraints": [
                {
                    "name": "Capacidad",
                    "coefficients": {"x": 1.0, "y": 1.0},
                    "operator": "<=",
                    "rhs": 10.0,
                }
            ],
        },
    }


def _previous_reference_document(start_at_two: bool) -> dict:
    family = {
        "name": "Enlace",
        "indices": ["j"],
        "sets": ["J"],
        "expression": "X[j] - X[j-1] <= paso",
    }
    if start_at_two:
        family["index_ranges"] = {"j": {"start": 2}}
    return {
        "schema_version": "1.1",
        "metadata": {"name": "Referencia anterior"},
        "problem": {
            "type": "Biobjetivo",
            "sets": {"J": {"start": 1, "end": 3}},
            "parameters": {"paso": {"value": 1.0}},
            "variables": [],
            "variable_families": [
                {"name": "X", "indices": ["j"], "sets": ["J"]}
            ],
            "bio_objectives": {
                "obj1": {
                    "sense": "Maximizar",
                    "coefficients": {},
                    "indexed_terms": [
                        {
                            "variable_family": "X",
                            "indices": ["j"],
                            "sets": ["J"],
                            "coefficient": "1",
                        }
                    ],
                },
                "obj2": {
                    "sense": "Minimizar",
                    "coefficients": {},
                    "indexed_terms": [
                        {
                            "variable_family": "X",
                            "indices": ["j"],
                            "sets": ["J"],
                            "coefficient": "1",
                        }
                    ],
                },
            },
            "constraints": [],
            "constraint_families": [
                {
                    "name": "Cota",
                    "indices": ["j"],
                    "sets": ["J"],
                    "expression": "X[j] <= 5",
                },
                family,
            ],
        },
    }


def _load(path: Path) -> dict:
    return deserialize_model(path.read_text(encoding="utf-8"))


def _problem(state: dict):
    return build_biobjective_problem_from_state(
        var_names=state["var_names"],
        obj1_sense=state["obj1_sense"],
        obj1_coeffs=state["obj1_coeffs"],
        obj2_sense=state["obj2_sense"],
        obj2_coeffs=state["obj2_coeffs"],
        canonical_constraints=state["constraints_data"],
    )


def test_json_10_historico_sigue_cargando() -> None:
    state = _load(HYDRO)
    assert state["schema_version"] == "1.0"
    assert state["num_vars"] == 24
    assert len(state["constraints_data"]) == 28
    assert "expansion_statistics" not in state


def test_json_11_explicito_solamente() -> None:
    document = _explicit_11()
    valid, error = validate_model_dict(document)
    state = deserialize_model(json.dumps(document))
    assert valid and error is None
    assert state["var_names"] == ["x", "y"]
    assert len(state["constraints_data"]) == 1
    assert state["expansion_statistics"]["generated_variables"] == 0
    assert state["expansion_statistics"]["generated_constraints"] == 0


def test_json_11_indexado_solamente_y_expansion_grande() -> None:
    state = _load(MODEL_1D)
    assert state["var_names"] == [f"X_{index}" for index in range(1, 41)]
    assert [row["name"] for row in state["constraints_data"]] == [
        f"Limite_{index}" for index in range(1, 41)
    ]
    assert state["expansion_statistics"]["generated_variables"] == 40
    assert state["expansion_statistics"]["generated_constraints"] == 40
    assert state["expansion_statistics"]["total_constraints"] >= 40


def test_json_11_mixto_explicito_e_indexado() -> None:
    state = _load(MODEL_2D)
    assert state["var_names"][0] == "reserva"
    assert state["constraints_data"][0]["name"] == "ReservaMaxima"
    assert state["constraints_data"][1] == {
        "name": "CasoEspecial",
        "coefficients": {"X_1_1": 1.0},
        "operator": ">=",
        "rhs": 1.0,
    }
    assert state["expansion_statistics"]["explicit_constraints"] == 2
    assert state["expansion_statistics"]["generated_constraints"] == 6


def test_variables_y_restricciones_2d_siguen_producto_cartesiano() -> None:
    state = _load(MODEL_2D)
    expected = [
        "X_1_1",
        "X_1_2",
        "X_2_1",
        "X_2_2",
        "X_3_1",
        "X_3_2",
    ]
    assert state["var_names"][1:] == expected
    assert [row["name"] for row in state["constraints_data"][2:]] == [
        name.replace("X", "Cota", 1) for name in expected
    ]


def test_parametro_escalar_e_indexado_2d_se_expanden() -> None:
    state = _load(MODEL_2D)
    generated = state["constraints_data"][2:]
    assert all(row["rhs"] == 5.0 for row in generated)
    assert state["obj2_coeffs"] == {
        "reserva": 0.2,
        "X_1_1": 1.0,
        "X_1_2": 1.2,
        "X_2_1": 1.4,
        "X_2_2": 1.6,
        "X_3_1": 1.8,
        "X_3_2": 2.0,
    }


def test_representacion_expandida_permanece_dispersa() -> None:
    for state in (_load(MODEL_1D), _load(MODEL_2D)):
        for row in state["constraints_data"]:
            assert row["coefficients"]
            assert all(value != 0.0 for value in row["coefficients"].values())


def test_trazabilidad_conserva_familia_indices_y_expresion() -> None:
    state = _load(MODEL_2D)
    variable = state["source_provenance"]["variables"]["X_2_1"]
    constraint = state["source_provenance"]["constraints"]["Cota_2_1"]
    assert variable["family_name"] == "X"
    assert variable["indices"] == {"j": 2, "m": 1}
    assert constraint["family_name"] == "Cota"
    assert constraint["indices"] == {"j": 2, "m": 1}
    assert constraint["source_expression"] == "X[j,m] <= capacidad"


def test_referencia_j_menos_uno_valida() -> None:
    state = deserialize_model(json.dumps(_previous_reference_document(True)))
    constraints = {row["name"]: row for row in state["constraints_data"]}
    assert constraints["Enlace_2"]["coefficients"] == {"X_2": 1.0, "X_1": -1.0}
    assert constraints["Enlace_3"]["coefficients"] == {"X_3": 1.0, "X_2": -1.0}


def test_indice_fuera_del_conjunto_es_rechazado() -> None:
    with pytest.raises(ValueError, match="fuera de J"):
        deserialize_model(json.dumps(_previous_reference_document(False)))


def test_parametro_incompleto_es_rechazado() -> None:
    document = json.loads(MODEL_2D.read_text(encoding="utf-8"))
    del document["problem"]["parameters"]["costo"]["values"]["3,2"]
    with pytest.raises(ValueError, match="faltan índices"):
        deserialize_model(json.dumps(document))


def test_expresion_no_lineal_es_rechazada() -> None:
    document = _previous_reference_document(True)
    document["problem"]["constraint_families"][0]["expression"] = "X[j] * X[j] <= 5"
    with pytest.raises(ValueError, match="no lineal"):
        deserialize_model(json.dumps(document))


def test_parser_no_invoca_eval_ni_exec() -> None:
    paths = [
        ROOT / "src" / "solver_optimizador" / "indexed_expression.py",
        ROOT / "src" / "solver_optimizador" / "unified_model.py",
    ]
    prohibited = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prohibited.extend(
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
        )
    assert prohibited == []


@pytest.mark.parametrize("path", [HYDRO, MODEL_1D, MODEL_2D])
def test_mismo_builder_recibe_todos_los_estilos(path: Path) -> None:
    problem = _problem(_load(path))
    assert problem.variables
    assert problem.constraints


def test_epsilon_resuelve_modelo_compilado() -> None:
    result = solve_biobjective_epsilon_constraint(
        _problem(_load(MODEL_1D)), primary_objective=1, r=2
    )
    assert len(result.runs) == 3
    assert all(run["status"] == "optimal" for run in result.runs)
    assert result.epsilon_levels == pytest.approx([0.0, 200.0, 400.0])


def test_ponderaciones_resuelve_modelo_compilado_2d() -> None:
    result = solve_biobjective_weighted(
        _problem(_load(MODEL_2D)), num_combinations=4
    )
    assert len(result.weighted_runs) == 4
    assert all(run["status"] == "Optimo" for run in result.weighted_runs)


def test_documento_de_entrada_no_se_modifica() -> None:
    document = _explicit_11()
    original = copy.deepcopy(document)
    deserialize_model(json.dumps(document))
    assert document == original


def _run_cli(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), str(path), *arguments, "--no-plot"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=60,
    )


def test_solve_model_carga_json_11_explicito(tmp_path: Path) -> None:
    path = tmp_path / "explicito_11.json"
    path.write_text(json.dumps(_explicit_11()), encoding="utf-8")
    process = _run_cli(path, "--method", "epsilon", "--primary", "1", "--r", "2")
    assert process.returncode == 0, process.stderr
    assert "Esquema JSON: 1.1 unificado" in process.stdout
    assert "0 variables explícitas" not in process.stdout


def test_solve_model_carga_json_11_indexado() -> None:
    process = _run_cli(MODEL_1D, "--method", "epsilon", "--primary", "1", "--r", "2")
    assert process.returncode == 0, process.stderr
    assert "0 variables explícitas + 40 indexadas" in process.stdout
    assert "0 restricciones explícitas + 40 generadas" in process.stdout


def test_solve_model_carga_json_11_mixto_2d() -> None:
    process = _run_cli(MODEL_2D, "--method", "weighted", "--num-weights", "4")
    assert process.returncode == 0, process.stderr
    assert "1 variables explícitas + 6 indexadas" in process.stdout
    assert "2 restricciones explícitas + 6 generadas" in process.stdout
