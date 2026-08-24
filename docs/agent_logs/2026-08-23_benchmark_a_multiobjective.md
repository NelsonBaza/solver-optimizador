# Informe de Agente: Benchmark A — Evaluación Multiobjetivo Exacta con AMPL + HiGHS

* **Fecha de ejecución:** 2026-08-23
* **ID de Registro:** `2026-08-23_benchmark_a_multiobjective`
* **Entorno:** Windows 11 / Server x86_64, Python 3.13.1, `.venv` aislado

---

## 1. Solicitud Recibida

Realizar exclusivamente el **Benchmark A multiobjetivo** sobre el problema biobjetivo lineal continuo académico:
$$\max Z_1 = 10 x_1 + 3 x_2, \quad \max Z_2 = 0.8 x_1 + 1.3 x_2$$
sujeto a $x_1 + x_2 \le 130$, $2.5 x_1 + x_2 \le 250$, $x_1, x_2 \ge 0$.

Se requirió:
1. Optimizar independientemente $Z_1$ y $Z_2$ con HiGHS y construir programáticamente la matriz de pagos.
2. Calcular dinámicamente los rangos de normalización ($Z_1^{\text{range}}, Z_2^{\text{range}}$) sin hardcodear constantes.
3. Ejecutar el barrido de 6 ponderaciones normalizadas $\alpha \in \{(0.0, 1.0), (0.2, 0.8), (0.4, 0.6), (0.6, 0.4), (0.8, 0.2), (1.0, 0.0)\}$.
4. Detectar programáticamente soluciones repetidas y evaluar dominancia de Pareto.
5. Generar gráficos en Matplotlib (espacio de objetivos y región factible) y guardar resultados en JSON.
6. Evaluar la ergonomía de AMPL y documentar hallazgos en `docs/BENCHMARK_A.md`, actualizando `STATUS.md`, `DECISIONS.md` y `agent_logs`.

---

## 2. Implementación

Se implementó el script autónomo [`benchmark_a_multiobjective.py`](../../benchmark_a_multiobjective.py):
* Carga de `amplpy` y módulos `ampl-module-base` y `ampl-module-highs`.
* Declaración del modelo con restricciones y múltiples objetivos en AMPL.
* Resolución independiente de $Z_1$ y $Z_2$, y extracción de valores cruzados en Python.
* Formulación paramétrica del objetivo agregado $W$ en AMPL (`param a1; param a2; param r1; param r2; maximize W: ...`).
* Bucle iterativo de 6 combinaciones de pesos con resolución por HiGHS.
* Algoritmo de detección de duplicados con tolerancia numérica ($10^{-4}$).
* Algoritmo de dominancia de Pareto para maximización simultánea de $(Z_1, Z_2)$.
* Renderizado gráfico de alta resolución con Matplotlib (backend `Agg`):
  * `results/benchmark_a_objective_space.png`
  * `results/benchmark_a_feasible_region.png`
* Exportación de datos estructurados a `results/benchmark_a_results.json`.

---

## 3. Resultados Obtenidos

### Optimización Individual y Matriz de Pagos:
* Óptimo $Z_1$: $x = (100.0, 0.0) \implies Z_1 = 1000.0, Z_2 = 80.0$ (`solved`, 1 simplex iter).
* Óptimo $Z_2$: $x = (0.0, 130.0) \implies Z_1 = 390.0, Z_2 = 169.0$ (`solved`, 2 simplex iters).
* Rangos de normalización:
  * $Z_1^{\text{range}} = 1000.0 - 390.0 = 610.0$
  * $Z_2^{\text{range}} = 169.0 - 80.0 = 89.0$

### Barrido de 6 Ponderaciones Normalizadas:
1. $\alpha=(0.0, 1.0) \implies x=(0.0, 130.0), Z=(390.0, 169.0), W=1.8989$ (`solved`)
2. $\alpha=(0.2, 0.8) \implies x=(0.0, 130.0), Z=(390.0, 169.0), W=1.6470$ (`solved`)
3. $\alpha=(0.4, 0.6) \implies x=(80.0, 50.0), Z=(950.0, 129.0), W=1.4926$ (`solved`)
4. $\alpha=(0.6, 0.4) \implies x=(80.0, 50.0), Z=(950.0, 129.0), W=1.5142$ (`solved`)
5. $\alpha=(0.8, 0.2) \implies x=(80.0, 50.0), Z=(950.0, 129.0), W=1.5358$ (`solved`)
6. $\alpha=(1.0, 0.0) \implies x=(100.0, 0.0), Z=(1000.0, 80.0), W=1.6393$ (`solved`)

