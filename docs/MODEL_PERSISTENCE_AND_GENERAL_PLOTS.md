# Persistencia de Modelos (JSON) y Gráficos Generales para N Variables

**Fecha:** 23 de agosto de 2026  
**Módulos:** `src/solver_optimizador/model_io.py`, `src/solver_optimizador/plotting.py`, `streamlit_app.py`

---

## 1. Esquema JSON de Persistencia (`schema_version: "1.0"`)

Para garantizar portabilidad, reproducibilidad e independencia total de la interfaz, se implementó un formato JSON estructurado, versionado y seguro (sin `pickle` ni código ejecutable):

```json
{
  "schema_version": "1.0",
  "metadata": {
    "name": "Generacion Hidroelectrica 4 Periodos",
    "description": "Modelo multiperiodo reducido de despacho y embalse.",
    "created_with": "solver-optimizador"
  },
  "problem": {
    "type": "Monoobjetivo",
    "num_vars": 8,
    "variables": ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"],
    "mono_objective": {
      "sense": "Minimizar",
      "coefficients": {
        "x1": 0.0, "x2": 0.0, "x3": 0.0, "x4": 0.0,
        "x5": 100.0, "x6": 100.0, "x7": 100.0, "x8": 100.0
      }
    },
    "constraints": [
      {
        "name": "Demanda P1",
        "coefficients": {"x1": 2.4525, "x2": 0.0, "x3": 0.0, "x4": 0.0, "x5": 1.0, "x6": 0.0, "x7": 0.0, "x8": 0.0},
        "operator": "=",
        "rhs": 60.0
      }
    ]
  }
}
```

### Características Principales:
* **Seguridad Estricta:** Serialización y deserialización basadas puramente en `json` estándar y validación tipada.
* **Tolerancia a Separador Decimal:** Admite cadenas numéricas con coma o punto (`"2,4525"` $\rightarrow 2.4525$).
* **Determinismo:** Conserva exactamente la firma matemática del modelo (`build_model_signature`).

---

## 2. Gráficos Generales de Resultados para $N \ge 1$ Variables

Cuando un modelo tiene más de 2 variables de decisión ($n > 2$), no es geométricamente posible graficar una región factible bidimensional $x_1 - x_2$. En su lugar, el sistema ofrece:

1. **Valores Óptimos de Variables (`plot_variable_values`):**
   * Gráfico de barras que presenta el valor óptimo exacto de cada variable ($x_1 \dots x_n$) con etiquetas sobre cada columna y auto-escalado dinámico.
2. **Análisis de Holguras por Restricción (`plot_constraint_slacks`):**
   * Gráfico de barras horizontal que identifica de forma clara las restricciones **activas** (holgura nula, cuellos de botella) en color rojo/vino y las restricciones **con holgura** (capacidad disponible) en verde.
3. **Sensibilidad frente a Ponderaciones (`plot_multiobjective_runs`):**
   * Subgráficos independientes para $Z_1$ y $Z_2$ que muestran cómo varía cada objetivo conforme $\alpha_1$ recorre el barrido $[0, 1]$, evitando distorsiones por escalas dispares.

---

## 3. Validación con Caso Real: Despacho Hidroeléctrico 8 Variables

Se verificó el ciclo de vida completo (formulación $\rightarrow$ resolución $\rightarrow$ guardado JSON $\rightarrow$ nuevo modelo $\rightarrow$ carga JSON $\rightarrow$ re-resolución):

* **Variables:** $x_1 \dots x_4$ (turbinación $T_1 \dots T_4$), $x_5 \dots x_8$ (térmica $GT_1 \dots GT_4$).
* **Objetivo:** $\text{MIN } Z = 100 x_5 + 100 x_6 + 100 x_7 + 100 x_8$.
* **Restricciones:** 4 de demanda (igualdades con coeficiente $2.4525$) y 4 de embalse acumulado.
* **Valor Óptimo Obtenido:** **$Z^* = 6701.25$** (coincidencia exacta antes y después de la carga).
* **Firma Matemática:** Idéntica al 100% (`sig_before == sig_after`).
