"""
Suite de pruebas unitarias para la generacion determinista de firmas del modelo matematico.
"""

import pytest
from solver_optimizador.signature import build_model_signature


def test_signature_deterministic_equality():
    """Valida que dos llamadas con exactamente la misma formulacion generen la misma firma."""
    sig1 = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Maximizar",
        obj_coeffs={"x1": 3.0, "x2": 2.0},
        constraints_data=[
            {"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 4.0},
            {"name": "c2", "x1": 1.0, "x2": 0.0, "operator": "<=", "rhs": 2.0},
        ],
    )

    sig2 = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Maximizar",
        obj_coeffs={"x1": 3.0, "x2": 2.0},
        constraints_data=[
            {"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 4.0},
            {"name": "c2", "x1": 1.0, "x2": 0.0, "operator": "<=", "rhs": 2.0},
        ],
    )

    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex length


def test_signature_changes_on_objective_coefficient():
    """Valida que modificar un coeficiente del objetivo cambie la firma."""
    base_sig = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Maximizar",
        obj_coeffs={"x1": 3.0, "x2": 2.0},
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 4.0}],
    )

    mod_sig = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Maximizar",
        obj_coeffs={"x1": 3.5, "x2": 2.0},  # Modificado
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 4.0}],
    )

    assert base_sig != mod_sig


def test_signature_changes_on_objective_sense():
    """Valida que modificar el sentido (MAX a MIN) cambie la firma."""
    sig_max = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Maximizar",
        obj_coeffs={"x1": 3.0, "x2": 2.0},
    )

    sig_min = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_sense="Minimizar",
        obj_coeffs={"x1": 3.0, "x2": 2.0},
    )

    assert sig_max != sig_min


def test_signature_changes_on_constraint_rhs():
    """Valida que modificar el lado derecho (RHS) de una restriccion cambie la firma."""
    sig1 = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_coeffs={"x1": 1.0, "x2": 1.0},
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 10.0}],
    )

    sig2 = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        obj_coeffs={"x1": 1.0, "x2": 1.0},
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 12.0}],
    )

    assert sig1 != sig2


def test_signature_changes_on_constraint_operator():
    """Valida que modificar el operador (<= a >=) cambie la firma."""
    sig_le = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 10.0}],
    )

    sig_ge = build_model_signature(
        problem_type="Monoobjetivo",
        var_names=["x1", "x2"],
        constraints_data=[{"name": "c1", "x1": 1.0, "x2": 1.0, "operator": ">=", "rhs": 10.0}],
    )

    assert sig_le != sig_ge


def test_signature_changes_on_multiobjective_weights():
    """Valida que modificar los parametros de ponderacion en biobjetivo cambie la firma."""
    sig_6w = build_model_signature(
        problem_type="Biobjetivo",
        var_names=["x1", "x2"],
        obj1_coeffs={"x1": 10.0, "x2": 3.0},
        obj2_coeffs={"x1": 0.8, "x2": 1.3},
        mo_mode="Barrido automatico",
        num_weights=6,
    )

    sig_11w = build_model_signature(
        problem_type="Biobjetivo",
        var_names=["x1", "x2"],
        obj1_coeffs={"x1": 10.0, "x2": 3.0},
        obj2_coeffs={"x1": 0.8, "x2": 1.3},
        mo_mode="Barrido automatico",
        num_weights=11,
    )

    sig_custom = build_model_signature(
        problem_type="Biobjetivo",
        var_names=["x1", "x2"],
        obj1_coeffs={"x1": 10.0, "x2": 3.0},
        obj2_coeffs={"x1": 0.8, "x2": 1.3},
        mo_mode="Ponderacion unica",
        custom_a1=0.7,
    )

    assert sig_6w != sig_11w
    assert sig_6w != sig_custom


def test_signature_changes_on_variable_count():
    """Valida que cambiar la cantidad o nombres de variables cambie la firma."""
    sig_2v = build_model_signature(problem_type="Monoobjetivo", var_names=["x1", "x2"])
    sig_3v = build_model_signature(problem_type="Monoobjetivo", var_names=["x1", "x2", "x3"])
    assert sig_2v != sig_3v
