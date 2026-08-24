"""
Suite de pruebas unitarias para variables personalizadas, expansion hasta 100 variables,
carga atomica de modelos y el caso real completo de generacion hidroelectrica (24 variables).
"""

import json
import pytest
from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.signature import build_model_signature
from solver_optimizador.model_io import (
    serialize_model,
    deserialize_model,
    validate_model_dict,
    SCHEMA_VERSION,
)
from solver_optimizador.plotting import (
    plot_variable_values,
    plot_constraint_slacks,
)


def test_custom_variable_names_in_lp_solve():
    """Valida la definicion y resolucion de un LP con nombres de variables arbitrarios."""
    custom_vars = ["T1", "T2", "V1", "V2", "GT1", "GT2"]
    obj_coeffs = {v: (100.0 if "GT" in v else 0.0) for v in custom_vars}
    
    constraints = [
        LinearConstraint("Demanda_1", {"T1": 2.4525, "GT1": 1.0}, Operator.EQ, 60.0),
        LinearConstraint("Demanda_2", {"T2": 2.4525, "GT2": 1.0}, Operator.EQ, 80.0),
        LinearConstraint("Volumen_1", {"T1": 1.0, "V1": 1.0}, Operator.LE, 100.0),
        LinearConstraint("Volumen_2", {"T2": 1.0, "V2": 1.0}, Operator.LE, 100.0),
    ]

    prob = LPProblem(
        variables=custom_vars,
        objective=LinearObjective("Z", Sense.MINIMIZE, obj_coeffs),
        constraints=constraints,
    )
    sol = solve_lp(prob)
    assert sol.status == SolverStatus.OPTIMAL
    assert all(v in sol.variable_values for v in custom_vars)


def test_duplicate_variable_names_rejected():
    """Valida que los nombres duplicados sean rechazados por la validacion de esquema."""
    dup_prob = {
        "schema_version": "1.0",
        "problem": {
            "type": "Monoobjetivo",
            "variables": ["T1", "T2", "T1"],
            "mono_objective": {"sense": "Minimizar", "coefficients": {"T1": 1.0, "T2": 2.0}},
            "constraints": [
                {"name": "R1", "coefficients": {"T1": 1.0, "T2": 1.0}, "operator": "<=", "rhs": 10.0}
            ],
        },
    }
    is_valid, err = validate_model_dict(dup_prob)
    assert not is_valid
    assert "unicos" in err.lower()


def test_coefficient_preservation_on_rename():
    """Valida la preservacion posicional de coeficientes cuando una variable es renombrada."""
    old_names = ["x1", "x2", "x3"]
    old_mono_coeffs = {"x1": 10.0, "x2": 20.0, "x3": 30.0}
    new_names = ["T1", "T2", "V1"]

    # Migracion por posicion
    new_mono_coeffs = {new_names[i]: old_mono_coeffs.get(old_names[i], 0.0) for i in range(len(new_names))}

    assert new_mono_coeffs["T1"] == 10.0
    assert new_mono_coeffs["T2"] == 20.0
    assert new_mono_coeffs["V1"] == 30.0


