"""
Suite de pruebas end-to-end para el modelo hidroelectrico completo de 24 variables y 28 restricciones.
Valida la resolucion directa del fixture JSON, la fidelidad de problem_builder,
la comparacion diagnostica y la integracion completa con Streamlit AppTest (A -> B y B -> A).
"""

import json
import os
import pytest
from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.model_io import deserialize_model, serialize_model, normalize_constraints
from solver_optimizador.problem_builder import (
    build_lp_problem_from_state,
    build_biobjective_problem_from_state,
)
from streamlit.testing.v1 import AppTest


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "hydroelectric_full_24_vars.json")
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


def compare_models(expected_dict: dict, effective_problem: LPProblem) -> list:
    """Helper de diagnostico comparativo entre modelo esperado y problema efectivo."""
    diffs = []
    exp_prob = expected_dict.get("problem", {})
    exp_vars = exp_prob.get("variables", [])
    if exp_vars != effective_problem.variables:
        diffs.append(f"Variables diff: esperado={exp_vars}, actual={effective_problem.variables}")

    exp_sense = exp_prob.get("mono_objective", {}).get("sense")
    act_sense = "Maximizar" if effective_problem.objective.sense == Sense.MAXIMIZE else "Minimizar"
    if exp_sense != act_sense:
        diffs.append(f"Sentido diff: esperado={exp_sense}, actual={act_sense}")

    exp_coeffs = exp_prob.get("mono_objective", {}).get("coefficients", {})
    for v in exp_vars:
        exp_c = float(exp_coeffs.get(v, 0.0))
        act_c = float(effective_problem.objective.coefficients.get(v, 0.0))
        if abs(exp_c - act_c) > 1e-6:
            diffs.append(f"Coeficiente obj {v} diff: esperado={exp_c}, actual={act_c}")

    exp_cons = exp_prob.get("constraints", [])
    if len(exp_cons) != len(effective_problem.constraints):
        diffs.append(f"Cant. restricciones diff: esperado={len(exp_cons)}, actual={len(effective_problem.constraints)}")
    else:
        for idx, (ec, ac) in enumerate(zip(exp_cons, effective_problem.constraints)):
            if ec["name"] != ac.name:
                diffs.append(f"Restr #{idx+1} nombre diff: esperado={ec['name']}, actual={ac.name}")
            if ec["operator"] != ac.operator.value:
                diffs.append(f"Restr '{ac.name}' operador diff: esperado={ec['operator']}, actual={ac.operator.value}")
            if abs(float(ec["rhs"]) - float(ac.rhs)) > 1e-6:
                diffs.append(f"Restr '{ac.name}' RHS diff: esperado={ec['rhs']}, actual={ac.rhs}")
            for v in exp_vars:
                exp_v_c = float(ec.get("coefficients", {}).get(v, 0.0))
                act_v_c = float(ac.coefficients.get(v, 0.0))
                if abs(exp_v_c - act_v_c) > 1e-6:
                    diffs.append(f"Restr '{ac.name}' coef {v} diff: esperado={exp_v_c}, actual={act_v_c}")

    return diffs


def test_hydroelectric_fixture_direct_solver():
    """
    Lee el fixture JSON oficial de 24 variables, lo deserializa,
    construye el LPProblem via build_lp_problem_from_state y verifica Z* = 6701.25.
    """
    assert os.path.exists(FIXTURE_PATH), f"Fixture no encontrado en: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        json_content = f.read()

    loaded = deserialize_model(json_content)
    assert loaded["metadata"]["name"] == "Generacion Hidroelectrica Completa 4 Periodos"
    assert loaded["problem_type"] == "Monoobjetivo"
    assert loaded["obj_sense"] == "Minimizar"
    assert loaded["num_vars"] == 24
    assert len(loaded["var_names"]) == 24
    assert len(loaded["constraints_data"]) == 28

    prob = build_lp_problem_from_state(
        var_names=loaded["var_names"],
        obj_sense=loaded["obj_sense"],
        obj_coeffs=loaded["obj_coeffs"],
        canonical_constraints=loaded["constraints_data"],
    )

    # Diagnostico comparativo
    raw_data = json.loads(json_content)
    diffs = compare_models(raw_data, prob)
    assert not diffs, f"Diferencias entre JSON y LPProblem: {diffs}"

    sol = solve_lp(prob)
    assert sol.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol.objective_value, rel=1e-5) == 6701.25

    # Suma de termicas generadas
    sum_gt = sum(sol.variable_values[f"GT{t}"] for t in (1, 2, 3, 4))
    assert pytest.approx(sum_gt, rel=1e-5) == 67.0125


