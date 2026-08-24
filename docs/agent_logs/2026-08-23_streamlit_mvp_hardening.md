# Registro de Implementación: Hardening del MVP Streamlit antes de Uso Docente

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Resolver los hallazgos de auditoría del MVP Streamlit y robustecer el motor matemático para garantizar estabilidad total en pruebas docentes reales con problemas monoobjetivo (MAX/MIN) y biobjetivo (MAX/MAX, MAX/MIN, MIN/MIN).

---

## 1. Solicitud y Auditoría Inicial
* **Baseline inicial:** 6 pruebas unitarias aprobadas en `tests/test_lp_core.py`.
* **Hallazgos a corregir:**
  1. Desincronización entre `session_state` y widgets de Streamlit al cargar ejemplos predefinidos.
  2. Nomenclatura no neutral (`Z1_max`, `Z2_max`) en problemas con sentido de minimización.
  3. Ausencia de pruebas formales para sentidos de minimización (`MIN`, `MAX/MIN`, `MIN/MIN`).
  4. Tratamiento implícito de rango nulo ($\Delta Z = 0$) mediante sustitución de factor unitario.
  5. Riesgo de errores con caracteres especiales en nombres de restricciones en Pyomo (`c_{i}_{c.name}`).
  6. Asignación indeterminada de ceros en corridas multiobjetivo fallidas.
  7. Riesgo de trazar polígonos no acotados o degenerados en gráficos 2D.
  8. Ausencia de validación estricta de números finitos (`NaN`, `inf`, `-inf`).

---

## 2. Archivos Modificados y Creados
* **`src/solver_optimizador/lp_models.py`:** Incorporación de helper `is_finite_number()` y validaciones de valores finitos en `LPProblem` y `BiobjectiveProblem`.
* **`src/solver_optimizador/__init__.py`:** Exportación de `is_finite_number`.
* **`src/solver_optimizador/lp_solver.py`:** Uso de identificadores seguros de restricciones `con_{i}` en Pyomo.
* **`src/solver_optimizador/multiobjective.py`:**
  * Nomenclatura neutral `Z1_opt` y `Z2_opt`.
  * Detección y detención controlada ante rango nulo ($\Delta Z_k < 10^{-7}$).
  * Manejo estricto de corridas no óptimas (`x = None`, `Z1 = None`, `Z2 = None`, `W = None`).
  * Asignación segura de restricciones en Pyomo.
* **`src/solver_optimizador/plotting.py`:** Validación de finitud, verificación de $\ge 3$ vértices sin restricciones de igualdad antes de sombrear polígonos factibles.
* **`streamlit_app.py`:** Sincronización completa con `_clear_widget_keys()` y control de versiones del editor `editor_version`. Validación de finitud y presentación de advertencias de rango nulo.
* **`tests/test_lp_core.py`:** Expansión exhaustiva de la suite a 12 pruebas unitarias.
* **`docs/UI_MVP_HARDENING.md`:** Informe técnico de hardening.
* **`docs/UI_MVP_VALIDATION.md`:** Actualización de matriz de pruebas y pendientes realistas.
* **`docs/STATUS.md`** y **`README.md`:** Actualización de estado y documentación.

---

## 3. Pruebas Automatizadas y Smoke Test
* **Ejecución de pytest:** `.\.venv\Scripts\python.exe -m pytest -v`
  * 12 pruebas ejecutadas, **12 aprobadas (100% PASS en 1.03 s)**.
* **Smoke Test de Streamlit:** Importación y carga sin excepciones ni errores de contexto.

---

## 4. Estado de los Casos Exigidos
1. **Monoobjetivo MIN:** Verificado con $\text{MIN } x_1 + 2x_2 \implies x^* = (3, 1), Z^* = 5.0$.
2. **Biobjetivo MAX/MIN:** Verificado con MAX $2x_1+x_2$, MIN $x_1+3x_2$ en $x_1+x_2 \le 4$. Óptimos en $(4,0)$ y $(0,0)$, rangos $(8, 4)$, ponderaciones y dominancia válidas.
3. **Biobjetivo MIN/MIN:** Verificado con MIN $2x_1+x_2$, MIN $x_1+2x_2$ en $x_1+x_2 \ge 4$. Óptimos en $(0,4)$ y $(4,0)$, rangos $(4, 4)$, no dominadas.
4. **Rango Cero:** Detención controlada con nota explicativa metodológica, sin división por cero ni falsos $W$.
5. **Benchmark A:** Totalmente intacto, reproduciendo las 3 soluciones no dominadas exactas.
