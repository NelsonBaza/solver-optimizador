"""Verificación reproducible del cierre seguro de una sesión Streamlit."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = str(ROOT / "streamlit_app.py")
CLOSE_LABEL = "⏻ Cerrar aplicación"
REOPEN_LABEL = "Reabrir aplicación"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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


def _configure_and_apply_indexed_model(at: AppTest) -> None:
    _route(at).set_value("Modelo indexado").run()
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
    at.run()
    _button(at, "Validar y compilar modelo indexado").click().run()
    _button(at, "Aplicar modelo indexado").click().run()


def main() -> None:
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _require(not at.exception, f"Excepción en apertura: {at.exception}")
    _require(at.session_state.app_closed is False, "app_closed no inicia en False")

    close_button = _button(at, CLOSE_LABEL)
    _require(
        "No detiene el servidor Streamlit" in (close_button.help or ""),
        "El botón no aclara que el servidor continúa activo",
    )
    _configure_and_apply_indexed_model(at)

    before = deepcopy(
        {
            "indexed_source_spec": at.session_state.indexed_source_spec,
            "indexed_source_status": at.session_state.indexed_source_status,
            "constraints_data": list(at.session_state.constraints_data),
            "var_names": list(at.session_state.var_names),
            "obj_sense": at.session_state.obj_sense,
            "obj_coeffs": dict(at.session_state.obj_coeffs),
            "obj1_coeffs": dict(at.session_state.obj1_coeffs),
            "obj2_coeffs": dict(at.session_state.obj2_coeffs),
        }
    )

    _button(at, CLOSE_LABEL).click().run()
    _require(not at.exception, f"Excepción al cerrar: {at.exception}")
    _require(at.session_state.app_closed is True, "El cierre no activó app_closed")
    _require(
        any(title.value == "⏻ Aplicación cerrada" for title in at.title),
        "No se mostró la pantalla cerrada",
    )
    _require(
        not any(
            control.label == "Ruta de formulación"
            for control in at.segmented_control
        ),
        "La formulación se renderizó durante el cierre",
    )
    _require(
        not any("Resolver" in button.label for button in at.button),
        "El control Resolver se renderizó durante el cierre",
    )
    after_close = {
        "indexed_source_spec": at.session_state.indexed_source_spec,
        "indexed_source_status": at.session_state.indexed_source_status,
        "constraints_data": list(at.session_state.constraints_data),
        "var_names": list(at.session_state.var_names),
        "obj_sense": at.session_state.obj_sense,
        "obj_coeffs": dict(at.session_state.obj_coeffs),
        "obj1_coeffs": dict(at.session_state.obj1_coeffs),
        "obj2_coeffs": dict(at.session_state.obj2_coeffs),
    }
    _require(after_close == before, "El cierre alteró el modelo de la sesión")

    _button(at, REOPEN_LABEL).click().run()
    _require(not at.exception, f"Excepción al reabrir: {at.exception}")
    _require(at.session_state.app_closed is False, "La reapertura no desactivó app_closed")
    route = _route(at)
    _require(
        route.options == ["Formulación explícita", "Modelo indexado"],
        "No se restauraron ambas rutas de formulación",
    )
    _require(route.value == "Modelo indexado", "No se conservó la ruta indexada")
    after_reopen = {
        "indexed_source_spec": at.session_state.indexed_source_spec,
        "indexed_source_status": at.session_state.indexed_source_status,
        "constraints_data": list(at.session_state.constraints_data),
        "var_names": list(at.session_state.var_names),
        "obj_sense": at.session_state.obj_sense,
        "obj_coeffs": dict(at.session_state.obj_coeffs),
        "obj1_coeffs": dict(at.session_state.obj1_coeffs),
        "obj2_coeffs": dict(at.session_state.obj2_coeffs),
    }
    _require(after_reopen == before, "La reapertura alteró el modelo indexado")

    print("open=PASS")
    print("close_screen=PASS")
    print("state_preservation=PASS")
    print("reopen=PASS")
    print("indexed_route_after_reopen=PASS")
    print("RESULT: PASS (close application session control satisfied)")


if __name__ == "__main__":
    main()
