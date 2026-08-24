# Registro de Implementación: Corrección de Validación de Filas Vacías en Restricciones Dinámicas

**Fecha:** 24 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Filtrar filas dinámicas completamente vacías generadas por `st.data_editor(num_rows="dynamic")` en la tabla de restricciones para que no bloqueen los botones de resolución y descarga, manteniendo el rechazo estricto de filas parcialmente diligenciadas o malformadas con mensajes visibles en la interfaz.

---

## 1. Síntoma y Causa Raíz
* **Síntoma:** Un modelo válido ($\min 15x_1 + 23x_2$ con $10x_1 + 5x_2 \le 130$ y $2x_1 + 13x_2 \le 250$) mostraba los botones **Resolver** y **Descargar** deshabilitados.
* **Causa:** `st.data_editor` con `num_rows="dynamic"` agrega una fila vacía al final para permitir la inserción de nuevas filas. Al convertir la tabla a diccionarios, esta fila vacía (`{"Nombre": None, "x1": None, "x2": None, "Operador": None, "RHS": None}`) ingresaba a `normalize_constraints` y fallaba por falta de operador/RHS, definiendo `cons_norm_error` y deshabilitando las acciones.

---

## 2. Corrección Implementada
1. **Detección de Fila Vacía (`is_empty_constraint_row`):**
   * Comprueba si todos los campos (`Nombre`, `Operador`, `RHS` y coeficientes de variables) son vacíos (`None`, `NaN`, `""`, espacios).
   * Respeta los ceros válidos (`0`, `0.0`), garantizando que restricciones con coeficientes nulos no se eliminen.
2. **Filtrado en `normalize_constraints`:**
   * Las filas completamente vacías se omiten limpiamente.
   * Las filas con algún valor diligenciado se validan estrictamente y, si están incompletas, lanzan un `ValueError` descriptivo.
3. **Banner Visible en la Interfaz (`streamlit_app.py`):**
   * Se agregó un mensaje de alerta visible (`st.error(...)` / `st.warning(...)`) antes de los botones de acción para explicar con claridad cualquier error de validación.

---

## 3. Pruebas y Validación
* **Suite Pytest (`tests/test_model_io.py` + suites completas):**
  * Total de pruebas: **49 tests (100% PASS en 1.48s)**.
* **Casos Nuevos Añadidos:**
  * `test_is_empty_constraint_row_cases`: Identificación de `None`, `NaN`, cadenas vacías, ceros válidos y filas incompletas.
  * `test_empty_dynamic_constraint_row_filtering`: 2 restricciones válidas + 1 fila vacía $\rightarrow 2$ restricciones normalizadas.
  * `test_partially_filled_constraint_row_produces_clear_error`: Filas incompletas producen error explicativo.
  * `test_mono_model_min_15x1_23x2_with_trailing_empty_row`: Modelo $\min 15x_1+23x_2$ con fila vacía resuelve a $Z^*=0.0$ y persiste exactamente 2 restricciones en JSON.
* **Benchmark A:** `benchmark_a_pyomo.py` 100% PASS verificado.
* **Smoke Test Streamlit:** Carga e inicialización limpias sin errores.
