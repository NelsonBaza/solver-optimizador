"""
Aplicacion Web Streamlit — MVP Suite de Optimizacion Matematica.
Soporta Programacion Lineal Continua Monoobjetivo y Biobjetivo (Metodo de Ponderaciones).
Backend provisional: Pyomo + HiGHS.
"""

import sys
import os
from typing import List, Dict, Any

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
)
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.multiobjective import solve_biobjective_weighted
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
# Inicializacion de Estado de Sesion
# ---------------------------------------------------------------------------
def _init_session_state():
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


def _load_example_mono():
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


def _load_example_bio():
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


_init_session_state()


# ---------------------------------------------------------------------------
# Barra Lateral (Sidebar)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuracion")
    st.caption("Backend provisional: **Pyomo + HiGHS (APPSI)**")

    st.subheader("📚 Ejemplos Precargados")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        if st.button("Ejemplo 1 (Mono)", help="MAX Z = 3x1 + 2x2"):
            _load_example_mono()
            st.rerun()
    with col_ex2:
        if st.button("Benchmark A (Bio)", help="Benchmark A: MAX Z1, MAX Z2"):
            _load_example_bio()
            st.rerun()

    st.markdown("---")
    st.subheader("1. Tipo de Problema")
    prob_type = st.radio(
        "Modalidad de optimizacion:",
        options=["Monoobjetivo", "Biobjetivo"],
        index=0 if st.session_state.problem_type == "Monoobjetivo" else 1,
        key="radio_prob_type",
    )
    st.session_state.problem_type = prob_type

    st.subheader("2. Variables de Decision")
    st.caption("Todas las variables son continuas y no negativas ($x_i \\ge 0$).")
    num_vars = st.number_input(
        "Numero de variables:",
        min_value=1,
        max_value=10,
        value=st.session_state.num_vars,
        step=1,
    )
    st.session_state.num_vars = num_vars

    # Actualizar nombres de variables
    var_names = [f"x{i+1}" for i in range(num_vars)]
    st.session_state.var_names = var_names

    st.info(f"Variables activas: `{'`, `'.join(var_names)}`")


# ---------------------------------------------------------------------------
# Encabezado Principal
# ---------------------------------------------------------------------------
st.title("📐 Suite de Optimizacion Matematica — MVP")
st.markdown(
    """
    Herramienta de optimizacion matematica para formulacion y analisis de 
    **Programacion Lineal Continua** monoobjetivo y biobjetivo (metodo de ponderaciones normalizado).
    """
)

# ---------------------------------------------------------------------------
# Seccion: Objetivos y Restricciones
# ---------------------------------------------------------------------------
col_obj, col_con = st.columns([1, 1.2])

