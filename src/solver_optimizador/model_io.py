"""
Modulo de serializacion, deserializacion y persistencia de modelos matematicos (JSON).
Permite guardar y cargar formulaciones completas de manera portable, segura y versionada.
"""

import json
import re
from typing import Dict, Any, Optional, Tuple, List

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


def sanitize_filename(name: str) -> str:
    """
    Convierte un nombre descriptivo en un nombre de archivo seguro para el sistema operativo.
    """
    if not name or not name.strip():
        return "modelo_optimizacion.json"
    # Reemplazar caracteres no alfanumericos por guion bajo
    s = re.sub(r"[^\w\s-]", "", name.strip()).strip()
    s = re.sub(r"[-\s]+", "_", s).lower()
    if not s:
        s = "modelo"
    if not s.endswith(".json"):
        s += ".json"
    return s


def _safe_float(val: Any) -> float:
    """Convierte de forma segura un valor numerico o string (incluso con coma decimal) a float."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Aceptar coma o punto decimal
        clean = val.strip().replace(",", ".")
        return float(clean)
    raise ValueError(f"No se puede convertir a numero: {val}")


def validate_model_dict(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Valida la estructura y tipos de un diccionario de modelo.
    Retorna (True, None) si es valido, o (False, mensaje_error).
    """
    if not isinstance(data, dict):
        return False, "El archivo JSON debe contener un objeto principal (diccionario)."

    # 1. Validar version de esquema
    schema_ver = data.get("schema_version")
    if not schema_ver:
        return False, "El archivo no contiene el campo obligatorio 'schema_version'."
    if str(schema_ver) not in SUPPORTED_SCHEMA_VERSIONS:
        return False, f"Version de esquema no soportada: '{schema_ver}'. Versiones compatibles: {list(SUPPORTED_SCHEMA_VERSIONS)}"

    # 2. Validar metadata (opcional pero debe ser dict si existe)
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return False, "El campo 'metadata' debe ser un objeto/diccionario."

    # 3. Validar problem
    problem = data.get("problem")
    if not isinstance(problem, dict):
        return False, "El archivo debe contener un objeto 'problem' con la formulacion."

    prob_type = problem.get("type")
    if prob_type not in ("Monoobjetivo", "Biobjetivo"):
        return False, f"Tipo de problema no valido: '{prob_type}'. Debe ser 'Monoobjetivo' o 'Biobjetivo'."

    variables = problem.get("variables")
    if not isinstance(variables, list) or len(variables) == 0:
        return False, "El problema debe definir una lista no vacia de variables."

    if len(set(variables)) != len(variables):
        return False, "Los nombres de las variables deben ser unicos."

    for v in variables:
        if not isinstance(v, str) or not v.strip():
            return False, f"Nombre de variable invalido: {v}"

    # 4. Validar objetivos
    if prob_type == "Monoobjetivo":
        mono_obj = problem.get("mono_objective")
        if not isinstance(mono_obj, dict):
            return False, "El problema monoobjetivo debe contener 'mono_objective'."
        sense = mono_obj.get("sense")
        if sense not in ("Maximizar", "Minimizar"):
            return False, f"Sentido de objetivo monoobjetivo invalido: '{sense}'."
        coeffs = mono_obj.get("coefficients", {})
        if not isinstance(coeffs, dict):
            return False, "Los coeficientes del objetivo deben ser un diccionario."
        for v in variables:
            try:
                _safe_float(coeffs.get(v, 0.0))
            except Exception:
                return False, f"Coeficiente no numerico para la variable '{v}' en el objetivo."

    else:  # Biobjetivo
        bio_objs = problem.get("bio_objectives")
        if not isinstance(bio_objs, dict):
            return False, "El problema biobjetivo debe contener 'bio_objectives'."
        for obj_key in ("obj1", "obj2"):
            obj_data = bio_objs.get(obj_key)
            if not isinstance(obj_data, dict):
                return False, f"Falta la configuracion para '{obj_key}' en 'bio_objectives'."
            sense = obj_data.get("sense")
            if sense not in ("Maximizar", "Minimizar"):
                return False, f"Sentido invalido para {obj_key}: '{sense}'."
            coeffs = obj_data.get("coefficients", {})
            if not isinstance(coeffs, dict):
                return False, f"Los coeficientes de {obj_key} deben ser un diccionario."
            for v in variables:
                try:
                    _safe_float(coeffs.get(v, 0.0))
                except Exception:
                    return False, f"Coeficiente no numerico para la variable '{v}' en {obj_key}."

    # 5. Validar restricciones
    constraints = problem.get("constraints")
    if not isinstance(constraints, list):
        return False, "El campo 'constraints' debe ser una lista de restricciones."
    if len(constraints) == 0:
        return False, "El modelo debe incluir al menos una restriccion."

    for idx, c in enumerate(constraints):
        if not isinstance(c, dict):
            return False, f"La restriccion en la posicion {idx+1} debe ser un diccionario."
        c_name = c.get("name", f"R_{idx+1}")
        op = c.get("operator")
        if op not in ("<=", ">=", "="):
            return False, f"Operador invalido en restriccion '{c_name}': '{op}'."
        try:
            _safe_float(c.get("rhs", 0.0))
        except Exception:
            return False, f"Valor de lado derecho (RHS) no numerico en restriccion '{c_name}'."
        c_coeffs = c.get("coefficients", {})
        if not isinstance(c_coeffs, dict):
            return False, f"Los coeficientes de la restriccion '{c_name}' deben ser un diccionario."
        for v in variables:
            try:
                _safe_float(c_coeffs.get(v, 0.0))
            except Exception:
                return False, f"Coeficiente no numerico para variable '{v}' en restriccion '{c_name}'."

    return True, None


