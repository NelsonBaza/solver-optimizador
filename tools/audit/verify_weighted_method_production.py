"""Verifica la implementacion productiva de la suma ponderada normalizada.

No es un oraculo independiente: importa el codigo bajo prueba. Su contraparte
independiente es ``verify_weighted_method_exact.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solver_optimizador.lp_models import (  # noqa: E402
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    Operator,
    Sense,
)
from solver_optimizador.model_io import deserialize_model  # noqa: E402
from solver_optimizador.multiobjective import (  # noqa: E402
    normalize_objective_value,
    solve_biobjective_weighted,
)
from solver_optimizador.problem_builder import (  # noqa: E402
    build_biobjective_problem_from_state,
)


WEIGHTS = [(0.0, 1.0), (0.2, 0.8), (0.4, 0.6), (0.5, 0.5), (0.6, 0.4), (0.8, 0.2), (1.0, 0.0)]
EXPECTED_BENCHMARK = [
    (0.0, 130.0, 390.0, 169.0),
    (0.0, 130.0, 390.0, 169.0),
    (80.0, 50.0, 950.0, 129.0),
    (80.0, 50.0, 950.0, 129.0),
    (80.0, 50.0, 950.0, 129.0),
    (80.0, 50.0, 950.0, 129.0),
    (100.0, 0.0, 1000.0, 80.0),
]


def benchmark_a() -> BiobjectiveProblem:
    return BiobjectiveProblem(
        variables=["x1", "x2"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x1": 10.0, "x2": 3.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"x1": 0.8, "x2": 1.3}),
        constraints=[
            LinearConstraint("c1", {"x1": 1.0, "x2": 1.0}, Operator.LE, 130.0),
            LinearConstraint("c2", {"x1": 2.5, "x2": 1.0}, Operator.LE, 250.0),
        ],
    )


def hydroelectric() -> BiobjectiveProblem:
    path = ROOT / "tests" / "fixtures" / "hydroelectric_full_24_vars.json"
    data = deserialize_model(path.read_text(encoding="utf-8"))
    variables = data["var_names"]
    return build_biobjective_problem_from_state(
        var_names=variables,
        obj1_sense="Minimizar",
        obj1_coeffs={v: (100.0 if v.startswith("GT") else 0.0) for v in variables},
        obj2_sense="Maximizar",
        obj2_coeffs={v: (1.0 if v == "V4" else 0.0) for v in variables},
        canonical_constraints=data["constraints_data"],
    )


def verify_run(problem: BiobjectiveProblem, run: dict, ranges: dict) -> None:
    z1 = problem.objective1.evaluate(run["x"])
    z2 = problem.objective2.evaluate(run["x"])
    n1 = normalize_objective_value(z1, ranges["Z1_min"], ranges["Z1_max"], problem.objective1.sense)
    n2 = normalize_objective_value(z2, ranges["Z2_min"], ranges["Z2_max"], problem.objective2.sense)
    w_value = run["alpha1"] * n1 + run["alpha2"] * n2
    assert math.isclose(run["Z1"], z1, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(run["Z2"], z2, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(run["N1"], n1, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(run["N2"], n2, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(run["W"], w_value, rel_tol=1e-12, abs_tol=1e-12)


def main() -> None:
    problem = benchmark_a()
    solution = solve_biobjective_weighted(problem, weights=WEIGHTS)
    print("BENCHMARK_A_PRODUCTION")
    for run, expected in zip(solution.weighted_runs, EXPECTED_BENCHMARK):
        verify_run(problem, run, solution.normalization_ranges)
        actual = (run["x"]["x1"], run["x"]["x2"], run["Z1"], run["Z2"])
        assert all(math.isclose(a, e, abs_tol=1e-7) for a, e in zip(actual, expected))
        print(
            f"alpha=({run['alpha1']:.1f},{run['alpha2']:.1f}) "
            f"x=({run['x']['x1']:.12g},{run['x']['x2']:.12g}) "
            f"Z1={run['Z1']:.12g} Z2={run['Z2']:.12g} "
            f"N1={run['N1']:.12g} N2={run['N2']:.12g} W={run['W']:.12g}"
        )

    problem = hydroelectric()
    hydro_weights = WEIGHTS[1:6]
    solution = solve_biobjective_weighted(problem, weights=hydro_weights)
    print("HYDROELECTRIC_PRODUCTION")
    expected_hydro = {
        (0.2, 0.8): (21416.25, 100.0),
        (0.4, 0.6): (21416.25, 100.0),
        (0.6, 0.4): (6701.25, 40.0),
        (0.8, 0.2): (6701.25, 40.0),
    }
    for run in solution.weighted_runs:
        verify_run(problem, run, solution.normalization_ranges)
        frontier_residual = run["Z1"] - (245.25 * run["Z2"] - 3108.75)
        assert math.isclose(frontier_residual, 0.0, abs_tol=1e-5)
        if (run["alpha1"], run["alpha2"]) == (0.5, 0.5):
            assert math.isclose(run["W"], 0.5, abs_tol=1e-10)
        else:
            expected = expected_hydro[(run["alpha1"], run["alpha2"])]
            assert math.isclose(run["Z1"], expected[0], abs_tol=1e-5)
            assert math.isclose(run["Z2"], expected[1], abs_tol=1e-7)
        print(
            f"alpha=({run['alpha1']:.1f},{run['alpha2']:.1f}) "
            f"Z1={run['Z1']:.12g} Z2={run['Z2']:.12g} "
            f"N1={run['N1']:.12g} N2={run['N2']:.12g} "
            f"W={run['W']:.12g} frontier_residual={frontier_residual:.3g}"
        )

    print("RESULT: PASS (production normalized weighted-sum contract satisfied)")


if __name__ == "__main__":
    main()
