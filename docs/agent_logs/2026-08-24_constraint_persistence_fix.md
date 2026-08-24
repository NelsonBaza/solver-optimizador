# Registro de Implementación: Normalización Canónica de Restricciones y Corrección de Persistencia

**Fecha:** 24 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Corregir la pérdida de coeficientes de restricciones durante la exportación JSON mediante normalización canónica obligatoria, eliminar valores por defecto silenciosos y unificar la representación de restricciones para resolución, firma y persistencia.

---

## 1. Evidencia y Causa Raíz
* **Bug Detectado:** En modelos creados en la UI, el JSON descargado guardaba `"coefficients": {"x1": 0.0, "x2": 0.0}` y `"rhs": 0.0`.
* **Causa Raíz:** Incompatibilidad de claves entre el DataFrame plano de `st.data_editor` (`Nombre, x1, x2, Operador, RHS`) y la serialización JSON que esperaba la estructura anidada `c["coefficients"]`. Al no encontrarse las claves esperadas, los métodos `.get()` caían en `0.0`.

---

## 2. Solución Aplicada
* **Función Canónica:** `normalize_constraints(raw_constraints, var_names)` en `src/solver_optimizador/model_io.py`.
* **Unificación de Flujos:** `streamlit_app.py` normaliza las restricciones una sola vez y pasa la lista canónica al solver, al cálculo de firma y a la serialización.
* **Manejo Estricto de Errores:** Se bloquea la descarga y la resolución si alguna restricción tiene formato inválido o carece de operador o RHS.

---

## 3. Pruebas y Verificación
* **Pytest Suite:** 45 pruebas unitarias e integración aprobadas al 100% en 1.51s.
* **Caso Específico:** $\max 10x_1 + 15x_2$ con $5x_1+4x_2 \le 15$ y $3x_1+x_2 \le 20$ verificado con preservación exacta de coeficientes, firma y valor óptimo.
* **Caso 24 Variables:** Caso hidroeléctrico completo round-trip evaluado en formato UI plano, obteniendo $Z^* = 6701.25$ antes y después.
* **Benchmark A:** `benchmark_a_pyomo.py` 100% PASS intacto.
