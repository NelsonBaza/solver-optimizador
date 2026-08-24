"""
Aplicacion Web Streamlit — Suite de Optimizacion Matematica (MVP LP).
Formulacion, resolucion, persistencia y analisis de Programacion Lineal Continua (Monoobjetivo y Biobjetivo).
Soporta hasta 100 variables, nombres personalizados, persistencia JSON y carga atomica.
Backend matematico: Pyomo + HiGHS (APPSI).
"""

import sys
import os
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


def _clear_widget_keys():
    """Limpia las claves de widgets para evitar desincronizacion con session_state."""
    prefixes = ("mono_c_", "bio_c1_", "bio_c2_", "var_name_")
    exact_keys = [
        "radio_prob_type",
        "num_vars_input",
        "mono_sense_select",
        "bio_sense1_select",
        "bio_sense2_select",
        "mo_mode_radio",
        "num_weights_slider",
        "custom_a1_slider",
        "model_name_input",
        "model_desc_input",
    ]
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefixes) or k in exact_keys:
            del st.session_state[k]


def _new_model():
    _clear_widget_keys()
    st.session_state.editor_version += 1
    st.session_state.model_name = "Nuevo Modelo"
    st.session_state.model_desc = ""
    st.session_state.problem_type = "Monoobjetivo"
    st.session_state.num_vars = 2
    st.session_state.var_names = ["x1", "x2"]
    st.session_state.obj_sense = "Maximizar"
    st.session_state.obj_coeffs = {"x1": 1.0, "x2": 1.0}
    st.session_state.obj1_sense = "Maximizar"
    st.session_state.obj1_coeffs = {"x1": 1.0, "x2": 1.0}
    st.session_state.obj2_sense = "Maximizar"
    st.session_state.obj2_coeffs = {"x1": 1.0, "x2": 1.0}
    st.session_state.constraints_data = [
        {"name": "Restriccion 1", "x1": 1.0, "x2": 1.0, "operator": "<=", "rhs": 10.0}
    ]
    st.session_state.last_solution = None
    st.session_state.last_solution_type = None
    st.session_state.last_solution_problem = None
    st.session_state.last_solution_signature = None
    st.session_state.example_msg = "Nuevo modelo en blanco iniciado."


