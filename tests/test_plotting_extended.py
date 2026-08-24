"""
Suite de pruebas unitarias para los graficos generales de resultados (plotting).
"""

import pytest
import matplotlib.pyplot as plt
from solver_optimizador.lp_models import ConstraintResult
from solver_optimizador.plotting import (
    plot_variable_values,
    plot_constraint_slacks,
    plot_multiobjective_runs,
)


def test_plot_variable_values_2_vars():
    fig = plot_variable_values({"x1": 2.0, "x2": 2.0})
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_variable_values_8_vars():
    vars_8 = {f"x{i+1}": (24.4648 if i < 4 else 0.0) for i in range(8)}
    fig = plot_variable_values(vars_8, title="Hidroelectrica 8 Variables")
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_constraint_slacks():
    results = [
        ConstraintResult("R1", 60.0, "<=", 60.0, 0.0, True),
        ConstraintResult("R2", 50.0, "<=", 80.0, 30.0, False),
        ConstraintResult("R3", 70.0, "<=", 70.0, 0.0, True),
    ]
    fig = plot_constraint_slacks(results)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_multiobjective_runs():
    runs = [
        {"run_index": 1, "alpha1": 0.0, "alpha2": 1.0, "Z1": 390.0, "Z2": 169.0},
        {"run_index": 2, "alpha1": 0.5, "alpha2": 0.5, "Z1": 950.0, "Z2": 129.0},
        {"run_index": 3, "alpha1": 1.0, "alpha2": 0.0, "Z1": 1000.0, "Z2": 80.0},
    ]
    fig = plot_multiobjective_runs(runs, "Z1", "Z2")
    assert isinstance(fig, plt.Figure)
    plt.close(fig)
