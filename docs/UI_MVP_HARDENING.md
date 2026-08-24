# Informe Técnico: Hardening del MVP Streamlit para Optimización Lineal

**Fecha:** 23 de agosto de 2026  
**Objetivo:** Corrección de hallazgos de auditoría y robustecimiento del MVP Streamlit y su motor matemático antes de pruebas docentes reales.  
**Backend:** Pyomo 6.10.1 + HiGHS 1.15.1 (APPSI / `highspy`)  
**Framework UI:** Streamlit 1.62.0  
**Test Suite:** pytest 9.1.1 (12 pruebas unitarias automatizadas)

---

## 1. Defectos y Riesgos Detectados en la Auditoría Inicial

1. **Desincronización de Widgets en Streamlit al Cargar Ejemplos:**
   * *Diagnóstico:* Al pulsar los botones de "Cargar Ejemplo" (Mono o Biobjetivo), Streamlit retenía valores antiguos en las claves internas de widgets (`mono_sense_select`, `constraints_editor`, etc.) si no se reseteaban explícitamente o si el editor de tablas conservaba su caché interna.
   * *Riesgo:* Aparición de filas residuales o discrepancias entre la interfaz visible y el problema resuelto.
2. **Nomenclatura Parcial e Inadecuada para Problemas de Minimización:**
   * *Diagnóstico:* Estructuras de datos internas utilizaban `Z1_max` y `Z2_max` incluso en problemas con sentido de minimización (`MIN`).
3. **Falta de Validación Formal de Minimización:**
   * *Diagnóstico:* La suite inicial probaba únicamente problemas de maximización continua (`MAX` / `MAX-MAX`).
4. **Tratamiento Implícito y Riesgoso de Rango Nulo ($\Delta Z = 0$):**
   * *Diagnóstico:* Ante un rango nulo en algún objetivo, el código sustituía silenciosamente $r_{\text{effective}} = 1.0$ y procedía con el barrido ponderado como si fuera una normalización estándar.
5. **Vulnerabilidad en Nombres de Restricciones en Pyomo:**
   * *Diagnóstico:* Se creaban atributos de modelo con `f"c_{i}_{c.name}"`, lo que producía fallos cuando los nombres contenían espacios, caracteres matemáticos como `≥` o símbolos como `#`.
6. **Manejo Indeterminado de Corridas Fallidas en Multiobjetivo:**
   * *Diagnóstico:* Corridas no óptimas asignaban ceros ($x=0, Z=0$), lo que podía confundirse con soluciones factibles en el origen.
7. **Riesgo Geométrico en Visualización de Región Factible:**
   * *Diagnóstico:* Regiones degeneradas, no acotadas o con restricciones de igualdad podían inducir al trazado de polígonos incorrectos.
8. **Falta de Validación Estricta de Entradas Numéricas Finitas:**
   * *Diagnóstico:* Posible ingreso de `NaN`, `inf` o `-inf` desde la interfaz hacia el solver.

---

## 2. Correcciones Técnicas Implementadas

### A. Sincronización Completa de Estado y Widgets en Streamlit
* Se implementó una función de reseteo explícito `_clear_widget_keys()` que elimina del `st.session_state` todas las claves vinculadas a widgets al cargar ejemplos (`mono_c_*`, `bio_c1_*`, `bio_c2_*`, selectores y radios).
* Se introdujo un contador de versión `editor_version` para generar dinámicamente la clave del editor de tablas `f"constraints_editor_{st.session_state.editor_version}"`. Al pulsar un botón de ejemplo, se incrementa la versión forzando una reconstrucción limpia y exacta de la tabla sin residuos.

### B. Nomenclatura Neutral en Estructuras de Datos
* Se refactorizaron las claves en `individual_optima` a identificadores neutrales:
  * `Z1_opt` (Óptimo individual de $Z_1$, independiente de si es MAX o MIN)
  * `Z2_opt` (Óptimo individual de $Z_2$, independiente de si es MAX o MIN)
* Se actualizaron en el núcleo, la interfaz, las pruebas y los documentos.

### C. Tratamiento Metodológicamente Riguroso de Rango Nulo
* Si $\Delta Z_1 < 10^{-7}$ o $\Delta Z_2 < 10^{-7}$, el motor **detiene el barrido ponderado de forma controlada**, devolviendo `weighted_runs = []` y `unique_solutions = []`.
* Devuelve un mensaje metodológico explícito:
  > *"No es posible aplicar la normalización por rangos porque al menos uno de los objetivos tiene rango nulo ($\Delta Z \approx 0$). Esto puede indicar que el objetivo es redundante, constante sobre los puntos evaluados o que no existe conflicto observable entre objetivos mediante esta matriz de pagos."*
* La interfaz muestra la matriz de pagos obtenida y advierte al usuario sin generar errores no controlados.

