# Registro de Implementación: Corrección Conceptual de Interpretación Biobjetivo según Sentido MAX/MIN

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Hacer que el módulo de interpretación multiobjetivo (`src/solver_optimizador/interpretation.py`) sea estrictamente consciente del sentido (MAX/MIN) de cada función objetivo en todas sus combinaciones (MAX/MAX, MAX/MIN, MIN/MAX, MIN/MIN), evitando asunciones implícitas de maximización y sobregeneralizaciones sobre estabilidad.

---

## 1. Problemas Conceptuales Abordados
1. **Asunción de Maximización en Óptimos Individuales:**
   * Frases previas usaban "priorizar Z1 al máximo" o "reduce Z2" de forma genérica sin considerar si el objetivo era de minimización.
2. **Identificación Incorrecta de Extremos Favorables:**
   * Se determinaba la solución favorable a $Z_1$ únicamente ordenando por valor numérico ascendente/descendente sin verificar si $Z_1$ o $Z_2$ eran MIN.
3. **Sobregeneralización de Estabilidad:**
   * Se afirmaba que una solución obtenida con múltiples pesos era "óptima frente a un rango amplio de preferencias relativas", lo cual era una extrapolación indebida a partir de un barrido discreto finito.

---

## 2. Correcciones Implementadas
* **Consciencia de Sentido (MAX/MIN):**
  * Se evalúa `problem.objective1.sense` y `problem.objective2.sense`.
  * Se expresa con claridad el verbo adecuado ("al maximizar $Z_1$", "al minimizar $Z_2$") y su impacto en la matriz de pagos.
* **Evaluación Rigurosa de Extremos:**
  * Para MAX: la solución más favorable es aquella con el mayor valor de $Z_k$.
  * Para MIN: la solución más favorable es aquella con el menor valor de $Z_k$.
* **Redacción Precisa de Estabilidad:**
  * Sustituida por: *"El hecho de que varias ponderaciones evaluadas produzcan la misma solución (...) indica que dicha alternativa resulta óptima para varias de las preferencias discretas analizadas en el barrido."*
* **Aviso de Rigor Metodológico:**
  * Recuerda que la interpretación describe exclusivamente el conjunto discreto evaluado para las ponderaciones analizadas.

---

## 3. Pruebas Unitarias Implementadas
En `tests/test_interpretation.py` se ampliaron las pruebas a 8 casos:
* `test_interpret_mono_optimal`: PASS
* `test_interpret_mono_infeasible`: PASS
* `test_interpret_mono_unbounded`: PASS
* `test_interpret_biobjective_max_max`: PASS (Benchmark A)
* `test_interpret_biobjective_max_min`: PASS (Distingue MAX y MIN)
* `test_interpret_biobjective_min_max`: PASS (Distingue MIN y MAX)
* `test_interpret_biobjective_min_min`: PASS (Evalúa ambos extremos como mínimos)
* `test_interpret_biobjective_stability_phrasing`: PASS (Verifica ausencia de sobregeneralizaciones)

**Total Suite pytest:** **27 tests (100% PASS)**.

---

## 4. Benchmark A y Smoke Test
* **Benchmark A (`benchmark_a_pyomo.py`):** 100% PASS, manteniendo exactas las 3 soluciones no dominadas $(390, 169)$, $(950, 129)$ y $(1000, 80)$.
* **Streamlit Smoke Test:** Carga limpia sin excepciones ni advertencias de deprecación.
