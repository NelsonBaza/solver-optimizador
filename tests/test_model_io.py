"""
Suite de pruebas unitarias para la serializacion, deserializacion, normalizacion y persistencia de modelos (model_io).
Incluye la prueba del caso exacto que origino el reporte de auditoria (MAX 10x1 + 15x2) y el filtrado
de filas dinamicas vacias en la tabla de restricciones.
"""

import json
import math
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
    normalize_constraints,
    is_empty_constraint_row,
    sanitize_filename,
    SCHEMA_VERSION,
)


def test_sanitize_filename():
    assert sanitize_filename("Generacion hidroelectrica 4 periodos") == "generacion_hidroelectrica_4_periodos.json"
    assert sanitize_filename("Modelo #1 / Tarea (2026)") == "modelo_1_tarea_2026.json"
    assert sanitize_filename("") == "modelo_optimizacion.json"


def test_is_empty_constraint_row_cases():
    """Valida la identificacion exacta de filas totalmente vacias frente a filas diligenciadas o ceros validos."""
    var_names = ["x1", "x2"]

    # Fila completamente vacia con None
    assert is_empty_constraint_row({"Nombre": None, "x1": None, "x2": None, "Operador": None, "RHS": None}, var_names) is True

    # Fila completamente vacia con NaN
    assert is_empty_constraint_row({"Nombre": float("nan"), "x1": float("nan"), "x2": float("nan"), "Operador": float("nan"), "RHS": float("nan")}, var_names) is True

    # Fila completamente vacia con strings vacios
    assert is_empty_constraint_row({"Nombre": "", "x1": "  ", "x2": "", "Operador": "", "RHS": ""}, var_names) is True

    # Fila completamente vacia en formato anidado
    assert is_empty_constraint_row({"name": None, "operator": None, "rhs": None, "coefficients": {"x1": None, "x2": None}}, var_names) is True

    # Fila con ceros validos (NO es vacia)
    assert is_empty_constraint_row({"Nombre": "R1", "x1": 0.0, "x2": 1.0, "Operador": "<=", "RHS": 10.0}, var_names) is False
    assert is_empty_constraint_row({"Nombre": "", "x1": 0.0, "x2": 0.0, "Operador": "", "RHS": None}, var_names) is False

    # Fila parcialmente diligenciada (NO es vacia)
    assert is_empty_constraint_row({"Nombre": "R1", "x1": None, "x2": None, "Operador": None, "RHS": None}, var_names) is False
    assert is_empty_constraint_row({"Nombre": None, "x1": 5.0, "x2": None, "Operador": None, "RHS": None}, var_names) is False


def test_empty_dynamic_constraint_row_filtering():
    """Valida que una fila dinamica vacia al final sea ignorada sin generar error."""
    var_names = ["x1", "x2"]
    raw_rows = [
        {"Nombre": "Restriccion 1", "x1": 10.0, "x2": 5.0, "Operador": "<=", "RHS": 130.0},
        {"Nombre": "Restriccion 2", "x1": 2.0, "x2": 13.0, "Operador": "<=", "RHS": 250.0},
        {"Nombre": None, "x1": None, "x2": None, "Operador": None, "RHS": None},
    ]

    canonical = normalize_constraints(raw_rows, var_names)
    assert len(canonical) == 2
    assert canonical[0]["name"] == "Restriccion 1"
    assert canonical[0]["coefficients"] == {"x1": 10.0, "x2": 5.0}
    assert canonical[0]["rhs"] == 130.0
    assert canonical[1]["name"] == "Restriccion 2"
    assert canonical[1]["coefficients"] == {"x1": 2.0, "x2": 13.0}
    assert canonical[1]["rhs"] == 250.0


