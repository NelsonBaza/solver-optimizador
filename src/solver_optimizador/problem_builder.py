"""
Modulo constructor de problemas matematicos a partir de estructuras de estado normalizadas.
Garantiza coherencia total entre la interfaz de usuario, los tests y el motor de resolucion.
"""

from typing import List, Dict, Any, Optional
from .lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
)
from .model_io import normalize_constraints


def build_lp_problem_from_state(
    var_names: List[str],
    obj_sense: str,
    obj_coeffs: Dict[str, float],
    canonical_constraints: List[Dict[str, Any]],
    obj_name: str = "Z",
) -> LPProblem:
    """
    Construye una instancia valida de LPProblem (monoobjetivo) a partir de variables,
    sentido, coeficientes y restricciones normalizadas.
    """
    # Asegurar que las restricciones esten en forma canonica
    normalized_cons = normalize_constraints(canonical_constraints, var_names)

    sense_enum = Sense.from_str(obj_sense)
    clean_coeffs = {v: float(obj_coeffs.get(v, 0.0)) for v in var_names}

    constraints_list: List[LinearConstraint] = [
        LinearConstraint(
            name=c["name"],
            coefficients=c["coefficients"],
            operator=Operator.from_str(c["operator"]),
            rhs=float(c["rhs"]),
        )
        for c in normalized_cons
    ]

    return LPProblem(
        variables=list(var_names),
        objective=LinearObjective(name=obj_name, sense=sense_enum, coefficients=clean_coeffs),
        constraints=constraints_list,
    )


def build_biobjective_problem_from_state(
    var_names: List[str],
    obj1_sense: str,
    obj1_coeffs: Dict[str, float],
    obj2_sense: str,
    obj2_coeffs: Dict[str, float],
    canonical_constraints: List[Dict[str, Any]],
    obj1_name: str = "Z1",
    obj2_name: str = "Z2",
) -> BiobjectiveProblem:
    """
    Construye una instancia valida de BiobjectiveProblem a partir de variables,
    sentidos, coeficientes y restricciones normalizadas.
    """
    normalized_cons = normalize_constraints(canonical_constraints, var_names)

    sense1_enum = Sense.from_str(obj1_sense)
    sense2_enum = Sense.from_str(obj2_sense)

    clean_coeffs1 = {v: float(obj1_coeffs.get(v, 0.0)) for v in var_names}
    clean_coeffs2 = {v: float(obj2_coeffs.get(v, 0.0)) for v in var_names}

    constraints_list: List[LinearConstraint] = [
        LinearConstraint(
            name=c["name"],
            coefficients=c["coefficients"],
            operator=Operator.from_str(c["operator"]),
            rhs=float(c["rhs"]),
        )
        for c in normalized_cons
    ]

    return BiobjectiveProblem(
        variables=list(var_names),
        objective1=LinearObjective(name=obj1_name, sense=sense1_enum, coefficients=clean_coeffs1),
        objective2=LinearObjective(name=obj2_name, sense=sense2_enum, coefficients=clean_coeffs2),
        constraints=constraints_list,
    )
