"""Recorrido reproducible de la UI indexada mediante Streamlit AppTest."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from solver_optimizador.lp_models import SolverStatus


APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def _text_area(at: AppTest, prefix: str):
    return next(element for element in at.text_area if element.label.startswith(prefix))


def test_indexed_ui_compile_apply_and_solve_complete_model():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    route = next(element for element in at.segmented_control if element.label == "Ruta de formulación")
    route.set_value("Modelo indexado").run()
    assert not at.exception

    _text_area(at, "Conjuntos").set_value("name,start,end\nT,1,10")
    _text_area(at, "Parámetros escalares").set_value("name,value")
    parameter_rows = ["parameter,index_set,index,value"]
    parameter_rows.extend(f"cap,T,{index},10" for index in range(1, 11))
    _text_area(at, "Parámetros indexados").set_value("\n".join(parameter_rows))
    _text_area(at, "Familias de variables").set_value(
        "family,index_set\nX,T\nY,T"
    )
    _text_area(at, "Objetivos indexados").set_value(
        "objective,sense,variable_family,index_set,start_index,end_index,coefficient\n"
        "Z,Minimizar,X,T,1,10,1\n"
        "Z,Minimizar,Y,T,1,10,1"
    )
    _text_area(at, "Familias de restricciones").set_value(
        "name,index_set,index_symbol,start_index,end_index,expression\n"
        "CapX,T,t,1,10,X[t] <= cap[t]\n"
        "CapY,T,t,1,10,Y[t] <= cap[t]"
    )
    at.run()
    compile_button = next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    )
    compile_button.click().run()
    assert not at.exception
    preview = at.session_state.indexed_compile_preview
    assert preview.statistics["sets"] == 1
    assert preview.statistics["variable_families"] == 2
    assert preview.statistics["generated_variables"] == 20
    assert preview.statistics["constraint_families"] == 2
    assert preview.statistics["generated_constraints"] == 20
    preview_frames = [frame.value for frame in at.dataframe if len(frame.value) <= 20]
    assert preview_frames

    apply_button = next(button for button in at.button if button.label == "Aplicar modelo indexado")
    apply_button.click().run()
    assert not at.exception
    assert len(at.session_state.var_names) == 20
    assert len(at.session_state.constraints_data) == 20
    assert at.session_state.indexed_source_status == "synchronized"

    solve_button = next(button for button in at.button if "Resolver" in button.label)
    solve_button.click().run()
    assert not at.exception
    assert at.session_state.last_solution.status == SolverStatus.OPTIMAL
    assert at.session_state.last_solution.objective_value == pytest.approx(0.0)
    assert len(at.session_state.last_solution.constraint_results) == 20
