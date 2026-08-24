"""
Suite de pruebas unitarias para la serializacion, deserializacion y persistencia de modelos (model_io).
Incluye la prueba obligatoria de round-trip y resolucion del modelo hidroelectrico de 8 variables.
"""

import json
import pytest
from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.signature import build_model_signature
from solver_optimizador.model_io import (
    serialize_model,
    deserialize_model,
    validate_model_dict,
    sanitize_filename,
    SCHEMA_VERSION,
)


def test_sanitize_filename():
    assert sanitize_filename("Generacion hidroelectrica 4 periodos") == "generacion_hidroelectrica_4_periodos.json"
    assert sanitize_filename("Modelo #1 / Tarea (2026)") == "modelo_1_tarea_2026.json"
    assert sanitize_filename("") == "modelo_optimizacion.json"


def test_serialize_deserialize_mono_roundtrip():
    """Valida serializacion y deserializacion de un problema monoobjetivo manteniendo la firma matematica."""
    prob_dict = {
        "type": "Monoobjetivo",
        "variables": ["x1", "x2"],
        "mono_objective": {
            "sense": "Maximizar",
            "coefficients": {"x1": 3.0, "x2": 2.0},
        },
        "constraints": [
            {"name": "Capacidad", "coefficients": {"x1": 1.0, "x2": 1.0}, "operator": "<=", "rhs": 4.0},
            {"name": "Limite x1", "coefficients": {"x1": 1.0, "x2": 0.0}, "operator": "<=", "rhs": 2.0},
        ],
    }
    meta = {"name": "Ejemplo 1 Mono", "description": "Prueba de persistencia"}

    sig_before = build_model_signature(
        problem_type=prob_dict["type"],
        var_names=prob_dict["variables"],
        obj_sense=prob_dict["mono_objective"]["sense"],
        obj_coeffs=prob_dict["mono_objective"]["coefficients"],
        constraints_data=prob_dict["constraints"],
    )

    json_str = serialize_model(prob_dict, meta)
    loaded = deserialize_model(json_str)

    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["metadata"]["name"] == "Ejemplo 1 Mono"
    assert loaded["problem_type"] == "Monoobjetivo"
    assert loaded["var_names"] == ["x1", "x2"]
    assert loaded["obj_sense"] == "Maximizar"
    assert loaded["obj_coeffs"] == {"x1": 3.0, "x2": 2.0}
    assert len(loaded["constraints_data"]) == 2

    sig_after = build_model_signature(
        problem_type=loaded["problem_type"],
        var_names=loaded["var_names"],
        obj_sense=loaded["obj_sense"],
        obj_coeffs=loaded["obj_coeffs"],
        constraints_data=loaded["constraints_data"],
    )

    assert sig_before == sig_after


def test_serialize_deserialize_bio_roundtrip():
    """Valida serializacion y deserializacion del Benchmark A biobjetivo."""
    prob_dict = {
        "type": "Biobjetivo",
        "variables": ["x1", "x2"],
        "bio_objectives": {
            "obj1": {"sense": "Maximizar", "coefficients": {"x1": 10.0, "x2": 3.0}},
            "obj2": {"sense": "Maximizar", "coefficients": {"x1": 0.8, "x2": 1.3}},
        },
        "constraints": [
            {"name": "R1", "coefficients": {"x1": 1.0, "x2": 1.0}, "operator": "<=", "rhs": 130.0},
            {"name": "R2", "coefficients": {"x1": 2.5, "x2": 1.0}, "operator": "<=", "rhs": 250.0},
        ],
        "multiobjective_settings": {
            "mode": "Barrido automatico",
            "num_weights": 6,
            "custom_a1": 0.5,
        },
    }

    sig_before = build_model_signature(
        problem_type=prob_dict["type"],
        var_names=prob_dict["variables"],
        obj1_sense=prob_dict["bio_objectives"]["obj1"]["sense"],
        obj1_coeffs=prob_dict["bio_objectives"]["obj1"]["coefficients"],
        obj2_sense=prob_dict["bio_objectives"]["obj2"]["sense"],
        obj2_coeffs=prob_dict["bio_objectives"]["obj2"]["coefficients"],
        constraints_data=prob_dict["constraints"],
        mo_mode=prob_dict["multiobjective_settings"]["mode"],
        num_weights=prob_dict["multiobjective_settings"]["num_weights"],
    )

    json_str = serialize_model(prob_dict, {"name": "Benchmark A"})
    loaded = deserialize_model(json_str)

    sig_after = build_model_signature(
        problem_type=loaded["problem_type"],
        var_names=loaded["var_names"],
        obj1_sense=loaded["obj1_sense"],
        obj1_coeffs=loaded["obj1_coeffs"],
        obj2_sense=loaded["obj2_sense"],
        obj2_coeffs=loaded["obj2_coeffs"],
        constraints_data=loaded["constraints_data"],
        mo_mode=loaded["mo_mode"],
        num_weights=loaded["num_weights"],
    )

    assert sig_before == sig_after


