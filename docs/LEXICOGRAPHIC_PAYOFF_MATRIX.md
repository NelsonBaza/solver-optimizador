# Desempate Lexicográfico y Matriz de Pagos Eficiente en Optimización Biobjetivo

> [!IMPORTANT]
> **Documento histórico.** Describe la motivación del mecanismo secundario que
> selecciona representantes para las anclas de la matriz de pagos. Desde Fase
> 2B, la especificación normativa del método que genera alternativas es
> [`METODO_PONDERACIONES.md`](METODO_PONDERACIONES.md): todas las corridas,
> incluidos los pesos extremos, resuelven la suma ponderada normalizada. Este
> documento no debe interpretarse como definición de un método híbrido ni como
> prueba general de unicidad o multiplicidad.

**Fecha:** 24 de agosto de 2026  
**Módulos:** `src/solver_optimizador/multiobjective.py`, `src/solver_optimizador/interpretation.py`, `streamlit_app.py`

---

## 1. Concepto: El Problema de los Múltiples Óptimos Individuales

En programación multiobjetivo, el primer paso clásico del **método de ponderaciones normalizadas** consiste en calcular la **matriz de pagos** (*payoff matrix*), resolviendo cada objetivo por separado para identificar sus óptimos individuales ($Z_1^*, Z_2^*$) y los valores cruzados correspondientes.

Sin embargo, cuando la función objetivo individual es paralela a una arista o cara de la región factible, existe un **conjunto continuo de múltiples soluciones óptimas**. Un solver LP estándar como HiGHS devuelve un vértice arbitrario de dicha cara.

### ¿Por qué esto es problemático?
Si el solver devuelve un vértice donde el objetivo principal alcanza su óptimo pero el objetivo secundario toma un valor muy desfavorable, dicha solución resulta **débilmente dominada** por otro punto de la misma cara que logra el mismo valor óptimo principal pero con un valor sustancialmente mejor en el objetivo secundario.

Incluir un extremo dominado en la matriz de pagos:
1. **Infla artificialmente el rango de normalización** ($\Delta Z = Z_{\max} - Z_{\min}$).
2. **Distorsiona la escala de los pesos ponderados** ($\alpha_1, \alpha_2$).
3. **Provoca que el barrido genere soluciones dominadas** en las ponderaciones extremas ($\alpha_1 = 0$ o $\alpha_2 = 0$).

---

## 2. Regla histórica de selección secundaria de anclas

Para evitar escoger un representante débilmente dominado en el caso documentado,
se implementó una selección secundaria en dos etapas para cada ancla. En el
flujo vigente se trata exclusivamente como preprocesamiento de la matriz de
pagos: no genera alternativas ponderadas y no demuestra por sí sola que un
óptimo individual sea único o múltiple.

### Procedimiento para el Extremo $Z_1$:
1. **Paso Primario:** Resolver $\text{Opt } Z_1$ sujeto a las restricciones originales del problema $\rightarrow Z_1^*$.
2. **Paso Secundario:** Fijar el valor del objetivo primario mediante una restricción de cota:
   * Si $Z_1$ es **MIN**: $\sum c_{1,j} x_j \le Z_1^* + \text{tol}$ (con igualdad exacta $\sum c_{1,j} x_j = Z_1^*$ en primera instancia).
   * Si $Z_1$ es **MAX**: $\sum c_{1,j} x_j \ge Z_1^* - \text{tol}$ (con igualdad exacta $\sum c_{1,j} x_j = Z_1^*$).
3. **Optimización Secundaria:** Optimizar el objetivo secundario $Z_2$ según su propio sentido ($\text{MAX } Z_2$ o $\text{MIN } Z_2$).
4. **Resultado:** El vector obtenido es el **extremo eficiente lexicográfico de $Z_1$**.

### Procedimiento para el Extremo $Z_2$:
1. **Paso Primario:** Resolver $\text{Opt } Z_2 \rightarrow Z_2^*$.
2. **Paso Secundario:** Fijar $Z_2 = Z_2^*$ (o cota correspondiente según MAX/MIN).
3. **Optimización Secundaria:** Optimizar $Z_1$ según su propio sentido.
4. **Resultado:** El vector obtenido es el **extremo eficiente lexicográfico de $Z_2$**.

---

## 3. Demostración en el Caso Real Hidroeléctrico (24 Variables, 28 Restricciones)

### Formulación:
* **$Z_1$ (Costo térmico):** $\text{MIN } Z_1 = 100 GT_1 + 100 GT_2 + 100 GT_3 + 100 GT_4$.
* **$Z_2$ (Almacenamiento final):** $\text{MAX } Z_2 = V_4$.

### Comparativa: Sin Desempate vs. Con Desempate Lexicográfico

| Métrica | Sin Desempate (Ingenuo) | Con Desempate Lexicográfico (Corregido) |
| :--- | :---: | :---: |
| **Óptimo $Z_2^*$** | $V_4 = 100.0$ | $V_4 = 100.0$ |
| **Punto obtenido para $Z_2$** | $(Z_1 = 30000.0, Z_2 = 100.0)$ ❌ *Dominado* | **$(Z_1 = 21416.25, Z_2 = 100.0)$** ✅ *No dominado* |
| **Punto obtenido para $Z_1$** | $(Z_1 = 6701.25, Z_2 = 40.0)$ | $(Z_1 = 6701.25, Z_2 = 40.0)$ |
| **Rango $\Delta Z_1$** | $30000.0 - 6701.25 = \mathbf{23298.75}$ | $21416.25 - 6701.25 = \mathbf{14715.00}$ |
| **Rango $\Delta Z_2$** | $100.0 - 40.0 = \mathbf{60.00}$ | $100.0 - 40.0 = \mathbf{60.00}$ |

### Matriz de Pagos Eficiente Resultante:
$$\begin{pmatrix} \text{Extremo } Z_1 & Z_1 = 6701.25 & Z_2 = 40.00 \\ \text{Extremo } Z_2 & Z_1 = 21416.25 & Z_2 = 100.00 \end{pmatrix}$$

---

## 4. Resultados del Barrido de Ponderaciones Normalizadas

Con los rangos correctos ($\Delta Z_1 = 14715, \Delta Z_2 = 60$), la función escalarizada normalizada:
$$W = \alpha_1 \frac{21416.25 - Z_1}{14715} + \alpha_2 \frac{Z_2 - 40}{60}$$
produce los siguientes resultados rigurosos:

| $\alpha_1$ | $\alpha_2$ | $Z_1$ (Costo) | $Z_2$ (Volumen) | Clasificación Pareto |
| :---: | :---: | :---: | :---: | :---: |
| **0.0** | **1.0** | $21416.25$ | $100.0$ | No dominada |
| **0.2** | **0.8** | $21416.25$ | $100.0$ | No dominada |
| **0.4** | **0.6** | $21416.25$ | $100.0$ | No dominada |
| **0.6** | **0.4** | $6701.25$ | $40.0$ | No dominada |
| **0.8** | **0.2** | $6701.25$ | $40.0$ | No dominada |
| **1.0** | **0.0** | $6701.25$ | $40.0$ | No dominada |

### Caso particular documentado $\alpha = (0.50, 0.50)$

Para este modelo hidroeléctrico concreto, la relación documentada
$Z_1=245.25Z_2-3108.75$ implica que $W=0.5$ sobre la frontera eficiente. Esta
conclusión procede de la ecuación del caso, no del mero hecho de usar pesos
iguales. La aplicación vigente no presenta una afirmación general de
degeneración o unicidad; ese diagnóstico formal permanece abierto en
`AUD-HIGH-02`.
