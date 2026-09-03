"""Recorrido reproducible de la UI indexada mediante Streamlit AppTest."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from solver_optimizador.lp_models import SolverStatus
from solver_optimizador.indexed_examples import production_planning_example_spec
from solver_optimizador.indexed_model import serialize_indexed_model_spec


APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def _text_area(at: AppTest, prefix: str):
    return next(element for element in at.text_area if element.label.startswith(prefix))


def _configure_indexed_model(at: AppTest, parameter_value: float = 10) -> None:
    _text_area(at, "Conjuntos").set_value("name,start,end\nT,1,10")
    _text_area(at, "Parámetros escalares").set_value("name,value")
    parameter_rows = ["parameter,index_set,index,value"]
    parameter_rows.extend(
        f"cap,T,{index},{parameter_value}" for index in range(1, 11)
    )
    _text_area(at, "Parámetros indexados").set_value("\n".join(parameter_rows))
    _text_area(at, "Familias de variables").set_value("family,index_set\nX,T\nY,T")
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


def _parameter_csv(value_at_five: float) -> bytes:
    rows = ["parameter,index_set,index,value"]
    rows.extend(
        f"cap,T,{index},{value_at_five if index == 5 else 10}"
        for index in range(1, 11)
    )
    return "\n".join(rows).encode("utf-8")


def test_indexed_ui_compile_apply_and_solve_complete_model():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    route = next(element for element in at.segmented_control if element.label == "Ruta de formulación")
    route.set_value("Modelo indexado").run()
    assert not at.exception

    _configure_indexed_model(at)
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


def test_stale_indexed_preview_is_blocked_then_recompile_applies_visible_change():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    route = next(element for element in at.segmented_control if element.label == "Ruta de formulación")
    route.set_value("Modelo indexado").run()
    _configure_indexed_model(at)
    at.run()
    next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    ).click().run()
    assert at.session_state.indexed_compile_preview is not None
    original_signature = at.session_state.indexed_compile_preview_signature
    explicit_variables_before = list(at.session_state.var_names)
    explicit_constraints_before = list(at.session_state.constraints_data)
    solution_before = at.session_state.last_solution
    version_before = at.session_state.editor_version

    parameter_text = _text_area(at, "Parámetros indexados").value
    _text_area(at, "Parámetros indexados").set_value(
        parameter_text.replace("cap,T,5,10", "cap,T,5,999")
    ).run()
    apply_button = next(button for button in at.button if button.label == "Aplicar modelo indexado")
    assert apply_button.disabled
    assert any("Debe validar y compilar nuevamente" in warning.value for warning in at.warning)
    assert at.session_state.indexed_compile_preview_signature == original_signature
    assert list(at.session_state.var_names) == explicit_variables_before
    assert list(at.session_state.constraints_data) == explicit_constraints_before
    assert at.session_state.last_solution is solution_before
    assert at.session_state.editor_version == version_before
    assert at.session_state.indexed_source_status is None

    next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    ).click().run()
    assert at.session_state.indexed_compile_preview_signature != original_signature
    apply_button = next(button for button in at.button if button.label == "Aplicar modelo indexado")
    assert not apply_button.disabled
    apply_button.click().run()
    constraints = {row["name"]: row for row in at.session_state.constraints_data}
    assert constraints["CapX_5"]["rhs"] == 999.0
    assert constraints["CapY_5"]["rhs"] == 999.0
    assert at.session_state.indexed_source_status == "synchronized"

    next(button for button in at.button if "Resolver" in button.label).click().run()
    assert not at.exception
    assert at.session_state.last_solution.status == SolverStatus.OPTIMAL
    solved_constraints = {
        result.name: result for result in at.session_state.last_solution.constraint_results
    }
    assert solved_constraints["CapX_5"].rhs == 999.0


def test_changing_effective_parameter_csv_blocks_previous_preview():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    next(
        element for element in at.segmented_control if element.label == "Ruta de formulación"
    ).set_value("Modelo indexado").run()
    _configure_indexed_model(at)
    at.run()
    uploader = next(
        element
        for element in at.file_uploader
        if element.label == "Parámetros indexados desde CSV"
    )
    uploader.set_value(("parameters_a.csv", _parameter_csv(10), "text/csv")).run()
    next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    ).click().run()
    signature_a = at.session_state.indexed_compile_preview_signature

    uploader = next(
        element
        for element in at.file_uploader
        if element.label == "Parámetros indexados desde CSV"
    )
    uploader.set_value(("parameters_b.csv", _parameter_csv(999), "text/csv")).run()
    apply_button = next(button for button in at.button if button.label == "Aplicar modelo indexado")
    assert apply_button.disabled
    assert at.session_state.indexed_compile_preview_signature == signature_a
    assert at.session_state.indexed_source_status is None

    next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    ).click().run()
    assert at.session_state.indexed_compile_preview_signature != signature_a
    next(button for button in at.button if button.label == "Aplicar modelo indexado").click().run()
    constraints = {row["name"]: row for row in at.session_state.constraints_data}
    assert constraints["CapX_5"]["rhs"] == 999.0


def test_loading_another_indexed_json_invalidates_existing_preview():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    next(
        element for element in at.segmented_control if element.label == "Ruta de formulación"
    ).set_value("Modelo indexado").run()
    _configure_indexed_model(at)
    at.run()
    next(
        button for button in at.button if button.label == "Validar y compilar modelo indexado"
    ).click().run()
    assert at.session_state.indexed_compile_preview is not None
    assert at.session_state.indexed_compile_preview_signature is not None

    json_payload = serialize_indexed_model_spec(production_planning_example_spec(4)).encode("utf-8")
    uploader = next(
        element
        for element in at.file_uploader
        if element.label == "Importar especificacion indexada JSON"
    )
    uploader.set_value(("indexed_b.json", json_payload, "application/json")).run()
    next(button for button in at.button if button.label == "Cargar JSON indexado").click().run()
    assert not at.exception
    assert at.session_state.indexed_compile_preview is None
    assert at.session_state.indexed_compile_preview_signature is None
    assert not any(button.label == "Aplicar modelo indexado" for button in at.button)
