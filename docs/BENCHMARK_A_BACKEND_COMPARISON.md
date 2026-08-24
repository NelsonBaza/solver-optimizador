# Benchmark A — Comparación Técnica de Backends: Pyomo + HiGHS vs. AMPL + HiGHS

**Fecha de evaluación:** 23 de agosto de 2026  
**Problema evaluado:** Benchmark A — Programación Lineal Continua Biobjetivo  
**Solvers:** HiGHS 1.15.1 (vía `ampl-module-highs` y vía `highspy` APPSI)  
**Entorno:** Windows x86_64, Python 3.13.1, `.venv` aislado  

---

## 1. Resumen Ejecutivo

Se implementó y validó el mismo problema biobjetivo lineal de referencia académica utilizando dos arquitecturas de modelado distintas sobre el intérprete Python 3.13.1:

1. **AMPL + amplpy + HiGHS:** Modelado mediante el lenguaje algebraico AMPL (vía evaluación de cadenas de texto y wrapper `amplpy 0.18.0`).
2. **Pyomo + APPSI + highspy:** Modelado mediante programación orientada a objetos en Python nativo (`pyomo 6.10.1` + `highspy 1.15.1`).

Ambos enfoques alcanzaron **100% de coincidencia matemática** en todos los óptimos individuales, la matriz de pagos, los rangos de normalización, el barrido de 6 ponderaciones y la clasificación de dominancia de Pareto.

---

## 2. Comparación Detallada por Criterio

| Criterio | AMPL + HiGHS | Pyomo + HiGHS | Observaciones y Análisis |
| :--- | :--- | :--- | :--- |
| **1. Exactitud matemática** | 100% exacto contra referencia | 100% exacto contra referencia | Ambos solvers identificaron exactamente los mismos puntos extremos: Solución A (0, 130), Solución B (80, 50) y Solución C (100, 0). |
| **2. Formulación** | Basada en DSL algebraico (cadenas de texto enviadas al motor AMPL). | Programación orientada a objetos en Python nativo (`ConcreteModel`, `Var`, `Constraint`, `Objective`). | Pyomo ofrece autocompletado de IDE, linting estático y tipado seguro. AMPL ofrece sintaxis algebraica compacta pero requiere pasar cadenas de texto al intérprete (`ampl.eval(...)`). |
| **3. Cambio de objetivos** | Mediante comando `objective ObjName;` en el motor AMPL. | Mediante asignación/recreación del objeto `Objective` o activación/desactivación (`deactivate()`/`activate()`). | AMPL permite definir múltiples objetivos nombrados en un mismo modelo y alternar entre ellos con un comando; Pyomo requiere manipular objetos en memoria. |
| **4. Parámetros / pesos** | Actualización en memoria con `ampl.param["a1"] = val` sin recompilar el modelo. | Recreación del objetivo o uso de `pyo.Param(mutable=True)`. | AMPL gestiona la parametrización de manera muy limpia a nivel de motor. En Pyomo se puede instanciar la expresión o parametrizar formalmente. |
| **5. Código específico backend** | ~82 líneas de código específico (inicialización, carga de módulos, declaración DSL, llamadas solve, extracción de valores). | ~63 líneas de código específico (creación de modelo base, variables, restricciones, objetivos y llamadas APPSI). | Pyomo requiere ligeramente menos líneas específicas de backend para el flujo completo y evita la interfaz de texto. |
| **6. Código multiobjetivo manual** | ~334 líneas (matriz de pagos, rangos, barrido de pesos, detección de duplicados, dominancia de Pareto, gráficos, JSON). | ~334 líneas (exactamente la misma lógica conceptual de normalización, barrido, Pareto y visualización). | **Hallazgo clave:** Ninguno de los dos frameworks incluye soporte multiobjetivo nativo. Todo el workflow de pesos, normalización y Pareto debe implementarse en Python. |
| **7. Instalación** | Requiere `pip install amplpy ampltools` seguido de descarga de módulos binarios (`amplpy.modules.install('highs')`). | Requiere únicamente `pip install pyomo highspy` desde PyPI estándar. | Pyomo utiliza binarios precompilados en ruedas (*wheels*) estándar de PyPI sin pasos adicionales de instalación de módulos. |
| **8. Reproducibilidad** | Alta, pero sujeta a la disponibilidad de repositorios de módulos de AMPL y control de licencias. | Máxima. Totalmente reproducible con un simple `pip install -r requirements-pyomo.txt`. | Los wheels de Pyomo y highspy no tienen dependencias externas ni requieren configuración de licencias. |
| **9. Licenciamiento** | **Propietario / Restrictivo:** `amplpy` es BSD-3, pero el motor AMPL y los módulos están sujetos a licencias comerciales o licencias académicas comunitarias con posibles limitaciones de tamaño/tiempo. | **100% Código Abierto Permisivo:** Pyomo (licencia BSD-3) y HiGHS / highspy (licencia MIT). Sin restricciones de tamaño de problema, caducidad ni uso. | Pyomo + highspy garantiza libertad total de redistribución para uso académico, docente y de investigación. |
| **10. Integración Python** | Wrapper que se comunica vía proceso/IPC con el binario de AMPL. | Framework nativo de Python; expresiones simbólicas son estructuras de datos de Python inspeccionables. | Pyomo se integra de forma directa con NumPy, Pandas, SciPy, SymPy y Streamlit sin puentes intermediarios. |
| **11. Extensibilidad** | Limitada al catálogo de solvers soportados por AMPL y su sintaxis. | Alta. Admite múltiples solvers (HiGHS, SCIP, IPOPT, GLPK, CBC) mediante interfaces unificadas y plugins APPSI. | Pyomo permite intercambiar solvers de LP, MILP y NLP con mínimas modificaciones de código. |
| **12. Rendimiento observado** | Solve individual: ~1400 ms; Barrido 6 pesos: ~4180 ms; Proceso total: ~6.8 s. | Solve individual: ~9.4 ms; Barrido 6 pesos: ~21.1 ms; Proceso total: ~1.4 s. | Pyomo APPSI utiliza bindings directos en C++ en memoria (`highspy`), mientras AMPL invoca el ejecutable del solver mediante archivos `.nl` y procesos externos. |

