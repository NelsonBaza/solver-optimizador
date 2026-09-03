"""Oráculo exacto e independiente para Benchmark A.

Este script usa únicamente la biblioteca estándar. No importa el paquete
``solver_optimizador`` ni llama a ningún solver numérico. Enumera las
intersecciones de las fronteras, filtra factibilidad y evalúa objetivos y
ponderaciones mediante ``fractions.Fraction``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations


@dataclass(frozen=True)
class Constraint:
    name: str
    x1: F
    x2: F
    operator: str
    rhs: F

    def lhs(self, point: tuple[F, F]) -> F:
        return self.x1 * point[0] + self.x2 * point[1]

    def is_satisfied(self, point: tuple[F, F]) -> bool:
        lhs = self.lhs(point)
        if self.operator == "<=":
            return lhs <= self.rhs
        if self.operator == ">=":
            return lhs >= self.rhs
        if self.operator == "=":
            return lhs == self.rhs
        raise ValueError(f"Operador no soportado: {self.operator}")


CONSTRAINTS = (
    Constraint("c1", F(1), F(1), "<=", F(130)),
    Constraint("c2", F(5, 2), F(1), "<=", F(250)),
    Constraint("x1_nonnegative", F(1), F(0), ">=", F(0)),
    Constraint("x2_nonnegative", F(0), F(1), ">=", F(0)),
)

WEIGHTS = (
    (F(0), F(1)),
    (F(1, 5), F(4, 5)),
    (F(2, 5), F(3, 5)),
    (F(1, 2), F(1, 2)),
    (F(3, 5), F(2, 5)),
    (F(4, 5), F(1, 5)),
    (F(1), F(0)),
)

EXPECTED_VERTICES = (
    (F(0), F(0)),
    (F(0), F(130)),
    (F(80), F(50)),
    (F(100), F(0)),
)

EXPECTED_WEIGHTED_POINTS = {
    (F(0), F(1)): (F(0), F(130)),
    (F(1, 5), F(4, 5)): (F(0), F(130)),
    (F(2, 5), F(3, 5)): (F(80), F(50)),
    (F(1, 2), F(1, 2)): (F(80), F(50)),
    (F(3, 5), F(2, 5)): (F(80), F(50)),
    (F(4, 5), F(1, 5)): (F(80), F(50)),
    (F(1), F(0)): (F(100), F(0)),
}


def intersection(first: Constraint, second: Constraint) -> tuple[F, F] | None:
    determinant = first.x1 * second.x2 - first.x2 * second.x1
    if determinant == 0:
        return None
    x1 = (first.rhs * second.x2 - first.x2 * second.rhs) / determinant
    x2 = (first.x1 * second.rhs - first.rhs * second.x1) / determinant
    return x1, x2


def enumerate_feasible_vertices() -> tuple[tuple[F, F], ...]:
    points: set[tuple[F, F]] = set()
    for first, second in combinations(CONSTRAINTS, 2):
        point = intersection(first, second)
        if point is not None and all(row.is_satisfied(point) for row in CONSTRAINTS):
            points.add(point)
    return tuple(sorted(points))


def z1(point: tuple[F, F]) -> F:
    return F(10) * point[0] + F(3) * point[1]


def z2(point: tuple[F, F]) -> F:
    return F(4, 5) * point[0] + F(13, 10) * point[1]


def active_constraints(point: tuple[F, F]) -> tuple[str, ...]:
    return tuple(row.name for row in CONSTRAINTS if row.lhs(point) == row.rhs)


def unique_maximizer(
    points: tuple[tuple[F, F], ...], objective: Callable[[tuple[F, F]], F]
) -> tuple[tuple[F, F], F]:
    values = {point: objective(point) for point in points}
    optimum = max(values.values())
    maximizers = tuple(point for point, value in values.items() if value == optimum)
    assert len(maximizers) == 1, f"Se esperaba un maximizador único: {maximizers}"
    return maximizers[0], optimum


def weighted_value(point: tuple[F, F], alpha1: F, alpha2: F) -> F:
    """Valor legacy de Fase 1B, preservado para reproducibilidad histórica."""

    return alpha1 * z1(point) / F(610) + alpha2 * z2(point) / F(89)


def format_point(point: tuple[F, F]) -> str:
    return f"({point[0]}, {point[1]})"


def main() -> None:
    vertices = enumerate_feasible_vertices()
    assert vertices == EXPECTED_VERTICES, (vertices, EXPECTED_VERTICES)
    assert all(all(row.is_satisfied(point) for row in CONSTRAINTS) for point in vertices)

    z1_point, z1_optimum = unique_maximizer(vertices, z1)
    z2_point, z2_optimum = unique_maximizer(vertices, z2)
    assert (z1_point, z1_optimum, z2(z1_point)) == ((F(100), F(0)), F(1000), F(80))
    assert (z2_point, z1(z2_point), z2_optimum) == ((F(0), F(130)), F(390), F(169))

    z1_range = z1_optimum - z1(z2_point)
    z2_range = z2_optimum - z2(z1_point)
    assert z1_range == F(610)
    assert z2_range == F(89)

    print("BENCHMARK_A_EXACT_VERIFICATION")
    print("formulation: x1+x2<=130; (5/2)*x1+x2<=250; x1,x2>=0")
    print("objectives: MAX Z1=10*x1+3*x2; MAX Z2=(4/5)*x1+(13/10)*x2")
    print("vertices:")
    for point in vertices:
        print(
            f"  x={format_point(point)} feasible=True Z1={z1(point)} Z2={z2(point)} "
            f"active={','.join(active_constraints(point))}"
        )
    print(f"payoff_Z1: x={format_point(z1_point)} Z1={z1_optimum} Z2={z2(z1_point)}")
    print(f"payoff_Z2: x={format_point(z2_point)} Z1={z1(z2_point)} Z2={z2_optimum}")
    print(f"ranges: Z1={z1_range} Z2={z2_range}")
    print("weighted_runs:")

    for alpha1, alpha2 in WEIGHTS:
        assert alpha1 + alpha2 == 1
        point, score = unique_maximizer(
            vertices, lambda candidate: weighted_value(candidate, alpha1, alpha2)
        )
        expected_point = EXPECTED_WEIGHTED_POINTS[(alpha1, alpha2)]
        assert point == expected_point, ((alpha1, alpha2), point, expected_point)
        print(
            f"  alpha=({float(alpha1):.1f},{float(alpha2):.1f}) "
            f"alpha_exact=({alpha1},{alpha2}) x={format_point(point)} "
            f"Z1={z1(point)} Z2={z2(point)} W={score} "
            f"W_decimal={float(score):.9f} feasible=True"
        )

    print("RESULT: PASS (all exact Fraction assertions satisfied)")


if __name__ == "__main__":
    main()
