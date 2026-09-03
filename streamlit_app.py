"""
Aplicacion Web Streamlit — Suite de Optimizacion Matematica (MVP LP).
Formulacion, resolucion, persistencia y analisis de Programacion Lineal Continua (Monoobjetivo y Biobjetivo).
Soporta entrada manual acotada e importacion masiva dispersa, persistencia JSON
y carga atomica sincronizada.
Backend matematico: Pyomo + HiGHS (APPSI).
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Asegurar que el directorio src este en sys.path
src_dir = os.path.join(os.path.dirname(__file__), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import streamlit as st
import pandas as pd

from solver_optimizador.lp_models import (
    Sense,
    Operator,
    LinearObjective,
    LinearConstraint,
    LPProblem,
    BiobjectiveProblem,
    SolverStatus,
    is_finite_number,
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted, generate_weight_combinations
from solver_optimizador.signature import build_model_signature
from solver_optimizador.interpretation import (
    interpret_mono_solution,
    interpret_biobjective_solution,
)
from solver_optimizador.model_io import (
    serialize_model,
    deserialize_model,
    normalize_constraints,
    sanitize_filename,
    SCHEMA_VERSION,
)
from solver_optimizador.problem_builder import (
    build_lp_problem_from_state,
    build_biobjective_problem_from_state,
)
from solver_optimizador.constraint_import import (
    ConstraintImportResult,
    constraint_template_sparse,
    constraint_template_wide,
    constraints_to_sparse_csv,
    list_xlsx_sheets,
    objective_template_bi,
    objective_template_mono,
    parse_constraint_text,
    parse_objective_text,
    parse_variable_names,
    parse_xlsx_constraints,
    validate_variable_names,
)
from solver_optimizador.input_application import (
    apply_constraint_import,
    apply_manual_variable_rename,
    apply_objective_import,
    apply_variable_import,
)
from solver_optimizador.plotting import (
    plot_feasible_region_2d,
    plot_objective_space_2d,
    plot_variable_values,
    plot_constraint_slacks,
    plot_multiobjective_runs,
)


st.set_page_config(
    page_title="Suite de Optimizacion Matematica — MVP LP",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _format_result_value(value: Optional[float], decimals: int = 4) -> str:
    """Formatea resultados para UI sin modificar los floats canonicos."""

    if value is None:
        return "—"
    numeric_value = float(value)
    magnitude = abs(numeric_value)
    if numeric_value != 0.0 and (
        magnitude < 10 ** (-decimals) or magnitude >= 10 ** (decimals + 3)
    ):
        return f"{numeric_value:.6g}"
    return f"{numeric_value:.{decimals}f}"


MANUAL_VARIABLE_EDITOR_LIMIT = 100
MANUAL_CONSTRAINT_ROW_LIMIT = 100
MANUAL_CONSTRAINT_CELL_LIMIT = 2_000
IMPORT_PREVIEW_LIMIT = 20


@st.cache_data(max_entries=10, show_spinner=False)
def _cached_xlsx_sheets(data: bytes) -> List[str]:
    return list_xlsx_sheets(data)


@st.cache_data(max_entries=10, show_spinner=False)
def _cached_xlsx_constraints(
    data: bytes,
    sheet_name: str,
    decimal_separator: str,
) -> ConstraintImportResult:
    return parse_xlsx_constraints(
        data,
        sheet_name=sheet_name,
        input_format="auto",
        decimal_separator=decimal_separator,
    )


def _canonical_to_flat_rows(
    constraints: List[Dict[str, Any]], variable_names: List[str]
) -> List[Dict[str, Any]]:
    """Crea solo la copia densa necesaria para el editor manual pequeno."""

    rows: List[Dict[str, Any]] = []
    for index, constraint in enumerate(constraints):
        coefficients = constraint.get("coefficients", {})
        row = {
            "Nombre": constraint.get("name", f"Restriccion {index + 1}"),
            "Operador": constraint.get("operator", "<="),
            "RHS": float(constraint.get("rhs", 0.0)),
        }
        for variable in variable_names:
            row[variable] = float(
                coefficients.get(variable, constraint.get(variable, 0.0))
                if isinstance(coefficients, dict)
                else constraint.get(variable, 0.0)
            )
        rows.append(row)
    return rows


def _constraint_preview_rows(
    constraints: List[Dict[str, Any]], search: str = ""
) -> List[Dict[str, Any]]:
    needle = search.strip().lower()
    preview: List[Dict[str, Any]] = []
    for constraint in constraints:
        if needle and needle not in str(constraint["name"]).lower():
            continue
        terms = list(constraint["coefficients"].items())
        expression = " + ".join(
            f"{coefficient:g}*{variable}" for variable, coefficient in terms[:8]
        ).replace("+ -", "- ")
        if len(terms) > 8:
            expression += f" + ... ({len(terms)} terminos)"
        preview.append(
            {
                "Restriccion": constraint["name"],
                "LHS disperso": expression or "0",
                "Operador": constraint["operator"],
                "RHS": constraint["rhs"],
            }
        )
    return preview


def _render_constraint_import_preview(result: ConstraintImportResult, key: str) -> None:
    for error in result.errors:
        st.error(error, icon=":material/error:")
    for warning in result.warnings:
        st.warning(warning, icon=":material/warning:")
    if not result.constraints:
        return
    with st.container(horizontal=True):
        st.metric("Variables detectadas", result.number_of_variables)
        st.metric("Restricciones", result.number_of_constraints)
        st.metric("Coeficientes no nulos", result.nonzero_coefficients)
        st.metric("Densidad estimada", f"{100 * result.density:.2f} %")
    search = st.text_input(
        "Filtrar vista previa por nombre",
        key=f"{key}_search",
        placeholder="Ejemplo: Balance_H",
    )
    matching = _constraint_preview_rows(result.constraints, search)
    shown = matching[:IMPORT_PREVIEW_LIMIT]
    st.dataframe(pd.DataFrame(shown), hide_index=True, width="stretch")
    st.caption(
        f"Vista previa: {len(shown)} de {len(matching)} restricciones coincidentes; "
        f"el lote completo contiene {result.number_of_constraints}."
    )


def _render_apply_import_controls(
    result: ConstraintImportResult,
    *,
    key: str,
    source_metadata: Dict[str, Any],
) -> None:
    variable_policy = st.segmented_control(
        "Tratamiento de variables",
        ["Validar contra variables actuales", "Usar variables detectadas"],
        default="Validar contra variables actuales",
        required=True,
        key=f"{key}_variable_policy",
        width="stretch",
    )
    if st.button(
        "Aplicar importacion",
        key=f"{key}_apply",
        type="primary",
        disabled=not result.is_valid,
        icon=":material/check_circle:",
    ):
        try:
            apply_constraint_import(
                st.session_state,
                result,
                use_detected_variables=variable_policy == "Usar variables detectadas",
                source_metadata=source_metadata,
            )
            st.session_state.constraint_import_preview = None
            st.session_state.example_msg = (
                f"{result.number_of_constraints} restricciones importadas; "
                f"{result.number_of_variables} variables reconocidas; "
                f"{result.nonzero_coefficients} coeficientes no nulos."
            )
            st.rerun()
        except ValueError as exc:
            st.error(str(exc), icon=":material/error:")


# ---------------------------------------------------------------------------
# Inicializacion y Sincronizacion de Estado de Sesion
# ---------------------------------------------------------------------------
def _init_session_state():
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0
    if "model_name" not in st.session_state:
        st.session_state.model_name = "Modelo de Optimizacion"
    if "model_desc" not in st.session_state:
        st.session_state.model_desc = ""
    if "problem_type" not in st.session_state:
        st.session_state.problem_type = "Biobjetivo"
    if "num_vars" not in st.session_state:
        st.session_state.num_vars = 2
    if "var_names" not in st.session_state:
        st.session_state.var_names = ["x1", "x2"]
    if "obj_sense" not in st.session_state:
        st.session_state.obj_sense = "Maximizar"
    if "obj_coeffs" not in st.session_state:
        st.session_state.obj_coeffs = {"x1": 3.0, "x2": 2.0}
    if "obj1_sense" not in st.session_state:
        st.session_state.obj1_sense = "Maximizar"
    if "obj1_coeffs" not in st.session_state:
        st.session_state.obj1_coeffs = {"x1": 10.0, "x2": 3.0}
    if "obj2_sense" not in st.session_state:
        st.session_state.obj2_sense = "Maximizar"
    if "obj2_coeffs" not in st.session_state:
        st.session_state.obj2_coeffs = {"x1": 0.8, "x2": 1.3}
    if "constraints_data" not in st.session_state:
        st.session_state.constraints_data = [
            {"name": "Restriccion 1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 130.0},
            {"name": "Restriccion 2", "x1": 2.5, "x2": 1.0, "operator": "<=", "rhs": 250.0},
        ]
    if "mo_mode" not in st.session_state:
        st.session_state.mo_mode = "Barrido automatico"
    if "num_weights" not in st.session_state:
        st.session_state.num_weights = 6
    if "custom_a1" not in st.session_state:
        st.session_state.custom_a1 = 0.5
    if "last_solution" not in st.session_state:
        st.session_state.last_solution = None
    if "last_solution_type" not in st.session_state:
        st.session_state.last_solution_type = None
    if "last_solution_problem" not in st.session_state:
        st.session_state.last_solution_problem = None
    if "last_solution_signature" not in st.session_state:
        st.session_state.last_solution_signature = None
    if "example_msg" not in st.session_state:
        st.session_state.example_msg = None
    if "constraint_import_preview" not in st.session_state:
        st.session_state.constraint_import_preview = None
    if "objective_import_preview" not in st.session_state:
        st.session_state.objective_import_preview = None
    if "variable_import_preview" not in st.session_state:
        st.session_state.variable_import_preview = None
    if "constraint_import_metadata" not in st.session_state:
        st.session_state.constraint_import_metadata = None
    if "constraint_import_preview_metadata" not in st.session_state:
        st.session_state.constraint_import_preview_metadata = None
    if "objective_import_metadata" not in st.session_state:
        st.session_state.objective_import_metadata = None
    if "variable_import_metadata" not in st.session_state:
        st.session_state.variable_import_metadata = None


def _clear_widget_keys(state=None):
    """
    Las claves de widgets estan versionadas mediante `editor_version`.
    Al incrementar `editor_version`, Streamlit instancia widgets totalmente nuevos
    inicializados deterministicamente desde `session_state`.
    """
    pass


def _new_model(state=None):
    if state is None:
        state = st.session_state
    _clear_widget_keys(state)
    state.editor_version += 1
    state.model_name = "Nuevo Modelo"
    state.model_desc = ""
    state.problem_type = "Monoobjetivo"
    state.num_vars = 2
    state.var_names = ["x1", "x2"]
    state.obj_sense = "Maximizar"
    state.obj_coeffs = {"x1": 1.0, "x2": 1.0}
    state.obj1_sense = "Maximizar"
    state.obj1_coeffs = {"x1": 1.0, "x2": 1.0}
    state.obj2_sense = "Maximizar"
    state.obj2_coeffs = {"x1": 1.0, "x2": 1.0}
    state.constraints_data = [
        {"name": "Restriccion 1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 10.0}
    ]
    state.last_solution = None
    state.last_solution_type = None
    state.last_solution_problem = None
    state.last_solution_signature = None
    state.constraint_import_preview = None
    state.objective_import_preview = None
    state.variable_import_preview = None
    state.constraint_import_metadata = None
    state.objective_import_metadata = None
    state.variable_import_metadata = None
    state.example_msg = "Nuevo modelo en blanco iniciado."


def _load_model_dict(data: Dict[str, Any], state=None):
    """Carga atomica completa del modelo desde la estructura deserializada."""
    if state is None:
        state = st.session_state
    _clear_widget_keys(state)
    state.editor_version += 1
    meta_name = data.get("metadata", {}).get("name", "Modelo Importado")
    state.model_name = meta_name
    state.model_desc = data.get("metadata", {}).get("description", "")
    state.problem_type = data["problem_type"]
    state.num_vars = data["num_vars"]
    state.var_names = list(data["var_names"])
    state.constraints_data = data["constraints_data"]

    if data["problem_type"] == "Monoobjetivo":
        state.obj_sense = data["obj_sense"]
        state.obj_coeffs = data["obj_coeffs"]
        state.obj1_sense = "Maximizar"
        state.obj1_coeffs = {v: 0.0 for v in data["var_names"]}
        state.obj2_sense = "Maximizar"
        state.obj2_coeffs = {v: 0.0 for v in data["var_names"]}
    else:
        state.obj1_sense = data["obj1_sense"]
        state.obj1_coeffs = data["obj1_coeffs"]
        state.obj2_sense = data["obj2_sense"]
        state.obj2_coeffs = data["obj2_coeffs"]
        state.mo_mode = data.get("mo_mode", "Barrido automatico")
        state.num_weights = data.get("num_weights", 6)
        state.custom_a1 = data.get("custom_a1", 0.5)
        state.obj_sense = "Maximizar"
        state.obj_coeffs = {v: 0.0 for v in data["var_names"]}

    state.last_solution = None
    state.last_solution_type = None
    state.last_solution_problem = None
    state.last_solution_signature = None
    state.constraint_import_preview = None
    state.objective_import_preview = None
    state.variable_import_preview = None
    state.constraint_import_metadata = {
        "source_type": "json",
        "filename": data.get("metadata", {}).get("name", "modelo.json"),
        "constraint_count": len(data["constraints_data"]),
        "variable_count": len(data["var_names"]),
    }

    n_v = data["num_vars"]
    n_c = len(data["constraints_data"])
    p_t = data["problem_type"]
    s_info = data["obj_sense"] if p_t == "Monoobjetivo" else f"Z1:{data['obj1_sense']} / Z2:{data['obj2_sense']}"
    state.example_msg = f"✅ Modelo '{meta_name}' cargado correctamente ({n_v} variables · {n_c} restricciones · {p_t} · {s_info})."


def _load_example_mono():
    _clear_widget_keys()
    st.session_state.editor_version += 1
    st.session_state.model_name = "Ejemplo 1 (Monoobjetivo)"
    st.session_state.model_desc = "MAX Z = 3x1 + 2x2 sujeto a restricciones lineales basicas."
    st.session_state.problem_type = "Monoobjetivo"
    st.session_state.num_vars = 2
    st.session_state.var_names = ["x1", "x2"]
    st.session_state.obj_sense = "Maximizar"
    st.session_state.obj_coeffs = {"x1": 3.0, "x2": 2.0}
    st.session_state.constraints_data = [
        {"name": "Capacidad total", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 4.0},
        {"name": "Limite x1", "x1": 1.0, "x2": 0.0, "operator": "<=", "rhs": 2.0},
        {"name": "Limite x2", "x1": 0.0, "x2": 1.0, "operator": "<=", "rhs": 3.0},
    ]
    st.session_state.last_solution = None
    st.session_state.last_solution_type = None
    st.session_state.last_solution_problem = None
    st.session_state.last_solution_signature = None
    st.session_state.constraint_import_metadata = {"source_type": "example", "constraint_count": 3, "variable_count": 2}
    st.session_state.example_msg = "Ejemplo 1 (Monoobjetivo) cargado exitosamente."


def _load_example_bio():
    _clear_widget_keys()
    st.session_state.editor_version += 1
    st.session_state.model_name = "Benchmark A (Biobjetivo)"
    st.session_state.model_desc = "Problema biobjetivo continuo MAX Z1, MAX Z2 con 6 ponderaciones."
    st.session_state.problem_type = "Biobjetivo"
    st.session_state.num_vars = 2
    st.session_state.var_names = ["x1", "x2"]
    st.session_state.obj1_sense = "Maximizar"
    st.session_state.obj1_coeffs = {"x1": 10.0, "x2": 3.0}
    st.session_state.obj2_sense = "Maximizar"
    st.session_state.obj2_coeffs = {"x1": 0.8, "x2": 1.3}
    st.session_state.constraints_data = [
        {"name": "Limite recursos A", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 130.0},
        {"name": "Limite recursos B", "x1": 2.5, "x2": 1.0, "operator": "<=", "rhs": 250.0},
    ]
    st.session_state.mo_mode = "Barrido automatico"
    st.session_state.num_weights = 6
    st.session_state.last_solution = None
    st.session_state.last_solution_type = None
    st.session_state.last_solution_problem = None
    st.session_state.last_solution_signature = None
    st.session_state.constraint_import_metadata = {"source_type": "example", "constraint_count": 2, "variable_count": 2}
    st.session_state.example_msg = "Benchmark A (Biobjetivo) cargado exitosamente."


_init_session_state()


# ---------------------------------------------------------------------------
# Barra Lateral (Configuracion y Gestion de Modelos)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuracion")
    st.caption("Backend: **Pyomo 6.10.1 + HiGHS 1.15.1**")

    # 1. Gestion de Modelos (Guardar, Cargar, Nuevo)
    with st.container(border=True):
        st.subheader("📁 Gestion de Modelos")

        col_new, _ = st.columns([1, 1])
        with col_new:
            if st.button("➕ Nuevo", help="Crear un modelo en blanco", width="stretch"):
                _new_model()
                st.rerun()

        # Metadata del modelo (versionado determinista)
        st.session_state.model_name = st.text_input(
            "Nombre del modelo:",
            value=st.session_state.model_name,
            key=f"model_name_input_{st.session_state.editor_version}",
        )
        st.session_state.model_desc = st.text_area(
            "Descripcion / Notas:",
            value=st.session_state.model_desc,
            height=60,
            key=f"model_desc_input_{st.session_state.editor_version}",
        )

        # Cargar archivo JSON con confirmacion explicita
        uploader_key = f"uploader_json_{st.session_state.uploader_version}"
        uploaded_file = st.file_uploader("Seleccionar modelo (.json):", type=["json"], key=uploader_key)
        if uploaded_file is not None:
            try:
                content = uploaded_file.getvalue().decode("utf-8")
                parsed_data = deserialize_model(content)

                # Resumen del archivo seleccionado antes de aplicar
                st.info("📄 **Archivo seleccionado:**")
                f_name = parsed_data.get("metadata", {}).get("name", "Sin nombre")
                f_type = parsed_data.get("problem_type")
                f_vars = parsed_data.get("num_vars")
                f_cons = len(parsed_data.get("constraints_data", []))
                f_obj = parsed_data.get("obj_sense") if f_type == "Monoobjetivo" else f"Z1:{parsed_data.get('obj1_sense')}, Z2:{parsed_data.get('obj2_sense')}"
                st.markdown(f"- **Nombre:** {f_name}\n- **Tipo:** {f_type}\n- **Variables:** {f_vars}\n- **Restricciones:** {f_cons}\n- **Objetivo(s):** {f_obj}")

                if st.button("📥 Cargar modelo", type="primary", width="stretch"):
                    _load_model_dict(parsed_data)
                    st.session_state.uploader_version += 1
                    st.rerun()
            except Exception as e:
                st.error(f"No se pudo leer el archivo JSON: {e}")

    # 2. Ejemplos Precargados
    with st.container(border=True):
        st.subheader("📚 Ejemplos Academicos")
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            if st.button("Ejemplo 1 (Mono)", help="MAX Z = 3x1 + 2x2", width="stretch"):
                _load_example_mono()
                st.rerun()
        with col_ex2:
            if st.button("Benchmark A (Bio)", help="Benchmark A: MAX Z1, MAX Z2", width="stretch"):
                _load_example_bio()
                st.rerun()

    # 3. Modalidad y Variables
    with st.container(border=True):
        st.subheader("1. Tipo de Problema")
        prob_type_index = 0 if st.session_state.problem_type == "Monoobjetivo" else 1
        prob_type = st.radio(
            "Seleccione la modalidad:",
            options=["Monoobjetivo", "Biobjetivo"],
            index=prob_type_index,
            key=f"radio_prob_type_{st.session_state.editor_version}",
        )
        st.session_state.problem_type = prob_type

        st.subheader("2. Variables de Decision")
        st.caption(
            "Variables continuas no negativas ($x_i \\ge 0$). "
            "La edicion celda a celda se limita a 100 variables; los lotes admiten mas."
        )
        num_vars = st.number_input(
            "Cantidad de variables:",
            min_value=1,
            max_value=5000,
            value=int(st.session_state.num_vars),
            step=1,
            key=f"num_vars_input_{st.session_state.editor_version}",
        )

        old_var_names = list(st.session_state.var_names)
        if int(num_vars) != len(old_var_names):
            if int(num_vars) > len(old_var_names):
                for i in range(len(old_var_names), int(num_vars)):
                    new_default_name = f"x{i+1}"
                    suffix = 1
                    while new_default_name in old_var_names:
                        new_default_name = f"x{i+1}_{suffix}"
                        suffix += 1
                    old_var_names.append(new_default_name)
            else:
                old_var_names = old_var_names[:int(num_vars)]
            apply_variable_import(
                st.session_state,
                old_var_names,
                source_metadata={"mode": "quantity_control"},
            )
            st.rerun()

        has_var_name_error = False
        if len(st.session_state.var_names) <= MANUAL_VARIABLE_EDITOR_LIMIT:
            st.markdown("**Nombres de variables:**")
            df_vars_data = [
                {"#": index + 1, "Nombre": name}
                for index, name in enumerate(st.session_state.var_names)
            ]
            edited_vars_df = st.data_editor(
                pd.DataFrame(df_vars_data),
                disabled=["#"],
                hide_index=True,
                width="stretch",
                column_config={
                    "#": st.column_config.NumberColumn("#", width="small"),
                    "Nombre": st.column_config.TextColumn(
                        "Nombre Variable", width="medium", required=True
                    ),
                },
                key=f"var_names_editor_{st.session_state.editor_version}",
            )
            candidate_names = [
                str(row["Nombre"]).strip() for _, row in edited_vars_df.iterrows()
            ]
            manual_name_errors = validate_variable_names(candidate_names)
            if manual_name_errors:
                for error in manual_name_errors:
                    st.error(error, icon=":material/error:")
                has_var_name_error = True
            elif candidate_names != st.session_state.var_names:
                apply_manual_variable_rename(st.session_state, candidate_names)
                st.rerun()
        else:
            st.info(
                f"Modelo con {len(st.session_state.var_names)} variables. "
                "La tabla de nombres esta deshabilitada por rendimiento."
            )
            st.caption(
                "Muestra: " + ", ".join(st.session_state.var_names[:20])
                + (" ..." if len(st.session_state.var_names) > 20 else "")
            )

        with st.expander("Nombres de variables en bloque"):
            variable_text = st.text_area(
                "Pegue nombres separados por coma, tabulador o salto de linea",
                key=f"variable_batch_text_{st.session_state.editor_version}",
                placeholder="x1,x2,x3,x4,x5",
                height=110,
            )
            if st.button(
                "Validar nombres",
                key=f"validate_variables_{st.session_state.editor_version}",
                icon=":material/rule:",
            ):
                st.session_state.variable_import_preview = parse_variable_names(variable_text)
            variable_preview = st.session_state.variable_import_preview
            if variable_preview is not None:
                for error in variable_preview.errors:
                    st.error(error, icon=":material/error:")
                if variable_preview.variables:
                    st.info(f"Variables detectadas: {len(variable_preview.variables)}")
                    st.code(", ".join(variable_preview.variables[:30]))
                if st.button(
                    "Usar variables detectadas",
                    key=f"apply_variables_{st.session_state.editor_version}",
                    type="primary",
                    disabled=not variable_preview.is_valid,
                    icon=":material/check_circle:",
                ):
                    apply_variable_import(
                        st.session_state,
                        variable_preview,
                        source_metadata={"mode": "block_text"},
                    )
                    st.session_state.variable_import_preview = None
                    st.session_state.example_msg = (
                        f"{len(variable_preview.variables)} variables aplicadas."
                    )
                    st.rerun()

        var_names = list(st.session_state.var_names)

    # 4. Metodologia / Ayuda
    with st.expander("ℹ️ Metodologia Multiobjetivo"):
        st.markdown(
            """
            * **Ponderaciones:** Combina los dos objetivos mediante pesos $(\\alpha_1, \\alpha_2)$ donde $\\alpha_1 + \\alpha_2 = 1$.
            * **Matriz de pagos:** Los optimos individuales definen las anclas y rangos:
              $$\\Delta Z_k = Z_{k,\\max} - Z_{k,\\min}$$
            * **Normalizacion orientada al beneficio:**
              $$N_k = \\frac{Z_k-Z_{k,\\min}}{\\Delta Z_k}\\quad(\\mathrm{MAX}),\\qquad
              N_k = \\frac{Z_{k,\\max}-Z_k}{\\Delta Z_k}\\quad(\\mathrm{MIN})$$
            * **Suma ponderada normalizada:** Cada peso resuelve
              $$\\max\\; W = \\alpha_1 N_1 + \\alpha_2 N_2$$
              sujeto a todas las restricciones originales, incluidos los pesos extremos $(1,0)$ y $(0,1)$.
            * **Rigor:** Las soluciones corresponden a las ponderaciones evaluadas y no necesariamente representan toda la frontera de Pareto continua.
            """
        )


# ---------------------------------------------------------------------------
# Encabezado Principal
# ---------------------------------------------------------------------------
st.title("📐 Suite de Optimizacion Matematica")
st.markdown(
    f"Formulacion, resolucion y analisis de **Programacion Lineal Continua** · **{st.session_state.model_name}**"
)

if st.session_state.example_msg:
    st.toast(st.session_state.example_msg)
    st.session_state.example_msg = None


# ---------------------------------------------------------------------------
# Pestañas Principales: 1. Formulacion vs. 2. Resultados
# ---------------------------------------------------------------------------
tab_form, tab_res = st.tabs(["📝 1. Formulacion del Modelo", "📊 2. Resultados y Analisis"])


# ===========================================================================
# PESTAÑA 1: FORMULACION DEL MODELO
# ===========================================================================
with tab_form:
    col_left, col_right = st.columns([1.1, 1.3])

    # -----------------------------------------------------------------------
    # Columna Izquierda: Objetivos y Ponderaciones
    # -----------------------------------------------------------------------
    with col_left:
        with st.container(border=True):
            st.subheader("🎯 Funcion(es) Objetivo")

            if st.session_state.problem_type == "Monoobjetivo":
                st.markdown("**Objetivo Lineal $Z$:**")
                col_s, _ = st.columns([1, 2])
                with col_s:
                    sense_idx = 0 if st.session_state.obj_sense == "Maximizar" else 1
                    sense_str = st.selectbox(
                        "Sentido:",
                        ["Maximizar", "Minimizar"],
                        index=sense_idx,
                        key=f"mono_sense_select_{st.session_state.editor_version}",
                    )
                    st.session_state.obj_sense = sense_str

                st.markdown("**Coeficientes lineales del objetivo:**")
                st.caption("💡 **Nota:** Use punto (.) como separador decimal (ejemplo: 2.4525).")

                if len(var_names) <= MANUAL_VARIABLE_EDITOR_LIMIT:
                    obj_df_data = [
                        {
                            "Variable": variable,
                            "Coeficiente": float(
                                st.session_state.obj_coeffs.get(variable, 0.0)
                            ),
                        }
                        for variable in var_names
                    ]
                    edited_obj_df = st.data_editor(
                        pd.DataFrame(obj_df_data),
                        disabled=["Variable"],
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Variable": st.column_config.TextColumn("Variable", width="medium"),
                            "Coeficiente": st.column_config.NumberColumn(
                                "Coeficiente", format="%.6g", required=True
                            ),
                        },
                        key=f"mono_obj_editor_{st.session_state.editor_version}",
                    )
                    st.session_state.obj_coeffs = {
                        str(row["Variable"]): float(row["Coeficiente"])
                        for _, row in edited_obj_df.iterrows()
                    }
                else:
                    st.info(
                        "La tabla de coeficientes esta deshabilitada para este tamano. "
                        "Use la entrada masiva de objetivo."
                    )

            else:  # Biobjetivo
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    sense1_idx = 0 if st.session_state.obj1_sense == "Maximizar" else 1
                    sense1_str = st.selectbox(
                        "Sentido $Z_1$:",
                        ["Maximizar", "Minimizar"],
                        index=sense1_idx,
                        key=f"bio_sense1_select_{st.session_state.editor_version}",
                    )
                    st.session_state.obj1_sense = sense1_str
                with col_s2:
                    sense2_idx = 0 if st.session_state.obj2_sense == "Maximizar" else 1
                    sense2_str = st.selectbox(
                        "Sentido $Z_2$:",
                        ["Maximizar", "Minimizar"],
                        index=sense2_idx,
                        key=f"bio_sense2_select_{st.session_state.editor_version}",
                    )
                    st.session_state.obj2_sense = sense2_str

                st.markdown("**Coeficientes de ambos objetivos:**")
                st.caption("💡 **Nota:** Use punto (.) como separador decimal (ejemplo: 2.4525).")

                if len(var_names) <= MANUAL_VARIABLE_EDITOR_LIMIT:
                    bio_df_data = [
                        {
                            "Variable": variable,
                            "Coeficiente Z1": float(
                                st.session_state.obj1_coeffs.get(variable, 0.0)
                            ),
                            "Coeficiente Z2": float(
                                st.session_state.obj2_coeffs.get(variable, 0.0)
                            ),
                        }
                        for variable in var_names
                    ]
                    edited_bio_df = st.data_editor(
                        pd.DataFrame(bio_df_data),
                        disabled=["Variable"],
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Variable": st.column_config.TextColumn("Variable", width="medium"),
                            "Coeficiente Z1": st.column_config.NumberColumn(
                                f"Coef. Z1 ({st.session_state.obj1_sense[:3].upper()})",
                                format="%.6g",
                                required=True,
                            ),
                            "Coeficiente Z2": st.column_config.NumberColumn(
                                f"Coef. Z2 ({st.session_state.obj2_sense[:3].upper()})",
                                format="%.6g",
                                required=True,
                            ),
                        },
                        key=f"bio_obj_editor_{st.session_state.editor_version}",
                    )
                    st.session_state.obj1_coeffs = {
                        str(row["Variable"]): float(row["Coeficiente Z1"])
                        for _, row in edited_bio_df.iterrows()
                    }
                    st.session_state.obj2_coeffs = {
                        str(row["Variable"]): float(row["Coeficiente Z2"])
                        for _, row in edited_bio_df.iterrows()
                    }
                else:
                    st.info(
                        "Las tablas de objetivos estan deshabilitadas para este tamano. "
                        "Use la entrada masiva."
                    )

            with st.expander("Entrada masiva de objetivo"):
                expected_header = (
                    "variable,coefficient"
                    if st.session_state.problem_type == "Monoobjetivo"
                    else "variable,Z1,Z2"
                )
                st.caption(
                    f"Formato: `{expected_header}`. Las variables omitidas pasan a 0 "
                    "solo al aplicar el lote."
                )
                objective_text = st.text_area(
                    "Pegue coeficientes CSV/TSV",
                    key=f"objective_batch_text_{st.session_state.editor_version}",
                    height=140,
                    placeholder=(
                        objective_template_mono()
                        if st.session_state.problem_type == "Monoobjetivo"
                        else objective_template_bi()
                    ),
                )
                objective_file = st.file_uploader(
                    "O seleccione un CSV de objetivo",
                    type=["csv"],
                    key=f"objective_batch_file_{st.session_state.editor_version}",
                    max_upload_size=5,
                )
                if st.button(
                    "Validar objetivo",
                    key=f"validate_objective_{st.session_state.editor_version}",
                    icon=":material/rule:",
                ):
                    try:
                        objective_source = (
                            objective_file.getvalue().decode("utf-8-sig")
                            if objective_file is not None
                            else objective_text
                        )
                        st.session_state.objective_import_preview = parse_objective_text(
                            objective_source,
                            problem_type=st.session_state.problem_type,
                            declared_variables=var_names,
                        )
                    except UnicodeDecodeError:
                        st.session_state.objective_import_preview = None
                        st.error("El CSV de objetivo debe usar UTF-8 o UTF-8-SIG.")
                objective_preview = st.session_state.objective_import_preview
                if objective_preview is not None:
                    for error in objective_preview.errors:
                        st.error(error, icon=":material/error:")
                    for warning in objective_preview.warnings:
                        st.warning(warning, icon=":material/warning:")
                    st.write(
                        f"Variables reconocidas: {len(objective_preview.recognized_variables)} · "
                        f"desconocidas: {len(objective_preview.unknown_variables)} · "
                        f"duplicadas: {len(objective_preview.duplicates)}"
                    )
                    if st.button(
                        "Aplicar objetivo",
                        key=f"apply_objective_{st.session_state.editor_version}",
                        type="primary",
                        disabled=not objective_preview.is_valid,
                        icon=":material/check_circle:",
                    ):
                        apply_objective_import(
                            st.session_state,
                            objective_preview,
                            source_metadata={
                                "filename": objective_file.name if objective_file else None
                            },
                        )
                        st.session_state.objective_import_preview = None
                        st.session_state.example_msg = "Objetivo masivo aplicado correctamente."
                        st.rerun()

        # Ponderaciones (solo en Biobjetivo)
        if st.session_state.problem_type == "Biobjetivo":
            with st.container(border=True):
                st.subheader("⚖️ Configuracion de Ponderaciones")
                mo_mode_idx = 0 if st.session_state.mo_mode == "Barrido automatico" else 1
                mo_mode = st.radio(
                    "Modalidad de pesos:",
                    options=["Barrido automatico", "Ponderacion unica"],
                    index=mo_mode_idx,
                    horizontal=True,
                    key=f"mo_mode_radio_{st.session_state.editor_version}",
                )
                st.session_state.mo_mode = mo_mode

                if mo_mode == "Barrido automatico":
                    num_weights = st.slider(
                        "Numero de combinaciones $(\\alpha_1, \\alpha_2)$:",
                        min_value=2,
                        max_value=21,
                        value=int(st.session_state.num_weights),
                        step=1,
                        key=f"num_weights_slider_{st.session_state.editor_version}",
                    )
                    st.session_state.num_weights = num_weights
                    preview_w = generate_weight_combinations(num_weights)
                    preview_str = ", ".join(f"({a1:.2f}, {a2:.2f})" for a1, a2 in preview_w)
                    st.caption(f"**Ponderaciones generadas:** {preview_str}")
                else:
                    custom_a1 = st.slider(
                        "Peso $\\alpha_1$ (para $Z_1$):",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(st.session_state.custom_a1),
                        step=0.05,
                        key=f"custom_a1_slider_{st.session_state.editor_version}",
                    )
                    st.session_state.custom_a1 = custom_a1
                    custom_a2 = round(1.0 - custom_a1, 4)
                    st.info(f"$\\alpha_1 = {custom_a1:.2f} \\quad (Z_1), \\quad \\alpha_2 = {custom_a2:.2f} \\quad (Z_2) \\implies \\alpha_1 + \\alpha_2 = 1.0$")

    # -----------------------------------------------------------------------
    # Columna Derecha: Restricciones y Vista Previa
    # -----------------------------------------------------------------------
    with col_right:
        with st.container(border=True):
            st.subheader("📋 Restricciones Lineales")
            st.caption(
                "Elija edicion manual para modelos pequenos o una importacion atomica "
                "para matrices medianas y grandes."
            )
            input_mode = st.segmented_control(
                "Modo de entrada",
                ["Manual", "Pegar tabla", "CSV / XLSX", "Matriz dispersa"],
                default="Manual",
                required=True,
                key="constraint_input_mode",
                persist_state="session",
                width="stretch",
            )

            if input_mode == "Manual":
                st.markdown("**Manual — recomendado para modelos pequeños**")
                current_count = len(st.session_state.constraints_data)
                current_cells = current_count * max(1, len(var_names))
                manual_allowed = (
                    current_count <= MANUAL_CONSTRAINT_ROW_LIMIT
                    and current_cells <= MANUAL_CONSTRAINT_CELL_LIMIT
                    and len(var_names) <= MANUAL_VARIABLE_EDITOR_LIMIT
                )
                if manual_allowed:
                    current_data = _canonical_to_flat_rows(
                        st.session_state.constraints_data, var_names
                    )
                    df_constraints = pd.DataFrame(current_data)
                    column_order = ["Nombre"] + var_names + ["Operador", "RHS"]
                    col_config = {
                        "Nombre": st.column_config.TextColumn("Nombre", required=True),
                        "Operador": st.column_config.SelectboxColumn(
                            "Operador", options=["<=", ">=", "="], required=True
                        ),
                        "RHS": st.column_config.NumberColumn(
                            "Lado Derecho (RHS)", required=True, format="%.6g"
                        ),
                    }
                    for variable in var_names:
                        col_config[variable] = st.column_config.NumberColumn(
                            variable, required=True, format="%.6g"
                        )
                    edited_df = st.data_editor(
                        df_constraints.reindex(columns=column_order),
                        num_rows="dynamic",
                        width="stretch",
                        column_config=col_config,
                        key=f"constraints_editor_{st.session_state.editor_version}",
                    )
                    manual_submit = st.button(
                        "Aplicar cambios manuales",
                        type="primary",
                        key=f"apply_manual_constraints_{st.session_state.editor_version}",
                        icon=":material/check_circle:",
                    )
                    if manual_submit:
                        try:
                            manual_constraints = normalize_constraints(
                                edited_df.to_dict(orient="records"), var_names
                            )
                            manual_result = ConstraintImportResult(
                                constraints=manual_constraints,
                                detected_variables=list(var_names),
                                source_format="manual",
                                source_rows=len(manual_constraints),
                            )
                            apply_constraint_import(
                                st.session_state,
                                manual_result,
                                use_detected_variables=False,
                                source_metadata={"mode": "manual_editor"},
                            )
                            st.session_state.example_msg = (
                                f"{len(manual_constraints)} restricciones manuales aplicadas."
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc), icon=":material/error:")
                else:
                    st.warning(
                        f"Este modelo contiene {current_count} restricciones y "
                        f"{len(var_names)} variables. La edicion celda a celda esta "
                        "deshabilitada por rendimiento. Use importacion masiva o "
                        "exporte y edite el CSV disperso."
                    )

            elif input_mode == "Pegar tabla":
                st.markdown("**Paso 1 — pegar · Paso 2 — validar · Paso 3 — previsualizar · Paso 4 — aplicar**")
                pasted_text = st.text_area(
                    "Pegue una tabla ancha desde Excel, Google Sheets, CSV o TSV",
                    key="constraint_paste_text",
                    persist_state="session",
                    height=180,
                    placeholder=constraint_template_wide(),
                )
                decimal_separator = st.selectbox(
                    "Separador decimal",
                    [".", ","],
                    key="constraint_paste_decimal",
                )
                if st.button("Validar tabla pegada", key="validate_pasted_constraints", icon=":material/rule:"):
                    st.session_state.constraint_import_preview = parse_constraint_text(
                        pasted_text,
                        input_format="wide",
                        decimal_separator=decimal_separator,
                    )
                    st.session_state.constraint_import_preview_metadata = {
                        "source_type": "paste",
                        "format": "wide",
                    }
                result = st.session_state.constraint_import_preview
                metadata = st.session_state.constraint_import_preview_metadata or {}
                if result is not None and metadata.get("source_type") == "paste":
                    _render_constraint_import_preview(result, "paste_preview")
                    _render_apply_import_controls(result, key="paste", source_metadata=metadata)

            elif input_mode == "CSV / XLSX":
                st.markdown("**Paso 1 — cargar · Paso 2 — validar · Paso 3 — previsualizar · Paso 4 — aplicar**")
                uploaded_constraints = st.file_uploader(
                    "Seleccione CSV o XLSX (sin macros)",
                    type=["csv", "xlsx"],
                    key="constraint_file_upload",
                    max_upload_size=20,
                )
                decimal_separator = st.selectbox(
                    "Separador decimal del archivo",
                    [".", ","],
                    key="constraint_file_decimal",
                )
                selected_sheet = None
                file_error = None
                if uploaded_constraints is not None and uploaded_constraints.name.lower().endswith(".xlsx"):
                    try:
                        sheets = _cached_xlsx_sheets(uploaded_constraints.getvalue())
                        selected_sheet = st.selectbox("Hoja XLSX", sheets, key="constraint_xlsx_sheet")
                    except ValueError as exc:
                        file_error = str(exc)
                        st.error(file_error, icon=":material/error:")
                if st.button(
                    "Validar archivo",
                    key="validate_constraint_file",
                    disabled=uploaded_constraints is None or file_error is not None,
                    icon=":material/rule:",
                ):
                    filename = uploaded_constraints.name
                    lower_filename = filename.lower()
                    if lower_filename.endswith(".csv"):
                        try:
                            decoded = uploaded_constraints.getvalue().decode("utf-8-sig")
                            imported = parse_constraint_text(
                                decoded,
                                input_format="auto",
                                decimal_separator=decimal_separator,
                            )
                        except UnicodeDecodeError:
                            imported = ConstraintImportResult(
                                errors=["El CSV debe usar UTF-8 o UTF-8-SIG."],
                                source_format="csv",
                            )
                    elif lower_filename.endswith(".xlsx"):
                        imported = _cached_xlsx_constraints(
                            uploaded_constraints.getvalue(),
                            selected_sheet,
                            decimal_separator,
                        )
                    else:
                        imported = ConstraintImportResult(
                            errors=["Formato rechazado. Solo se admiten .csv y .xlsx."],
                            source_format="unsupported",
                        )
                    st.session_state.constraint_import_preview = imported
                    st.session_state.constraint_import_preview_metadata = {
                        "source_type": "file",
                        "filename": filename,
                        "sheet": selected_sheet,
                    }
                result = st.session_state.constraint_import_preview
                metadata = st.session_state.constraint_import_preview_metadata or {}
                if result is not None and metadata.get("source_type") == "file":
                    _render_constraint_import_preview(result, "file_preview")
                    _render_apply_import_controls(result, key="file", source_metadata=metadata)

            else:
                st.markdown("**Paso 1 — cargar tripletas · Paso 2 — validar · Paso 3 — previsualizar · Paso 4 — aplicar**")
                sparse_text = st.text_area(
                    "Tabla dispersa: constraint, variable, coefficient, operator, rhs",
                    key="constraint_sparse_text",
                    persist_state="session",
                    height=200,
                    placeholder=constraint_template_sparse(),
                )
                if st.button("Validar matriz dispersa", key="validate_sparse_constraints", icon=":material/rule:"):
                    st.session_state.constraint_import_preview = parse_constraint_text(
                        sparse_text, input_format="sparse"
                    )
                    st.session_state.constraint_import_preview_metadata = {
                        "source_type": "paste",
                        "format": "sparse",
                    }
                result = st.session_state.constraint_import_preview
                metadata = st.session_state.constraint_import_preview_metadata or {}
                if result is not None and metadata.get("format") == "sparse":
                    _render_constraint_import_preview(result, "sparse_preview")
                    _render_apply_import_controls(result, key="sparse", source_metadata=metadata)

            with st.expander("Descargar plantillas CSV"):
                st.download_button(
                    "Plantilla restricciones formato ancho",
                    constraint_template_wide(),
                    "restricciones_formato_ancho.csv",
                    "text/csv",
                )
                st.download_button(
                    "Plantilla restricciones formato disperso",
                    constraint_template_sparse(),
                    "restricciones_formato_disperso.csv",
                    "text/csv",
                )
                st.download_button(
                    "Plantilla objetivo monoobjetivo",
                    objective_template_mono(),
                    "objetivo_monoobjetivo.csv",
                    "text/csv",
                )
                st.download_button(
                    "Plantilla objetivos biobjetivo",
                    objective_template_bi(),
                    "objetivos_biobjetivo.csv",
                    "text/csv",
                )

            applied_constraints = normalize_constraints(
                st.session_state.constraints_data, var_names
            )
            applied_nnz = sum(len(row["coefficients"]) for row in applied_constraints)
            applied_density_denominator = len(applied_constraints) * len(var_names)
            applied_density = (
                applied_nnz / applied_density_denominator
                if applied_density_denominator
                else 0.0
            )
            st.markdown("**Modelo aplicado actualmente**")
            st.write(
                f"Variables: {len(var_names)} · Restricciones: {len(applied_constraints)} · "
                f"Coeficientes no nulos: {applied_nnz:,} · Densidad: {100 * applied_density:.2f} %"
            )
            applied_filter = st.text_input(
                "Buscar restriccion aplicada",
                key="applied_constraint_search",
                persist_state="session",
                placeholder="Nombre de restriccion",
            )
            applied_rows = _constraint_preview_rows(applied_constraints, applied_filter)
            st.dataframe(
                pd.DataFrame(applied_rows[:IMPORT_PREVIEW_LIMIT]),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"Vista previa: {min(IMPORT_PREVIEW_LIMIT, len(applied_rows))} de "
                f"{len(applied_rows)} restricciones coincidentes. El modelo completo no se trunca."
            )

        try:
            canonical_constraints = normalize_constraints(
                st.session_state.constraints_data, var_names
            )
            cons_norm_error = None
        except Exception as e:
            canonical_constraints = []
            cons_norm_error = str(e)

        # Vista Previa Matematica
        with st.container(border=True):
            st.subheader("👁️ Vista Previa Matematica del Modelo")
            if st.session_state.problem_type == "Monoobjetivo":
                s_txt = st.session_state.obj_sense[:3].upper()
                terms_z_all = [f"{c:g} {v}" for v, c in st.session_state.obj_coeffs.items() if abs(c) > 1e-7]
                terms_z = terms_z_all[:20]
                expr_z = " + ".join(terms_z).replace("+ -", "- ") if terms_z else "0"
                if len(terms_z_all) > 20:
                    expr_z += f" + \\dots\\quad ({len(terms_z_all)}\\;terminos)"
                st.latex(f"\\text{{{s_txt}}}\\quad Z = {expr_z}")
            else:
                s1_txt = st.session_state.obj1_sense[:3].upper()
                terms_z1_all = [f"{c:g} {v}" for v, c in st.session_state.obj1_coeffs.items() if abs(c) > 1e-7]
                terms_z1 = terms_z1_all[:20]
                expr_z1 = " + ".join(terms_z1).replace("+ -", "- ") if terms_z1 else "0"
                if len(terms_z1_all) > 20:
                    expr_z1 += f" + \\dots\\quad ({len(terms_z1_all)}\\;terminos)"

                s2_txt = st.session_state.obj2_sense[:3].upper()
                terms_z2_all = [f"{c:g} {v}" for v, c in st.session_state.obj2_coeffs.items() if abs(c) > 1e-7]
                terms_z2 = terms_z2_all[:20]
                expr_z2 = " + ".join(terms_z2).replace("+ -", "- ") if terms_z2 else "0"
                if len(terms_z2_all) > 20:
                    expr_z2 += f" + \\dots\\quad ({len(terms_z2_all)}\\;terminos)"

                st.latex(f"\\text{{{s1_txt}}}\\quad Z_1 = {expr_z1}")
                st.latex(f"\\text{{{s2_txt}}}\\quad Z_2 = {expr_z2}")

            # Restricciones en LaTeX (muestra; nunca trunca el modelo aplicado)
            latex_cons = []
            for constraint in canonical_constraints[:15]:
                c_terms = [
                    f"{coefficient:g} {variable}"
                    for variable, coefficient in constraint["coefficients"].items()
                    if abs(coefficient) > 1e-7
                ]
                lhs_str = " + ".join(c_terms).replace("+ -", "- ") if c_terms else "0"
                op_sym = (
                    "\\le"
                    if constraint["operator"] == "<="
                    else "\\ge" if constraint["operator"] == ">=" else "="
                )
                rhs_val = constraint["rhs"]
                latex_cons.append(f"{lhs_str} {op_sym} {rhs_val:g}")

            vars_nonneg = ", ".join(var_names[:6]) + (", \\dots" if len(var_names) > 6 else "") + " \\ge 0"
            all_lines = "\\\\\n".join(latex_cons + [vars_nonneg])
            st.latex(f"\\text{{sujeto a:}}\n\\begin{{cases}}\n{all_lines}\n\\end{{cases}}")

        # Diagnostico del Modelo Efectivo (Opcional / Cerrado por defecto)
        with st.expander("🔧 Diagnostico del modelo efectivo", expanded=False):
            st.markdown(f"**Nombre:** {st.session_state.model_name}")
            st.markdown(f"**Tipo de Problema:** {st.session_state.problem_type}")
            variable_sample = ", ".join(var_names[:20]) + (" ..." if len(var_names) > 20 else "")
            st.markdown(f"**Variables ({len(var_names)}):** `{variable_sample}`")
            if st.session_state.problem_type == "Monoobjetivo":
                st.markdown(f"**Sentido:** {st.session_state.obj_sense}")
                nonzero_objective = [
                    f"{variable}: {coefficient}"
                    for variable, coefficient in st.session_state.obj_coeffs.items()
                    if abs(coefficient) > 1e-7
                ]
                st.markdown(
                    f"**Coeficientes no nulos ({len(nonzero_objective)}):** "
                    f"{nonzero_objective[:20]}"
                    + (" ..." if len(nonzero_objective) > 20 else "")
                )
            else:
                st.markdown(f"**Sentidos:** Z1={st.session_state.obj1_sense}, Z2={st.session_state.obj2_sense}")
            st.markdown(f"**Restricciones validas procesadas:** {len(canonical_constraints)}")
            if canonical_constraints:
                diag_summary = []
                for c in canonical_constraints:
                    active_vars = [f"{v}: {val}" for v, val in c["coefficients"].items() if abs(val) > 1e-7]
                    diag_summary.append({
                        "Nombre": c["name"],
                        "Operador": c["operator"],
                        "RHS": c["rhs"],
                        "Variables Activas": ", ".join(active_vars[:4]) + (", ..." if len(active_vars) > 4 else ""),
                    })
                st.dataframe(
                    pd.DataFrame(diag_summary[:IMPORT_PREVIEW_LIMIT]),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    f"Diagnostico: {min(IMPORT_PREVIEW_LIMIT, len(diag_summary))} de "
                    f"{len(diag_summary)} restricciones."
                )

    # -----------------------------------------------------------------------
    # Boton de Resolucion y Descarga
    # -----------------------------------------------------------------------
    st.markdown("---")
    if has_var_name_error:
        st.error(
            "⚠️ **No es posible resolver ni descargar el modelo:** "
            "Existen errores en los nombres de las variables."
        )
    elif cons_norm_error:
        st.error(f"⚠️ **No es posible resolver ni descargar el modelo:** {cons_norm_error}")
    elif not canonical_constraints:
        st.warning("⚠️ **No es posible resolver ni descargar el modelo:** Ingrese al menos una restriccion lineal valida en la tabla.")

    col_act1, col_act2, col_act3 = st.columns([2, 1, 1])
    with col_act1:
        btn_solve = st.button(
            "🚀 Resolver Modelo con Pyomo + HiGHS",
            type="primary",
            width="stretch",
            disabled=bool(has_var_name_error or cons_norm_error or not canonical_constraints),
        )
    with col_act2:
        # Serializar modelo actual para descarga
        curr_export_dict = {
            "type": st.session_state.problem_type,
            "variables": var_names,
            "constraints": canonical_constraints if canonical_constraints else st.session_state.constraints_data,
        }
        if st.session_state.problem_type == "Monoobjetivo":
            curr_export_dict["mono_objective"] = {
                "sense": st.session_state.obj_sense,
                "coefficients": st.session_state.obj_coeffs,
            }
        else:
            curr_export_dict["bio_objectives"] = {
                "obj1": {"sense": st.session_state.obj1_sense, "coefficients": st.session_state.obj1_coeffs},
                "obj2": {"sense": st.session_state.obj2_sense, "coefficients": st.session_state.obj2_coeffs},
            }
            curr_export_dict["multiobjective_settings"] = {
                "mode": st.session_state.mo_mode,
                "num_weights": st.session_state.num_weights,
                "custom_a1": st.session_state.custom_a1,
            }
        try:
            json_export_str = serialize_model(
                curr_export_dict,
                {"name": st.session_state.model_name, "description": st.session_state.model_desc},
            )
            st.download_button(
                label="💾 Descargar Modelo (.json)",
                data=json_export_str,
                file_name=sanitize_filename(st.session_state.model_name),
                mime="application/json",
                width="stretch",
                disabled=bool(cons_norm_error or has_var_name_error or not canonical_constraints),
            )
        except Exception as e:
            st.error(f"No se pudo preparar la exportacion JSON: {e}")
    with col_act3:
        sparse_export = constraints_to_sparse_csv(canonical_constraints, var_names)
        csv_name = sanitize_filename(st.session_state.model_name).removesuffix(".json") + "_restricciones.csv"
        st.download_button(
            label="Descargar restricciones CSV",
            data=sparse_export,
            file_name=csv_name,
            mime="text/csv",
            width="stretch",
            disabled=bool(cons_norm_error or not canonical_constraints),
            icon=":material/download:",
        )


# ---------------------------------------------------------------------------
# Calculo de la Firma del Modelo Actual
# ---------------------------------------------------------------------------
current_model_signature = build_model_signature(
    problem_type=st.session_state.problem_type,
    var_names=var_names,
    obj_sense=st.session_state.obj_sense,
    obj_coeffs=st.session_state.obj_coeffs,
    obj1_sense=st.session_state.obj1_sense,
    obj1_coeffs=st.session_state.obj1_coeffs,
    obj2_sense=st.session_state.obj2_sense,
    obj2_coeffs=st.session_state.obj2_coeffs,
    constraints_data=canonical_constraints,
    mo_mode=st.session_state.mo_mode,
    num_weights=st.session_state.num_weights,
    custom_a1=st.session_state.custom_a1,
)


# ===========================================================================
# LOGICA DE RESOLUCION
# ===========================================================================
if btn_solve:
    if cons_norm_error:
        st.error(f"Error en restricciones: {cons_norm_error}")
    elif not canonical_constraints:
        st.error("El problema debe contener al menos una restriccion lineal valida.")
    else:
        if st.session_state.problem_type == "Monoobjetivo":
            problem_mono = build_lp_problem_from_state(
                var_names=var_names,
                obj_sense=st.session_state.obj_sense,
                obj_coeffs=st.session_state.obj_coeffs,
                canonical_constraints=canonical_constraints,
            )
            with st.spinner("Resolviendo el modelo con Pyomo + HiGHS..."):
                sol_mono = solve_lp(problem_mono)
            st.session_state.last_solution = sol_mono
            st.session_state.last_solution_type = "Monoobjetivo"
            st.session_state.last_solution_problem = problem_mono
            st.session_state.last_solution_signature = current_model_signature

        else:
            problem_bio = build_biobjective_problem_from_state(
                var_names=var_names,
                obj1_sense=st.session_state.obj1_sense,
                obj1_coeffs=st.session_state.obj1_coeffs,
                obj2_sense=st.session_state.obj2_sense,
                obj2_coeffs=st.session_state.obj2_coeffs,
                canonical_constraints=canonical_constraints,
            )
            weights_param = None
            num_comb_param = None
            if st.session_state.mo_mode == "Barrido automatico":
                num_comb_param = int(st.session_state.num_weights)
            else:
                weights_param = [(float(st.session_state.custom_a1), round(1.0 - float(st.session_state.custom_a1), 4))]

            with st.spinner("Resolviendo el modelo con Pyomo + HiGHS..."):
                sol_bio = solve_biobjective_weighted(
                    problem_bio,
                    weights=weights_param,
                    num_combinations=num_comb_param,
                )
            st.session_state.last_solution = sol_bio
            st.session_state.last_solution_type = "Biobjetivo"
            st.session_state.last_solution_problem = problem_bio
            st.session_state.last_solution_signature = current_model_signature


# ===========================================================================
# PESTAÑA 2: RESULTADOS Y ANALISIS
# ===========================================================================
with tab_res:
    if st.session_state.last_solution is None:
        st.info("Formule su problema en la pestaña **1. Formulacion del Modelo** y pulse **'🚀 Resolver Modelo con Pyomo + HiGHS'** para calcular y visualizar los resultados.")
    else:
        # Verificacion de resultados desactualizados mediante firma
        is_stale = (st.session_state.last_solution_signature != current_model_signature)
        if is_stale:
            st.warning(
                "⚠️ **Resultados desactualizados:** El modelo fue modificado despues de la ultima resolucion. "
                "Pulse **'🚀 Resolver Modelo con Pyomo + HiGHS'** en la pestaña de formulacion para actualizar los resultados."
            )
            st.caption("Estado del modelo: ⚠️ **Resultados pendientes de recalcular** (mostrando resultados de la ultima resolucion calculada)")
        else:
            st.caption("Estado del modelo: ✅ **Resultados actualizados**")

        # -------------------------------------------------------------------
        # RESULTADOS MONOOBJETIVO
        # -------------------------------------------------------------------
        if st.session_state.last_solution_type == "Monoobjetivo":
            sol = st.session_state.last_solution
            prob = st.session_state.last_solution_problem

            if sol.status == SolverStatus.OPTIMAL:
                st.success(f"**{sol.status_message}** · Tiempo de ejecucion: {sol.execution_time_sec*1000:.1f} ms")

                with st.container(border=True):
                    st.subheader("🎯 Solucion Optima (Ultima Resolucion)")
                    n_display_vars = min(len(prob.variables), 8)
                    m_cols = st.columns(1 + n_display_vars)
                    with m_cols[0]:
                        st.metric(label="Valor Optimo Z*", value=_format_result_value(sol.objective_value))
                    for i, v in enumerate(prob.variables[:n_display_vars]):
                        with m_cols[i + 1]:
                            st.metric(label=f"{v}*", value=_format_result_value(sol.variable_values[v]))
                    if len(prob.variables) > 8:
                        st.caption(f"*(Mostrando las primeras 8 variables. Todas las {len(prob.variables)} variables se encuentran detalladas en el grafico y la tabla inferior)*")

                # Sub-pestañas de analisis monoobjetivo
                tab_mono_tbl, tab_mono_plots = st.tabs(["📋 Restricciones y Holguras", "📊 Graficos de Resultados"])

                with tab_mono_tbl:
                    with st.container(border=True):
                        st.subheader("🔍 Analisis de Restricciones y Holguras")
                        con_rows = []
                        for cr in sol.constraint_results:
                            con_rows.append({
                                "Restriccion": cr.name,
                                "LHS Evaluado": cr.lhs,
                                "Operador": cr.operator,
                                "RHS": cr.rhs,
                                "Holgura": cr.slack,
                                "Estado": f"Activa (tol={sol.activity_tolerance:g})" if cr.is_active else "Con holgura",
                            })
                        df_res_con = pd.DataFrame(con_rows)
                        st.dataframe(
                            df_res_con,
                            width="stretch",
                            column_config={
                                "LHS Evaluado": st.column_config.NumberColumn(format="%.6g"),
                                "RHS": st.column_config.NumberColumn(format="%.6g"),
                                "Holgura": st.column_config.NumberColumn(format="%.6g"),
                            },
                        )

                with tab_mono_plots:
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        with st.container(border=True):
                            fig_vars = plot_variable_values(sol.variable_values)
                            st.pyplot(fig_vars)

                    with col_p2:
                        with st.container(border=True):
                            fig_slacks = plot_constraint_slacks(sol.constraint_results)
                            st.pyplot(fig_slacks)

                    # Grafico 2D si aplica
                    if len(prob.variables) == 2:
                        with st.container(border=True):
                            st.subheader("🗺️ Espacio de Variables (2D)")
                            fig_feas = plot_feasible_region_2d(
                                prob,
                                solutions=[{"id": "Optimo", "x": sol.variable_values}],
                                title="Espacio de variables: Region factible y vertice optimo",
                            )
                            if fig_feas:
                                st.pyplot(fig_feas)
                    else:
                        st.info(
                            f"ℹ️ La region factible 2D en el plano aplica para problemas con exactamente 2 variables. "
                            f"Para este modelo de {len(prob.variables)} variables se presentan los graficos generales de variables y holguras."
                        )

                # Interpretacion automatica base monoobjetivo
                with st.container(border=True):
                    st.subheader("💡 Interpretacion Base de Resultados")
                    mono_bullets = interpret_mono_solution(prob, sol)
                    for b in mono_bullets:
                        st.markdown(f"- {b}")

            else:
                st.error(f"**{sol.status_message}** ({sol.raw_termination})")
                if sol.status == SolverStatus.INFEASIBLE:
                    st.warning("No existe ninguna combinacion de variables $(x \\ge 0)$ que satisfaga todas las restricciones simultaneamente.")
                elif sol.status == SolverStatus.UNBOUNDED:
                    st.warning("El problema no esta acotado en la direccion del objetivo (el valor optimo tiende a infinito).")

                # Interpretacion automatica de infactibilidad / no acotamiento
                with st.container(border=True):
                    st.subheader("💡 Diagnostico e Interpretacion del Modelo")
                    mono_bullets = interpret_mono_solution(prob, sol)
                    for b in mono_bullets:
                        st.markdown(f"- {b}")

                with st.expander("Detalles tecnicos del solver"):
                    st.json({
                        "status": sol.status.value,
                        "raw_termination": sol.raw_termination,
                        "execution_time_sec": sol.execution_time_sec,
                    })

        # -------------------------------------------------------------------
        # RESULTADOS BIOBJETIVO
        # -------------------------------------------------------------------
        else:
            sol = st.session_state.last_solution
            prob = st.session_state.last_solution_problem

            if not sol.unique_solutions:
                st.warning("No fue posible completar el barrido de ponderaciones.")
                for note in sol.notes:
                    st.info(f"📌 {note}")

                if sol.payoff_matrix:
                    with st.container(border=True):
                        st.subheader("Matriz de Pagos Obtenida")
                        pm_data = [
                            {
                                "Solucion": "Optimo individual Z1",
                                "Z1": sol.payoff_matrix["opt_Z1"]["Z1"],
                                "Z2": sol.payoff_matrix["opt_Z1"]["Z2"],
                                "Variables": str(sol.payoff_matrix["opt_Z1"]["x"]),
                            },
                            {
                                "Solucion": "Optimo individual Z2",
                                "Z1": sol.payoff_matrix["opt_Z2"]["Z1"],
                                "Z2": sol.payoff_matrix["opt_Z2"]["Z2"],
                                "Variables": str(sol.payoff_matrix["opt_Z2"]["x"]),
                            },
                        ]
                        st.dataframe(
                            pd.DataFrame(pm_data),
                            width="stretch",
                            column_config={
                                "Z1": st.column_config.NumberColumn(format="%.6g"),
                                "Z2": st.column_config.NumberColumn(format="%.6g"),
                            },
                        )

            else:
                st.success(f"Evaluacion multiobjetivo completada · {len(sol.weighted_runs)} corridas · Tiempo: {sol.timing.get('total_sec', 0)*1000:.1f} ms")

                subtab_res, subtab_pareto, subtab_sweep, subtab_plots, subtab_diag = st.tabs([
                    "📋 Resumen",
                    "🏆 Soluciones No Dominadas",
                    "🔢 Tabla de Ponderaciones",
                    "📈 Graficos",
                    "⚙️ Diagnostico",
                ])

                # Subtab 1: Resumen, Matriz de Pagos e Interpretacion
                with subtab_res:
                    n_nd = sum(1 for u in sol.unique_solutions if "no dominada" in u["pareto_status"].lower())
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    with col_m1:
                        st.metric("Corridas Evaluadas", len(sol.weighted_runs))
                    with col_m2:
                        st.metric("Soluciones Unicas", len(sol.unique_solutions))
                    with col_m3:
                        st.metric("Soluciones No Dominadas", n_nd)
                    with col_m4:
                        st.metric(
                            "Rango Delta Z1 / Delta Z2",
                            f"{_format_result_value(sol.normalization_ranges['Z1_range'])} / {_format_result_value(sol.normalization_ranges['Z2_range'])}",
                        )

                    col_pm, col_rng = st.columns([1.2, 1.0])
                    with col_pm:
                        with st.container(border=True):
                            st.subheader("Matriz de Pagos y Anclas de Normalizacion")
                            pm1 = sol.payoff_matrix.get("opt_Z1", {})
                            pm2 = sol.payoff_matrix.get("opt_Z2", {})
                            lbl1 = f"Extremo Z1 ({prob.objective1.sense.value.upper()})"
                            if pm1.get("selection_metadata", {}).get("applied"):
                                lbl1 += " [Representante eficiente seleccionado]"
                            lbl2 = f"Extremo Z2 ({prob.objective2.sense.value.upper()})"
                            if pm2.get("selection_metadata", {}).get("applied"):
                                lbl2 += " [Representante eficiente seleccionado]"
                            pm_data = [
                                {
                                    "Extremo": lbl1,
                                    "Z1": pm1.get("Z1"),
                                    "Z2": pm1.get("Z2"),
                                    "Variables": str(pm1.get("x", {})),
                                },
                                {
                                    "Extremo": lbl2,
                                    "Z1": pm2.get("Z1"),
                                    "Z2": pm2.get("Z2"),
                                    "Variables": str(pm2.get("x", {})),
                                },
                            ]
                            st.dataframe(
                                pd.DataFrame(pm_data),
                                width="stretch",
                                column_config={
                                    "Z1": st.column_config.NumberColumn(format="%.6g"),
                                    "Z2": st.column_config.NumberColumn(format="%.6g"),
                                },
                            )

                    with col_rng:
                        with st.container(border=True):
                            st.subheader("Rangos de Normalizacion")
                            nr = sol.normalization_ranges
                            r_data = [
                                {"Objetivo": "Z1", "Minimo": nr["Z1_min"], "Maximo": nr["Z1_max"], "Rango (Delta Z)": nr["Z1_range"]},
                                {"Objetivo": "Z2", "Minimo": nr["Z2_min"], "Maximo": nr["Z2_max"], "Rango (Delta Z)": nr["Z2_range"]},
                            ]
                            st.dataframe(
                                pd.DataFrame(r_data),
                                width="stretch",
                                column_config={
                                    "Minimo": st.column_config.NumberColumn(format="%.6g"),
                                    "Maximo": st.column_config.NumberColumn(format="%.6g"),
                                    "Rango (Delta Z)": st.column_config.NumberColumn(format="%.6g"),
                                },
                            )

                    # Interpretacion automatica multiobjetivo
                    with st.container(border=True):
                        st.subheader("💡 Interpretacion Base del Modelo Multiobjetivo")
                        bio_bullets = interpret_biobjective_solution(prob, sol)
                        for b in bio_bullets:
                            st.markdown(f"- {b}")

                # Subtab 2: Soluciones No Dominadas
                with subtab_pareto:
                    st.caption(
                        "**Nota metodologica:** La clasificacion se realiza exclusivamente sobre el conjunto de soluciones obtenidas "
                        "en el barrido ejecutado. No implica la generacion de toda la frontera de Pareto continua."
                    )
                    unique_rows = []
                    for u in sol.unique_solutions:
                        ws_str = ", ".join(f"({w['alpha1']:.2f}, {w['alpha2']:.2f})" for w in u["generated_by_weights"])
                        row_u = {
                            "ID": u["id"],
                            "Z1": u["Z1"],
                            "Z2": u["Z2"],
                            "Veces Obtenida": u["count"],
                            "Ponderaciones Generadoras": ws_str,
                            "Clasificacion": u["pareto_status"],
                        }
                        for v in prob.variables:
                            row_u[v] = u["x"].get(v, 0.0)
                        unique_rows.append(row_u)

                    df_unique = pd.DataFrame(unique_rows)
                    col_cfg_unique = {
                        "Z1": st.column_config.NumberColumn(format="%.6g"),
                        "Z2": st.column_config.NumberColumn(format="%.6g"),
                        "Veces Obtenida": st.column_config.NumberColumn(format="%d"),
                    }
                    for v in prob.variables:
                        col_cfg_unique[v] = st.column_config.NumberColumn(format="%.6g")

                    st.dataframe(df_unique, width="stretch", column_config=col_cfg_unique)

                    st.markdown("#### Detalle de Soluciones Repetidas")
                    for u in sol.unique_solutions:
                        with st.container(border=True):
                            vars_str = ", ".join(f"{v} = {_format_result_value(u['x'].get(v, 0.0))}" for v in prob.variables)
                            weights_str = " | ".join(f"α = ({w['alpha1']:.2f}, {w['alpha2']:.2f})" for w in u["generated_by_weights"])
                            st.markdown(
                                f"**Solucion {u['id']}** ({u['pareto_status']}) · "
                                f"**Z = ({_format_result_value(u['Z1'])}, {_format_result_value(u['Z2'])})** · {vars_str}"
                            )
                            st.caption(f"Generada por {u['count']} ponderacion(es): {weights_str}")

                # Subtab 3: Tabla de Ponderaciones
                with subtab_sweep:
                    runs_data = []
                    for r in sol.weighted_runs:
                        row_dict = {
                            "Corrida": r["run_index"],
                            "alpha1": r["alpha1"],
                            "alpha2": r["alpha2"],
                        }
                        for v in prob.variables:
                            row_dict[v] = r["x"].get(v, None) if r["x"] else None
                        row_dict["Z1"] = r["Z1"]
                        row_dict["Z2"] = r["Z2"]
                        row_dict["N1"] = r["N1"]
                        row_dict["N2"] = r["N2"]
                        row_dict["W"] = r["W"]
                        row_dict["Estado"] = r["status"]
                        runs_data.append(row_dict)

                    df_sweep = pd.DataFrame(runs_data)
                    col_cfg_sweep = {
                        "alpha1": st.column_config.NumberColumn(format="%.2f"),
                        "alpha2": st.column_config.NumberColumn(format="%.2f"),
                        "Z1": st.column_config.NumberColumn(format="%.6g"),
                        "Z2": st.column_config.NumberColumn(format="%.6g"),
                        "N1": st.column_config.NumberColumn(format="%.6g"),
                        "N2": st.column_config.NumberColumn(format="%.6g"),
                        "W": st.column_config.NumberColumn(format="%.6g"),
                    }
                    for v in prob.variables:
                        col_cfg_sweep[v] = st.column_config.NumberColumn(format="%.6g")

                    st.dataframe(df_sweep, width="stretch", column_config=col_cfg_sweep)

                # Subtab 4: Graficos
                with subtab_plots:
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        with st.container(border=True):
                            fig_obj = plot_objective_space_2d(
                                sol.unique_solutions,
                                z1_name="Z1",
                                z2_name="Z2",
                                z1_sense=prob.objective1.sense,
                                z2_sense=prob.objective2.sense,
                            )
                            st.pyplot(fig_obj)

                    with col_g2:
                        with st.container(border=True):
                            fig_runs = plot_multiobjective_runs(sol.weighted_runs, z1_name="Z1", z2_name="Z2")
                            st.pyplot(fig_runs)

                    if len(prob.variables) == 2:
                        with st.container(border=True):
                            fig_rf = plot_feasible_region_2d(
                                prob,
                                solutions=sol.unique_solutions,
                                title="Espacio de variables: Region factible y soluciones",
                            )
                            if fig_rf:
                                st.pyplot(fig_rf)
                    else:
                        st.info("ℹ️ El grafico de region factible 2D en el espacio de variables aplica para modelos con exactamente dos variables.")

                # Subtab 5: Diagnostico
                with subtab_diag:
                    with st.container(border=True):
                        st.subheader("🔍 Detalle de Anclas de la Matriz de Pagos")
                        for k, name, s_obj in [("Z1_opt", "Z1", prob.objective1), ("Z2_opt", "Z2", prob.objective2)]:
                            opt_data = sol.individual_optima.get(k, {})
                            if isinstance(opt_data, dict):
                                selection = opt_data.get("selection_metadata", {})
                                prim_val = opt_data.get("primary_optimal_value")
                                z1_val = opt_data.get("Z1")
                                z2_val = opt_data.get("Z2")
                                st.markdown(f"**Extremo para {name} ({s_obj.sense.value.upper()}):**")
                                st.markdown(
                                    f"- Óptimo principal aislado: `{_format_result_value(prim_val)}`\n"
                                    f"- Selección secundaria de representante: `{'Aplicada' if selection.get('applied') else 'No aplicada'}`\n"
                                    f"- Valor primario preservado: `{'Sí' if selection.get('primary_value_preserved') else 'No verificado'}`\n"
                                    f"- Punto eficiente resultante: $Z_1 = {_format_result_value(z1_val)}, \\quad Z_2 = {_format_result_value(z2_val)}$"
                                )
                        st.caption(
                            "La selección de representantes pertenece al preprocesamiento de la matriz de pagos. "
                            "No sustituye las corridas ponderadas ni demuestra unicidad o multiplicidad."
                        )
                    with st.container(border=True):
                        st.subheader("⏱️ Tiempos de Resolucion (Pyomo + HiGHS)")
                        st.json(sol.timing)