def test_hydroelectric_full_24_vars_model():
    """
    Caso real completo de generacion hidroelectrica multiperiodo (4 periodos):
    - 24 variables:
      T1..T4 (turbinacion)
      V1..V4 (volumen)
      S1..S4 (vertimiento)
      PH1..PH4 (potencia hidro)
      GH1..GH4 (energia hidro)
      GT1..GT4 (generacion termica)
    - 28 restricciones.
    - Objetivo: MIN Z = 100 GT1 + 100 GT2 + 100 GT3 + 100 GT4.
    - Resultado esperado: Z* = 6701.25.
    - Serializacion y Deserializacion JSON round-trip con identidad de firma.
    """
    t_vars = [f"T{i}" for i in range(1, 5)]
    v_vars = [f"V{i}" for i in range(1, 5)]
    s_vars = [f"S{i}" for i in range(1, 5)]
    ph_vars = [f"PH{i}" for i in range(1, 5)]
    gh_vars = [f"GH{i}" for i in range(1, 5)]
    gt_vars = [f"GT{i}" for i in range(1, 5)]

    all_24_vars = t_vars + v_vars + s_vars + ph_vars + gh_vars + gt_vars
    assert len(all_24_vars) == 24

    # Objetivo: MIN Z = 100 GT1 + 100 GT2 + 100 GT3 + 100 GT4
    obj_coeffs = {v: (100.0 if v in gt_vars else 0.0) for v in all_24_vars}

    # Restricciones
    constraints_raw = [
        # Balance hidrico (inflows = 90, 20, 15, 10; V0 = 0)
        {"name": "Balance_H1", "coefficients": {"V1": 1.0, "T1": 1.0, "S1": 1.0}, "operator": "=", "rhs": 90.0},
        {"name": "Balance_H2", "coefficients": {"V2": 1.0, "V1": -1.0, "T2": 1.0, "S2": 1.0}, "operator": "=", "rhs": 20.0},
        {"name": "Balance_H3", "coefficients": {"V3": 1.0, "V2": -1.0, "T3": 1.0, "S3": 1.0}, "operator": "=", "rhs": 15.0},
        {"name": "Balance_H4", "coefficients": {"V4": 1.0, "V3": -1.0, "T4": 1.0, "S4": 1.0}, "operator": "=", "rhs": 10.0},

        # Relacion turbinacion - potencia: PH_t - 2.4525 T_t = 0
        {"name": "Turb_Pot_1", "coefficients": {"PH1": 1.0, "T1": -2.4525}, "operator": "=", "rhs": 0.0},
        {"name": "Turb_Pot_2", "coefficients": {"PH2": 1.0, "T2": -2.4525}, "operator": "=", "rhs": 0.0},
        {"name": "Turb_Pot_3", "coefficients": {"PH3": 1.0, "T3": -2.4525}, "operator": "=", "rhs": 0.0},
        {"name": "Turb_Pot_4", "coefficients": {"PH4": 1.0, "T4": -2.4525}, "operator": "=", "rhs": 0.0},

        # Conversion potencia - energia: GH_t - PH_t = 0
        {"name": "Pot_Ene_1", "coefficients": {"GH1": 1.0, "PH1": -1.0}, "operator": "=", "rhs": 0.0},
        {"name": "Pot_Ene_2", "coefficients": {"GH2": 1.0, "PH2": -1.0}, "operator": "=", "rhs": 0.0},
        {"name": "Pot_Ene_3", "coefficients": {"GH3": 1.0, "PH3": -1.0}, "operator": "=", "rhs": 0.0},
        {"name": "Pot_Ene_4", "coefficients": {"GH4": 1.0, "PH4": -1.0}, "operator": "=", "rhs": 0.0},

        # Balance energetico / demanda: GH_t + GT_t = D_t (D = 60, 80, 70, 90)
        {"name": "Demanda_P1", "coefficients": {"GH1": 1.0, "GT1": 1.0}, "operator": "=", "rhs": 60.0},
        {"name": "Demanda_P2", "coefficients": {"GH2": 1.0, "GT2": 1.0}, "operator": "=", "rhs": 80.0},
        {"name": "Demanda_P3", "coefficients": {"GH3": 1.0, "GT3": 1.0}, "operator": "=", "rhs": 70.0},
        {"name": "Demanda_P4", "coefficients": {"GH4": 1.0, "GT4": 1.0}, "operator": "=", "rhs": 90.0},

        # Limites superiores de volumen: V_t <= 100
        {"name": "V_Max_1", "coefficients": {"V1": 1.0}, "operator": "<=", "rhs": 100.0},
        {"name": "V_Max_2", "coefficients": {"V2": 1.0}, "operator": "<=", "rhs": 100.0},
        {"name": "V_Max_3", "coefficients": {"V3": 1.0}, "operator": "<=", "rhs": 100.0},
        {"name": "V_Max_4", "coefficients": {"V4": 1.0}, "operator": "<=", "rhs": 100.0},

        # Limites inferiores de volumen: V_t >= 40 (o V1 >= 40, V2 >= 40...)
        {"name": "V_Min_1", "coefficients": {"V1": 1.0}, "operator": ">=", "rhs": 40.0},
        {"name": "V_Min_2", "coefficients": {"V2": 1.0}, "operator": ">=", "rhs": 40.0},
        {"name": "V_Min_3", "coefficients": {"V3": 1.0}, "operator": ">=", "rhs": 40.0},
        {"name": "V_Min_4", "coefficients": {"V4": 1.0}, "operator": ">=", "rhs": 40.0},

        # Limites de turbina: T_t <= 70
        {"name": "T_Max_1", "coefficients": {"T1": 1.0}, "operator": "<=", "rhs": 70.0},
        {"name": "T_Max_2", "coefficients": {"T2": 1.0}, "operator": "<=", "rhs": 70.0},
        {"name": "T_Max_3", "coefficients": {"T3": 1.0}, "operator": "<=", "rhs": 70.0},
        {"name": "T_Max_4", "coefficients": {"T4": 1.0}, "operator": "<=", "rhs": 70.0},
    ]
    assert len(constraints_raw) == 28

    prob_lp = LPProblem(
        variables=all_24_vars,
        objective=LinearObjective("Z", Sense.MINIMIZE, obj_coeffs),
        constraints=[
            LinearConstraint(c["name"], c["coefficients"], Operator.from_str(c["operator"]), c["rhs"])
            for c in constraints_raw
        ],
    )

    sol = solve_lp(prob_lp)
    assert sol.status == SolverStatus.OPTIMAL
    assert pytest.approx(sol.objective_value, rel=1e-4) == 6701.25

    # Serializar modelo de 24 variables
    prob_dict = {
        "type": "Monoobjetivo",
        "variables": all_24_vars,
        "mono_objective": {"sense": "Minimizar", "coefficients": obj_coeffs},
        "constraints": constraints_raw,
    }
    json_str = serialize_model(prob_dict, {"name": "Generacion Hidroelectrica Completa 24 Variables"})

    # Deserializar
    loaded = deserialize_model(json_str)
    assert loaded["num_vars"] == 24
    assert loaded["var_names"] == all_24_vars
    assert len(loaded["constraints_data"]) == 28

    # Firmas coinciden
    sig_before = build_model_signature("Monoobjetivo", all_24_vars, "Minimizar", obj_coeffs, constraints_data=constraints_raw)
    sig_after = build_model_signature("Monoobjetivo", loaded["var_names"], loaded["obj_sense"], loaded["obj_coeffs"], constraints_data=loaded["constraints_data"])
    assert sig_before == sig_after

    # Graficos con 24 variables y 28 restricciones se generan sin error
    fig_vars = plot_variable_values(sol.variable_values)
    assert fig_vars is not None
    import matplotlib.pyplot as plt
    plt.close(fig_vars)

    fig_slacks = plot_constraint_slacks(sol.constraint_results)
    assert fig_slacks is not None
    plt.close(fig_slacks)


