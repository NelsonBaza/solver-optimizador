"""
Modulo de serializacion, deserializacion y persistencia de modelos matematicos (JSON).
Permite guardar y cargar formulaciones completas de manera portable, segura y versionada.
Incluye normalizacion canonica de restricciones y filtrado de filas dinamicas vacias.
"""

import json
import math
import re
from typing import Dict, Any, Optional, Tuple, List

from .constraint_import import validate_variable_names

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


def sanitize_filename(name: str) -> str:
    """
    Convierte un nombre descriptivo en un nombre de archivo seguro para el sistema operativo.
    """
    if not name or not name.strip():
        return "modelo_optimizacion.json"
    s = re.sub(r"[^\w\s-]", "", name.strip()).strip()
    s = re.sub(r"[-\s]+", "_", s).lower()
    if not s:
        s = "modelo"
    if not s.endswith(".json"):
        s += ".json"
    return s


def _is_blank_value(val: Any) -> bool:
    """
    Determina si un valor esta vacio (None, NaN, string vacio o espacios).
    Nota: 0 y 0.0 NO son valores vacios.
    """
    if val is None:
        return True
    if isinstance(val, (int, float)):
        if isinstance(val, bool):
            return False
        return math.isnan(val)
    if isinstance(val, str):
        s = val.strip()
        return s == "" or s.lower() == "nan" or s.lower() == "none"
    return False


def _safe_float(val: Any) -> float:
    """Convierte de forma segura un valor numerico o string (incluso con coma decimal) a float."""
    if _is_blank_value(val):
        raise ValueError(f"No se puede convertir un valor vacio/NaN a numero: {val}")
    if isinstance(val, (int, float)):
        number = float(val)
    elif isinstance(val, str):
        clean = val.strip().replace(",", ".")
        number = float(clean)
    else:
        raise ValueError(f"No se puede convertir a numero: {val}")
    if not math.isfinite(number):
        raise ValueError(f"El valor numerico debe ser finito: {val}")
    return number


def is_empty_constraint_row(row: Dict[str, Any], var_names: Optional[List[str]] = None) -> bool:
    """
    Determina si una fila de restricciones esta completamente vacia.
    Una fila se considera totalmente vacia si:
    - Nombre esta vacio o NaN
    - Operador esta vacio o NaN
    - RHS esta vacio o NaN
    - Todos los coeficientes de variables estan vacios o NaN.
    Si cualquier campo contiene un valor real (incluyendo el numero 0.0), la fila NO se considera vacia.
    """
    if not isinstance(row, dict):
        return False

    # 1. Comprobar nombre
    c_name = row.get("name") if "name" in row else row.get("Nombre")
    if not _is_blank_value(c_name):
        return False

    # 2. Comprobar operador
    c_op = row.get("operator") if "operator" in row else row.get("Operador")
    if not _is_blank_value(c_op):
        return False

    # 3. Comprobar RHS
    c_rhs = row.get("rhs") if "rhs" in row else row.get("RHS")
    if not _is_blank_value(c_rhs):
        return False

    # 4. Comprobar coeficientes
    nested_coeffs = row.get("coefficients")
    if isinstance(nested_coeffs, dict):
        for v in nested_coeffs.values():
            if not _is_blank_value(v):
                return False
    else:
        check_keys = var_names if var_names is not None else [k for k in row.keys() if k not in ("name", "Nombre", "operator", "Operador", "rhs", "RHS")]
        for k in check_keys:
            v = row.get(k)
            if not _is_blank_value(v):
                return False

    return True


