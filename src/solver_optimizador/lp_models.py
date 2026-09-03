"""
Estructuras de datos y modelos para Programacion Lineal Continua.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple


def is_finite_number(val: Any) -> bool:
    """Verifica si un valor es un numero real finito (no None, no NaN, no infinito)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return math.isfinite(val)


class Sense(str, Enum):
    MAXIMIZE = "max"
    MINIMIZE = "min"

    @classmethod
    def from_str(cls, value: str) -> "Sense":
        val = value.strip().lower()
        if val in ("max", "maximizar", "maximize"):
            return cls.MAXIMIZE
        if val in ("min", "minimizar", "minimize"):
            return cls.MINIMIZE
        raise ValueError(f"Sentido no valido: '{value}'. Usar 'max' o 'min'.")


class Operator(str, Enum):
    LE = "<="
    GE = ">="
    EQ = "="

    @classmethod
    def from_str(cls, value: str) -> "Operator":
        val = value.strip()
        if val in ("<=", "<", "le"):
            return cls.LE
        if val in (">=", ">", "ge"):
            return cls.GE
        if val in ("=", "==", "eq"):
            return cls.EQ
        raise ValueError(f"Operador no valido: '{value}'. Usar '<=', '>=' o '='.")


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    INFEASIBLE_OR_UNBOUNDED = "infeasibleOrUnbounded"
    ERROR = "error"

    @property
    def user_friendly_message(self) -> str:
        messages = {
            self.OPTIMAL: "Optimo encontrado",
            self.INFEASIBLE: "Problema infactible",
            self.UNBOUNDED: "Problema no acotado",
            self.INFEASIBLE_OR_UNBOUNDED: "Infactible o no acotado",
            self.ERROR: "Error del solver",
        }
        return messages.get(self, "Estado desconocido")


@dataclass
class LinearObjective:
    name: str
    sense: Sense
    coefficients: Dict[str, float]

    def evaluate(self, variable_values: Dict[str, float]) -> float:
        return sum(
            self.coefficients.get(v, 0.0) * variable_values.get(v, 0.0)
            for v in self.coefficients
        )


@dataclass
class LinearConstraint:
    name: str
    coefficients: Dict[str, float]
    operator: Operator
    rhs: float

    def evaluate_lhs(self, variable_values: Dict[str, float]) -> float:
        return sum(
            self.coefficients.get(v, 0.0) * variable_values.get(v, 0.0)
            for v in self.coefficients
        )

    def calculate_slack(self, variable_values: Dict[str, float]) -> float:
        lhs = self.evaluate_lhs(variable_values)
        if self.operator == Operator.LE:
            return self.rhs - lhs
        elif self.operator == Operator.GE:
            return lhs - self.rhs
        else:  # EQ
            return abs(lhs - self.rhs)


@dataclass
class ConstraintResult:
    name: str
    lhs: float
    operator: str
    rhs: float
    slack: float
    is_active: bool


@dataclass
class LPProblem:
    variables: List[str]
    objective: LinearObjective
    constraints: List[LinearConstraint]

    def validate(self) -> None:
        if not self.variables:
            raise ValueError("El problema debe contener al menos una variable.")
        if not self.constraints:
            raise ValueError("El problema debe contener al menos una restriccion.")
        for v in self.variables:
            if not isinstance(v, str) or not v.strip():
                raise ValueError("Los nombres de las variables deben ser cadenas no vacias.")
        for c in self.constraints:
            if not is_finite_number(c.rhs):
                raise ValueError(f"El lado derecho (RHS) de la restriccion '{c.name}' no es un numero finito: {c.rhs}")
            for v, coeff in c.coefficients.items():
                if v not in self.variables:
                    raise ValueError(f"Variable '{v}' en restriccion '{c.name}' no declarada en variables.")
                if not is_finite_number(coeff):
                    raise ValueError(f"Coeficiente de '{v}' en restriccion '{c.name}' no es un numero finito: {coeff}")
        for v, coeff in self.objective.coefficients.items():
            if v not in self.variables:
                raise ValueError(f"Variable '{v}' en objetivo no declarada en variables.")
            if not is_finite_number(coeff):
                raise ValueError(f"Coeficiente de '{v}' en objetivo no es un numero finito: {coeff}")


@dataclass
class BiobjectiveProblem:
    variables: List[str]
    objective1: LinearObjective
    objective2: LinearObjective
    constraints: List[LinearConstraint]

    def validate(self) -> None:
        if not self.variables:
            raise ValueError("El problema debe contener al menos una variable.")
        if not self.constraints:
            raise ValueError("El problema debe contener al menos una restriccion.")
        for v in self.variables:
            if not isinstance(v, str) or not v.strip():
                raise ValueError("Los nombres de las variables deben ser cadenas no vacias.")
        for c in self.constraints:
            if not is_finite_number(c.rhs):
                raise ValueError(f"El lado derecho (RHS) de la restriccion '{c.name}' no es un numero finito: {c.rhs}")
            for v, coeff in c.coefficients.items():
                if v not in self.variables:
                    raise ValueError(f"Variable '{v}' en restriccion '{c.name}' no declarada en variables.")
                if not is_finite_number(coeff):
                    raise ValueError(f"Coeficiente de '{v}' en restriccion '{c.name}' no es un numero finito: {coeff}")
        for v, coeff in self.objective1.coefficients.items():
            if v not in self.variables:
                raise ValueError(f"Variable '{v}' en objetivo 1 no declarada en variables.")
            if not is_finite_number(coeff):
                raise ValueError(f"Coeficiente de '{v}' en objetivo 1 no es un numero finito: {coeff}")
        for v, coeff in self.objective2.coefficients.items():
            if v not in self.variables:
                raise ValueError(f"Variable '{v}' en objetivo 2 no declarada en variables.")
            if not is_finite_number(coeff):
                raise ValueError(f"Coeficiente de '{v}' en objetivo 2 no es un numero finito: {coeff}")


@dataclass
class LPSolution:
    status: SolverStatus
    status_message: str
    raw_termination: str
    objective_value: Optional[float] = None
    variable_values: Dict[str, float] = field(default_factory=dict)
    constraint_results: List[ConstraintResult] = field(default_factory=list)
    execution_time_sec: float = 0.0
    activity_tolerance: float = 1e-6


@dataclass
class MultiobjectiveSolution:
    individual_optima: Dict[str, Any]
    payoff_matrix: Dict[str, Any]
    normalization_ranges: Dict[str, float]
    weighted_runs: List[Dict[str, Any]]
    unique_solutions: List[Dict[str, Any]]
    pareto_classification: Dict[str, Any]
    timing: Dict[str, float]
    notes: List[str] = field(default_factory=list)