def test_partially_filled_constraint_row_produces_clear_error():
    """Valida que filas incompletas produzcan errores claros y descriptivos."""
    var_names = ["x1", "x2"]

    # Falta operador en fila no vacia
    incomplete_op = [
        {"Nombre": "Restriccion 3", "x1": 1.0, "x2": 0.0, "Operador": None, "RHS": 50.0}
    ]
    with pytest.raises(ValueError, match="no especifica un operador"):
        normalize_constraints(incomplete_op, var_names)

    # Falta RHS en fila no vacia
    incomplete_rhs = [
        {"Nombre": "Restriccion 3", "x1": 1.0, "x2": 0.0, "Operador": "<=", "RHS": None}
    ]
    with pytest.raises(ValueError, match="no especifica un valor de lado derecho"):
        normalize_constraints(incomplete_rhs, var_names)


def test_mono_model_min_15x1_23x2_with_trailing_empty_row():
    """
    Valida el caso de prueba reportado por el usuario:
    MIN Z = 15x1 + 23x2
    10x1 + 5x2 <= 130
    2x1 + 13x2 <= 250
    + fila vacia adicional de st.data_editor.
    """
    var_names = ["x1", "x2"]
    obj_coeffs = {"x1": 15.0, "x2": 23.0}

    ui_constraints = [
        {"Nombre": "R1", "x1": 10.0, "x2": 5.0, "Operador": "<=", "RHS": 130.0},
        {"Nombre": "R2", "x1": 2.0, "x2": 13.0, "Operador": "<=", "RHS": 250.0},
        {"Nombre": float("nan"), "x1": None, "x2": None, "Operador": None, "RHS": None},
    ]

    canonical = normalize_constraints(ui_constraints, var_names)
    assert len(canonical) == 2

    # Resolver problema
    prob = LPProblem(
        variables=var_names,
        objective=LinearObjective("Z", Sense.MINIMIZE, obj_coeffs),
        constraints=[
            LinearConstraint(c["name"], c["coefficients"], Operator.from_str(c["operator"]), c["rhs"])
            for c in canonical
        ],
    )
    sol = solve_lp(prob)
    assert sol.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol.objective_value, abs=1e-5) == 0.0
    assert pytest.approx(sol.variable_values["x1"], abs=1e-5) == 0.0
    assert pytest.approx(sol.variable_values["x2"], abs=1e-5) == 0.0

    # Serializar y deserializar
    json_str = serialize_model(
        {
            "type": "Monoobjetivo",
            "variables": var_names,
            "mono_objective": {"sense": "Minimizar", "coefficients": obj_coeffs},
            "constraints": ui_constraints,
        },
        {"name": "Modelo Minimo"},
    )
    loaded = deserialize_model(json_str)
    assert len(loaded["constraints_data"]) == 2
    assert loaded["constraints_data"][0]["coefficients"] == {"x1": 10.0, "x2": 5.0}
    assert loaded["constraints_data"][1]["coefficients"] == {"x1": 2.0, "x2": 13.0}