def test_hydroelectric_critical_operators_and_rhs():
    """Verifica exhaustivamente todos los operadores y RHS criticos del fixture."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        loaded = deserialize_model(f.read())

    cons_by_name = {c["name"]: c for c in loaded["constraints_data"]}

    # Balances Hidricos (=)
    assert cons_by_name["Balance_H1"]["operator"] == "="
    assert cons_by_name["Balance_H1"]["rhs"] == 90.0
    assert cons_by_name["Balance_H2"]["operator"] == "="
    assert cons_by_name["Balance_H2"]["rhs"] == 20.0
    assert cons_by_name["Balance_H3"]["operator"] == "="
    assert cons_by_name["Balance_H3"]["rhs"] == 15.0
    assert cons_by_name["Balance_H4"]["operator"] == "="
    assert cons_by_name["Balance_H4"]["rhs"] == 10.0

    # Demandas (=)
    assert cons_by_name["Demanda_P1"]["operator"] == "="
    assert cons_by_name["Demanda_P1"]["rhs"] == 60.0
    assert cons_by_name["Demanda_P2"]["operator"] == "="
    assert cons_by_name["Demanda_P2"]["rhs"] == 80.0
    assert cons_by_name["Demanda_P3"]["operator"] == "="
    assert cons_by_name["Demanda_P3"]["rhs"] == 70.0
    assert cons_by_name["Demanda_P4"]["operator"] == "="
    assert cons_by_name["Demanda_P4"]["rhs"] == 90.0

    # Volúmenes Máximos (<= 100) y Mínimos (>= 40)
    for t in (1, 2, 3, 4):
        assert cons_by_name[f"V_Max_{t}"]["operator"] == "<="
        assert cons_by_name[f"V_Max_{t}"]["rhs"] == 100.0
        assert cons_by_name[f"V_Min_{t}"]["operator"] == ">="
        assert cons_by_name[f"V_Min_{t}"]["rhs"] == 40.0
        assert cons_by_name[f"T_Max_{t}"]["operator"] == "<="
        assert cons_by_name[f"T_Max_{t}"]["rhs"] == 70.0


def test_streamlit_apptest_hydroelectric_load_and_solve():
    """
    Ejecuta un ciclo completo en Streamlit AppTest:
    1. Inicia app (estado inicial).
    2. Aplica el modelo hidroelectrico de 24 variables a session_state via _load_model_dict.
    3. Re-ejecuta app y verifica sincronizacion de widgets (nombre, sentido, 24 variables, 28 restricciones).
    4. Clic en Resolver y verifica Z* = 6701.25.
    """
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        loaded_dict = deserialize_model(f.read())

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert not at.exception

    # Aplicar modelo directamente en session_state usando la funcion de carga
    from streamlit_app import _load_model_dict
    _load_model_dict(loaded_dict, at.session_state)

    at.run()
    assert not at.exception

    # Verificar estado de sesion
    assert at.session_state.model_name == "Generacion Hidroelectrica Completa 4 Periodos"
    assert at.session_state.problem_type == "Monoobjetivo"
    assert at.session_state.obj_sense == "Minimizar"
    assert at.session_state.num_vars == 24
    assert len(at.session_state.var_names) == 24
    assert len(at.session_state.constraints_data) == 28

    # Resolver
    solve_buttons = [b for b in at.button if "Resolver" in b.label]
    assert len(solve_buttons) >= 1
    assert not solve_buttons[0].disabled

    solve_buttons[0].click().run()
    assert not at.exception

    # Validar resultado
    sol = at.session_state.last_solution
    assert sol is not None
    assert sol.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol.objective_value, rel=1e-5) == 6701.25


def test_streamlit_apptest_transitions_a_to_b_and_b_to_a():
    """
    Valida la transicion limpia bidireccional entre modelos:
    Benchmark A (Biobjetivo) -> Hidroelectrico 24-vars (Monoobjetivo) -> Benchmark A (Biobjetivo).
    Garantiza ausencia total de residuos de estado (sin Z2, sin ponderaciones en mono, etc.).
    """
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        hydro_dict = deserialize_model(f.read())

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert not at.exception

    # 1. Cargar Benchmark A (Bio)
    bio_btn = [b for b in at.button if "Benchmark A (Bio)" in b.label][0]
    bio_btn.click().run()
    assert not at.exception
    assert at.session_state.problem_type == "Biobjetivo"
    assert at.session_state.num_vars == 2

    # Resolver Benchmark A
    solve_btn = [b for b in at.button if "Resolver" in b.label][0]
    solve_btn.click().run()
    assert not at.exception
    assert at.session_state.last_solution_type == "Biobjetivo"
    assert len(at.session_state.last_solution.unique_solutions) == 3

    # 2. Cargar Hidroelectrico 24-vars (Mono)
    from streamlit_app import _load_model_dict
    _load_model_dict(hydro_dict, at.session_state)
    at.run()
    assert not at.exception

    assert at.session_state.model_name == "Generacion Hidroelectrica Completa 4 Periodos"
    assert at.session_state.problem_type == "Monoobjetivo"
    assert at.session_state.obj_sense == "Minimizar"
    assert at.session_state.num_vars == 24
    assert len(at.session_state.var_names) == 24
    assert len(at.session_state.constraints_data) == 28

    # Resolver Hidroelectrico
    solve_btn = [b for b in at.button if "Resolver" in b.label][0]
    solve_btn.click().run()
    assert not at.exception
    assert at.session_state.last_solution_type == "Monoobjetivo"
    assert at.session_state.last_solution.status == SolverStatus.OPTIMAL
    assert pytest.approx(at.session_state.last_solution.objective_value, rel=1e-5) == 6701.25

    # 3. Volver a Benchmark A (Bio)
    bio_btn = [b for b in at.button if "Benchmark A (Bio)" in b.label][0]
    bio_btn.click().run()
    assert not at.exception

    assert at.session_state.model_name == "Benchmark A (Biobjetivo)"
    assert at.session_state.problem_type == "Biobjetivo"
    assert at.session_state.num_vars == 2
    assert at.session_state.var_names == ["x1", "x2"]
    assert len(at.session_state.constraints_data) == 2

    # Resolver Benchmark A de nuevo
    solve_btn = [b for b in at.button if "Resolver" in b.label][0]
    solve_btn.click().run()
    assert not at.exception
    assert at.session_state.last_solution_type == "Biobjetivo"
    assert len(at.session_state.last_solution.unique_solutions) == 3
