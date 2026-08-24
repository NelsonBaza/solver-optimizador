# Informe Técnico: Mejora de Gráficos e Interpretación Base Automática de Resultados

**Fecha:** 23 de agosto de 2026  
**Objetivo:** Eliminar solapamientos visuales en los gráficos 2D y añadir un motor de interpretación matemática automática de resultados para problemas mono y multiobjetivo.  
**Backend matemático:** Pyomo 6.10.1 + HiGHS 1.15.1 (APPSI / `highspy`)  
**Test Suite:** pytest 9.1.1 (24 pruebas unitarias automatizadas 100% PASS)

---

## 1. Problemas de Usabilidad Identificados en Gráficos

1. **Superposición de Anotaciones con Título y Ejes:**
   * En el espacio de objetivos ($Z_1$ vs. $Z_2$) y en la región factible ($x_1$ vs. $x_2$), los puntos superiores tenían cajas de texto que invadían el título o se cortaban con el marco superior.
2. **Cajas de Ponderaciones Excesivamente Altas:**
   * Cuando una misma solución no dominada era generada por 3 o más combinaciones de pesos, la caja de texto apilaba verticalmente cada $\alpha=(\dots)$, generando un bloque excesivamente alto que colisionaba con otros puntos.
3. **Competencia Espacial con la Leyenda:**
   * La leyenda por defecto se ubicaba en zonas transitadas por las soluciones o la región sombreada.

---

## 2. Estrategia Aplicada en Generación de Gráficos (`plotting.py`)

1. **Márgenes Dinámicos y Separación de Títulos:**
   * Se incrementó el padding del título a `pad=16`.
   * Se ampliaron los límites de los ejes ($+20\%$ en horizontal, $+24\%$ en vertical sobre el rango de los puntos), otorgando espacio libre superior e inferior.
2. **Formato Compacto de Pesos en Línea Única:**
   * Se reemplazó el desglose multi-línea por un formato condensado:
     $$\text{Pesos: } (0.4, 0.6), (0.6, 0.4), (0.8, 0.2)$$
3. **Offsets Inteligentes de Anotación:**
   * El punto extremo izquierdo se desplaza hacia la derecha (`xytext=(15, 12)`).
   * El punto extremo derecho se desplaza hacia la izquierda (`xytext=(-130, 12)`), evitando salirse del borde del gráfico.
   * Se utiliza flecha estilizada (`arrowprops`) con arco suave (`connectionstyle="arc3,rad=0.08"`).
4. **Reubicación de Leyendas:**
   * En el espacio de objetivos, la leyenda se fija en `loc="lower left"`, aprovechando que la frontera de compromiso discurre en sentido diagonal opuesto.

---

## 3. Motor de Interpretación Base Automática (`interpretation.py`)

Se desarrolló un módulo desacoplado que genera explicaciones rigurosas y sencillas basadas únicamente en la formulación matemática y la solución del solver:

### Monoobjetivo (`interpret_mono_solution`)
* **Sentido y Óptimo:** Explica si se maximiza o minimiza y el valor de $Z^*$.
* **Variables:** Identifica variables activas ($x_j^* > 0$) y variables nulas ($x_j^* = 0$), explicando que estas últimas no participan en la combinación óptima.
* **Restricciones Activas:** Destaca las restricciones con holgura nula como límites efectivos (cuellos de botella) que definen el vértice óptimo.
* **Restricciones No Limitantes:** Reporta la holgura ($s_i > 0$) indicando capacidad o margen excedente.
* **Diagnósticos:** En caso de infactibilidad o no acotamiento, orienta al usuario sobre cómo corregir el modelo.

### Biobjetivo (`interpret_biobjective_solution`)
* **Óptimos Individuales:** Presenta los mejores valores aislados $Z_1^*$ y $Z_2^*$.
* **Compromiso (Trade-off):** Cuantifica el sacrificio que experimenta un objetivo cuando se prioriza el otro a partir de la matriz de pagos.
* **Alternativas No Dominadas:** Reporta el número de corridas, soluciones únicas y soluciones no dominadas encontradas.
* **Estabilidad y Sensibilidad:** Explica que cuando múltiples combinaciones de ponderaciones convergen a la misma solución, dicha alternativa es robusta frente a un amplio rango de preferencias.
* **Extremos:** Identifica qué soluciones extremas favorecen prioritariamente a cada objetivo.
* **Aviso de Rigor:** Recuerda explícitamente que la interpretación corresponde al conjunto discreto evaluado y no a la frontera de Pareto continua completa.

---

## 4. Ubicación en la Interfaz Streamlit

* **Monoobjetivo:** Bloque delimitado `💡 Interpretación Base de Resultados` ubicado directamente debajo de la tabla de restricciones y el gráfico de la región factible.
* **Biobjetivo:** Bloque delimitado `💡 Interpretación Base del Modelo Multiobjetivo` ubicado en la pestaña principal `📋 Resumen` junto a la matriz de pagos y los rangos de normalización.

---

## 5. Limitaciones
* La interpretación no inventa significado comercial o contextual (ej. "aumentar producción de producto A"), respetando la neutralidad matemática del motor.
* Gráficos 2D aplican exclusivamente a problemas con exactamente 2 variables de decisión.