---

## 3. Desglose de Líneas de Código

| Componente | AMPL + HiGHS (`benchmark_a_multiobjective.py`) | Pyomo + HiGHS (`benchmark_a_pyomo.py`) |
| :--- | :---: | :---: |
| **Líneas totales del script** | 416 | 397 |
| **Líneas específicas de modelado y backend** | ~82 | ~63 |
| **Líneas del flujo multiobjetivo y análisis** | ~334 | ~334 |
| **Proporción de código específico de backend** | 19.7% | 15.9% |
| **Proporción de código multiobjetivo común** | 80.3% | 84.1% |

---

## 4. Análisis de Rendimiento y Tiempos

> [!NOTE]
> **Contexto de escala:** El Benchmark A es un problema LP biobjetivo continuo diminuto (2 variables, 2 restricciones). Las diferencias de tiempo no deben extrapolarse como factor determinante de capacidad matemática, pero sí reflejan la arquitectura de comunicación de cada backend.

| Fase de Ejecución | AMPL + HiGHS | Pyomo + HiGHS (APPSI) | Factor de Diferencia |
| :--- | :---: | :---: | :---: |
| **Optimización individual (Z1* + Z2*)** | 1,402.4 ms | 9.4 ms | Pyomo ~149x más rápido en solve en memoria |
| **Barrido de 6 combinaciones de pesos** | 4,184.5 ms | 21.1 ms | Pyomo ~198x más rápido en barrido iterativo |
| **Tiempo total interno del benchmark** | 6,132.0 ms | 30.6 ms | Pyomo ~200x más rápido |
| **Tiempo de pared total del proceso (wall-clock)** | ~6,840.0 ms | ~1,438.0 ms | Pyomo ~4.7x más rápido (incluye importaciones y renderizado de gráficos a 300 DPI) |

### Justificación Técnica de la Diferencia de Tiempo
1. **AMPL:** Cada llamada a `ampl.solve()` genera archivos temporales de comunicación (`.nl`), lanza el ejecutable binario de HiGHS como subproceso, procesa la solución y reimporta los resultados.
2. **Pyomo (APPSI):** La interfaz APPSI (`pyomo.contrib.appsi.solvers.Highs`) transfiere el modelo directamente a las estructuras de datos C++ de `highspy` en memoria sin interactuar con el disco ni lanzar subprocesos.

---

## 5. Tabla de Puntuación Comparativa (Escala 0 a 5)

| Criterio de Evaluación | AMPL + HiGHS | Pyomo + HiGHS | Justificación de la Calificación |
| :--- | :---: | :---: | :--- |
| **Exactitud matemática** | **5.0** | **5.0** | Ambos logran 100% de precisión exacta e idénticos resultados numéricos. |
| **Facilidad de modelado** | **4.5** | **4.5** | AMPL tiene sintaxis algebraica natural; Pyomo ofrece tipado, IDE tooling y objetos nativos. |
| **Facilidad multiobjetivo** | **2.5** | **2.5** | Ninguno tiene algoritmos multiobjetivo nativos; ambos requieren implementación manual. |
| **Cantidad de código** | **4.0** | **4.2** | Pyomo requiere menos código específico y evita construir cadenas de texto con concatenaciones. |
| **Reproducibilidad** | **4.0** | **5.0** | Pyomo se instala limpiamente vía `pip` sin dependencias de repositorios de módulos ni licencias. |
| **Licencia / Dependencia externa** | **3.0** | **5.0** | Pyomo (BSD) y HiGHS (MIT) son 100% libres; AMPL es propietario sujeto a licencias. |
| **Extensibilidad** | **4.0** | **5.0** | Pyomo soporta ecosistemas completos (SCIP, IPOPT, SciPy, pymoo, SymPy) de forma abierta. |
| **Integración Python** | **3.5** | **5.0** | Pyomo es un paquete Python nativo; AMPL es un wrapper de un binario independiente. |
| **TOTAL** | **30.5 / 40.0 (76.2%)** | **36.2 / 40.0 (90.5%)** | **Diferencia: +5.7 puntos para Pyomo** |

---

## 6. Recomendación Provisional

> [!IMPORTANT]
> **RECOMENDACIÓN PROVISIONAL: `Pyomo favorito provisional`**
>
> La evidencia técnica observable indica que:
> 1. **No hay pérdida matemática:** Pyomo + HiGHS produce exactamente las mismas soluciones óptimas y la misma frontera de Pareto que AMPL + HiGHS.
> 2. **Soberanía y licenciamiento:** Pyomo + HiGHS es 100% de código abierto permisivo (BSD-3 y MIT), eliminando barreras de licencias, límites de variables o dependencia de servidores comerciales de validación.
> 3. **Arquitectura limpia:** Pyomo se programa en Python puro orientado a objetos, facilitando la futura construcción de la suite, modularización de motores y acoplamiento con Streamlit / Matplotlib / SymPy.
> 4. **Eficiencia en memoria:** La interfaz APPSI de Pyomo resuelve problemas iterativos (como el barrido de pesos) directamente en memoria en milisegundos.
>
> *Nota:* Esta recomendación es provisional y no constituye una decisión arquitectónica definitiva cerrada. Se someterá a auditoría técnica externa.
