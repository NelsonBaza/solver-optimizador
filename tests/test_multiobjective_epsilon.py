"""Pruebas del motor epsilon-constraint con N objetivos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import solver_optimizador.multiobjective_epsilon as epsilon_module

from solver_optimizador import (
    BiobjectiveProblem,
    LinearConstraint,
    LinearObjective,
    MultiobjectiveProblem,
    Operator,
    Sense,
    build_multiobjective_problem_from_state,
    classify_pareto_multiobjective,
    deserialize_model,
    save_multiobjective_projection_plots,
    solve_multiobjective_epsilon_constraint,
)
from solver_optimizador.multiobjective_epsilon import _deduplicate_runs


ROOT = Path(__file__).resolve().parents[1]
MODEL_3 = ROOT / "models" / "ejemplo_tres_objetivos.json"


@pytest.fixture(scope="module")
def problem3() -> MultiobjectiveProblem:
    state = deserialize_model(MODEL_3.read_text(encoding="utf-8"))
    return build_multiobjective_problem_from_state(
        var_names=state["var_names"],
        objectives=state["objectives"],
        canonical_constraints=state["constraints_data"],
    )


def _problem4() -> MultiobjectiveProblem:
    return MultiobjectiveProblem(
        variables=["x", "y"],
        objectives=[
            LinearObjective("Z1", Sense.MAXIMIZE, {"x": 1.0}),
            LinearObjective("Z2", Sense.MAXIMIZE, {"y": 1.0}),
            LinearObjective("Z3", Sense.MAXIMIZE, {"x": 1.0, "y": 1.0}),
            LinearObjective("Z4", Sense.MAXIMIZE, {"x": 1.0, "y": 2.0}),
        ],
        constraints=[
            LinearConstraint("total", {"x": 1.0, "y": 1.0}, Operator.LE, 4.0),
            LinearConstraint("x", {"x": 1.0}, Operator.LE, 3.0),
            LinearConstraint("y", {"y": 1.0}, Operator.LE, 3.0),
        ],
    )


def test_json_tres_objetivos_y_sentidos_mixtos(problem3) -> None:
    assert len(problem3.objectives) == 3
    assert [objective.sense for objective in problem3.objectives] == [
        Sense.MAXIMIZE,
        Sense.MAXIMIZE,
        Sense.MINIMIZE,
    ]


def test_objectives_generico_tambien_admite_dos_objetivos() -> None:
    document = json.loads(MODEL_3.read_text(encoding="utf-8"))
    document["problem"]["type"] = "Biobjetivo"
    document["problem"]["objectives"] = document["problem"]["objectives"][:2]
    state = deserialize_model(json.dumps(document))
    assert state["problem_type"] == "Biobjetivo"
    assert len(state["objectives"]) == 2
    assert state["obj1_sense"] == "Maximizar"


def test_objectives_y_bio_objectives_simultaneos_se_rechazan() -> None:
    document = json.loads(MODEL_3.read_text(encoding="utf-8"))
    document["problem"]["type"] = "Biobjetivo"
    document["problem"]["objectives"] = document["problem"]["objectives"][:2]
    document["problem"]["bio_objectives"] = {"obj1": {}, "obj2": {}}
    with pytest.raises(ValueError, match="simultáneamente"):
        deserialize_model(json.dumps(document))


def test_multiobjetivo_exige_al_menos_tres() -> None:
    document = json.loads(MODEL_3.read_text(encoding="utf-8"))
    document["problem"]["objectives"] = document["problem"]["objectives"][:2]
    with pytest.raises(ValueError, match="al menos tres"):
        deserialize_model(json.dumps(document))


def test_matriz_de_pagos_3x3_y_desempate(problem3) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 1, 3: 1}
    )
    assert len(result.payoff_matrix) == 3
    assert all(
        len(row["objective_values"]) == 3
        for row in result.payoff_matrix.values()
    )
    assert result.payoff_matrix["opt_Z1"]["objective_values"] == pytest.approx(
        {"Z1": 8.0, "Z2": 2.0, "Z3": 10.0}
    )
    assert result.payoff_matrix["opt_Z2"]["objective_values"] == pytest.approx(
        {"Z1": 2.0, "Z2": 8.0, "Z3": 10.0}
    )
    assert result.payoff_matrix["opt_Z3"]["objective_values"] == pytest.approx(
        {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0}
    )


@pytest.mark.parametrize("primary", [1, 2, 3])
def test_cualquier_objetivo_puede_ser_principal(problem3, primary) -> None:
    restricted = {index: 1 for index in (1, 2, 3) if index != primary}
    result = solve_multiobjective_epsilon_constraint(problem3, primary, restricted)
    assert result.primary_objective == primary
    assert result.constrained_objectives == sorted(restricted)
    assert len(result.runs) == 4


def test_r_distintos_y_producto_cartesiano(problem3) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 2, 3: 1}
    )
    assert result.total_runs == 6
    assert len(result.runs) == 6
    assert {
        (run["epsilon_indices"]["Z2"], run["epsilon_indices"]["Z3"])
        for run in result.runs
    } == {(t2, t3) for t2 in range(3) for t3 in range(2)}


def test_operadores_max_y_min(problem3) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 1, 3: 1}
    )
    assert all(
        run["constraint_operators"] == {"Z2": ">=", "Z3": "<="}
        for run in result.runs
    )


def test_cada_corrida_conserva_restricciones_originales(
    problem3, monkeypatch
) -> None:
    original_solve_lp = epsilon_module.solve_lp
    sweep_problems = []

    def spy(problem, tol=1e-7):
        if any(
            constraint.name.startswith("_epsilon_")
            for constraint in problem.constraints
        ):
            sweep_problems.append(problem)
        return original_solve_lp(problem, tol=tol)

    monkeypatch.setattr(epsilon_module, "solve_lp", spy)
    result = epsilon_module.solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 1, 3: 1}
    )

    assert len(sweep_problems) == result.total_runs == 4
    original_names = {constraint.name for constraint in problem3.constraints}
    assert all(
        original_names.issubset(
            {constraint.name for constraint in submitted.constraints}
        )
        for submitted in sweep_problems
    )


def test_objetivos_se_reconstruyen_desde_el_mismo_x(problem3) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=2, r_by_objective={1: 1, 3: 2}
    )
    for run in result.runs:
        assert {
            "run_index",
            "epsilon_indices",
            "epsilon_levels",
            "status",
            "x",
            "objective_values",
            "execution_time_sec",
        }.issubset(run)
        if run["x"] is None:
            continue
        expected = {
            f"Z{index}": objective.evaluate(run["x"])
            for index, objective in enumerate(problem3.objectives, start=1)
        }
        assert run["objective_values"] == pytest.approx(expected)


def test_infactibles_no_detienen_el_barrido(problem3) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 1, 3: 1}
    )
    assert len(result.runs) == 4
    assert any(run["status"] == "infeasible" for run in result.runs)
    assert any("infactibles" in note for note in result.notes)


def test_cuatro_objetivos_max_y_matriz_4x4() -> None:
    problem = _problem4()
    result = solve_multiobjective_epsilon_constraint(
        problem, primary_objective=1, r_by_objective={2: 1, 3: 1, 4: 1}
    )
    assert len(result.payoff_matrix) == 4
    assert result.total_runs == 8
    assert len(result.runs) == 8
    assert all(
        len(row["objective_values"]) == 4
        for row in result.payoff_matrix.values()
    )


def test_resultado_general_conserva_campos_compatibles_en_dos_objetivos() -> None:
    biobjective = BiobjectiveProblem(
        variables=["x", "y"],
        objective1=LinearObjective("Z1", Sense.MAXIMIZE, {"x": 1.0}),
        objective2=LinearObjective("Z2", Sense.MAXIMIZE, {"y": 1.0}),
        constraints=[
            LinearConstraint("total", {"x": 1.0, "y": 1.0}, Operator.LE, 4.0)
        ],
    )
    problem = MultiobjectiveProblem(
        variables=biobjective.variables,
        objectives=[biobjective.objective1, biobjective.objective2],
        constraints=biobjective.constraints,
    )
    result = solve_multiobjective_epsilon_constraint(problem, 1, {2: 1})

    assert len(result.runs) == 2
    assert all(
        run["Z1"] == pytest.approx(run["objective_values"]["Z1"])
        and run["Z2"] == pytest.approx(run["objective_values"]["Z2"])
        for run in result.runs
        if run["x"] is not None
    )
    assert all(
        solution["Z1"] == pytest.approx(solution["objective_values"]["Z1"])
        and solution["Z2"] == pytest.approx(solution["objective_values"]["Z2"])
        for solution in result.unique_solutions
    )


def test_duplicados_comparan_todos_los_objetivos(problem3) -> None:
    base = {
        "status": "optimal",
        "x": {"x": 1.0, "y": 1.0},
        "epsilon_indices": {"Z2": 0, "Z3": 0},
        "epsilon_levels": {"Z2": 0.0, "Z3": 0.0},
    }
    runs = [
        {
            **base,
            "run_index": 0,
            "objective_values": {"Z1": 1, "Z2": 1, "Z3": 2},
        },
        {
            **base,
            "run_index": 1,
            "objective_values": {"Z1": 1, "Z2": 1, "Z3": 3},
        },
    ]
    assert len(_deduplicate_runs(problem3, runs, tol=1e-6)) == 2


def test_dominancia_utiliza_tres_dimensiones(problem3) -> None:
    solutions = [
        {
            "id": "A",
            "x": {},
            "objective_values": {"Z1": 5, "Z2": 5, "Z3": 5},
            "run_indices": [0],
            "epsilon_indices": [],
            "epsilon_levels": [],
        },
        {
            "id": "B",
            "x": {},
            "objective_values": {"Z1": 5, "Z2": 5, "Z3": 6},
            "run_indices": [1],
            "epsilon_indices": [],
            "epsilon_levels": [],
        },
    ]
    classification = classify_pareto_multiobjective(problem3, solutions)
    assert classification["A"]["status"] == "No dominada"
    assert classification["B"]["status"] == "Dominada (por A)"


def test_validaciones_de_r_y_objetivo(problem3) -> None:
    with pytest.raises(ValueError, match="objetivo principal Z1"):
        solve_multiobjective_epsilon_constraint(
            problem3, 1, {1: 2, 2: 2, 3: 2}
        )
    with pytest.raises(ValueError, match="Z4"):
        solve_multiobjective_epsilon_constraint(problem3, 1, {2: 2, 4: 2})
    with pytest.raises(ValueError, match="Falta especificar r"):
        solve_multiobjective_epsilon_constraint(problem3, 1, {2: 2})


def test_proyecciones_por_objetivo_restringido(problem3, tmp_path) -> None:
    result = solve_multiobjective_epsilon_constraint(
        problem3, primary_objective=1, r_by_objective={2: 1, 3: 1}
    )
    generated = save_multiobjective_projection_plots(
        problem3, result, "Ejemplo", tmp_path, "ejemplo_tres_objetivos"
    )
    assert [path.name for path, _ in generated] == [
        "ejemplo_tres_objetivos_epsilon_Z1_vs_Z2.png",
        "ejemplo_tres_objetivos_epsilon_Z1_vs_Z3.png",
    ]
    assert all(path.stat().st_size > 10_000 for path, _ in generated)
    assert all(
        point["nondominated"]
        for _, points in generated
        for point in points
    )
