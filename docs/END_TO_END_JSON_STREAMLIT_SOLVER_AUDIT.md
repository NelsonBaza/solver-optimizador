# Auditoría End-to-End: Carga JSON → Streamlit → LPProblem → Solver

**Fecha:** 24 de agosto de 2026  
**Módulos:** `src/solver_optimizador/problem_builder.py`, `src/solver_optimizador/model_io.py`, `streamlit_app.py`, `tests/fixtures/hydroelectric_full_24_vars.json`, `tests/test_hydroelectric_e2e.py`

---

## 1. Diagnóstico y Causa Raíz

### Síntoma Observado:
Al cargar el archivo JSON del modelo hidroeléctrico de 24 variables y 28 restricciones en la interfaz de Streamlit, el solver reportaba:
```text
Problema infactible
```
Adicionalmente, se observaban desincronizaciones visuales:
* El selector de sentido mostraba `Maximizar` en vez de `Minimizar`.
* El encabezado mostraba `Modelo de Optimización` en vez del nombre contenido en el archivo.
* La formulación visible presentaba solo 2 variables truncadas (`T1, T2`).

### Causa Raíz Técnica:
Los widgets de Streamlit (`st.text_input`, `st.radio`, `st.number_input`, `st.selectbox`, `st.slider`) estaban configurados con claves estáticas (`key="radio_prob_type"`, `key="num_vars_input"`, `key="mono_sense_select"`, etc.).
En el modelo de ejecución de Streamlit:
1. El registro interno de widgets persiste los valores interactivos previos vinculados a cada clave estática.
2. Al ejecutar `_load_model_dict` y realizar `st.rerun()`, los widgets con claves estáticas ignoraban los nuevos valores de `st.session_state` e inyectaban sus valores antiguos (ej. `num_vars = 2`, `obj_sense = Maximizar`).
3. El widget de variables provocaba la reducción de las 24 variables a 2 (`T1, T2`), convirtiendo restricciones como $V_1 + T_1 + S_1 = 90$ en $T_1 = 90$, lo cual entraba en conflicto directo con $T_1 \le 70$, volviendo el modelo matemáticamente infactible.

---

## 2. Correcciones Implementadas

### A. Versionado Determinista de Claves de Widgets (`editor_version`):
Todos los widgets interactivos de la aplicación fueron actualizados para incorporar el sufijo de versión:
* `key=f"model_name_input_{editor_version}"`
* `key=f"model_desc_input_{editor_version}"`
* `key=f"radio_prob_type_{editor_version}"`
* `key=f"num_vars_input_{editor_version}"`
* `key=f"mono_sense_select_{editor_version}"`
* `key=f"bio_sense1_select_{editor_version}"`
* `key=f"bio_sense2_select_{editor_version}"`
* `key=f"mo_mode_radio_{editor_version}"`
* `key=f"num_weights_slider_{editor_version}"`
* `key=f"custom_a1_slider_{editor_version}"`
* `key=f"var_names_editor_{editor_version}"`
* `key=f"mono_obj_editor_{editor_version}"`
* `key=f"bio_obj_editor_{editor_version}"`
* `key=f"constraints_editor_{editor_version}"`

Cada carga de modelo (`_load_model_dict`), reinicio (`_new_model`) o carga de ejemplo incrementa `editor_version += 1`, obligando a Streamlit a destruir las instancias anteriores y montar componentes nuevos inicializados directamente desde el estado cargado.

### B. Módulo Constructor de Problemas (`src/solver_optimizador/problem_builder.py`):
Se creó un módulo desacoplado con las funciones:
* `build_lp_problem_from_state(var_names, obj_sense, obj_coeffs, canonical_constraints)`
* `build_biobjective_problem_from_state(var_names, obj1_sense, obj1_coeffs, obj2_sense, obj2_coeffs, canonical_constraints)`

Garantiza que la UI, los scripts CLI y la suite de pruebas construyan instancias de `LPProblem` y `BiobjectiveProblem` 100% idénticas.

### C. Expander de Diagnóstico del Modelo Efectivo:
Se agregó en la pestaña de formulación el bloque:
`🔧 Diagnóstico del modelo efectivo` (cerrado por defecto), mostrando el recuento de variables activas, sentido real y tabla canónica de restricciones.

---

## 3. Fixture Oficial y Validación Matemática

Se incorporó el fixture estandarizado en:
[`tests/fixtures/hydroelectric_full_24_vars.json`](../tests/fixtures/hydroelectric_full_24_vars.json)

### Comparación Modelo Esperado vs. LPProblem Efectivo:
| Componente | Esperado (JSON) | Efectivo (`problem_builder` / Solver) | Coincidencia |
| :--- | :--- | :--- | :---: |
| **Variables** | 24 variables (`T1..T4`, `V1..V4`, `S1..S4`, `PH1..PH4`, `GH1..GH4`, `GT1..GT4`) | 24 variables idénticas | ✅ Exacta |
| **Sentido** | `Minimizar` | `Sense.MINIMIZE` | ✅ Exacta |
| **Objetivo** | $100 GT_1 + 100 GT_2 + 100 GT_3 + 100 GT_4$ | Coeficientes $100.0$ en $GT_{1..4}$, $0.0$ en resto | ✅ Exacta |
| **Balances Hídricos** | `Balance_H1..4` ($=$ RHS $90, 20, 15, 10$) | Operador `=`, RHS $90, 20, 15, 10$ | ✅ Exacta |
| **Turb-Pot / Pot-Ene** | `Turb_Pot_1..4` ($=$), `Pot_Ene_1..4` ($=$) | Operador `=`, RHS $0.0$ | ✅ Exacta |
| **Demandas** | `Demanda_P1..4` ($=$ RHS $60, 80, 70, 90$) | Operador `=`, RHS $60, 80, 70, 90$ | ✅ Exacta |
| **Cotas de Volumen** | `V_Max_1..4` ($\le 100$), `V_Min_1..4` ($\ge 40$) | Operadores $\le$ y $\ge$, RHS $100$ y $40$ | ✅ Exacta |
| **Cotas de Turbina** | `T_Max_1..4` ($\le 70$) | Operador $\le$, RHS $70$ | ✅ Exacta |
| **Total Restricciones** | 28 restricciones | 28 restricciones canónicas | ✅ Exacta |
| **Estado Solver** | Óptimo | `SolverStatus.OPTIMAL` | ✅ Exacta |
| **Valor Óptimo $Z^*$** | $6701.25$ | **$6701.25$** ($\sum GT_t = 67.0125$) | ✅ Exacta |

---

## 4. Pruebas Automatizadas End-to-End (`test_hydroelectric_e2e.py`)

1. `test_hydroelectric_fixture_direct_solver`: Validación directa de resolución del fixture JSON ($Z^* = 6701.25$).
2. `test_hydroelectric_critical_operators_and_rhs`: Verificación estricta de los 28 operadores y valores RHS.
3. `test_streamlit_apptest_hydroelectric_load_and_solve`: Carga del modelo en Streamlit AppTest, sincronización de widgets y resolución óptima ($Z^* = 6701.25$).
4. `test_streamlit_apptest_transitions_a_to_b_and_b_to_a`: Transición bidireccional Benchmark A (Bio) $\rightarrow$ Hidroeléctrico (Mono) $\rightarrow$ Benchmark A (Bio) con verificación de aislamiento de estado.
