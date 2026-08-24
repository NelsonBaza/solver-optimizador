# Nombres Personalizados de Variables y Carga Atómica de Modelos

**Fecha:** 24 de agosto de 2026  
**Módulos:** `src/solver_optimizador/model_io.py`, `src/solver_optimizador/problem_builder.py`, `src/solver_optimizador/plotting.py`, `streamlit_app.py`

---

## 1. Carga Atómica de Modelos con Confirmación Explícita y Versionado de Widgets

### Diagnóstico de Riesgo de Desincronización:
Anteriormente, los widgets de Streamlit (`text_input`, `radio`, `number_input`, `selectbox`, `slider`) poseían claves estáticas (`key="radio_prob_type"`, `key="num_vars_input"`, etc.). En el ciclo de vida de Streamlit, los widgets con claves estáticas conservan en caché su valor interactivo anterior e ignoran los parámetros `value=` / `index=` en los re-renderizados, lo que provocaba que al cargar un modelo de 24 variables se sobreescribiera la sesión con los valores viejos (ej. truncando a 2 variables y cambiando sentido a MAX).

### Solución Implementada:
1. **Versionado Dinámico de Widgets (`editor_version`):**
   * Todos los componentes interactivos usan claves vinculadas al contador de versión:
     `key=f"model_name_input_{editor_version}"`
     `key=f"radio_prob_type_{editor_version}"`
     `key=f"num_vars_input_{editor_version}"`
     `key=f"mono_sense_select_{editor_version}"`
     `key=f"var_names_editor_{editor_version}"`
     `key=f"constraints_editor_{editor_version}"`
   * Al cargar un modelo (`_load_model_dict`), iniciar nuevo (`_new_model`) o cargar ejemplos (`_load_example_mono`, `_load_example_bio`), `editor_version` se incrementa atómicamente, forzando a Streamlit a montar widgets completamente nuevos inicializados directamente desde los datos cargados.
2. **Tarjeta de Vista Previa del Archivo:**
   * Muestra metadata, tipo de problema, recuento de variables, restricciones y sentidos antes de aplicar los cambios.
3. **Módulo Desacoplado `problem_builder.py`:**
   * `build_lp_problem_from_state` y `build_biobjective_problem_from_state` actúan como constructores únicos y canónicos compartidos entre la interfaz y los tests unitarios.

---

## 2. Nombres Personalizados de Variables y Capacidad Ampliada

* **Independencia de `x1...xn`:** El usuario puede nombrar libremente sus variables (ej. `T1, T2, V1, V2, PH1, GH1, GT1`, etc.).
* **Capacidad de Interfaz:** Ampliada de 20 a **100 variables** (`max_value = 100`).
* **Preservación de Coeficientes:** Al renombrar variables en el editor tabular, los coeficientes en la función objetivo y en las restricciones se preservan automáticamente por correspondencia de posición.
* **Validación de Unicidad:** Nombres vacíos o duplicados son detectados y bloquean la resolución con un mensaje explicativo hasta ser corregidos.
* **Formulación Tabular Escalable:** La función objetivo se gestiona mediante un editor de datos tabular con columnas fijadas para las variables y campos editables para los coeficientes, soportando decenas de variables sin saturar la pantalla.

---

## 3. Validación con Caso Real Completo: Hidroeléctrico 24 Variables

Se formuló y resolvió el problema completo de despacho hidrotérmico multiperíodo (4 períodos):

* **Variables (24):**
  * Turbinación: $T_1, T_2, T_3, T_4$
  * Volumen embalse: $V_1, V_2, V_3, V_4$
  * Vertimiento: $S_1, S_2, S_3, S_4$
  * Potencia hidroeléctrica: $PH_1, PH_2, PH_3, PH_4$
  * Generación hidroeléctrica: $GH_1, GH_2, GH_3, GH_4$
  * Generación térmica: $GT_1, GT_2, GT_3, GT_4$
* **Objetivo:** $\text{MIN } Z = 100 GT_1 + 100 GT_2 + 100 GT_3 + 100 GT_4$.
* **Restricciones (28):** Balance hídrico, relación turbinación-potencia, conversión potencia-energía, balance energético/demanda, cotas de volumen y cotas de turbina.
* **Valor Óptimo Obtenido:** **$Z^* = 6701.25$**.
* **Persistencia Round-Trip:** Guardado a JSON (Schema 1.0) $\rightarrow$ Carga en modelo en blanco $\rightarrow$ Resolución: **$Z^* = 6701.25$** con coincidencia exacta de firma matemática y ausencia de residuos de estado.
