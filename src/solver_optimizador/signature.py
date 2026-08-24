"""
Modulo para generar firmas deterministas del modelo matematico.
Permite detectar si los resultados mostrados en la interfaz corresponden
exactamente al modelo formulado actualmente o si quedaron desactualizados.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional


def build_model_signature(
    problem_type: str,
    var_names: List[str],
    obj_sense: Optional[str] = None,
    obj_coeffs: Optional[Dict[str, float]] = None,
    obj1_sense: Optional[str] = None,
    obj1_coeffs: Optional[Dict[str, float]] = None,
    obj2_sense: Optional[str] = None,
    obj2_coeffs: Optional[Dict[str, float]] = None,
    constraints_data: Optional[List[Dict[str, Any]]] = None,
    mo_mode: Optional[str] = None,
    num_weights: Optional[int] = None,
    custom_a1: Optional[float] = None,
) -> str:
    """
    Genera un hash SHA-256 determinista a partir de los parametros matematicos del modelo.
    Ignora aspectos visuales o temporales (editor_version, timestamps, widgets IDs).
    """
    canonical_data: Dict[str, Any] = {
        "problem_type": str(problem_type).strip(),
        "var_names": [str(v).strip() for v in var_names],
    }

    if problem_type == "Monoobjetivo":
        canonical_data["obj_sense"] = str(obj_sense).strip().lower() if obj_sense else "max"
        canonical_data["obj_coeffs"] = {
            v: float(obj_coeffs.get(v, 0.0)) for v in var_names
        } if obj_coeffs else {}
    else:  # Biobjetivo
        canonical_data["obj1_sense"] = str(obj1_sense).strip().lower() if obj1_sense else "max"
        canonical_data["obj1_coeffs"] = {
            v: float(obj1_coeffs.get(v, 0.0)) for v in var_names
        } if obj1_coeffs else {}
        canonical_data["obj2_sense"] = str(obj2_sense).strip().lower() if obj2_sense else "max"
        canonical_data["obj2_coeffs"] = {
            v: float(obj2_coeffs.get(v, 0.0)) for v in var_names
        } if obj2_coeffs else {}
        canonical_data["mo_mode"] = str(mo_mode).strip() if mo_mode else "Barrido automatico"
        if canonical_data["mo_mode"] == "Barrido automatico":
            canonical_data["num_weights"] = int(num_weights) if num_weights is not None else 6
        else:
            canonical_data["custom_a1"] = round(float(custom_a1), 4) if custom_a1 is not None else 0.5

    # Restricciones
    cons_list = []
    if constraints_data:
        for c in constraints_data:
            c_name = str(c.get("name", c.get("Nombre", ""))).strip()
            c_op = str(c.get("operator", c.get("Operador", "<="))).strip()
            raw_rhs = c.get("rhs", c.get("RHS", 0.0))
            try:
                c_rhs = float(raw_rhs)
            except (ValueError, TypeError):
                c_rhs = 0.0

            c_coeffs = {}
            for v in var_names:
                raw_c = c.get(v, 0.0)
                try:
                    c_coeffs[v] = float(raw_c)
                except (ValueError, TypeError):
                    c_coeffs[v] = 0.0

            cons_list.append({
                "name": c_name,
                "operator": c_op,
                "rhs": c_rhs,
                "coeffs": c_coeffs,
            })
    canonical_data["constraints"] = cons_list

    raw_json = json.dumps(canonical_data, sort_keys=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
