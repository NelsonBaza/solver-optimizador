# Registro de Saneamiento Final: Adopción Provisional de Pyomo + HiGHS

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Atender los hallazgos de auditoría de la comparativa AMPL vs. Pyomo, formalizar la adopción provisional de Pyomo + HiGHS como backend exacto para la siguiente fase y corregir la precisión conceptual en la documentación técnica.

---

## 1. Solicitud y Contexto
Tras la auditoría externa del checkpoint comparativo (commit `5ee6825254f970a0e0bb8cc518a51c4152e09afc`), se identificaron requerimientos de rigor técnico y simetría:
1. **Rigor en la terminología de Pareto:** Evitar expresiones ambiguas como "obtuvieron la misma frontera de Pareto" y sustituirlas por afirmaciones matemáticamente exactas sobre el conjunto discreto de soluciones no dominadas evaluadas en las 6 ponderaciones.
2. **Contextualización de tiempos de resolución:** Descartar conclusiones categóricas de aceleración (149x, 198x, 200x) y presentar las mediciones como evidencia experimental exploratoria en un microproblema (2 variables, 2 restricciones), destacando que la diferencia principal radica en el menor overhead de comunicación de la interfaz APPSI en memoria.
3. **Inconsistencia de serialización JSON en AMPL:** Corregir el orden de cálculo y guardado de `timing` en `benchmark_a_multiobjective.py` para asegurar que `results/benchmark_a_results.json` contenga la sección `timing`.
4. **Formalización de ADR-007 y actualización de STATUS:** Formalizar `ADR-007: Pyomo + HiGHS como backend exacto provisional` en `docs/DECISIONS.md` conservando a AMPL como backend comparativo, y actualizar `docs/STATUS.md`.

---

## 2. Cambios Realizados

### 2.1 Corrección de Serialización de Tiempos en AMPL
* En `benchmark_a_multiobjective.py`, se reordenó el flujo final:
  1. Cálculo de `t_total_end` y `t_total`.
  2. Inserción de `benchmark_data["timing"]` con `individual_optima_sec`, `weighted_sweep_sec` y `total_sec`.
  3. Escritura del archivo `results/benchmark_a_results.json`.
  4. Impresión por consola.

### 2.2 Reejecución Simétrica y Verificación de JSONs
* Se ejecutaron `verify_ampl_highs.py`, `benchmark_a_multiobjective.py` y `benchmark_a_pyomo.py`.
* Se comprobó mediante script de aserción que ambos JSONs (`results/benchmark_a_results.json` y `results/benchmark_a_pyomo_results.json`) coinciden de forma idéntica al 100% en:
  * Óptimos individuales ($Z_1^*$ y $Z_2^*$).
  * Matriz de pagos.
  * Rangos de normalización ($\Delta Z_1 = 610, \Delta Z_2 = 89$).
  * 6 corridas de ponderaciones.
  * Soluciones únicas identificadas ($A, B, C$).
  * Clasificación de no dominancia de Pareto.
  * Ambos contienen ahora su bloque `timing` correspondiente.

### 2.3 Saneamiento de Lenguaje en `docs/BENCHMARK_A_BACKEND_COMPARISON.md`
* Se sustituyó cualquier referencia general a "la misma frontera de Pareto" por:
  > *Ambos backends obtuvieron exactamente el mismo conjunto discreto de soluciones no dominadas para las seis ponderaciones evaluadas.*
* Se incorporó la advertencia teórica explícita sobre las limitaciones del método de suma ponderada (no garantiza recuperar toda la frontera eficiente en problemas generales).
* Se eliminaron las afirmaciones de velocidad categórica y se reformuló el análisis:
  > *El Benchmark A es un microproblema de 2 variables y 2 restricciones. Las diferencias relativas observadas reflejan principalmente el overhead de inicialización y comunicación del backend y no deben extrapolarse a modelos reales o de gran escala.*
  > *Conclusión válida: Pyomo + APPSI mostró menor overhead observado en este microbenchmark.*

### 2.4 Formalización de Decisiones y Estado
* Se actualizó `docs/DECISIONS.md` estructurando formalmente `ADR-007: Pyomo + HiGHS como backend exacto provisional` con secciones de Evidencia, Decisión y Condición de Provisionalidad (conservando a AMPL como referencia).
* Se actualizó `docs/STATUS.md` reflejando las designaciones de rol:
  * **Backend exacto provisional:** `Pyomo + HiGHS`
  * **Backend comparativo validado:** `AMPL + HiGHS`
  * **Próximo hito:** `Método epsilon-restricciones con Pyomo + HiGHS`

---

## 3. Tiempos Observados en esta Ejecución Exploratoria

| Fase | AMPL + HiGHS | Pyomo + HiGHS (APPSI) |
| :--- | :---: | :---: |
| **Solves individuales ($Z_1^* + Z_2^*$)** | 1,394.5 ms | 9.5 ms |
| **Barrido de 6 ponderaciones** | 4,189.1 ms | 27.9 ms |
| **Tiempo total interno benchmark** | 6,094.4 ms | 37.6 ms |

---

## 4. Archivos Modificados
1. `benchmark_a_multiobjective.py` (orden de serialización de timing).
2. `results/benchmark_a_results.json` (incorporación de timing).
3. `results/benchmark_a_pyomo_results.json` (actualización de timing en nueva ejecución).
4. `docs/BENCHMARK_A_BACKEND_COMPARISON.md` (saneamiento conceptual de Pareto y tiempos).
5. `docs/DECISIONS.md` (formalización de ADR-007).
6. `docs/STATUS.md` (roles de backends y próximo hito).
7. `docs/agent_logs/2026-08-23_finalize_pyomo_provisional_backend.md` (este registro).