def normalize_constraints(
    raw_constraints: List[Dict[str, Any]],
    var_names: List[str],
) -> List[Dict[str, Any]]:
    """
    Normaliza cualquier representacion de restricciones (formato UI aplanado o canonico anidado)
    a la estructura canonica unica:
    {
        "name": str,
        "coefficients": {v: float for v con coeficiente distinto de cero},
        "operator": str ("<=" | ">=" | "="),
        "rhs": float,
    }
    Filtra automaticamente filas completamente vacias (como la fila dinamica de st.data_editor).
    Lanza ValueError con mensaje descriptivo si faltan campos obligatorios en filas parcialmente diligenciadas.
    """
    if not isinstance(raw_constraints, list):
        raise ValueError(f"Las restricciones deben ser una lista, se recibio: {type(raw_constraints)}")

    canonical_list: List[Dict[str, Any]] = []
    variable_set = set(var_names)

    for idx, c in enumerate(raw_constraints):
        if not isinstance(c, dict):
            raise ValueError(f"La restriccion #{idx+1} debe ser un diccionario.")

        # Ignorar filas completamente vacias
        if is_empty_constraint_row(c, var_names):
            continue

        # 1. Nombre
        raw_name = c.get("name") if "name" in c else c.get("Nombre")
        if _is_blank_value(raw_name):
            c_name = f"Restriccion_{idx+1}"
        else:
            c_name = str(raw_name).strip()
            if not c_name:
                c_name = f"Restriccion_{idx+1}"

        # 2. Operador
        raw_op = c.get("operator") if "operator" in c else c.get("Operador")
        if _is_blank_value(raw_op):
            raise ValueError(f"La restriccion '{c_name}' no especifica un operador ('<=', '>=', '=').")
        c_op = str(raw_op).strip()
        if c_op not in ("<=", ">=", "="):
            raise ValueError(f"Operador no valido '{c_op}' en restriccion '{c_name}'.")

        # 3. Lado derecho (RHS)
        raw_rhs = c.get("rhs") if "rhs" in c else (c.get("RHS") if "RHS" in c else None)
        if _is_blank_value(raw_rhs):
            raise ValueError(f"La restriccion '{c_name}' no especifica un valor de lado derecho (RHS).")
        rhs_val = _safe_float(raw_rhs)

        # 4. Coeficientes (extraer de 'coefficients' anidado o del dict plano)
        coeffs_dict: Dict[str, float] = {}
        nested_coeffs = c.get("coefficients")
        if isinstance(nested_coeffs, dict):
            candidates = dict(nested_coeffs)
            candidates.update(
                {
                    key: value
                    for key, value in c.items()
                    if key in variable_set and key not in candidates
                }
            )
            for v, raw_v in candidates.items():
                if v not in variable_set:
                    continue
                if not _is_blank_value(raw_v):
                    value = _safe_float(raw_v)
                    if value != 0.0:
                        coeffs_dict[v] = value
        else:
            for v, raw_v in c.items():
                if v not in variable_set:
                    continue
                if not _is_blank_value(raw_v):
                    value = _safe_float(raw_v)
                    if value != 0.0:
                        coeffs_dict[v] = value

        canonical_list.append({
            "name": c_name,
            "coefficients": coeffs_dict,
            "operator": c_op,
            "rhs": rhs_val,
        })

    return canonical_list


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

    variable_errors = validate_variable_names(variables)
    if variable_errors:
        return False, variable_errors[0]

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

    # 5. Validar restricciones mediante normalizacion
    constraints = problem.get("constraints")
    if not isinstance(constraints, list):
        return False, "El campo 'constraints' debe ser una lista de restricciones."

    try:
        norm_cons = normalize_constraints(constraints, variables)
        if len(norm_cons) == 0:
            return False, "El modelo debe incluir al menos una restriccion valida."
    except Exception as e:
        return False, f"Error en restricciones: {e}"

    return True, None


def serialize_model(
    problem_dict: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Serializa la formulacion del problema y su metadata a una cadena JSON determinista e indentada.
    Normaliza obligatoriamente las restricciones para asegurar integridad absoluta.
    """
    raw_meta_name = (metadata or {}).get("name", "")
    clean_meta_name = str(raw_meta_name).strip() if raw_meta_name else ""
    if not clean_meta_name:
        clean_meta_name = "Modelo de Optimizacion"

    meta = {
        "name": clean_meta_name,
        "description": str((metadata or {}).get("description", "")).strip(),
        "created_with": "solver-optimizador",
    }

    prob_type = problem_dict.get("type", "Monoobjetivo")
    var_names = list(problem_dict.get("variables", ["x1", "x2"]))
    variable_errors = validate_variable_names(var_names)
    if variable_errors:
        raise ValueError("Variables invalidas: " + "; ".join(variable_errors))

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

    # Restricciones normalizadas
    raw_cons = problem_dict.get("constraints", [])
    prob_clean["constraints"] = normalize_constraints(raw_cons, var_names)

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

    # Normalizar restricciones para asegurar consistencia
    canonical_cons = normalize_constraints(problem.get("constraints", []), var_names)

    # Mantener representacion canonica dispersa. La UI solo crea una copia
    # densa y acotada cuando abre el editor manual para modelos pequenos.
    constraints_data = canonical_cons

    meta_name = str(metadata.get("name", "")).strip() or "Modelo Importado"
    res: Dict[str, Any] = {
        "schema_version": data.get("schema_version"),
        "metadata": {
            "name": meta_name,
            "description": str(metadata.get("description", "")).strip(),
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
