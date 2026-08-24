# Informe de Refinamiento UI/UX: Suite de Optimización Matemática (Streamlit)

**Fecha:** 23 de agosto de 2026  
**Objetivo:** Refinamiento de la interfaz y experiencia de usuario aplicando principios de desarrollo en Streamlit para el MVP de optimización lineal continua.  
**Backend matemático:** Pyomo 6.10.1 + HiGHS 1.15.1 (APPSI / `highspy`)  
**Framework UI:** Streamlit 1.62.0  
**Test Suite:** pytest 9.1.1 (12 pruebas unitarias automatizadas 100% PASS)

---

## 1. Recomendaciones de Desarrollo en Streamlit Aplicadas

Durante el proceso de diseño e implementación se aplicaron las siguientes directrices y mejores prácticas de Streamlit:

1. **Eliminación de APIs Deprecadas (`width="stretch"`):**
   * Se reemplazaron todas las llamadas `use_container_width=True` en `st.dataframe`, `st.data_editor` y `st.button` por el parámetro estándar `width="stretch"`.
   * Se eliminó el 100% de advertencias de obsolescencia.
2. **Separación de Etapas (Formulación vs. Resultados):**
   * Estructuración en dos pestañas principales de nivel superior:
     * `📝 1. Formulación del Modelo`: Zona interactiva de entrada de datos, coeficientes, restricciones y vista previa en tiempo real.
     * `📊 2. Resultados y Análisis`: Zona de visualización de soluciones, tablas estructuradas, análisis de holguras, soluciones no dominadas y gráficos 2D.
3. **Persistencia de Resultados en `st.session_state`:**
   * La solución calculada se almacena en `st.session_state.last_solution` y `st.session_state.last_solution_problem`, permitiendo que el usuario explore pestañas de resultados y modifique vistas sin recalcular innecesariamente.
4. **Agrupación Visual Jerárquica con `st.container(border=True)`:**
   * Los bloques conceptuales (Objetivos, Restricciones, Ponderaciones, Vista previa, Métricas y Tablas) están delimitados con contenedores nativos con borde, mejorando la legibilidad en pantallas de cualquier resolución.
5. **Formateo y Tipado Numérico en DataFrames:**
   * Las tablas `st.dataframe` y `st.data_editor` conservan valores numéricos reales (`float`/`int`) con configuración de formato (`st.column_config.NumberColumn(format="%.2f")` y `"%.4f"`), habilitando ordenamiento y filtrado nativo.
6. **Vista Previa Matemática en Tiempo Real (`st.latex`):**
   * Renderizado dinámico seguro de la función objetivo ($Z$ o $Z_1, Z_2$) y del sistema completo de restricciones lineales en notación algebraica formal.
7. **Feedback Inmediato de Carga de Ejemplos (`st.toast`):**
   * Notificación no invasiva al cargar un ejemplo predefinido, confirmando que la interfaz ha sido completamente sincronizada.

---

## 2. Comparativa Conceptual (Before vs. After)

| Aspecto | Estado Previo | Estado Refinado |
| :--- | :--- | :--- |
| **Flujo de Usuario** | Entrada y resultados superpuestos verticalmente en una única vista larga. | Dos pestañas independientes: **Formulación** y **Resultados**, con flujo estructurado en pasos. |
| **Advertencias de Deprecación** | Múltiples avisos de `use_container_width`. | **0 warnings** de deprecación; uso exclusivo de `width="stretch"`. |
| **Vista Previa Matemática** | Solo fórmula de la función objetivo. | Modelo algebraico completo en LaTeX (objetivo + sistema de restricciones + no negatividad). |
| **Configuración de Pesos** | Sliders básicos sin previsualización de pares. | Selector con vista previa explícita de todos los pares $(\alpha_1, \alpha_2)$ generados. |
| **Persistencia de Solución** | Se borraba al menor re-renderizado de la página. | Almacenamiento desacoplado en `session_state`. |
| **Matriz de Pagos** | Nombres técnicos (`opt_Z1`, `opt_Z2`). | Nombres académicos legibles (`Óptimo individual Z1`, `Óptimo individual Z2`). |
| **Detalle de Soluciones Repetidas** | Tabla simple con IDs sin desglose visual. | Tarjetas con desglose explícito de los valores de variables y pesos asociados a cada solución única. |
| **Gráficos 2D** | Títulos genéricos y leyendas imprecisas. | Nombres formales: *Espacio de variables* y *Espacio de objetivos* con etiquetas de no dominancia precisas. |

---

## 3. Clasificación de Advertencias (Warnings)

1. **Corregibles (CORREGIDO):**
   * Advertencias sobre `use_container_width` $\rightarrow$ Eliminadas completamente al migrar a `width="stretch"`.
2. **Externas / Entorno (NO BLOQUEANTE):**
   * `missing ScriptRunContext` $\rightarrow$ Advertencia benigna generada exclusivamente cuando se importa `streamlit_app` directamente desde un script de prueba de consola (bare mode); no ocurre al ejecutar con `streamlit run`.
   * En sistemas Windows sin permisos elevados, avisos de symlinks son gestionados nativamente por el sistema operativo sin impacto en la aplicación.

---

## 4. Validación de Ejemplos Académicos

* **Ejemplo 1 (Monoobjetivo):**
  * $\text{MAX } Z = 3x_1 + 2x_2$ s.a. $x_1 + x_2 \le 4, x_1 \le 2, x_2 \le 3, x_1,x_2 \ge 0$.
  * Resultado: $x_1^* = 2.0, x_2^* = 2.0, Z^* = 10.0$.
* **Benchmark A (Biobjetivo):**
  * $\text{MAX } Z_1 = 10x_1 + 3x_2, \text{MAX } Z_2 = 0.8x_1 + 1.3x_2$ s.a. $x_1 + x_2 \le 130, 2.5x_1 + x_2 \le 250, x_1,x_2 \ge 0$.
  * 3 soluciones únicas no dominadas: $A(0,130) \rightarrow (390,169)$, $B(80,50) \rightarrow (950,129)$, $C(100,0) \rightarrow (1000,80)$.