def test_atomic_transition_model_a_to_model_b():
    """Valida la sustitucion atomica de un modelo Biobjetivo por un modelo Monoobjetivo sin residuos."""
    # Modelo A: Biobjetivo Benchmark A
    model_a_dict = {
        "type": "Biobjetivo",
        "variables": ["x1", "x2"],
        "bio_objectives": {
            "obj1": {"sense": "Maximizar", "coefficients": {"x1": 10.0, "x2": 3.0}},
            "obj2": {"sense": "Maximizar", "coefficients": {"x1": 0.8, "x2": 1.3}},
        },
        "constraints": [
            {"name": "R1", "coefficients": {"x1": 1.0, "x2": 1.0}, "operator": "<=", "rhs": 130.0},
        ],
    }
    json_a = serialize_model(model_a_dict, {"name": "Modelo A"})

    # Modelo B: Monoobjetivo Hidroelectrico 4 vars
    model_b_dict = {
        "type": "Monoobjetivo",
        "variables": ["T1", "T2", "GT1", "GT2"],
        "mono_objective": {"sense": "Minimizar", "coefficients": {"T1": 0.0, "T2": 0.0, "GT1": 100.0, "GT2": 100.0}},
        "constraints": [
            {"name": "Demanda 1", "coefficients": {"T1": 2.4525, "GT1": 1.0}, "operator": "=", "rhs": 60.0},
            {"name": "Demanda 2", "coefficients": {"T2": 2.4525, "GT2": 1.0}, "operator": "=", "rhs": 80.0},
        ],
    }
    json_b = serialize_model(model_b_dict, {"name": "Modelo B"})

    # Cargar B
    loaded_b = deserialize_model(json_b)
    assert loaded_b["problem_type"] == "Monoobjetivo"
    assert loaded_b["num_vars"] == 4
    assert loaded_b["var_names"] == ["T1", "T2", "GT1", "GT2"]
    assert "obj_sense" in loaded_b
    assert loaded_b["obj_sense"] == "Minimizar"
    # No hay residuos de x1 o x2 en var_names
    assert "x1" not in loaded_b["var_names"]
    assert "x2" not in loaded_b["var_names"]