def serialize_model(
    problem_dict: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Serializa la formulacion del problema y su metadata a una cadena JSON determinista e indentada.
    """
    meta = {
        "name": (metadata or {}).get("name", "Modelo de Optimizacion"),
        "description": (metadata or {}).get("description", ""),
        "created_with": "solver-optimizador",
    }

    # Asegurar que los coeficientes y numeros sean floats puros
    prob_type = problem_dict.get("type", "Monoobjetivo")
    var_names = list(problem_dict.get("variables", ["x1", "x2"]))

    prob_clean: Dict[str, Any] = {
        "type": prob_type,
        "num_vars": len(var_names),
        "variables": var_names,
    }

    if prob_type == "Monoobjetivo":
        mono_raw = problem_dict.get("mono_objective", {})
        prob_clean["mono_objective"] = {
            "sense": mono_raw.get("sense", "Maximizar"),
            "coefficients": {v: _safe_float(mono_raw.get("coefficients", {}).get(v, 0.0)) for v in var_names},
        }
    else:
        bio_raw = problem_dict.get("bio_objectives", {})
        obj1_raw = bio_raw.get("obj1", {})
        obj2_raw = bio_raw.get("obj2", {})
        prob_clean["bio_objectives"] = {
            "obj1": {
                "sense": obj1_raw.get("sense", "Maximizar"),
                "coefficients": {v: _safe_float(obj1_raw.get("coefficients", {}).get(v, 0.0)) for v in var_names},
            },
            "obj2": {
                "sense": obj2_raw.get("sense", "Maximizar"),
                "coefficients": {v: _safe_float(obj2_raw.get("coefficients", {}).get(v, 0.0)) for v in var_names},
            },
        }
        mo_settings = problem_dict.get("multiobjective_settings", {})
        prob_clean["multiobjective_settings"] = {
            "mode": mo_settings.get("mode", "Barrido automatico"),
            "num_weights": int(mo_settings.get("num_weights", 6)),
            "custom_a1": float(mo_settings.get("custom_a1", 0.5)),
        }

    # Restricciones
    cons_clean = []
    for idx, c in enumerate(problem_dict.get("constraints", [])):
        c_coeffs_raw = c.get("coefficients", {})
        cons_clean.append({
            "name": str(c.get("name", f"Restriccion {idx+1}")).strip(),
            "coefficients": {v: _safe_float(c_coeffs_raw.get(v, 0.0)) for v in var_names},
            "operator": str(c.get("operator", "<=")),
            "rhs": _safe_float(c.get("rhs", 0.0)),
        })
    prob_clean["constraints"] = cons_clean

    full_data = {
        "schema_version": SCHEMA_VERSION,
        "metadata": meta,
        "problem": prob_clean,
    }

    return json.dumps(full_data, indent=2, ensure_ascii=False)


def deserialize_model(json_str: str) -> Dict[str, Any]:
    """
    Parsea y valida una cadena JSON. Retorna la estructura limpia y validada del modelo.
    Lanza ValueError si el formato o esquema no es valido.
    """
    try:
        data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"JSON malformado o no valido: {e}")

    is_valid, err_msg = validate_model_dict(data)
    if not is_valid:
        raise ValueError(err_msg)

    metadata = data.get("metadata", {})
    problem = data.get("problem", {})
    var_names = list(problem.get("variables", []))
    prob_type = problem.get("type", "Monoobjetivo")

    # Adaptar restricciones a formato amigable de dataframe / session_state
    constraints_data = []
    for c in problem.get("constraints", []):
        row = {
            "name": c.get("name", "Restriccion"),
            "operator": c.get("operator", "<="),
            "rhs": _safe_float(c.get("rhs", 0.0)),
        }
        c_coeffs = c.get("coefficients", {})
        for v in var_names:
            row[v] = _safe_float(c_coeffs.get(v, 0.0))
        constraints_data.append(row)

    res: Dict[str, Any] = {
        "schema_version": data.get("schema_version"),
        "metadata": {
            "name": metadata.get("name", "Modelo Importado"),
            "description": metadata.get("description", ""),
        },
        "problem_type": prob_type,
        "num_vars": len(var_names),
        "var_names": var_names,
        "constraints_data": constraints_data,
    }

    if prob_type == "Monoobjetivo":
        mono = problem.get("mono_objective", {})
        res["obj_sense"] = mono.get("sense", "Maximizar")
        res["obj_coeffs"] = {v: _safe_float(mono.get("coefficients", {}).get(v, 0.0)) for v in var_names}
    else:
        bio = problem.get("bio_objectives", {})
        res["obj1_sense"] = bio.get("obj1", {}).get("sense", "Maximizar")
        res["obj1_coeffs"] = {v: _safe_float(bio.get("obj1", {}).get("coefficients", {}).get(v, 0.0)) for v in var_names}
        res["obj2_sense"] = bio.get("obj2", {}).get("sense", "Maximizar")
        res["obj2_coeffs"] = {v: _safe_float(bio.get("obj2", {}).get("coefficients", {}).get(v, 0.0)) for v in var_names}
        mo_set = problem.get("multiobjective_settings", {})
        res["mo_mode"] = mo_set.get("mode", "Barrido automatico")
        res["num_weights"] = int(mo_set.get("num_weights", 6))
        res["custom_a1"] = float(mo_set.get("custom_a1", 0.5))

    return res
