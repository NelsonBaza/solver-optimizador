"""Pruebas AppTest del cierre seguro de la interfaz por sesión."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
CLOSE_LABEL = "⏻ Cerrar aplicación"
REOPEN_LABEL = "Reabrir aplicación"


def _button(at: AppTest, label: str):
    return next(button for button in at.button if button.label == label)


def _route(at: AppTest):
    return next(
        control
        for control in at.segmented_control
        if control.label == "Ruta de formulación"
    )


def _text_area(at: AppTest, prefix: str):
    return next(element for element in at.text_area if element.label.startswith(prefix))


def _configure_indexed_model(at: AppTest) -> None:
    _text_area(at, "Conjuntos").set_value("name,start,end\nT,1,2")
    _text_area(at, "Parámetros escalares").set_value("name,value")
    _text_area(at, "Parámetros indexados").set_value(
        "parameter,index_set,index,value\ncap,T,1,10\ncap,T,2,20"
    )
    _text_area(at, "Familias de variables").set_value("family,index_set\nX,T")
    _text_area(at, "Objetivos indexados").set_value(
        "objective,sense,variable_family,index_set,start_index,end_index,coefficient\n"
        "Z,Minimizar,X,T,1,2,1"
    )
    _text_area(at, "Familias de restricciones").set_value(
        "name,index_set,index_symbol,start_index,end_index,expression\n"
        "Cap,T,t,1,2,X[t] <= cap[t]"
    )


def _model_snapshot(at: AppTest) -> dict:
    return deepcopy(
        {
            "var_names": list(at.session_state.var_names),
            "constraints_data": list(at.session_state.constraints_data),
            "obj_sense": at.session_state.obj_sense,
            "obj_coeffs": dict(at.session_state.obj_coeffs),
            "obj1_sense": at.session_state.obj1_sense,
            "obj1_coeffs": dict(at.session_state.obj1_coeffs),
            "obj2_sense": at.session_state.obj2_sense,
            "obj2_coeffs": dict(at.session_state.obj2_coeffs),
        }
    )


def _close(at: AppTest) -> AppTest:
    return _button(at, CLOSE_LABEL).click().run()


def test_close_1_application_opens_with_session_active():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    assert at.session_state.app_closed is False
    assert _route(at).value == "Formulación explícita"


def test_close_2_safe_close_button_exists_with_server_help():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    close_button = _button(at, CLOSE_LABEL)
    assert close_button.help is not None
    assert "No detiene el servidor Streamlit" in close_button.help
    assert "Ctrl+C" in close_button.help


def test_close_3_clicking_close_sets_session_state():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _close(at)
    assert not at.exception
    assert at.session_state.app_closed is True


def test_close_4_closed_screen_hides_main_controls():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _close(at)
    assert any(title.value == "⏻ Aplicación cerrada" for title in at.title)
    assert not any(
        control.label == "Ruta de formulación" for control in at.segmented_control
    )
    assert not any("Resolver" in button.label for button in at.button)
    assert not any(CLOSE_LABEL == button.label for button in at.button)


def test_close_5_closing_preserves_existing_model_and_objectives():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _button(at, "Benchmark A (Bio)").click().run()
    before = _model_snapshot(at)
    _close(at)
    assert _model_snapshot(at) == before


def test_close_6_closed_screen_offers_reopen_button():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _close(at)
    assert _button(at, REOPEN_LABEL)


def test_close_7_reopening_restores_normal_interface():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _close(at)
    _button(at, REOPEN_LABEL).click().run()
    assert not at.exception
    assert at.session_state.app_closed is False
    assert any("Resolver" in button.label for button in at.button)


def test_close_8_reopening_restores_both_formulation_routes():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _close(at)
    _button(at, REOPEN_LABEL).click().run()
    route = _route(at)
    assert route.options == ["Formulación explícita", "Modelo indexado"]


def test_close_9_indexed_model_survives_close_and_reopen():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _route(at).set_value("Modelo indexado").run()
    _configure_indexed_model(at)
    at.run()
    _button(at, "Validar y compilar modelo indexado").click().run()
    _button(at, "Aplicar modelo indexado").click().run()

    before_spec = deepcopy(at.session_state.indexed_source_spec)
    before_status = at.session_state.indexed_source_status
    before_constraints = deepcopy(list(at.session_state.constraints_data))
    before_variables = list(at.session_state.var_names)

    _close(at)
    _button(at, REOPEN_LABEL).click().run()

    assert at.session_state.app_closed is False
    assert at.session_state.indexed_source_spec == before_spec
    assert at.session_state.indexed_source_status == before_status == "synchronized"
    assert list(at.session_state.constraints_data) == before_constraints
    assert list(at.session_state.var_names) == before_variables
    assert _route(at).value == "Modelo indexado"