### Soluciones Únicas y Clasificación de Pareto:
* **Solución A:** $(x_1=0, x_2=130) \to Z=(390, 169)$ | Ponderaciones: $(0.0, 1.0), (0.2, 0.8)$ | **No dominada**
* **Solución B:** $(x_1=80, x_2=50) \to Z=(950, 129)$ | Ponderaciones: $(0.4, 0.6), (0.6, 0.4), (0.8, 0.2)$ | **No dominada**
* **Solución C:** $(x_1=100, x_2=0) \to Z=(1000, 80)$ | Ponderaciones: $(1.0, 0.0)$ | **No dominada**

---

## 4. Pruebas Realizadas y Comparación con Referencia Académica

Se ejecutaron aserciones numéricas estrictas con tolerancia $\varepsilon = 10^{-4}$ comparando cada paso contra la tabla de referencia académica:
* Validación de óptimos individuales: **100% coincidente**
* Validación de matriz de pagos: **100% coincidente**
* Validación de rangos (610.0 y 89.0): **100% coincidente**
* Validación de las 6 soluciones ponderadas: **100% coincidente**
* Identificación de las 3 soluciones únicas: **100% coincidente**
* Clasificación de no dominancia: **100% coincidente**

---

## 5. Problemas Encontrados y Correcciones

1. **Codificación de Caracteres en Consola de Windows (CP1252):**
   * *Problema:* El intento de imprimir el carácter griego `α` en la terminal causó `UnicodeEncodeError` en Python 3.13 sobre Windows.
   * *Corrección:* Se sustituyó por etiquetas ASCII seguras (`a1`, `a2`) en los `print()` de consola.
2. **Sintaxis de Mathtext en Matplotlib:**
   * *Problema:* Se utilizó `\le` en las etiquetas LaTeX de la leyenda de Matplotlib, provocando `ValueError` en el parser mathtext.
   * *Corrección:* Se cambió a `\leq` y se ajustaron las tuplas de offset en `annotate()`.

---

## 6. Evaluación de AMPL como Plataforma

| Componente del Flujo | Nivel de Soporte en AMPL |
| :--- | :--- |
| Definición y alternancia de objetivos | **Nativo de AMPL** |
| Parametrización y actualización de pesos | **Facilitado por AMPL** |
| Matriz de pagos | **Programado manualmente en Python** |
| Cálculo de rangos de normalización | **Programado manualmente en Python** |
| Detección de soluciones repetidas | **Programado manualmente en Python** |
| Algoritmo de dominancia de Pareto | **Programado manualmente en Python** |
| Renderizado gráfico 2D | **Programado manualmente en Python** |

**Conclusión:** AMPL + HiGHS ofrece un motor solver rápido y limpio para resolver los subproblemas lineales y actualizar parámetros. No obstante, casi toda la lógica metodológica multiobjetivo y de visualización recae en la capa de Python.

---

## 7. Archivos Creados / Modificados

* [`benchmark_a_multiobjective.py`](../../benchmark_a_multiobjective.py) (script ejecutable del benchmark).
* [`results/benchmark_a_results.json`](../../results/benchmark_a_results.json) (exportación estructurada de resultados).
* [`results/benchmark_a_objective_space.png`](../../results/benchmark_a_objective_space.png) (gráfico Z1 vs Z2).
* [`results/benchmark_a_feasible_region.png`](../../results/benchmark_a_feasible_region.png) (gráfico x1 vs x2).
* [`requirements-ampl.txt`](../../requirements-ampl.txt) (inclusión de `matplotlib==3.11.1`).
* [`docs/BENCHMARK_A.md`](../BENCHMARK_A.md) (informe técnico detallado).
* [`docs/STATUS.md`](../STATUS.md) (actualización con estado PASS en Benchmark A).
* [`docs/DECISIONS.md`](../DECISIONS.md) (registro del ADR-006).
* [`docs/agent_logs/2026-08-23_benchmark_a_multiobjective.md`](2026-08-23_benchmark_a_multiobjective.md) (este informe).

---

## 8. Respuesta Final Emitida al Usuario

*(Registrada íntegramente en la entrega del agente al usuario).*