def test_hydroelectric_model_roundtrip_and_solve():
    """
    Prueba obligatoria con el modelo reducido de generacion hidroelectrica de 8 variables.
    Valida:
    - Resolucion inicial Z* = 6701.25.
    - Serializacion a JSON.
    - Deserializacion desde JSON.
    - Identidad de firma matematica antes y despues.
    - Resolucion del modelo cargado Z* = 6701.25.
    """
    var_names = [f"x{i+1}" for i in range(8)]
    # MIN Z = 100x5 + 100x6 + 100x7 + 100x8
    obj_coeffs = {v: (100.0 if v in ("x5", "x6", "x7", "x8") else 0.0) for v in var_names}

    # Restricciones
    # 2.4525x1 + x5 = 60
    # 2.4525x2 + x6 = 80
    # 2.4525x3 + x7 = 70
    # 2.4525x4 + x8 = 90
    # x1 <= 50
    # x1+x2 <= 70
    # x1+x2+x3 <= 85
    # x1+x2+x3+x4 <= 95
    constraints_raw = [
        {"name": "Demanda P1", "coefficients": {v: (2.4525 if v == "x1" else (1.0 if v == "x5" else 0.0)) for v in var_names}, "operator": "=", "rhs": 60.0},
        {"name": "Demanda P2", "coefficients": {v: (2.4525 if v == "x2" else (1.0 if v == "x6" else 0.0)) for v in var_names}, "operator": "=", "rhs": 80.0},
        {"name": "Demanda P3", "coefficients": {v: (2.4525 if v == "x3" else (1.0 if v == "x7" else 0.0)) for v in var_names}, "operator": "=", "rhs": 70.0},
        {"name": "Demanda P4", "coefficients": {v: (2.4525 if v == "x4" else (1.0 if v == "x8" else 0.0)) for v in var_names}, "operator": "=", "rhs": 90.0},
        {"name": "Embalse P1", "coefficients": {v: (1.0 if v == "x1" else 0.0) for v in var_names}, "operator": "<=", "rhs": 50.0},
        {"name": "Embalse P2", "coefficients": {v: (1.0 if v in ("x1", "x2") else 0.0) for v in var_names}, "operator": "<=", "rhs": 70.0},
        {"name": "Embalse P3", "coefficients": {v: (1.0 if v in ("x1", "x2", "x3") else 0.0) for v in var_names}, "operator": "<=", "rhs": 85.0},
        {"name": "Embalse P4", "coefficients": {v: (1.0 if v in ("x1", "x2", "x3", "x4") else 0.0) for v in var_names}, "operator": "<=", "rhs": 95.0},
    ]

    prob_lp_before = LPProblem(
        variables=var_names,
        objective=LinearObjective("Z", Sense.MINIMIZE, obj_coeffs),
        constraints=[
            LinearConstraint(c["name"], c["coefficients"], Operator.from_str(c["operator"]), c["rhs"])
            for c in constraints_raw
        ],
    )

    sol_before = solve_lp(prob_lp_before)
    assert sol_before.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol_before.objective_value, rel=1e-4) == 6701.25

    # Serializar
    prob_dict = {
        "type": "Monoobjetivo",
        "variables": var_names,
        "mono_objective": {
            "sense": "Minimizar",
            "coefficients": obj_coeffs,
        },
        "constraints": constraints_raw,
    }
    json_str = serialize_model(prob_dict, {"name": "Generacion Hidroelectrica 4 Periodos"})

    # Deserializar
    loaded = deserialize_model(json_str)

    # Reconstruir LPProblem desde datos cargados
    prob_lp_after = LPProblem(
        variables=loaded["var_names"],
        objective=LinearObjective("Z", Sense.from_str(loaded["obj_sense"]), loaded["obj_coeffs"]),
        constraints=[
            LinearConstraint(
                c["name"],
                {v: c[v] for v in loaded["var_names"]},
                Operator.from_str(c["operator"]),
                c["rhs"],
            )
            for c in loaded["constraints_data"]
        ],
    )

    sol_after = solve_lp(prob_lp_after)
    assert sol_after.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol_after.objective_value, rel=1e-4) == 6701.25

    # Firmas coinciden
    sig_before = build_model_signature("Monoobjetivo", var_names, "Minimizar", obj_coeffs, constraints_data=constraints_raw)
    sig_after = build_model_signature("Monoobjetivo", loaded["var_names"], loaded["obj_sense"], loaded["obj_coeffs"], constraints_data=loaded["constraints_data"])
    assert sig_before == sig_after


def test_invalid_json_and_schema_validation():
    """Valida el manejo robusto de JSONs corruptos o esquemas incompatibles."""
    with pytest.raises(ValueError, match="JSON malformado"):
        deserialize_model("{corrupt_json: 123}")

    with pytest.raises(ValueError, match="schema_version"):
        deserialize_model(json.dumps({"problem": {}}))

    with pytest.raises(ValueError, match="no soportada"):
        deserialize_model(json.dumps({"schema_version": "99.0", "problem": {}}))

    with pytest.raises(ValueError, match="Tipo de problema no valido"):
        deserialize_model(json.dumps({"schema_version": "1.0", "problem": {"type": "Invalido"}}))


def test_comma_decimal_parsing():
    """Valida que valores con coma decimal '2,4525' se procesen correctamente."""
    prob_dict = {
        "type": "Monoobjetivo",
        "variables": ["x1"],
        "mono_objective": {"sense": "Maximizar", "coefficients": {"x1": "3,5"}},
        "constraints": [{"name": "R1", "coefficients": {"x1": "2,4525"}, "operator": "<=", "rhs": "60,5"}],
    }
    json_str = serialize_model(prob_dict)
    loaded = deserialize_model(json_str)

    assert loaded["obj_coeffs"]["x1"] == 3.5
    assert loaded["constraints_data"][0]["x1"] == 2.4525
    assert loaded["constraints_data"][0]["rhs"] == 60.5
