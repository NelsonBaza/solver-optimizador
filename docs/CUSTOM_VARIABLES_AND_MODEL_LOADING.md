# Nombres Personalizados de Variables y Carga Atómica de Modelos

**Fecha:** 23 de agosto de 2026  
**Módulos:** `src/solver_optimizador/model_io.py`, `src/solver_optimizador/plotting.py`, `streamlit_app.py`

---

## 1. Carga Atómica de Modelos con Confirmación Explícita

### Diagnóstico del Problema Anterior:
Anteriormente, al seleccionar un archivo en `st.file_uploader`, la carga se disparaba de forma automática e inmediata. Esto provocaba desincronización de estado interno, mezcla de configuraciones previas (ej. residuos de objetivos biobjetivo en modelos monoobjetivo) y potenciales bucles de re-ejecución.

### Solución Implementada:
1. **Selección sin Modificación de Estado:** Al seleccionar un archivo `.json`, la aplicación no modifica el modelo activo inmediatamente.
2. **Tarjeta de Vista Previa:** Muestra un resumen claro del archivo validado:
   * Nombre del modelo y descripción.
   * Tipo de problema (Monoobjetivo / Biobjetivo).
   * Cantidad y nombres de variables.
   * Cantidad de restricciones.
   * Sentidos de optimización.
3. **Botón Explícito de Carga (`📥 Cargar modelo`):** Solo al hacer clic se ejecuta una carga **atómica ("todo o nada")**, limpiando claves obsoletas, incrementando `uploader_version` para reiniciar el componente de subida y refrescando la interfaz con un mensaje unívoco de confirmación.

---

## 2. Nombres Personalizados de Variables y Capacidad Ampliada

* **Independencia de `x1...xn`:** El usuario puede nombrar libremente sus variables (ej. `T1, T2, V1, V2, PH1, GH1, GT1`, etc.).
* **Capacidad de Interfaz:** Ampliada de 20 a **100 variables** (`max_value = 100`).
* **Preservación de Coeficientes:** Al renombrar variables en el editor tabular, los coeficientes en la función objetivo y en las restricciones se preservan automáticamente por correspondencia de posición.
* **Validación de Unicidad:** Nombres vacíos o duplicados son detectados y bloquean la resolución con un mensaje explicativo hasta ser corregidos.
* **Formulación Tabular Escalable:** La función objetivo se gestiona mediante un editor de datos tabular con columnas fijadas para las variables y campos editables para los coeficientes, soportando decenas de variables sin saturar la pantalla.

---

## 3. Validación con Caso Real Completo: Hidroeléctrico 24 Variables

Se formuló y resolvió el problema completo de despacho hidrotérmico multiperíodo (4 períodos):

* **Variables (24):**
  * Turbinación: $T_1, T_2, T_3, T_4$
  * Volumen embalse: $V_1, V_2, V_3, V_4$
  * Vertimiento: $S_1, S_2, S_3, S_4$
  * Potencia hidroeléctrica: $PH_1, PH_2, PH_3, PH_4$
  * Generación hidroeléctrica: $GH_1, GH_2, GH_3, GH_4$
  * Generación térmica: $GT_1, GT_2, GT_3, GT_4$
* **Objetivo:** $\text{MIN } Z = 100 GT_1 + 100 GT_2 + 100 GT_3 + 100 GT_4$.
* **Restricciones (28):** Balance hídrico, relación turbinación-potencia, conversión potencia-energía, balance energético/demanda, cotas de volumen y cotas de turbina.
* **Valor Óptimo Obtenido:** **$Z^* = 6701.25$**.
* **Persistencia Round-Trip:** Guardado a JSON (Schema 1.0) $\rightarrow$ Carga en modelo en blanco $\rightarrow$ Resolución: **$Z^* = 6701.25$** con coincidencia exacta de firma matemática.