### D. Identificadores Seguros para Restricciones en Pyomo
* Las restricciones se asignan internamente con identificadores basados únicamente en el índice `setattr(model, f"con_{i}", con_obj)`.
* El nombre descriptivo del usuario (`c.name`) se conserva exclusivamente para reporte, tablas y trazabilidad.

### E. Manejo Controlado de Corridas No Óptimas en Multiobjetivo
* Si una corrida del barrido ponderado no resulta óptima, se asigna explícitamente `x = None`, `Z1 = None`, `Z2 = None`, `W = None` y `status = term_str`.
* El agrupamiento de soluciones únicas y la clasificación de no dominancia de Pareto filtran y descartan automáticamente corridas sin solución válida.

### F. Validación de Números Finitos
* Se creó el helper `is_finite_number(val)` que comprueba `math.isfinite(val)` y descarta `None`, `bool`, `nan`, `inf` y `-inf`.
* Se integró en `LPProblem.validate()`, `BiobjectiveProblem.validate()`, el verificador de pesos y la captura de datos en Streamlit.

### G. Robustez en la Visualización 2D
* La función `plot_feasible_region_2d` únicamente sombrea el polígono cuando:
  1. Hay al menos 3 vértices factibles detectados.
  2. No existen restricciones de igualdad ($=$).
  3. Todas las coordenadas son finitas y acotadas.
* Si estas condiciones no se cumplen, dibuja las restricciones lineales y los puntos de solución calculados sin inventar un polígono artificial.

---

## 3. Matriz de Pruebas Unitarias Automatizadas (pytest)

La suite creció de 6 a **12 pruebas unitarias**, cubriendo todos los escenarios exigidos:

| ID | Test | Propósito / Caso Verificado | Estado |
| :---: | :--- | :--- | :---: |
| 1 | `test_single_objective_max` | Ejemplo 1 MAX ($3x_1+2x_2 \le 4, x_1 \le 2, x_2 \le 3 \implies x=(2,2), Z=10$) | **PASS** |
| 2 | `test_single_objective_min` | Caso A MIN ($x_1+2x_2, x_1+x_2 \ge 4, x_1 \ge 1, x_2 \ge 1 \implies x=(3,1), Z=5$) | **PASS** |
| 3 | `test_biobjective_benchmark_a` | Benchmark A MAX/MAX (6 ponderaciones, 3 soluciones únicas no dominadas) | **PASS** |
| 4 | `test_biobjective_max_min` | Caso B MAX/MIN (MAX $2x_1+x_2$, MIN $x_1+3x_2$ en simplex $x_1+x_2 \le 4$) | **PASS** |
| 5 | `test_biobjective_min_min` | Caso C MIN/MIN (MIN $2x_1+x_2$, MIN $x_1+2x_2$ en región $x_1+x_2 \ge 4$) | **PASS** |
| 6 | `test_infeasible_problem` | Detección limpia de problema infactible | **PASS** |
| 7 | `test_unbounded_problem` | Detección limpia de problema no acotado | **PASS** |
| 8 | `test_invalid_weights_validation` | Rechazo de pesos negativos, sumas $\ne 1.0$ o $N < 2$ | **PASS** |
| 9 | `test_zero_range_handling` | Manejo controlado de rango cero sin división por cero ni falsos $W$ | **PASS** |
| 10 | `test_special_constraint_names` | Nombres con caracteres especiales (`"Demanda ≥ mínima #1"`, `"Capacidad (A+B)"`) | **PASS** |
| 11 | `test_non_finite_inputs_validation` | Rechazo de `NaN`, `inf`, `-inf` en objetivos y restricciones | **PASS** |
| 12 | `test_plotting_functions` | Retorno de Figure en 2D acotado, None en $>2$ vars, y estabilidad ante degeneración | **PASS** |

**Resultado global:** 12 tests ejecutados, **12 aprobados (100% PASS en 1.03 s)**.

---

## 4. Verificación de Flujos de Usuario (Smoke Test)

1. **Flujo 1 (Ejemplo 1 Mono):** Carga $3x_1 + 2x_2$ con restricciones $(\le 4, \le 2, \le 3)$. Resuelve $x_1=2, x_2=2, Z=10$.
2. **Flujo 2 (Benchmark A Bio):** Modificando previamente datos arbitrarios y pulsando "Benchmark A", la interfaz se limpia por completo y carga el Benchmark A exacto. Resuelve obteniendo las 3 soluciones no dominadas: $(0,130) \rightarrow (390,169)$, $(80,50) \rightarrow (950,129)$ y $(100,0) \rightarrow (1000,80)$.
3. **Flujo 3 (Minimización):** Selección de problemas MIN y resolución correcta de óptimos, signos ponderados y holguras.