def _load_model_dict(data: Dict[str, Any]):
    """Carga atómica completa del modelo desde la estructura deserializada."""
    _clear_widget_keys()
    st.session_state.editor_version += 1
    meta_name = data.get("metadata", {}).get("name", "Modelo Importado")
    st.session_state.model_name = meta_name
    st.session_state.model_desc = data.get("metadata", {}).get("description", "")
    st.session_state.problem_type = data["problem_type"]
    st.session_state.num_vars = data["num_vars"]
    st.session_state.var_names = list(data["var_names"])
    st.session_state.constraints_data = data["constraints_data"]

    if data["problem_type"] == "Monoobjetivo":
        st.session_state.obj_sense = data["obj_sense"]
        st.session_state.obj_coeffs = data["obj_coeffs"]
        st.session_state.obj1_sense = "Maximizar"
        st.session_state.obj1_coeffs = {v: 0.0 for v in data["var_names"]}
        st.session_state.obj2_sense = "Maximizar"
        st.session_state.obj2_coeffs = {v: 0.0 for v in data["var_names"]}
    else:
        st.session_state.obj1_sense = data["obj1_sense"]
        st.session_state.obj1_coeffs = data["obj1_coeffs"]
        st.session_state.obj2_sense = data["obj2_sense"]
        st.session_state.obj2_coeffs = data["obj2_coeffs"]
        st.session_state.mo_mode = data.get("mo_mode", "Barrido automatico")
        st.session_state.num_weights = data.get("num_weights", 6)
        st.session_state.custom_a1 = data.get("custom_a1", 0.5)
        st.session_state.obj_sense = "Maximizar"
        st.session_state.obj_coeffs = {v: 0.0 for v in data["var_names"]}

    st.session_state.last_solution = None
    st.session_state.last_solution_type = None
    st.session_state.last_solution_problem = None
    st.session_state.last_solution_signature = None

    n_v = data["num_vars"]
    n_c = len(data["constraints_data"])
    p_t = data["problem_type"]
    s_info = data["obj_sense"] if p_t == "Monoobjetivo" else f"Z1:{data['obj1_sense']} / Z2:{data['obj2_sense']}"
    st.session_state.example_msg = f"✅ Modelo '{meta_name}' cargado correctamente ({n_v} variables · {n_c} restricciones · {p_t} · {s_info})."


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

        # Metadata del modelo
        st.session_state.model_name = st.text_input(
            "Nombre del modelo:",
            value=st.session_state.model_name,
            key="model_name_input",
        )
        st.session_state.model_desc = st.text_area(
            "Descripcion / Notas:",
            value=st.session_state.model_desc,
            height=60,
            key="model_desc_input",
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
            key="radio_prob_type",
        )
        st.session_state.problem_type = prob_type

        st.subheader("2. Variables de Decision")
        st.caption("Variables continuas no negativas ($x_i \\ge 0$). Soporta hasta 100 variables.")
        num_vars = st.number_input(
            "Cantidad de variables (1..100):",
            min_value=1,
            max_value=100,
            value=int(st.session_state.num_vars),
            step=1,
            key="num_vars_input",
        )
        
        # Sincronizar longitud de nombres al cambiar num_vars
        old_var_names = list(st.session_state.var_names)
        if int(num_vars) != len(old_var_names):
            st.session_state.num_vars = int(num_vars)
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
            st.session_state.var_names = old_var_names

        # Editor de nombres de variables
        st.markdown("**Nombres de variables:**")
        df_vars_data = [{"#": i+1, "Nombre": name} for i, name in enumerate(st.session_state.var_names)]
        edited_vars_df = st.data_editor(
            pd.DataFrame(df_vars_data),
            disabled=["#"],
            hide_index=True,
            width="stretch",
            column_config={
                "#": st.column_config.NumberColumn("#", width="small"),
                "Nombre": st.column_config.TextColumn("Nombre Variable", width="medium", required=True),
            },
            key=f"var_names_editor_{st.session_state.editor_version}",
        )

        # Extraer y validar nombres editados
        candidate_names = [str(r["Nombre"]).strip() for _, r in edited_vars_df.iterrows()]
        has_var_name_error = False
        if any(not name for name in candidate_names):
            st.error("Los nombres de las variables no pueden estar vacios.")
            has_var_name_error = True
        elif len(set(candidate_names)) != len(candidate_names):
            st.error("Los nombres de las variables deben ser unicos.")
            has_var_name_error = True
        elif candidate_names != st.session_state.var_names:
            # Migrar coeficientes por posicion
            old_names = list(st.session_state.var_names)
            new_names = list(candidate_names)
            
            # Monoobjetivo
            new_mono = {new_names[i]: float(st.session_state.obj_coeffs.get(old_names[i], 0.0)) for i in range(len(new_names))}
            st.session_state.obj_coeffs = new_mono
            
            # Biobjetivo
            new_bio1 = {new_names[i]: float(st.session_state.obj1_coeffs.get(old_names[i], 0.0)) for i in range(len(new_names))}
            new_bio2 = {new_names[i]: float(st.session_state.obj2_coeffs.get(old_names[i], 0.0)) for i in range(len(new_names))}
            st.session_state.obj1_coeffs = new_bio1
            st.session_state.obj2_coeffs = new_bio2

            # Restricciones
            new_cons_data = []
            for row in st.session_state.constraints_data:
                new_row = {"name": row.get("name", "Restriccion"), "operator": row.get("operator", "<="), "rhs": row.get("rhs", 0.0)}
                for i in range(len(new_names)):
                    old_k = old_names[i] if i < len(old_names) else f"x{i+1}"
                    new_k = new_names[i]
                    new_row[new_k] = float(row.get(old_k, 0.0))
                new_cons_data.append(new_row)
            st.session_state.constraints_data = new_cons_data
            st.session_state.var_names = new_names
            st.session_state.editor_version += 1
            st.rerun()

        var_names = list(st.session_state.var_names)

    # 4. Metodologia / Ayuda
    with st.expander("ℹ️ Metodologia Multiobjetivo"):
        st.markdown(
            """
            * **Ponderaciones:** Combina los dos objetivos mediante pesos $(\\alpha_1, \\alpha_2)$ donde $\\alpha_1 + \\alpha_2 = 1$.
            * **Normalizacion por Rangos:** Utiliza la matriz de pagos:
              $$\\Delta Z_k = Z_{k,\\max} - Z_{k,\\min}$$
              $$W = \\alpha_1 \\frac{\\pm Z_1}{\\Delta Z_1} + \\alpha_2 \\frac{\\pm Z_2}{\\Delta Z_2}$$
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
                        key="mono_sense_select",
                    )
                    st.session_state.obj_sense = sense_str

                st.markdown("**Coeficientes lineales del objetivo:**")
                st.caption("💡 **Nota:** Use punto (.) como separador decimal (ejemplo: 2.4525).")

                # Editor tabular escalable para coeficientes
                obj_df_data = [
                    {"Variable": v, "Coeficiente": float(st.session_state.obj_coeffs.get(v, 1.0 if idx < 2 else 0.0))}
                    for idx, v in enumerate(var_names)
                ]
                edited_obj_df = st.data_editor(
                    pd.DataFrame(obj_df_data),
                    disabled=["Variable"],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Variable": st.column_config.TextColumn("Variable", width="medium"),
                        "Coeficiente": st.column_config.NumberColumn("Coeficiente", format="%.4f", required=True),
                    },
                    key=f"mono_obj_editor_{st.session_state.editor_version}",
                )
                obj_coeffs = {str(r["Variable"]): float(r["Coeficiente"]) for _, r in edited_obj_df.iterrows()}
                st.session_state.obj_coeffs = obj_coeffs

            else:  # Biobjetivo
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    sense1_idx = 0 if st.session_state.obj1_sense == "Maximizar" else 1
                    sense1_str = st.selectbox(
                        "Sentido $Z_1$:",
                        ["Maximizar", "Minimizar"],
                        index=sense1_idx,
                        key="bio_sense1_select",
                    )
                    st.session_state.obj1_sense = sense1_str
                with col_s2:
                    sense2_idx = 0 if st.session_state.obj2_sense == "Maximizar" else 1
                    sense2_str = st.selectbox(
                        "Sentido $Z_2$:",
                        ["Maximizar", "Minimizar"],
                        index=sense2_idx,
                        key="bio_sense2_select",
                    )
                    st.session_state.obj2_sense = sense2_str

                st.markdown("**Coeficientes de ambos objetivos:**")
                st.caption("💡 **Nota:** Use punto (.) como separador decimal (ejemplo: 2.4525).")

                bio_df_data = [
                    {
                        "Variable": v,
                        "Coeficiente Z1": float(st.session_state.obj1_coeffs.get(v, 10.0 if idx == 0 else (3.0 if idx == 1 else 0.0))),
                        "Coeficiente Z2": float(st.session_state.obj2_coeffs.get(v, 0.8 if idx == 0 else (1.3 if idx == 1 else 0.0))),
                    }
                    for idx, v in enumerate(var_names)
                ]
                edited_bio_df = st.data_editor(
                    pd.DataFrame(bio_df_data),
                    disabled=["Variable"],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Variable": st.column_config.TextColumn("Variable", width="medium"),
                        "Coeficiente Z1": st.column_config.NumberColumn(f"Coef. Z1 ({st.session_state.obj1_sense[:3].upper()})", format="%.4f", required=True),
                        "Coeficiente Z2": st.column_config.NumberColumn(f"Coef. Z2 ({st.session_state.obj2_sense[:3].upper()})", format="%.4f", required=True),
                    },
                    key=f"bio_obj_editor_{st.session_state.editor_version}",
                )
                obj1_coeffs = {str(r["Variable"]): float(r["Coeficiente Z1"]) for _, r in edited_bio_df.iterrows()}
                obj2_coeffs = {str(r["Variable"]): float(r["Coeficiente Z2"]) for _, r in edited_bio_df.iterrows()}
                st.session_state.obj1_coeffs = obj1_coeffs
                st.session_state.obj2_coeffs = obj2_coeffs

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
                    key="mo_mode_radio",
                )
                st.session_state.mo_mode = mo_mode

                if mo_mode == "Barrido automatico":
                    num_weights = st.slider(
                        "Numero de combinaciones $(\\alpha_1, \\alpha_2)$:",
                        min_value=2,
                        max_value=21,
                        value=int(st.session_state.num_weights),
                        step=1,
                        key="num_weights_slider",
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
                        key="custom_a1_slider",
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
            st.caption("Añada, edite o elimine restricciones lineales. Use punto (.) como separador decimal:")

            current_data = []
            for idx, c_dict in enumerate(st.session_state.constraints_data):
                row = {
                    "Nombre": c_dict.get("name", f"Restriccion {idx+1}"),
                    "Operador": c_dict.get("operator", "<="),
                    "RHS": float(c_dict.get("rhs", 10.0)),
                }
                for v in var_names:
                    row[v] = float(c_dict.get(v, 0.0))
                current_data.append(row)

            df_constraints = pd.DataFrame(current_data)
            column_order = ["Nombre"] + var_names + ["Operador", "RHS"]
            col_config = {
                "Nombre": st.column_config.TextColumn("Nombre", required=True),
                "Operador": st.column_config.SelectboxColumn("Operador", options=["<=", ">=", "="], required=True),
                "RHS": st.column_config.NumberColumn("Lado Derecho (RHS)", required=True, format="%.4f"),
            }
            for v in var_names:
                col_config[v] = st.column_config.NumberColumn(f"{v}", required=True, format="%.4f")

            edited_df = st.data_editor(
                df_constraints[column_order],
                num_rows="dynamic",
                width="stretch",
                column_config=col_config,
                key=f"constraints_editor_{st.session_state.editor_version}",
            )

        # Vista Previa Matematica
        with st.container(border=True):
            st.subheader("👁️ Vista Previa Matematica del Modelo")
            if st.session_state.problem_type == "Monoobjetivo":
                s_txt = st.session_state.obj_sense[:3].upper()
                terms_z = [f"{c:g} {v}" for v, c in st.session_state.obj_coeffs.items() if abs(c) > 1e-7]
                expr_z = " + ".join(terms_z).replace("+ -", "- ") if terms_z else "0"
                st.latex(f"\\text{{{s_txt}}}\\quad Z = {expr_z}")
            else:
                s1_txt = st.session_state.obj1_sense[:3].upper()
                terms_z1 = [f"{c:g} {v}" for v, c in st.session_state.obj1_coeffs.items() if abs(c) > 1e-7]
                expr_z1 = " + ".join(terms_z1).replace("+ -", "- ") if terms_z1 else "0"

                s2_txt = st.session_state.obj2_sense[:3].upper()
                terms_z2 = [f"{c:g} {v}" for v, c in st.session_state.obj2_coeffs.items() if abs(c) > 1e-7]
                expr_z2 = " + ".join(terms_z2).replace("+ -", "- ") if terms_z2 else "0"

                st.latex(f"\\text{{{s1_txt}}}\\quad Z_1 = {expr_z1}")
                st.latex(f"\\text{{{s2_txt}}}\\quad Z_2 = {expr_z2}")

            # Restricciones en LaTeX (mostrar hasta 12 para mantener rendimiento)
            latex_cons = []
            if not edited_df.empty:
                for _, r in edited_df.head(15).iterrows():
                    c_terms = [f"{r[v]:g} {v}" for v in var_names if abs(r.get(v, 0.0)) > 1e-7]
                    lhs_str = " + ".join(c_terms).replace("+ -", "- ") if c_terms else "0"
                    op_sym = "\\le" if r.get("Operador") == "<=" else ("\\ge" if r.get("Operador") == ">=" else "=")
                    rhs_val = r.get("RHS", 0.0)
                    latex_cons.append(f"{lhs_str} {op_sym} {rhs_val:g}")

            vars_nonneg = ", ".join(var_names[:6]) + (", \\dots" if len(var_names) > 6 else "") + " \\ge 0"
            all_lines = "\\\\\n".join(latex_cons + [vars_nonneg])
            st.latex(f"\\text{{sujeto a:}}\n\\begin{{cases}}\n{all_lines}\n\\end{{cases}}")

    # Normalizar restricciones de forma canonica
    raw_ui_records = edited_df.to_dict(orient="records") if not edited_df.empty else []
    try:
        canonical_constraints = normalize_constraints(raw_ui_records, var_names) if raw_ui_records else []
        cons_norm_error = None
    except Exception as e:
        canonical_constraints = []
        cons_norm_error = str(e)

    # -----------------------------------------------------------------------
    # Boton de Resolucion y Descarga
    # -----------------------------------------------------------------------
    st.markdown("---")
    if has_var_name_error:
        st.error("⚠️ **No es posible resolver ni descargar el modelo:** Existen errores en los nombres de las variables (nombres vacios o duplicados).")
    elif cons_norm_error:
        st.error(f"⚠️ **No es posible resolver ni descargar el modelo:** {cons_norm_error}")
    elif not canonical_constraints:
        st.warning("⚠️ **No es posible resolver ni descargar el modelo:** Ingrese al menos una restriccion lineal valida en la tabla.")

    col_act1, col_act2 = st.columns([2, 1])
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
        constraints_list = [
            LinearConstraint(
                name=c["name"],
                coefficients=c["coefficients"],
                operator=Operator.from_str(c["operator"]),
                rhs=c["rhs"],
            )
            for c in canonical_constraints
        ]

        if st.session_state.problem_type == "Monoobjetivo":
            sense_enum = Sense.from_str(st.session_state.obj_sense)
            problem_mono = LPProblem(
                variables=var_names,
                objective=LinearObjective("Z", sense_enum, st.session_state.obj_coeffs),
                constraints=constraints_list,
            )
            with st.spinner("Resolviendo el modelo con Pyomo + HiGHS..."):
                sol_mono = solve_lp(problem_mono)
            st.session_state.last_solution = sol_mono
            st.session_state.last_solution_type = "Monoobjetivo"
            st.session_state.last_solution_problem = problem_mono
            st.session_state.last_solution_signature = current_model_signature

        else:
            sense1_enum = Sense.from_str(st.session_state.obj1_sense)
            sense2_enum = Sense.from_str(st.session_state.obj2_sense)
            problem_bio = BiobjectiveProblem(
                variables=var_names,
                objective1=LinearObjective("Z1", sense1_enum, st.session_state.obj1_coeffs),
                objective2=LinearObjective("Z2", sense2_enum, st.session_state.obj2_coeffs),
                constraints=constraints_list,
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
                "⚠️ **Resultados desactualizados:** El modelo fue modificado después de la última resolución. "
                "Pulse **'🚀 Resolver Modelo con Pyomo + HiGHS'** en la pestaña de formulación para actualizar los resultados."
            )
            st.caption("Estado del modelo: ⚠️ **Resultados pendientes de recalcular** (mostrando resultados de la última resolución calculada)")
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
                        st.metric(label="Valor Optimo Z*", value=f"{sol.objective_value:.4f}")
                    for i, v in enumerate(prob.variables[:n_display_vars]):
                        with m_cols[i + 1]:
                            st.metric(label=f"{v}*", value=f"{sol.variable_values[v]:.4f}")
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
                                "LHS Evaluado": round(cr.lhs, 4),
                                "Operador": cr.operator,
                                "RHS": round(cr.rhs, 4),
                                "Holgura": round(cr.slack, 4),
                                "Estado": "Activa (0.00)" if cr.is_active else "Con holgura",
                            })
                        df_res_con = pd.DataFrame(con_rows)
                        st.dataframe(
                            df_res_con,
                            width="stretch",
                            column_config={
                                "LHS Evaluado": st.column_config.NumberColumn(format="%.4f"),
                                "RHS": st.column_config.NumberColumn(format="%.4f"),
                                "Holgura": st.column_config.NumberColumn(format="%.4f"),
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
                        st.dataframe(pd.DataFrame(pm_data), width="stretch")

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
                        st.metric("Rango Delta Z1 / Delta Z2", f"{sol.normalization_ranges['Z1_range']:.1f} / {sol.normalization_ranges['Z2_range']:.1f}")

                    col_pm, col_rng = st.columns([1.2, 1.0])
                    with col_pm:
                        with st.container(border=True):
                            st.subheader("Matriz de Pagos (Payoff Matrix)")
                            pm_data = [
                                {
                                    "Solucion Individual": f"Optimo individual Z1 ({prob.objective1.sense.value.upper()})",
                                    "Z1": sol.payoff_matrix["opt_Z1"]["Z1"],
                                    "Z2": sol.payoff_matrix["opt_Z1"]["Z2"],
                                    "Variables": str(sol.payoff_matrix["opt_Z1"]["x"]),
                                },
                                {
                                    "Solucion Individual": f"Optimo individual Z2 ({prob.objective2.sense.value.upper()})",
                                    "Z1": sol.payoff_matrix["opt_Z2"]["Z1"],
                                    "Z2": sol.payoff_matrix["opt_Z2"]["Z2"],
                                    "Variables": str(sol.payoff_matrix["opt_Z2"]["x"]),
                                },
                            ]
                            st.dataframe(
                                pd.DataFrame(pm_data),
                                width="stretch",
                                column_config={
                                    "Z1": st.column_config.NumberColumn(format="%.2f"),
                                    "Z2": st.column_config.NumberColumn(format="%.2f"),
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
                                    "Minimo": st.column_config.NumberColumn(format="%.2f"),
                                    "Maximo": st.column_config.NumberColumn(format="%.2f"),
                                    "Rango (Delta Z)": st.column_config.NumberColumn(format="%.2f"),
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
                        "Z1": st.column_config.NumberColumn(format="%.2f"),
                        "Z2": st.column_config.NumberColumn(format="%.2f"),
                        "Veces Obtenida": st.column_config.NumberColumn(format="%d"),
                    }
                    for v in prob.variables:
                        col_cfg_unique[v] = st.column_config.NumberColumn(format="%.2f")

                    st.dataframe(df_unique, width="stretch", column_config=col_cfg_unique)

                    st.markdown("#### Detalle de Soluciones Repetidas")
                    for u in sol.unique_solutions:
                        with st.container(border=True):
                            vars_str = ", ".join(f"{v} = {u['x'].get(v, 0.0):.2f}" for v in prob.variables)
                            weights_str = " | ".join(f"α = ({w['alpha1']:.2f}, {w['alpha2']:.2f})" for w in u["generated_by_weights"])
                            st.markdown(f"**Solucion {u['id']}** ({u['pareto_status']}) · **Z = ({u['Z1']:.2f}, {u['Z2']:.2f})** · {vars_str}")
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
                        row_dict["W"] = r["W"]
                        row_dict["Estado"] = r["status"]
                        runs_data.append(row_dict)

                    df_sweep = pd.DataFrame(runs_data)
                    col_cfg_sweep = {
                        "alpha1": st.column_config.NumberColumn(format="%.2f"),
                        "alpha2": st.column_config.NumberColumn(format="%.2f"),
                        "Z1": st.column_config.NumberColumn(format="%.2f"),
                        "Z2": st.column_config.NumberColumn(format="%.2f"),
                        "W": st.column_config.NumberColumn(format="%.4f"),
                    }
                    for v in prob.variables:
                        col_cfg_sweep[v] = st.column_config.NumberColumn(format="%.2f")

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
                        st.subheader("Tiempos de Resolucion (Pyomo + HiGHS)")
                        st.json(sol.timing)
