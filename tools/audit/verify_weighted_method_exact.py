"""Oraculo exacto de la suma ponderada normalizada para Benchmark A.

Usa solo biblioteca estandar y ``fractions.Fraction``. No importa codigo de
produccion, Pyomo ni HiGHS.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations


Point = tuple[F, F]


@dataclass(frozen=True)
class Boundary:
    x1: F
    x2: F
    rhs: F

    def lhs(self, point: Point) -> F:
        return self.x1 * point[0] + self.x2 * point[1]


BOUNDARIES = (
    Boundary(F(1), F(1), F(130)),
    Boundary(F(5, 2), F(1), F(250)),
    Boundary(F(1), F(0), F(0)),
    Boundary(F(0), F(1), F(0)),
)

COURSE_WEIGHTS = (
    (F(0), F(1)),
    (F(1, 5), F(4, 5)),
    (F(2, 5), F(3, 5)),
    (F(3, 5), F(2, 5)),
    (F(4, 5), F(1, 5)),
    (F(1), F(0)),
)
DIAGNOSTIC_WEIGHT = (F(1, 2), F(1, 2))

EXPECTED = {
    (F(0), F(1)): (F(0), F(130)),
    (F(1, 5), F(4, 5)): (F(0), F(130)),
    (F(2, 5), F(3, 5)): (F(80), F(50)),
    (F(1, 2), F(1, 2)): (F(80), F(50)),
    (F(3, 5), F(2, 5)): (F(80), F(50)),
    (F(4, 5), F(1, 5)): (F(80), F(50)),
    (F(1), F(0)): (F(100), F(0)),
}


def intersection(first: Boundary, second: Boundary) -> Point | None:
    determinant = first.x1 * second.x2 - first.x2 * second.x1
    if determinant == 0:
        return None
    return (
        (first.rhs * second.x2 - first.x2 * second.rhs) / determinant,
        (first.x1 * second.rhs - first.rhs * second.x1) / determinant,
    )


def is_feasible(point: Point) -> bool:
    x1, x2 = point
    return (
        x1 >= 0
        and x2 >= 0
        and x1 + x2 <= 130
        and F(5, 2) * x1 + x2 <= 250
    )


def vertices() -> tuple[Point, ...]:
    candidates = {
        point
        for first, second in combinations(BOUNDARIES, 2)
        if (point := intersection(first, second)) is not None and is_feasible(point)
    }
    return tuple(sorted(candidates))


def z1(point: Point) -> F:
    return 10 * point[0] + 3 * point[1]


def z2(point: Point) -> F:
    return F(4, 5) * point[0] + F(13, 10) * point[1]


def n1(point: Point) -> F:
    return (z1(point) - 390) / 610


def n2(point: Point) -> F:
    return (z2(point) - 80) / 89


def weighted_value(point: Point, alpha1: F, alpha2: F) -> F:
    return alpha1 * n1(point) + alpha2 * n2(point)


def format_fraction(value: F) -> str:
    return str(value) if value.denominator != 1 else str(value.numerator)


def format_point(point: Point) -> str:
    return f"({format_fraction(point[0])},{format_fraction(point[1])})"


def solve_weight(points: tuple[Point, ...], alpha1: F, alpha2: F) -> tuple[Point, F]:
    scores = {point: weighted_value(point, alpha1, alpha2) for point in points}
    optimum = max(scores.values())
    maximizers = tuple(point for point, value in scores.items() if value == optimum)
    assert len(maximizers) == 1, (alpha1, alpha2, maximizers)
    return maximizers[0], optimum


def main() -> None:
    points = vertices()
    assert points == ((F(0), F(0)), (F(0), F(130)), (F(80), F(50)), (F(100), F(0)))

    z1_anchor = max(points, key=z1)
    z2_anchor = max(points, key=z2)
    assert (z1_anchor, z1(z1_anchor), z2(z1_anchor)) == ((F(100), F(0)), F(1000), F(80))
    assert (z2_anchor, z1(z2_anchor), z2(z2_anchor)) == ((F(0), F(130)), F(390), F(169))
    assert n1(z2_anchor) == 0 and n1(z1_anchor) == 1
    assert n2(z1_anchor) == 0 and n2(z2_anchor) == 1

    print("NORMALIZED_WEIGHTED_METHOD_EXACT_ORACLE")
    print("normalization: N1=(Z1-390)/610; N2=(Z2-80)/89")
    print("objective: MAX W=alpha1*N1+alpha2*N2")
    print("payoff: opt_Z1=(100,0;1000,80) opt_Z2=(0,130;390,169)")

    for alpha1, alpha2 in (*COURSE_WEIGHTS, DIAGNOSTIC_WEIGHT):
        assert alpha1 >= 0 and alpha2 >= 0 and alpha1 + alpha2 == 1
        point, score = solve_weight(points, alpha1, alpha2)
        assert point == EXPECTED[(alpha1, alpha2)]
        print(
            "alpha1={} alpha2={} x={} Z1={} Z2={} N1={} N2={} W={}".format(
                float(alpha1),
                float(alpha2),
                format_point(point),
                format_fraction(z1(point)),
                format_fraction(z2(point)),
                format_fraction(n1(point)),
                format_fraction(n2(point)),
                format_fraction(score),
            )
        )

    print("RESULT: PASS (pure normalized weighted-sum oracle satisfied)")


if __name__ == "__main__":
    main()
