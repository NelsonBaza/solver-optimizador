"""Demuestra rechazo de codigo/no linealidad y aceptacion de expresiones lineales."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from solver_optimizador.indexed_expression import IndexedExpressionError, parse_linear_relation


SCALARS = {}
PARAMETERS = {"cost": {1: 3.0, 2: 4.0}}
VARIABLES = {"X": ("T", {1, 2}), "Y": ("T", {1, 2})}


def parse(source: str, index: int = 2):
    return parse_linear_relation(
        source,
        scalar_parameters=SCALARS,
        indexed_parameters=PARAMETERS,
        variable_sets=VARIABLES,
        index_symbol="t",
        index_value=index,
        context=f"Safety[{index}]",
    )


def main() -> None:
    rejected = (
        "eval(X[t]) <= 1",
        "exec(X[t]) <= 1",
        "__import__('os') <= 1",
        "open('file') <= 1",
        "X[t].real <= 1",
        "sin(X[t]) <= 1",
        "X[t] * Y[t] <= 1",
        "X[t] ** 2 <= 1",
    )
    accepted = (
        "2 * X[t] <= 1",
        "cost[t] * X[t] <= 1",
        "X[t] / 3600 <= 1",
        "X[t] - X[t-1] = 0",
    )
    for source in rejected:
        try:
            parse(source)
        except IndexedExpressionError:
            print(f"REJECTED: {source}")
        else:
            raise AssertionError(f"Unsafe/nonlinear expression accepted: {source}")
    for source in accepted:
        coefficients, operator, rhs = parse(source)
        assert operator in {"<=", ">=", "="}
        assert coefficients
        print(f"ACCEPTED: {source} -> nnz={len(coefficients)}, rhs={rhs:g}")
    print("RESULT: PASS (indexed expression safety contract satisfied)")


if __name__ == "__main__":
    main()
