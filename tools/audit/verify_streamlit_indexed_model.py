"""Ejecuta el flujo indexado completo de Streamlit sin interaccion manual."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest

from solver_optimizador.lp_models import SolverStatus


def _area(app, prefix):
    return next(element for element in app.text_area if element.label.startswith(prefix))


def main() -> None:
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    route = next(item for item in app.segmented_control if item.label == "Ruta de formulación")
    route.set_value("Modelo indexado").run()
    _area(app, "Conjuntos").set_value("name,start,end\nT,1,10")
    _area(app, "Parámetros escalares").set_value("name,value")
    parameters = ["parameter,index_set,index,value"]
    parameters.extend(f"cap,T,{index},10" for index in range(1, 11))
    _area(app, "Parámetros indexados").set_value("\n".join(parameters))
    _area(app, "Familias de variables").set_value("family,index_set\nX,T\nY,T")
    _area(app, "Objetivos indexados").set_value(
        "objective,sense,variable_family,index_set,start_index,end_index,coefficient\n"
        "Z,Minimizar,X,T,1,10,1\nZ,Minimizar,Y,T,1,10,1"
    )
    _area(app, "Familias de restricciones").set_value(
        "name,index_set,index_symbol,start_index,end_index,expression\n"
        "CapX,T,t,1,10,X[t] <= cap[t]\nCapY,T,t,1,10,Y[t] <= cap[t]"
    )
    app.run()
    next(button for button in app.button if button.label == "Validar y compilar modelo indexado").click().run()
    assert not app.exception
    preview = app.session_state.indexed_compile_preview
    assert preview.statistics["generated_variables"] == 20
    assert preview.statistics["generated_constraints"] == 20
    next(button for button in app.button if button.label == "Aplicar modelo indexado").click().run()
    assert len(app.session_state.constraints_data) == 20
    next(button for button in app.button if "Resolver" in button.label).click().run()
    assert not app.exception
    assert app.session_state.last_solution.status == SolverStatus.OPTIMAL
    assert len(app.session_state.last_solution.constraint_results) == 20
    print("set=T=1..10")
    print("variable_families=2")
    print("generated_variables=20")
    print("constraint_families=2")
    print("generated_constraints=20")
    print("preview_limit=20")
    print("applied_constraints=20")
    print(f"solver_status={app.session_state.last_solution.status.value}")
    print("RESULT: PASS (Streamlit indexed model flow satisfied)")


if __name__ == "__main__":
    main()
