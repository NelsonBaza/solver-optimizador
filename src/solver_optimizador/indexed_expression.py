"""Parser estatico y evaluador afín seguro para familias indexadas."""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Mapping


class IndexedExpressionError(ValueError):
    """Expresion indexada invalida, insegura o no lineal."""


@dataclass(frozen=True)
class AffineExpression:
    constant: float = 0.0
    coefficients: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "coefficients",
            {name: value for name, value in (self.coefficients or {}).items() if value != 0.0},
        )

    @property
    def is_numeric(self) -> bool:
        return not self.coefficients


def _combine(left: AffineExpression, right: AffineExpression, sign: float) -> AffineExpression:
    coefficients = dict(left.coefficients or {})
    for name, value in (right.coefficients or {}).items():
        coefficients[name] = coefficients.get(name, 0.0) + sign * value
        if coefficients[name] == 0.0:
            del coefficients[name]
    return AffineExpression(left.constant + sign * right.constant, coefficients)


def _scale(expression: AffineExpression, factor: float) -> AffineExpression:
    return AffineExpression(
        expression.constant * factor,
        {name: value * factor for name, value in (expression.coefficients or {}).items()},
    )


class _AffineParser:
    def __init__(
        self,
        *,
        scalar_parameters: Mapping[str, float],
        indexed_parameters: Mapping[str, Mapping[int, float]],
        variable_sets: Mapping[str, tuple[str, set[int]]],
        index_symbol: str,
        index_value: int,
        context: str,
        allow_variables: bool,
    ) -> None:
        self.scalar_parameters = scalar_parameters
        self.indexed_parameters = indexed_parameters
        self.variable_sets = variable_sets
        self.index_symbol = index_symbol
        self.index_value = index_value
        self.context = context
        self.allow_variables = allow_variables

    def parse(self, source: str) -> AffineExpression:
        try:
            tree = ast.parse(source.strip(), mode="eval")
        except SyntaxError as exc:
            raise IndexedExpressionError(f"{self.context}: sintaxis invalida: {exc.msg}.") from exc
        return self._visit(tree.body)

    def _visit(self, node: ast.AST) -> AffineExpression:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise IndexedExpressionError(f"{self.context}: solo se permiten literales numericos.")
            value = float(node.value)
            if not math.isfinite(value):
                raise IndexedExpressionError(f"{self.context}: los valores deben ser finitos.")
            return AffineExpression(value)
        if isinstance(node, ast.Name):
            if node.id in self.scalar_parameters:
                return AffineExpression(float(self.scalar_parameters[node.id]))
            if node.id == self.index_symbol:
                return AffineExpression(float(self.index_value))
            raise IndexedExpressionError(f"{self.context}: simbolo desconocido '{node.id}'.")
        if isinstance(node, ast.Subscript):
            return self._subscript(node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else _scale(value, -1.0)
        if isinstance(node, ast.BinOp):
            left = self._visit(node.left)
            right = self._visit(node.right)
            if isinstance(node.op, ast.Add):
                return _combine(left, right, 1.0)
            if isinstance(node.op, ast.Sub):
                return _combine(left, right, -1.0)
            if isinstance(node.op, ast.Mult):
                if left.is_numeric:
                    return _scale(right, left.constant)
                if right.is_numeric:
                    return _scale(left, right.constant)
                raise IndexedExpressionError(
                    f"{self.context}: multiplicacion no lineal entre expresiones con variables."
                )
            if isinstance(node.op, ast.Div):
                if not right.is_numeric:
                    raise IndexedExpressionError(
                        f"{self.context}: el denominador no puede depender de variables."
                    )
                if right.constant == 0.0:
                    raise IndexedExpressionError(f"{self.context}: division por cero.")
                return _scale(left, 1.0 / right.constant)
            raise IndexedExpressionError(
                f"{self.context}: operador no permitido '{type(node.op).__name__}'."
            )
        raise IndexedExpressionError(
            f"{self.context}: construccion no permitida '{type(node).__name__}'."
        )

    def _index(self, node: ast.AST) -> int:
        value = self._visit_index(node)
        if isinstance(value, bool) or int(value) != value:
            raise IndexedExpressionError(f"{self.context}: el indice debe ser entero.")
        return int(value)

    def _visit_index(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == self.index_symbol:
            return float(self.index_value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._visit_index(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            left = self._visit_index(node.left)
            right = self._visit_index(node.right)
            return left + right if isinstance(node.op, ast.Add) else left - right
        raise IndexedExpressionError(
            f"{self.context}: el indice solo admite enteros y desplazamientos de '{self.index_symbol}'."
        )

    def _subscript(self, node: ast.Subscript) -> AffineExpression:
        if not isinstance(node.value, ast.Name):
            raise IndexedExpressionError(f"{self.context}: acceso indexado no permitido.")
        symbol = node.value.id
        index = self._index(node.slice)
        if symbol in self.indexed_parameters:
            values = self.indexed_parameters[symbol]
            if index not in values:
                raise IndexedExpressionError(
                    f"{self.context} referencia {symbol}[{index}], fuera de su conjunto."
                )
            return AffineExpression(float(values[index]))
        if symbol in self.variable_sets:
            if not self.allow_variables:
                raise IndexedExpressionError(
                    f"{self.context}: el coeficiente no puede depender de la variable {symbol}[{index}]."
                )
            set_name, indices = self.variable_sets[symbol]
            if index not in indices:
                raise IndexedExpressionError(
                    f"{self.context} referencia {symbol}[{index}], fuera del conjunto {set_name}."
                )
            return AffineExpression(0.0, {f"{symbol}_{index}": 1.0})
        raise IndexedExpressionError(f"{self.context}: familia o parametro desconocido '{symbol}'.")


_RELATION_PATTERN = re.compile(r"<=|>=|(?<![<>=!])=(?!=)")


def parse_linear_relation(
    source: str,
    *,
    scalar_parameters: Mapping[str, float],
    indexed_parameters: Mapping[str, Mapping[int, float]],
    variable_sets: Mapping[str, tuple[str, set[int]]],
    index_symbol: str,
    index_value: int,
    context: str,
) -> tuple[dict[str, float], str, float]:
    matches = list(_RELATION_PATTERN.finditer(source))
    if len(matches) != 1:
        raise IndexedExpressionError(
            f"{context}: la expresion debe contener exactamente un operador <=, >= o =."
        )
    match = matches[0]
    lhs_source, rhs_source = source[: match.start()], source[match.end() :]
    if not lhs_source.strip() or not rhs_source.strip():
        raise IndexedExpressionError(f"{context}: ambos lados de la relacion son obligatorios.")
    parser = _AffineParser(
        scalar_parameters=scalar_parameters,
        indexed_parameters=indexed_parameters,
        variable_sets=variable_sets,
        index_symbol=index_symbol,
        index_value=index_value,
        context=context,
        allow_variables=True,
    )
    lhs = parser.parse(lhs_source)
    rhs = parser.parse(rhs_source)
    difference = _combine(lhs, rhs, -1.0)
    return dict(difference.coefficients or {}), match.group(), -difference.constant


def parse_numeric_expression(
    source: str,
    *,
    scalar_parameters: Mapping[str, float],
    indexed_parameters: Mapping[str, Mapping[int, float]],
    index_symbol: str,
    index_value: int,
    context: str,
) -> float:
    parser = _AffineParser(
        scalar_parameters=scalar_parameters,
        indexed_parameters=indexed_parameters,
        variable_sets={},
        index_symbol=index_symbol,
        index_value=index_value,
        context=context,
        allow_variables=False,
    )
    result = parser.parse(source)
    if not result.is_numeric or not math.isfinite(result.constant):
        raise IndexedExpressionError(f"{context}: se esperaba una expresion numerica finita.")
    return result.constant
