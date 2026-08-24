# Registro de Implementación: Desempate Lexicográfico y Matriz de Pagos Eficiente

**Fecha:** 24 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Implementar desempate lexicográfico para la resolución de óptimos individuales con múltiples soluciones en problemas biobjetivo, garantizando que la matriz de pagos utilice exclusivamente extremos Pareto-eficientes no dominados y calcule rangos de normalización precisos.

---

## 1. Problema Conceptual
En el modelo hidrotérmico biobjetivo de 24 variables y 28 restricciones:
* $Z_1 = \text{MIN costo térmico} = \sum 100 GT_t$
* $Z_2 = \text{MAX volumen final} = V_4$

Al optimizar $Z_2$ aisladamente, existen múltiples soluciones óptimas con $V_4 = 100.0$. El solver devolvía arbitrariamente una solución con $Z_1 = 30000.0$. Aunque $Z_2=100.0$ es óptimo, el punto $(30000.0, 100.0)$ está débilmente dominado por $(21416.25, 100.0)$. Su inclusión en la matriz de pagos generaba un rango inflado $\Delta Z_1 = 23298.75$ (en lugar de $14715.0$), distorsionando las ponderaciones.

---

## 2. Causa Raíz
La optimización monoobjetivo directa de $Z_2$ no tenía incentivo para minimizar $Z_1$ sobre la cara óptima donde $V_4 = 100$. La matriz de pagos tomaba directamente los valores del primer vértice simplex devuelto.

---

## 3. Algoritmo Implementado (`solve_lexicographic_extreme`)
Para cada objetivo primario ($Z_k$ con $k \in \{1, 2\}$):
1. **Fase 1:** Resolver $\text{Opt } Z_k$ sobre el poliedro factible original $\rightarrow Z_k^*$.
2. **Fase 2:** Fijar $Z_k = Z_k^*$ mediante restricción de igualdad exacta (con fallback acotado por tolerancia $\le Z_k^* + \text{tol}$ para MIN o $\ge Z_k^* - \text{tol}$ para MAX).
3. **Fase 3:** Optimizar el objetivo secundario $Z_{3-k}$ según su propio sentido.
4. **Fase 4:** Retornar el vector de variables del extremo eficiente lexicográfico.

---

## 4. Tolerancia Numérica
* Restricción primaria resuelta en igualdad exacta por simplex HiGHS.
* Fallback de tolerancia numérica defensiva fijado en $\text{tol} = 10^{-6}$ (alineado con la tolerancia primal de HiGHS $10^{-7}$).

---

## 5. Matriz de Pagos: Antes vs. Después (Caso Hidroeléctrico)

### Antes (Ingenua):
```text
                     Z1 (MIN)      Z2 (MAX)
Extremo Z1           6701.25          40.0
Extremo Z2          30000.00         100.0   (Dominado por 21416.25, 100.0)
Rangos: Delta Z1 = 23298.75, Delta Z2 = 60.0
```

### Después (Lexicográfica Eficiente):
```text
                     Z1 (MIN)      Z2 (MAX)
Extremo Z1           6701.25          40.0   (Óptimo único)
Extremo Z2          21416.25         100.0   (Desempate lexicográfico con MIN Z1)
Rangos: Delta Z1 = 14715.00, Delta Z2 = 60.0
```

---

## 6. Resultados del Barrido Ponderado (6 Pesos)
* $\alpha = (0.0, 1.0) \rightarrow (21416.25, 100.0)$ [No dominada]
* $\alpha = (0.2, 0.8) \rightarrow (21416.25, 100.0)$ [No dominada]
* $\alpha = (0.4, 0.6) \rightarrow (21416.25, 100.0)$ [No dominada]
* $\alpha = (0.6, 0.4) \rightarrow (6701.25, 40.0)$ [No dominada]
* $\alpha = (0.8, 0.2) \rightarrow (6701.25, 40.0)$ [No dominada]
* $\alpha = (1.0, 0.0) \rightarrow (6701.25, 40.0)$ [No dominada]

---

## 7. Comportamiento en $\alpha = (0.50, 0.50)$
Debido a la linealidad constante de la frontera de Pareto ($\Delta Z_1 / \Delta Z_2 = 245.25$), la función ponderada con pesos iguales es paralela al segmento. Existe degeneración de la función ponderada y múltiples óptimos alternativos a lo largo del segmento entre $(6701.25, 40.0)$ y $(21416.25, 100.0)$, reportado explícitamente en la interpretación automática.

---

## 8. Verificación y Suite de Tests
* **Total de tests:** **69 tests unitarios (100% PASS en 9.04s)**.
* **Benchmark A (Pyomo):** 100% PASS verificado contra referencia académica sin alteraciones.
* **Smoke test Streamlit:** Ejecución completa con AppTest para barrido de 6 ponderaciones y ponderación única 0.5/0.5.

---

## 9. Limitaciones Restantes
* Implementación restringida a modelos biobjetivo ($N=2$).
* Métodos avanzados como $\varepsilon$-restricciones y NSGA-II programados para fases posteriores.
