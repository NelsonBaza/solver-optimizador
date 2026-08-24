# Registro de Implementación: Nombres Personalizados de Variables y Carga Atómica de Modelos

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Corregir el flujo de carga de modelos JSON mediante previsualización y confirmación explícita atómica, habilitar nombres personalizados de variables con preservación posicional de coeficientes, ampliar el límite de variables de UI a 100 y validar con el caso real hidroeléctrico completo de 24 variables y 28 restricciones.

---

## 1. Problemas Abordados
1. **Carga Automática Desincronizada:** Al seleccionar un archivo en `file_uploader`, el estado cambiaba inmediatamente sin confirmación del usuario, dejando a veces widgets con claves obsoletas o residuos entre modos Monoobjetivo y Biobjetivo.
2. **Dependencia Exclusiva de `x1...xn`:** No era posible asignar nombres reales de dominio a las variables (ej. $T_1, V_1, GT_1$).
3. **Límite Reducido de Variables (20):** Problemas multiperíodo completos no podían formularse cómodamente.

---

## 2. Soluciones Implementadas
* **Carga Atómica con Confirmación Explícita:**
  * Al subir un archivo `.json`, se valida y despliega una tarjeta de resumen.
  * Solo al hacer clic en `📥 Cargar modelo` se aplica el estado de forma atómica ("todo o nada").
  * Se versiona la clave del uploader (`uploader_version`) para resetearlo limpiamente tras la carga y evitar bucles.
* **Nombres Personalizados y Capacidad Ampliada a 100 Variables:**
  * Editor tabular de variables en la barra lateral (`#`, `Nombre`).
  * Validación estricta contra nombres vacíos o duplicados.
  * Migración automática de coeficientes en objetivos y restricciones al renombrar variables.
* **Formulación Tabular Escalable:**
  * Editor de datos para coeficientes de la función objetivo, permitiendo formular decenas de variables sin saturar la interfaz.
* **Gráficos Dinámicos para Altas Dimensiones:**
  * Rotación y auto-escalado en `plot_variable_values` y `plot_constraint_slacks` para graficar con total nitidez 24 variables y 28 restricciones.

---

## 3. Pruebas Automatizadas y Validación
* **Suite Pytest (`tests/test_custom_variables.py` + suites previas):**
  * Total de pruebas: **42 tests (100% PASS en 1.39s)**.
* **Caso Real Hidroeléctrico Completo (24 variables, 28 restricciones):**
  * $\text{MIN } Z = 100 GT_1 + 100 GT_2 + 100 GT_3 + 100 GT_4$.
  * $Z^* = 6701.25$ (óptimo exacto).
  * Serialización y deserialización JSON sin pérdida con coincidencia de firma matemática al 100%.
* **Benchmark A Baseline (`benchmark_a_pyomo.py`):** 100% PASS, manteniendo exactas las 3 soluciones no dominadas.