with col_obj:
    st.subheader("🎯 Funcion(es) Objetivo")

    if st.session_state.problem_type == "Monoobjetivo":
        st.markdown("**Objetivo Lineal $Z$:**")
        col_s, col_l = st.columns([1, 2])
        with col_s:
            sense_str = st.selectbox("Sentido:", ["Maximizar", "Minimizar"], key="mono_sense_select")
        
        st.markdown("**Coeficientes de $Z$:**")
        cols_c = st.columns(len(var_names))
        obj_coeffs = {}
        for i, v in enumerate(var_names):
            with cols_c[i]:
                default_val = st.session_state.obj_coeffs.get(v, 1.0)
                val = st.number_input(f"Coef. ${v}$:", value=float(default_val), step=1.0, key=f"mono_c_{v}")
                obj_coeffs[v] = val

        # Representacion algebraica
        terms = [f"{c:g} {v}" for v, c in obj_coeffs.items() if abs(c) > 1e-7]
        expr_str = " + ".join(terms).replace("+ -", "- ") if terms else "0"
        st.latex(f"\\text{{{sense_str[:3].upper()}}}\\; Z = {expr_str}")

    else:  # Biobjetivo
        st.markdown("#### Objetivo 1 ($Z_1$)")
        col_s1, _ = st.columns([1, 2])
        with col_s1:
            sense1_str = st.selectbox("Sentido $Z_1$:", ["Maximizar", "Minimizar"], key="bio_sense1_select")
        
        cols_c1 = st.columns(len(var_names))
        obj1_coeffs = {}
        for i, v in enumerate(var_names):
            with cols_c1[i]:
                default_val = st.session_state.obj1_coeffs.get(v, 1.0)
                val = st.number_input(f"Coef. ${v}$ ($Z_1$):", value=float(default_val), step=1.0, key=f"bio_c1_{v}")
                obj1_coeffs[v] = val

        st.markdown("#### Objetivo 2 ($Z_2$)")
        col_s2, _ = st.columns([1, 2])
        with col_s2:
            sense2_str = st.selectbox("Sentido $Z_2$:", ["Maximizar", "Minimizar"], key="bio_sense2_select")

        cols_c2 = st.columns(len(var_names))
        obj2_coeffs = {}
        for i, v in enumerate(var_names):
            with cols_c2[i]:
                default_val = st.session_state.obj2_coeffs.get(v, 1.0)
                val = st.number_input(f"Coef. ${v}$ ($Z_2$):", value=float(default_val), step=1.0, key=f"bio_c2_{v}")
                obj2_coeffs[v] = val

        # Configuracion Multiobjetivo
        st.markdown("---")
        st.markdown("#### ⚖️ Parametros de Ponderacion")
        mo_mode = st.radio(
            "Modalidad de ponderacion:",
            options=["Barrido automatico", "Ponderacion unica"],
            horizontal=True,
            key="mo_mode_radio",
        )
        if mo_mode == "Barrido automatico":
            num_weights = st.slider("Numero de combinaciones $(\\alpha_1, \\alpha_2)$:", min_value=2, max_value=21, value=6, step=1)
        else:
            custom_a1 = st.slider("Peso $\\alpha_1$ (para $Z_1$):", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
            custom_a2 = round(1.0 - custom_a1, 4)
            st.info(f"$\\alpha_1 = {custom_a1:.2f}, \\quad \\alpha_2 = {custom_a2:.2f}$")

        with st.expander("ℹ️ Metodo de Normalizacion"):
            st.markdown(
                """
                Se utiliza la normalizacion basada en la **matriz de pagos**:
                $$\\text{Rango } \\Delta Z_k = Z_{k,\\max} - Z_{k,\\min}$$
                $$W = \\alpha_1 \\frac{Z_1}{\\Delta Z_1} + \\alpha_2 \\frac{Z_2}{\\Delta Z_2}$$
                *(ajustando el signo negativo en caso de minimizacion).*
                """
            )


with col_con:
    st.subheader("📋 Restricciones Lineales")
    st.caption("Agregue o edite las restricciones lineales del problema.")

    # Asegurar que cada restriccion tenga todas las variables activas
    current_data = []
    for idx, c_dict in enumerate(st.session_state.constraints_data):
        row = {
            "Nombre": c_dict.get("name", f"Restriccion {idx+1}"),
            "Operador": c_dict.get("operator", "<="),
            "RHS": float(c_dict.get("rhs", 10.0)),
        }
        for v in var_names:
            row[v] = float(c_dict.get(v, 1.0))
        current_data.append(row)

    df_constraints = pd.DataFrame(current_data)

    # Column config para editor de datos
    column_order = ["Nombre"] + var_names + ["Operador", "RHS"]
    col_config = {
        "Nombre": st.column_config.TextColumn("Nombre", required=True),
        "Operador": st.column_config.SelectboxColumn("Operador", options=["<=", ">=", "="], required=True),
        "RHS": st.column_config.NumberColumn("Lado Derecho (RHS)", required=True),
    }
    for v in var_names:
        col_config[v] = st.column_config.NumberColumn(f"Coef. {v}", required=True)

    edited_df = st.data_editor(
        df_constraints[column_order],
        num_rows="dynamic",
        use_container_width=True,
        column_config=col_config,
        key="constraints_editor",
    )


# ---------------------------------------------------------------------------
# Boton de Resolucion
# ---------------------------------------------------------------------------
st.markdown("---")
col_btn, _ = st.columns([1, 4])
with col_btn:
    btn_solve = st.button("🚀 Resolver Problema", type="primary", use_container_width=True)


# ---------------------------------------------------------------------------
# Logica de Resolucion y Presentacion de Resultados
# ---------------------------------------------------------------------------
if btn_solve:
    # 1. Validar y construir lista de restricciones
    constraints_list: List[LinearConstraint] = []
    has_validation_error = False

    if edited_df.empty:
        st.error("❌ El problema debe contener al menos una restriccion lineal.")
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
                st.error(f"❌ Error en fila {idx+1}: {e}")
                has_validation_error = True
                break

            rhs_val = row.get("RHS")
            if pd.isna(rhs_val):
                st.error(f"❌ La restriccion '{c_name}' no tiene un valor valido en el lado derecho (RHS).")
                has_validation_error = True
                break

            c_coeffs = {}
            for v in var_names:
                c_val = row.get(v)
                if pd.isna(c_val):
                    st.error(f"❌ Falta el coeficiente de '{v}' en la restriccion '{c_name}'.")
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
        st.header("📊 Resultados de la Optimizacion")

        # -------------------------------------------------------------------
        # CASO 1: MONOOBJETIVO
        # -------------------------------------------------------------------
        if st.session_state.problem_type == "Monoobjetivo":
            sense_enum = Sense.from_str(sense_str)
            problem_mono = LPProblem(
                variables=var_names,
                objective=LinearObjective("Z", sense_enum, obj_coeffs),
                constraints=constraints_list,
            )

            with st.spinner("Resolviendo con Pyomo + HiGHS..."):
                sol_mono = solve_lp(problem_mono)

            if sol_mono.status == SolverStatus.OPTIMAL:
                st.success(f"✅ **{sol_mono.status_message}** (Tiempo de solve: {sol_mono.execution_time_sec*1000:.1f} ms)")

                # Metricas clave
                m_cols = st.columns(1 + len(var_names))
                with m_cols[0]:
                    st.metric(label="Valor Optimo $Z^*$", value=f"{sol_mono.objective_value:.4f}")
                for i, v in enumerate(var_names):
                    with m_cols[i + 1]:
                        st.metric(label=f"Variable ${v}^*$", value=f"{sol_mono.variable_values[v]:.4f}")

                st.markdown("#### 🔍 Analisis de Restricciones y Holguras")
                con_data = []
                for cr in sol_mono.constraint_results:
                    con_data.append({
                        "Restriccion": cr.name,
                        "LHS Evaluado": f"{cr.lhs:.4f}",
                        "Op": cr.operator,
                        "RHS": f"{cr.rhs:.4f}",
                        "Holgura": f"{cr.slack:.4f}",
                        "Estado": "🔴 Activa (Limite estricto)" if cr.is_active else "🟢 No activa (Con holgura)",
                    })
                st.dataframe(pd.DataFrame(con_data), use_container_width=True)

                # Grafico 2D si hay 2 variables
                if len(var_names) == 2:
                    st.markdown("#### 🗺️ Region Factible y Vertice Optimo")
                    fig_feas = plot_feasible_region_2d(
                        problem_mono,
                        solutions=[{"id": "Optimo", "x": sol_mono.variable_values}],
                        title="Region Factible y Solucion Optima (Pyomo + HiGHS)",
                    )
                    if fig_feas:
                        st.pyplot(fig_feas)
                else:
                    st.info("ℹ️ La region factible 2D no esta disponible para problemas con mas de dos variables.")

            else:
                st.error(f"⚠️ **{sol_mono.status_message}** ({sol_mono.raw_termination})")
                if sol_mono.status == SolverStatus.INFEASIBLE:
                    st.warning("No existe ninguna asignacion de variables $(x \\ge 0)$ que satisfaga todas las restricciones simultaneamente.")
                elif sol_mono.status == SolverStatus.UNBOUNDED:
                    st.warning("El problema no esta acotado en la direccion del objetivo (el valor optimo tiende a infinito).")

                with st.expander("Detalles tecnicos del solver"):
                    st.json({
                        "status": sol_mono.status.value,
                        "raw_termination": sol_mono.raw_termination,
                        "execution_time_sec": sol_mono.execution_time_sec,
                    })

        # -------------------------------------------------------------------
        # CASO 2: BIOBJETIVO
        # -------------------------------------------------------------------
        else:
            sense1_enum = Sense.from_str(sense1_str)
            sense2_enum = Sense.from_str(sense2_str)

            problem_bio = BiobjectiveProblem(
                variables=var_names,
                objective1=LinearObjective("Z1", sense1_enum, obj1_coeffs),
                objective2=LinearObjective("Z2", sense2_enum, obj2_coeffs),
                constraints=constraints_list,
            )

            # Preparar configuracion de pesos
            weights_param = None
            num_comb_param = None
            if mo_mode == "Barrido automatico":
                num_comb_param = num_weights
            else:
                weights_param = [(custom_a1, custom_a2)]

            with st.spinner("Ejecutando evaluacion biobjetivo (Pyomo + HiGHS)..."):
                sol_bio = solve_biobjective_weighted(
                    problem_bio,
                    weights=weights_param,
                    num_combinations=num_comb_param,
                )

            if not sol_bio.unique_solutions:
                st.error("⚠️ No se pudieron obtener soluciones optimas para los objetivos individuales.")
                for note in sol_bio.notes:
                    st.warning(note)
            else:
                st.success("✅ **Evaluacion Biobjetivo completada con exito**")

                # Pestañas de resultados
                tab_opt, tab_sweep, tab_pareto, tab_plots = st.tabs([
                    "1. Optimos & Matriz de Pagos",
                    "2. Barrido de Ponderaciones",
                    "3. Clasificacion de Dominancia",
                    "4. Visualizacion Grafica",
                ])

                with tab_opt:
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        st.markdown("#### Matriz de Pagos (Payoff Matrix)")
                        pm_data = [
                            {
                                "Optimo Individual": "Maximizacion/Minimizacion Z1",
                                "Z1 Evaluado": sol_bio.payoff_matrix["opt_Z1"]["Z1"],
                                "Z2 Evaluado": sol_bio.payoff_matrix["opt_Z1"]["Z2"],
                                "Variables": str(sol_bio.payoff_matrix["opt_Z1"]["x"]),
                            },
                            {
                                "Optimo Individual": "Maximizacion/Minimizacion Z2",
                                "Z1 Evaluado": sol_bio.payoff_matrix["opt_Z2"]["Z1"],
                                "Z2 Evaluado": sol_bio.payoff_matrix["opt_Z2"]["Z2"],
                                "Variables": str(sol_bio.payoff_matrix["opt_Z2"]["x"]),
                            },
                        ]
                        st.dataframe(pd.DataFrame(pm_data), use_container_width=True)

                    with col_p2:
                        st.markdown("#### Rangos de Normalizacion Calculados")
                        nr = sol_bio.normalization_ranges
                        r_data = [
                            {"Objetivo": "Z1", "Minimo": nr["Z1_min"], "Maximo": nr["Z1_max"], "Rango (Delta Z)": nr["Z1_range"]},
                            {"Objetivo": "Z2", "Minimo": nr["Z2_min"], "Maximo": nr["Z2_max"], "Rango (Delta Z)": nr["Z2_range"]},
                        ]
                        st.dataframe(pd.DataFrame(r_data), use_container_width=True)

                    if sol_bio.notes:
                        for n in sol_bio.notes:
                            st.info(f"📌 {n}")

                with tab_sweep:
                    st.markdown("#### Tabla Completa de Corridas Ponderadas")
                    runs_table = []
                    for r in sol_bio.weighted_runs:
                        row_dict = {
                            "Corrida": r["run_index"],
                            "alpha1": f"{r['alpha1']:.2f}",
                            "alpha2": f"{r['alpha2']:.2f}",
                            "Z1": r["Z1"],
                            "Z2": r["Z2"],
                            "W (Obj. Ponderado)": f"{r['W']:.4f}",
                            "Estado": r["status"],
                        }
                        for v in var_names:
                            row_dict[v] = r["x"].get(v, "-")
                        runs_table.append(row_dict)
                    st.dataframe(pd.DataFrame(runs_table), use_container_width=True)

                with tab_pareto:
                    st.markdown("#### Soluciones Unicas y Clasificacion de Dominancia")
                    st.caption(
                        "🔍 **Nota metodologica:** La clasificacion se realiza exclusivamente sobre las soluciones obtenidas "
                        "en el barrido ejecutado. No implica que se haya generado toda la frontera de Pareto."
                    )
                    unique_table = []
                    for u in sol_bio.unique_solutions:
                        ws_str = ", ".join(f"({w['alpha1']:.2f}, {w['alpha2']:.2f})" for w in u["generated_by_weights"])
                        row_u = {
                            "ID": u["id"],
                            "Z1": u["Z1"],
                            "Z2": u["Z2"],
                            "Veces Obtenida": u["count"],
                            "Generada por Ponderaciones": ws_str,
                            "Clasificacion Pareto": "🏆 " + u["pareto_status"] if "no dominada" in u["pareto_status"].lower() else "⚠️ " + u["pareto_status"],
                        }
                        for v in var_names:
                            row_u[v] = u["x"].get(v, "-")
                        unique_table.append(row_u)
                    st.dataframe(pd.DataFrame(unique_table), use_container_width=True)

                with tab_plots:
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        st.markdown("#### Espacio de Objetivos ($Z_1$ vs $Z_2$)")
                        fig_obj = plot_objective_space_2d(
                            sol_bio.unique_solutions,
                            z1_name="Z1",
                            z2_name="Z2",
                            z1_sense=sense1_enum,
                            z2_sense=sense2_enum,
                        )
                        st.pyplot(fig_obj)

                    with col_g2:
                        st.markdown("#### Espacio de Variables (Region Factible 2D)")
                        if len(var_names) == 2:
                            fig_rf = plot_feasible_region_2d(
                                problem_bio,
                                solutions=sol_bio.unique_solutions,
                                title="Region Factible y Soluciones del Barrido",
                            )
                            if fig_rf:
                                st.pyplot(fig_rf)
                        else:
                            st.info("ℹ️ La region factible 2D no esta disponible para problemas con mas de dos variables.")

                with st.expander("⏱️ Tiempos de Ejecucion"):
                    st.json(sol_bio.timing)