def test_exact_bug_case_10x1_15x2_preservation():
    """
    Reproduce exactamente el caso que detecto la falla en pruebas reales:
    MAX Z = 10 x1 + 15 x2
    5 x1 + 4 x2 <= 15
    3 x1 + 1 x2 <= 20
    En formato real de salida de st.data_editor (Nombre, x1, x2, Operador, RHS).
    """
    var_names = ["x1", "x2"]
    obj_coeffs = {"x1": 10.0, "x2": 15.0}

    ui_constraints = [
        {"Nombre": "Restriccion 1", "x1": 5.0, "x2": 4.0, "Operador": "<=", "RHS": 15.0},
        {"Nombre": "Restriccion 2", "x1": 3.0, "x2": 1.0, "Operador": "<=", "RHS": 20.0},
    ]

    # 1. Normalizar
    canonical_cons = normalize_constraints(ui_constraints, var_names)
    assert len(canonical_cons) == 2
    assert canonical_cons[0]["name"] == "Restriccion 1"
    assert canonical_cons[0]["coefficients"] == {"x1": 5.0, "x2": 4.0}
    assert canonical_cons[0]["operator"] == "<="
    assert canonical_cons[0]["rhs"] == 15.0

    assert canonical_cons[1]["name"] == "Restriccion 2"
    assert canonical_cons[1]["coefficients"] == {"x1": 3.0, "x2": 1.0}
    assert canonical_cons[1]["operator"] == "<="
    assert canonical_cons[1]["rhs"] == 20.0

    # 2. Resolver modelo original
    prob_orig = LPProblem(
        variables=var_names,
        objective=LinearObjective("Z", Sense.MAXIMIZE, obj_coeffs),
        constraints=[
            LinearConstraint(c["name"], c["coefficients"], Operator.from_str(c["operator"]), c["rhs"])
            for c in canonical_cons
        ],
    )
    sol_orig = solve_lp(prob_orig)
    assert sol_orig.status == SolverStatus.OPTIMAL
    z_expected = sol_orig.objective_value
    assert z_expected > 0.0

    # 3. Serializar pasando los registros de la UI directamente
    prob_dict = {
        "type": "Monoobjetivo",
        "variables": var_names,
        "mono_objective": {"sense": "Maximizar", "coefficients": obj_coeffs},
        "constraints": ui_constraints,
    }
    json_str = serialize_model(prob_dict, {"name": "Modelo Prueba 2"})

    # 4. Inspeccionar el JSON crudo para garantizar que NO se guardaron ceros
    raw_parsed = json.loads(json_str)
    c1_json = raw_parsed["problem"]["constraints"][0]
    assert c1_json["name"] == "Restriccion 1"
    assert c1_json["coefficients"]["x1"] == 5.0
    assert c1_json["coefficients"]["x2"] == 4.0
    assert c1_json["rhs"] == 15.0

    c2_json = raw_parsed["problem"]["constraints"][1]
    assert c2_json["name"] == "Restriccion 2"
    assert c2_json["coefficients"]["x1"] == 3.0
    assert c2_json["coefficients"]["x2"] == 1.0
    assert c2_json["rhs"] == 20.0

    # 5. Deserializar y reconstruir problema
    loaded = deserialize_model(json_str)
    prob_loaded = LPProblem(
        variables=loaded["var_names"],
        objective=LinearObjective("Z", Sense.from_str(loaded["obj_sense"]), loaded["obj_coeffs"]),
        constraints=[
                LinearConstraint(
                    c["name"],
                    c["coefficients"],
                    Operator.from_str(c["operator"]),
                    c["rhs"],
            )
            for c in loaded["constraints_data"]
        ],
    )
    sol_loaded = solve_lp(prob_loaded)
    assert sol_loaded.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol_loaded.objective_value, rel=1e-5) == z_expected

    # 6. Firmas coinciden
    sig_before = build_model_signature("Monoobjetivo", var_names, "Maximizar", obj_coeffs, constraints_data=canonical_cons)
    sig_after = build_model_signature("Monoobjetivo", loaded["var_names"], loaded["obj_sense"], loaded["obj_coeffs"], constraints_data=loaded["constraints_data"])
    assert sig_before == sig_after


def test_normalize_constraints_validation_errors():
    """Valida que estructuras invalidas en restricciones lancen ValueError con mensaje claro."""
    var_names = ["x1", "x2"]

    # No es lista
    with pytest.raises(ValueError, match="lista"):
        normalize_constraints("no es lista", var_names)

    # Elemento no es dict
    with pytest.raises(ValueError, match="diccionario"):
        normalize_constraints(["no_dict"], var_names)

    # Falta operador
    with pytest.raises(ValueError, match="operador"):
        normalize_constraints([{"Nombre": "R1", "RHS": 10.0, "x1": 1.0}], var_names)

    # Operador invalido
    with pytest.raises(ValueError, match="Operador no valido"):
        normalize_constraints([{"Nombre": "R1", "Operador": "INVALID", "RHS": 10.0}], var_names)

    # Falta RHS
    with pytest.raises(ValueError, match="RHS"):
        normalize_constraints([{"Nombre": "R1", "Operador": "<="}], var_names)


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
    obj_coeffs = {v: (100.0 if v in ("x5", "x6", "x7", "x8") else 0.0) for v in var_names}

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
                    c["coefficients"],
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
    assert loaded["constraints_data"][0]["coefficients"]["x1"] == 2.4525
    assert loaded["constraints_data"][0]["rhs"] == 60.5
