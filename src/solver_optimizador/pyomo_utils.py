"""Utilidades pequenas compartidas por los adaptadores Pyomo actuales."""

from __future__ import annotations

from typing import Any, Mapping

import pyomo.environ as pyo


def build_linear_expression(
    coefficients: Mapping[str, float],
    variables: Mapping[str, Any],
) -> Any:
    """Construye una expresion Pyomo, incluido el cero algebraico.

    ``sum([])`` devuelve el entero Python ``0`` y una comparacion posterior se
    convierte en ``True`` o ``False`` antes de llegar a ``pyo.Constraint``.
    Para una restriccion constante se conserva un cero simbolico mediante una
    variable existente multiplicada por cero.
    """

    terms = [
        coefficient * variables[variable_name]
        for variable_name, coefficient in coefficients.items()
        if coefficient != 0.0
    ]
    if terms:
        return pyo.quicksum(terms)
    try:
        first_variable = next(iter(variables.values()))
    except StopIteration as exc:
        raise ValueError(
            "Se requiere al menos una variable para construir el cero algebraico."
        ) from exc
    return 0.0 * first_variable
