"""
Suite de pruebas de integridad para streamlit_app.py.
Valida la ausencia de NameError, imports faltantes, y verifica la ejecucion real
mediante analisis estatico de AST y el harness AppTest de Streamlit.
"""

import ast
import builtins
import os
import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


def test_streamlit_app_ast_global_names_defined():
    """
    Analiza el AST de streamlit_app.py para verificar que todos los simbolos importados
    o usados a nivel global esten definidos y no existan NameErrors latentes.
    """
    with open(APP_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=APP_PATH)

    imported_names = set(dir(builtins))
    defined_names = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)

    # Verificar que las funciones llamadas principales existan
    known_names = imported_names | defined_names
    assert "normalize_constraints" in known_names, "normalize_constraints no esta importado en streamlit_app.py"
    assert "serialize_model" in known_names
    assert "deserialize_model" in known_names
    assert "solve_lp" in known_names
    assert "solve_biobjective_weighted" in known_names


def test_streamlit_app_apptest_initial_render_and_buttons_enabled():
    """
    Ejecuta streamlit_app.py mediante AppTest de Streamlit.
    Verifica que no haya excepciones (NameError, TypeError, etc.) y que los botones de accion esten habilitados.
    """
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception, f"Excepcion durante la ejecucion inicial de Streamlit: {at.exception}"

    solve_buttons = [b for b in at.button if "Resolver" in b.label]
    assert len(solve_buttons) >= 1, "No se encontro el boton de Resolver"
    assert not solve_buttons[0].disabled, "El boton de Resolver no deberia estar deshabilitado en el estado inicial"


def test_streamlit_app_apptest_solve_mono_example():
    """
    Carga el Ejemplo 1 Monoobjetivo y ejecuta la resolucion mediante AppTest.
    """
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception

    # Clic en boton Ejemplo 1 (Mono)
    ex_buttons = [b for b in at.button if "Ejemplo 1 (Mono)" in b.label]
    assert len(ex_buttons) >= 1
    ex_buttons[0].click().run()
    assert not at.exception

    # Clic en Resolver
    solve_buttons = [b for b in at.button if "Resolver" in b.label]
    assert len(solve_buttons) >= 1
    assert not solve_buttons[0].disabled
    solve_buttons[0].click().run()
    assert not at.exception

def test_streamlit_app_apptest_solve_bio_benchmark_a():
    """
    Carga Benchmark A (Biobjetivo) y ejecuta la resolucion mediante AppTest.
    """
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception

    # Clic en Benchmark A (Bio)
    bio_buttons = [b for b in at.button if "Benchmark A (Bio)" in b.label]
    assert len(bio_buttons) >= 1
    bio_buttons[0].click().run()
    assert not at.exception

    # Clic en Resolver
    solve_buttons = [b for b in at.button if "Resolver" in b.label]
    assert len(solve_buttons) >= 1
    assert not solve_buttons[0].disabled
    solve_buttons[0].click().run()
    assert not at.exception

    solution = at.session_state.last_solution
    assert solution is not None
    assert all({"N1", "N2", "W"}.issubset(run) for run in solution.weighted_runs)
    sweep_tables = [
        element.value
        for element in at.dataframe
        if {"alpha1", "alpha2", "Z1", "Z2", "N1", "N2", "W", "Estado"}.issubset(
            element.value.columns
        )
    ]
    assert len(sweep_tables) == 1
