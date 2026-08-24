# Registro de Implementación: Detección de Resultados Desactualizados tras Modificar el Modelo

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Implementar una huella/firma determinista del modelo matemático (`build_model_signature`) para detectar en tiempo real si los resultados almacenados en `st.session_state` quedaron desactualizados debido a modificaciones en los parámetros del problema.

---

## 1. Problema Abordado
* **Riesgo UX:** Al persistir `last_solution` en `st.session_state` para evitar recalcular innecesariamente al navegar entre pestañas o gráficos, si el usuario modificaba un coeficiente, sentido, restricción o peso sin pulsar "Resolver", la pestaña de resultados seguía mostrando la solución del modelo previo sin advertencia.
* **Solución:** Implementación de una firma determinista canónica (`build_model_signature`) basada en SHA-256 de los parámetros matemáticos. Al resolver, se almacena `last_solution_signature`. En cada re-renderizado, si `current_model_signature != last_solution_signature`, se marca el estado como desactualizado con una advertencia visual prominente sin destruir la solución previa.

---

## 2. Enfoque y Campos Incluidos en la Firma
* **Módulo creado:** `src/solver_optimizador/signature.py` con la función `build_model_signature`.
* **Campos incluidos en la firma:**
  * `problem_type`: Tipo de problema ("Monoobjetivo" / "Biobjetivo").
  * `var_names`: Lista ordenada de nombres de variables activas.
  * Sentidos de objetivos: `obj_sense` (Mono) o `obj1_sense`, `obj2_sense` (Bio).
  * Coeficientes de objetivos: Diccionarios de coeficientes por variable.
  * Restricciones: Lista ordenada de tuplas con nombre, operador, RHS y coeficientes por variable.
  * Parámetros multiobjetivo: `mo_mode`, `num_weights` (si barrido) o `custom_a1` (si ponderación única).
* **Elementos excluidos (sin impacto matemático):**
  * `editor_version`, claves dinámicas de widgets, marcas de tiempo, estados de apertura de expanders o cambio de pestañas.

---

## 3. Pruebas Unitarias Implementadas
Se creó `tests/test_model_signature.py` con 7 pruebas específicas:
1. `test_signature_deterministic_equality`: Formulaciones idénticas producen el mismo SHA-256 (64 caracteres).
2. `test_signature_changes_on_objective_coefficient`: Modificar un coeficiente de $Z$ altera la firma.
3. `test_signature_changes_on_objective_sense`: Cambiar de MAX a MIN altera la firma.
4. `test_signature_changes_on_constraint_rhs`: Modificar el RHS de una restricción altera la firma.
5. `test_signature_changes_on_constraint_operator`: Cambiar operador ($\le$ a $\ge$) altera la firma.
6. `test_signature_changes_on_multiobjective_weights`: Cambiar número de pesos o $\alpha_1$ altera la firma.
7. `test_signature_changes_on_variable_count`: Cambiar número o nombres de variables altera la firma.

**Total suite pytest:** 19 pruebas ejecutadas, **19 aprobadas (100% PASS)**.

---

## 4. Comportamiento en la Interfaz (Smoke Test)
* **Caso 1:** Cargar Ejemplo 1 $\rightarrow$ Resolver $\implies$ `Estado del modelo: ✅ Resultados actualizados`.
* **Caso 2:** Modificar coeficiente de $x_1$ de 3 a 4 $\implies$ La pestaña de resultados muestra inmediatamente el banner:
  > *"⚠️ **Resultados desactualizados:** El modelo fue modificado después de la última resolución. Pulse 'Resolver Modelo con Pyomo + HiGHS' en la pestaña de formulación para actualizar los resultados."*  
  > `Estado del modelo: ⚠️ Resultados pendientes de recalcular (mostrando resultados de la última resolución calculada)`.
* **Caso 3:** Pulsar Resolver $\implies$ Vuelve a `✅ Resultados actualizados`.
* **Caso 4:** Navegar entre pestañas o cambiar de vista $\implies$ Permanece `✅ Resultados actualizados` sin invalidación espuria.
* **Caso 5:** Benchmark A $\rightarrow$ Cambiar $\alpha_1$ o número de combinaciones $\implies$ Se marca desactualizado hasta volver a resolver.
