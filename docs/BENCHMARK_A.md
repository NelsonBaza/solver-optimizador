# Benchmark A — Evaluación Multiobjetivo Exacta con AMPL + HiGHS

Este documento describe la formulación, metodología, resultados numéricos, análisis de Pareto y conclusiones técnicas del **Benchmark A**, diseñado para evaluar el desempeño de **AMPL**, **amplpy** y el solver gratuito **HiGHS** en la resolución multiobjetivo mediante el método académico de suma ponderada normalizada.

---

## 1. Definición del Problema de Referencia

El problema evaluado corresponde a un modelo de programación lineal continua biobjetivo estándar:

### Variables de Decisión:
$$x_1 \ge 0, \quad x_2 \ge 0$$

### Restricciones del Espacio de Búsqueda:
$$\begin{aligned}
c_1: & \quad x_1 + x_2 \le 130 \\
c_2: & \quad 2.5 x_1 + x_2 \le 250
\end{aligned}$$

### Funciones Objetivo:
$$\begin{aligned}
\text{Maximizar } & Z_1(x) = 10 x_1 + 3 x_2 \\
\text{Maximizar } & Z_2(x) = 0.8 x_1 + 1.3 x_2
\end{aligned}$$

---

## 2. Etapa 1: Optimización Individual y Matriz de Pagos

Cada objetivo se resolvió de forma independiente utilizando HiGHS dentro de la misma sesión de AMPL:

### Resultados de Optimización Individual:
1. **Optimización de $Z_1$:**
   * Solución óptima: $x^{*(1)} = (100.0, 0.0)$
   * Valor de $Z_1$: $1000.0$ (valor ideal de $Z_1$)
   * Valor cruzado de $Z_2$: $80.0$
   * Estado: `solved` (HiGHS 1.15.1, 1 iteración simplex)

2. **Optimización de $Z_2$:**
   * Solución óptima: $x^{*(2)} = (0.0, 130.0)$
   * Valor cruzado de $Z_1$: $390.0$
   * Valor de $Z_2$: $169.0$ (valor ideal de $Z_2$)
   * Estado: `solved` (HiGHS 1.15.1, 2 iteraciones simplex)

### Matriz de Pagos (*Payoff Matrix*):
$$\begin{pmatrix} 
Z_1(x^{*(1)}) & Z_2(x^{*(1)}) \\ 
Z_1(x^{*(2)}) & Z_2(x^{*(2)}) 
\end{pmatrix} = \begin{pmatrix} 
1000.0 & 80.0 \\ 
390.0 & 169.0 
\end{pmatrix}$$

### Cálculo Dinámico de Rangos de Normalización:
$$\begin{aligned}
Z_1^{\text{range}} &= Z_1^{\max} - Z_1^{\min} = 1000.0 - 390.0 = 610.0 \\
Z_2^{\text{range}} &= Z_2^{\max} - Z_2^{\min} = 169.0 - 80.0 = 89.0
\end{aligned}$$

---

## 3. Etapa 2: Método de Suma Ponderada Normalizada

Se formuló la función objetivo agregada normalizada:
$$N_1=\frac{Z_1-390}{610},\qquad N_2=\frac{Z_2-80}{89}$$
$$\max W = \alpha_1N_1+\alpha_2N_2 \quad \text{con } \alpha_1 + \alpha_2 = 1, \; \alpha_k \ge 0$$

### Barrido de Ponderaciones (6 Combinaciones):

| Ejecución | $\alpha_1$ | $\alpha_2$ | $x_1$ | $x_2$ | $Z_1$ Original | $Z_2$ Original | Valor Agregado $W$ | Estado Solver |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | $0.0$ | $1.0$ | $0.0$ | $130.0$ | $390.0$ | $169.0$ | $1.0000$ | `solved` |
| **2** | $0.2$ | $0.8$ | $0.0$ | $130.0$ | $390.0$ | $169.0$ | $0.8000$ | `solved` |
| **3** | $0.4$ | $0.6$ | $80.0$ | $50.0$ | $950.0$ | $129.0$ | $0.6976$ | `solved` |
| **4** | $0.6$ | $0.4$ | $80.0$ | $50.0$ | $950.0$ | $129.0$ | $0.7710$ | `solved` |
| **5** | $0.8$ | $0.2$ | $80.0$ | $50.0$ | $950.0$ | $129.0$ | $0.8445$ | `solved` |
| **6** | $1.0$ | $0.0$ | $100.0$ | $0.0$ | $1000.0$ | $80.0$ | $1.0000$ | `solved` |

Los JSON de `results/` fueron generados antes de Fase 2B y se conservan como
artefactos históricos con su definición legacy identificada en metadatos. La
referencia vigente y reproducible está en `tools/audit/verify_weighted_method_exact.py`.

---

## 4. Análisis de Soluciones Únicas y Dominancia de Pareto

