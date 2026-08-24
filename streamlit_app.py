"""
Aplicacion Web Streamlit — Suite de Optimizacion Matematica (MVP LP).
Formulacion, resolucion y analisis de Programacion Lineal Continua (Monoobjetivo y Biobjetivo).
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
from solver_optimizador.plotting import (
    plot_feasible_region_2d,
    plot_objective_space_2d,
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
    keys_to_clear = [
        "radio_prob_type",
        "num_vars_input",
        "mono_sense_select",
        "bio_sense1_select",
        "bio_sense2_select",
        "mo_mode_radio",
        "num_weights_slider",
        "custom_a1_slider",
    ]
    for k in list(st.session_state.keys()):
        if k.startswith("mono_c_") or k.startswith("bio_c1_") or k.startswith("bio_c2_") or k in keys_to_clear:
            del st.session_state[k]


def _load_example_mono():
    _clear_widget_keys()
    st.session_state.editor_version += 1
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
    st.session_state.last_solution_signature = None
    st.session_state.example_msg = "Ejemplo 1 (Monoobjetivo) cargado exitosamente."


def _load_example_bio():
    _clear_widget_keys()
    st.session_state.editor_version += 1
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
    st.session_state.last_solution_signature = None
    st.session_state.example_msg = "Benchmark A (Biobjetivo) cargado exitosamente."


_init_session_state()


# ---------------------------------------------------------------------------
# Barra Lateral (Configuracion del Problema)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuracion")
    st.caption("Backend: **Pyomo 6.10.1 + HiGHS 1.15.1**")

    # 1. Ejemplos Precargados
    with st.container(border=True):
        st.subheader("📚 Ejemplos Academicos")
        st.caption("Cargue un ejemplo predefinido para explorar la herramienta o modifiquelo para formular su propio problema.")
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            if st.button("Ejemplo 1 (Mono)", help="MAX Z = 3x1 + 2x2", width="stretch"):
                _load_example_mono()
                st.rerun()
        with col_ex2:
            if st.button("Benchmark A (Bio)", help="Benchmark A: MAX Z1, MAX Z2", width="stretch"):
                _load_example_bio()
                st.rerun()

    # 2. Modalidad y Variables
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
        st.caption("Variables continuas no negativas ($x_i \\ge 0$).")
        num_vars = st.number_input(
            "Cantidad de variables:",
            min_value=1,
            max_value=10,
            value=int(st.session_state.num_vars),
            step=1,
            key="num_vars_input",
        )
        st.session_state.num_vars = int(num_vars)

        var_names = [f"x{i+1}" for i in range(num_vars)]
        st.session_state.var_names = var_names
        st.info(f"Variables activas: `{'`, `'.join(var_names)}`")

    # 3. Metodologia / Ayuda
    with st.expander("ℹ️ Metodologia Multiobjetivo"):
        st.markdown(
            """
            * **Ponderaciones:** Combina los dos objetivos mediante pesos $(\\alpha_1, \\alpha_2)$ donde $\\alpha_1 + \\alpha_2 = 1$. Un peso mayor indica mayor importancia relativa.
            * **Normalizacion por Rangos:** Utiliza la matriz de pagos:
              $$\\Delta Z_k = Z_{k,\\max} - Z_{k,\\min}$$
              $$W = \\alpha_1 \\frac{Z_1}{\\Delta Z_1} + \\alpha_2 \\frac{Z_2}{\\Delta Z_2}$$
              *(con signo negativo para objetivos de minimizacion).*
            * **Rigor:** Las soluciones corresponden a las ponderaciones evaluadas y no necesariamente representan toda la frontera de Pareto continua.
            """
        )


# ---------------------------------------------------------------------------
# Encabezado Principal
# ---------------------------------------------------------------------------
st.title("📐 Suite de Optimizacion Matematica")
st.markdown(
    "Plataforma para formulacion, resolucion y analisis de **Programacion Lineal Continua** "
    "(Monoobjetivo y Biobjetivo mediante Ponderaciones Normalizadas)."
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

                st.markdown("**Coeficientes lineales:**")
                cols_c = st.columns(len(var_names))
                obj_coeffs = {}
                for i, v in enumerate(var_names):
                    with cols_c[i]:
                        default_val = float(st.session_state.obj_coeffs.get(v, 1.0))
                        val = st.number_input(
                            f"Coef. ${v}$:",
                            value=default_val,
                            step=1.0,
                            key=f"mono_c_{v}",
                        )
                        obj_coeffs[v] = val
                st.session_state.obj_coeffs = obj_coeffs

            else:  # Biobjetivo
                st.markdown("#### Objetivo 1 ($Z_1$)")
                col_s1, _ = st.columns([1, 2])
                with col_s1:
                    sense1_idx = 0 if st.session_state.obj1_sense == "Maximizar" else 1
                    sense1_str = st.selectbox(
                        "Sentido $Z_1$:",
                        ["Maximizar", "Minimizar"],
                        index=sense1_idx,
                        key="bio_sense1_select",
                    )
                    st.session_state.obj1_sense = sense1_str

                cols_c1 = st.columns(len(var_names))
                obj1_coeffs = {}
                for i, v in enumerate(var_names):
                    with cols_c1[i]:
                        default_val = float(st.session_state.obj1_coeffs.get(v, 1.0))
                        val = st.number_input(
                            f"Coef. ${v}$ ($Z_1$):",
                            value=default_val,
                            step=1.0,
                            key=f"bio_c1_{v}",
                        )
                        obj1_coeffs[v] = val
                st.session_state.obj1_coeffs = obj1_coeffs

                st.markdown("#### Objetivo 2 ($Z_2$)")
                col_s2, _ = st.columns([1, 2])
                with col_s2:
                    sense2_idx = 0 if st.session_state.obj2_sense == "Maximizar" else 1
                    sense2_str = st.selectbox(
                        "Sentido $Z_2$:",
                        ["Maximizar", "Minimizar"],
                        index=sense2_idx,
                        key="bio_sense2_select",
                    )
                    st.session_state.obj2_sense = sense2_str

                cols_c2 = st.columns(len(var_names))
                obj2_coeffs = {}
                for i, v in enumerate(var_names):
                    with cols_c2[i]:
                        default_val = float(st.session_state.obj2_coeffs.get(v, 1.0))
                        val = st.number_input(
                            f"Coef. ${v}$ ($Z_2$):",
                            value=default_val,
                            step=1.0,
                            key=f"bio_c2_{v}",
                        )
                        obj2_coeffs[v] = val
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
            st.caption("Añada, edite o elimine restricciones lineales en la tabla interactiva:")

            current_data = []
            for idx, c_dict in enumerate(st.session_state.constraints_data):
                row = {
                    "Nombre": c_dict.get("name", f"Restriccion {idx+1}"),
                    "Operador": c_dict.get("operator", "<="),
                    "RHS": float(c_dict.get("rhs", 10.0)),
                }
                for v in var_names:
                    row[v] = float(c_dict.get(v, 1.0 if v in ("x1", "x2") else 0.0))
                current_data.append(row)

            df_constraints = pd.DataFrame(current_data)
            column_order = ["Nombre"] + var_names + ["Operador", "RHS"]
            col_config = {
                "Nombre": st.column_config.TextColumn("Nombre", required=True),
                "Operador": st.column_config.SelectboxColumn("Operador", options=["<=", ">=", "="], required=True),
                "RHS": st.column_config.NumberColumn("Lado Derecho (RHS)", required=True, format="%.2f"),
            }
            for v in var_names:
                col_config[v] = st.column_config.NumberColumn(f"Coef. {v}", required=True, format="%.2f")

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

            # Restricciones en LaTeX
            latex_cons = []
            if not edited_df.empty:
                for _, r in edited_df.iterrows():
                    c_terms = [f"{r[v]:g} {v}" for v in var_names if abs(r.get(v, 0.0)) > 1e-7]
                    lhs_str = " + ".join(c_terms).replace("+ -", "- ") if c_terms else "0"
                    op_sym = "\\le" if r.get("Operador") == "<=" else ("\\ge" if r.get("Operador") == ">=" else "=")
                    rhs_val = r.get("RHS", 0.0)
                    latex_cons.append(f"{lhs_str} {op_sym} {rhs_val:g}")

            vars_nonneg = ", ".join(var_names) + " \\ge 0"
            all_lines = "\\\\\n".join(latex_cons + [vars_nonneg])
            st.latex(f"\\text{{sujeto a:}}\n\\begin{{cases}}\n{all_lines}\n\\end{{cases}}")

    # -----------------------------------------------------------------------
    # Boton de Resolucion
    # -----------------------------------------------------------------------
    st.markdown("---")
    btn_solve = st.button("🚀 Resolver Modelo con Pyomo + HiGHS", type="primary", width="stretch")


# ---------------------------------------------------------------------------
# Calculo de la Firma del Modelo Actual
# ---------------------------------------------------------------------------
constraints_records = edited_df.to_dict(orient="records") if not edited_df.empty else []
current_model_signature = build_model_signature(
    problem_type=st.session_state.problem_type,
    var_names=var_names,
    obj_sense=st.session_state.obj_sense,
    obj_coeffs=st.session_state.obj_coeffs,
    obj1_sense=st.session_state.obj1_sense,
    obj1_coeffs=st.session_state.obj1_coeffs,
    obj2_sense=st.session_state.obj2_sense,
    obj2_coeffs=st.session_state.obj2_coeffs,
    constraints_data=constraints_records,
    mo_mode=st.session_state.mo_mode,
    num_weights=st.session_state.num_weights,
    custom_a1=st.session_state.custom_a1,
)


# ===========================================================================
# LOGICA DE RESOLUCION
# ===========================================================================
if btn_solve:
    constraints_list: List[LinearConstraint] = []
    has_validation_error = False

    if edited_df.empty:
        st.error("El problema debe contener al menos una restriccion lineal.")
        has_validation_error = True
    else:
        for idx, row in edited_df.iterrows():
            c_name = str(row.get("Nombre", f"Restriccion_{idx+1}")).strip()
            if not c_name:
                c_name = f"R_{idx+1}"
            op_str = str(row.get("Operador", "<=")).strip()
            try:
                op_enum = Operator.from_str(op_str)
            except Exception as e:
                st.error(f"Error en la fila {idx+1}: {e}")
                has_validation_error = True
                break

            rhs_val = row.get("RHS")
            if not is_finite_number(rhs_val):
                st.error(f"La restriccion '{c_name}' no tiene un valor numerico finito en el lado derecho (RHS): {rhs_val}")
                has_validation_error = True
                break

            c_coeffs = {}
            for v in var_names:
                c_val = row.get(v)
                if not is_finite_number(c_val):
                    st.error(f"El coeficiente de '{v}' en la restriccion '{c_name}' no es un numero finito: {c_val}")
                    has_validation_error = True
                    break
                c_coeffs[v] = float(c_val)

            if has_validation_error:
                break

            constraints_list.append(
                LinearConstraint(
                    name=c_name,
                    coefficients=c_coeffs,
                    operator=op_enum,
                    rhs=float(rhs_val),
                )
            )

    if not has_validation_error:
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
                    m_cols = st.columns(1 + len(prob.variables))
                    with m_cols[0]:
                        st.metric(label="Valor Optimo Z*", value=f"{sol.objective_value:.4f}")
                    for i, v in enumerate(prob.variables):
                        with m_cols[i + 1]:
                            st.metric(label=f"Variable {v}*", value=f"{sol.variable_values[v]:.4f}")

                col_tbl, col_plot = st.columns([1.2, 1.0])

                with col_tbl:
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
                                "Estado": "Activa" if cr.is_active else "Con holgura",
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

                with col_plot:
                    with st.container(border=True):
                        st.subheader("🗺️ Espacio de Variables (2D)")
                        if len(prob.variables) == 2:
                            fig_feas = plot_feasible_region_2d(
                                prob,
                                solutions=[{"id": "Optimo", "x": sol.variable_values}],
                                title="Espacio de variables: Region factible y vertice optimo",
                            )
                            if fig_feas:
                                st.pyplot(fig_feas)
                        else:
                            st.info("La representacion grafica 2D esta disponible unicamente para problemas de exactamente dos variables.")

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
                            if len(prob.variables) == 2:
                                fig_rf = plot_feasible_region_2d(
                                    prob,
                                    solutions=sol.unique_solutions,
                                    title="Espacio de variables: Region factible y soluciones",
                                )
                                if fig_rf:
                                    st.pyplot(fig_rf)
                            else:
                                st.info("El espacio de variables 2D solo se representa graficamente para problemas con exactamente dos variables.")

                # Subtab 5: Diagnostico
                with subtab_diag:
                    with st.container(border=True):
                        st.subheader("Tiempos de Resolucion (Pyomo + HiGHS)")
                        st.json(sol.timing)