### Detección de Soluciones Repetidas:
El barrido de 6 ponderaciones colapsó en exactamente **3 soluciones únicas** en el espacio de variables y objetivos:
* **Solución A:** $(x_1=0, x_2=130) \implies Z=(390, 169)$ generada por $\alpha \in \{(0.0, 1.0), (0.2, 0.8)\}$.
* **Solución B:** $(x_1=80, x_2=50) \implies Z=(950, 129)$ generada por $\alpha \in \{(0.4, 0.6), (0.6, 0.4), (0.8, 0.2)\}$.
* **Solución C:** $(x_1=100, x_2=0) \implies Z=(1000, 80)$ generada por $\alpha \in \{(1.0, 0.0)\}$.

### Comprobación Algorítmica de Dominancia de Pareto:
Para ambos objetivos a maximizar:
* Solución A vs B: $Z_1(A) < Z_1(B)$ ($390 < 950$), pero $Z_2(A) > Z_2(B)$ ($169 > 129$) $\implies$ **No dominada**.
* Solución B vs C: $Z_1(B) < Z_1(C)$ ($950 < 1000$), pero $Z_2(B) > Z_2(C)$ ($129 > 80$) $\implies$ **No dominada**.
* Solución A vs C: $Z_1(A) < Z_1(C)$ ($390 < 1000$), pero $Z_2(A) > Z_2(C)$ ($169 > 80$) $\implies$ **No dominada**.

**Resultado:** Las 3 soluciones únicas encontradas son rigurosamente **No Dominadas**.

---

## 5. Visualización de Resultados

Se generaron los siguientes gráficos guardados en `results/`:
1. **Espacio de Objetivos ($Z_1$ vs. $Z_2$):** [`results/benchmark_a_objective_space.png`](../results/benchmark_a_objective_space.png)
   * Muestra los puntos de las 6 ejecuciones ponderadas, los 3 puntos no dominados y la línea de aproximación discreta.
2. **Región Factible ($x_1$ vs. $x_2$):** [`results/benchmark_a_feasible_region.png`](../results/benchmark_a_feasible_region.png)
   * Muestra las restricciones lineales, el polígono factible y la ubicación de los vértices correspondientes a las soluciones A, B y C.

---

## 6. Evaluación de AMPL como Plataforma de Optimización

Para evaluar objetivamente cuánto trabajo reduce AMPL en comparación con la programación necesaria en Python, se clasificaron las etapas del benchmark:

| Tarea del Benchmark | Clasificación | Justificación Técnica |
| :--- | :---: | :--- |
| **Definición y Cambio de Objetivos** | **Nativo de AMPL** | AMPL permite declarar múltiples objetivos (`maximize Obj1`, `maximize Obj2`) y alternar entre ellos con `objective Obj1; solve;` sin regenerar el modelo algebraico. |
| **Construcción de Matriz de Pagos** | **Programado manualmente** | AMPL no ofrece un comando automático para matriz de pagos; se requiere orquestación en Python. |
| **Cálculo de Rangos de Normalización** | **Programado manualmente** | Requiere extraer los máximos/mínimos de la matriz y computar los denominadores en Python. |
| **Parametrización de Ponderaciones** | **Facilitado por AMPL** | El uso de parámetros simbólicos (`param a1; param a2;`) permite reoptimizar instantáneamente modificando valores sin recompilar matrices. |
| **Detección de Soluciones Repetidas** | **Programado manualmente** | Requiere implementar comparación de vectores de decisión y objetivos con tolerancia numérica en Python. |
| **Filtro de Dominancia de Pareto** | **Programado manualmente** | El motor de AMPL no clasifica frentes de Pareto; la comparación de no dominancia debe codificarse algorítmicamente en Python. |
| **Visualización y Gráficos** | **Programado manualmente** | AMPL carece de subsistema de renderizado gráfico integrado; requiere Matplotlib. |

### Balance de Ergonomía:
* **Líneas de código:** El script completo [`benchmark_a_multiobjective.py`](../benchmark_a_multiobjective.py) contiene ~380 líneas (incluyendo validaciones estrictas, exportación JSON y generación de dos gráficos de alta resolución). La lógica central de interacción con AMPL ocupa ~70 líneas.
* **Ventajas de AMPL:** Parametrización limpia, presolve veloz y cambio rápido de objetivos.
* **Limitaciones de AMPL para la suite:** Toda la lógica de análisis multiobjetivo (matriz de pagos, normalización, dominancia, filtrado de repetidos, gráficos y exportaciones) debe implementarse en Python de cualquier forma.

---

## 7. Limitaciones Teóricas del Método de Suma Ponderada

Como observación académica obligatoria:
1. **Soluciones no soportadas:** La suma ponderada solo puede identificar soluciones en la envoltura convexa de la frontera de Pareto. En problemas con fronteras no convexas (que se estudiarán en fases posteriores), el método de ponderaciones no puede recuperar soluciones situadas en zonas cóncavas.
2. **Soluciones repetidas:** Múltiples combinaciones de pesos pueden converger al mismo vértice del politopo (como ocurrió en este benchmark, donde 6 pesos produjeron solo 3 soluciones distintas).
3. **Aproximación finita:** Un conjunto discreto de ponderaciones proporciona una muestra puntual y no garantiza haber identificado la totalidad de la frontera eficiente continua.
