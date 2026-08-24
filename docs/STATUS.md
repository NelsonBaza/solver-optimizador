# Estado Técnico del Proyecto (Snapshot)

* **Fecha de corte:** 2026-08-23
* **Sistema Operativo:** Windows 11 / Windows Server (64-bit, `x86_64`)
* **Python (Global):** `3.13.1` (MSC v.1942 64-bit AMD64)
* **Python (.venv):** `3.13.1` (`E:\AI\solver-optimizador\.venv\Scripts\python.exe`)
* **Gestor de paquetes (pip en .venv):** `24.3.1`
* **amplpy:** `0.18.0` (fijado en `requirements-ampl.txt`)
* **ampltools:** `0.7.5` (fijado en `requirements-ampl.txt`)
* **matplotlib:** `3.11.1` (fijado en `requirements-ampl.txt`, `requirements-pyomo.txt`, `pyproject.toml`)
* **pyomo:** `6.10.1` (fijado en `requirements-pyomo.txt`, `pyproject.toml`)
* **highspy:** `1.15.1` (fijado en `requirements-pyomo.txt`, `pyproject.toml`)
* **streamlit:** `1.62.0` (fijado en `requirements-ui.txt`, `pyproject.toml`)
* **pytest:** `9.1.1` (fijado en `requirements-ui.txt`, `pyproject.toml`)
* **AMPL Engine (`ampl-module-base`):** `20260809`
* **HiGHS Solver:** `1.15.1` (vía `ampl-module-highs` 20260813 y vía `highspy` 1.15.1)
* **Backend exacto provisional:** `Pyomo + HiGHS` (adoptado provisionalmente según ADR-007)
* **Backend comparativo validado:** `AMPL + HiGHS` (conservado como baseline de referencia)

---

## 1. Estado de los Benchmarks y Pruebas

| Prueba / Benchmark | Script / Comando | Estado | Resultado Resumido |
| :--- | :--- | :---: | :--- |
| **Baseline Monoobjetivo (AMPL)** | [`verify_ampl_highs.py`](../verify_ampl_highs.py) | **PASS** | $x=(2.0, 2.0), Z=10.0$ (HiGHS 1.15.1, `solve_result=solved`). |
| **Benchmark A (AMPL + HiGHS)** | [`benchmark_a_multiobjective.py`](../benchmark_a_multiobjective.py) | **PASS** | Matriz de pagos validada, rangos $\Delta Z=(610, 89)$, 6 ejecuciones ponderadas, 3 soluciones únicas no dominadas verificadas contra referencia académica. |
| **Benchmark A (Pyomo + HiGHS)** | [`benchmark_a_pyomo.py`](../benchmark_a_pyomo.py) | **PASS** | Coincidencia matemática exacta al 100% con AMPL y referencia. Matriz de pagos, rangos, 6 pesos, 3 soluciones únicas no dominadas idénticas. |
| **Comparación de Backends** | [`docs/BENCHMARK_A_BACKEND_COMPARISON.md`](BENCHMARK_A_BACKEND_COMPARISON.md) | **PASS** | Evaluación en 12 criterios y 8 dimensiones. Pyomo adoptado como backend exacto provisional (+5.7 pts). |
| **Suite de Pruebas Unitarias** | `pytest tests/` | **PASS** | 12 pruebas unitarias aprobadas (mono MAX/MIN, bio MAX/MAX, MAX/MIN, MIN/MIN, infactibilidad, no acotamiento, validación de pesos, rango nulo, nombres especiales, entradas no finitas y gráficos). |
| **MVP Interfaz Web** | `streamlit run streamlit_app.py` | **PASS** | Interfaz funcional y sincronizada para LP mono y biobjetivo con tablas dinámicas y gráficos 2D. |

---

## 2. Inventario de Archivos Principales

| Archivo / Carpeta | Descripción |
| :--- | :--- |
| [`src/solver_optimizador/`](../src/solver_optimizador/) | Paquete principal del motor matemático desacoplado (`lp_models`, `lp_solver`, `multiobjective`, `plotting`). |
| [`streamlit_app.py`](../streamlit_app.py) | Aplicación web interactiva Streamlit. |
| [`tests/test_lp_core.py`](../tests/test_lp_core.py) | Suite de pruebas unitarias para el motor matemático (`pytest`, 12 tests). |
| [`verify_ampl_highs.py`](../verify_ampl_highs.py) | Script de verificación reproducible del entorno base AMPL + HiGHS. |
| [`benchmark_a_multiobjective.py`](../benchmark_a_multiobjective.py) | Script ejecutable del Benchmark A con AMPL + HiGHS. |
| [`benchmark_a_pyomo.py`](../benchmark_a_pyomo.py) | Script ejecutable del Benchmark A con Pyomo + HiGHS (APPSI). |
| [`results/benchmark_a_results.json`](../results/benchmark_a_results.json) | Resultados estructurados del Benchmark A (AMPL). |
| [`results/benchmark_a_pyomo_results.json`](../results/benchmark_a_pyomo_results.json) | Resultados estructurados del Benchmark A (Pyomo). |
| [`results/benchmark_a_objective_space.png`](../results/benchmark_a_objective_space.png) | Gráfico de espacio de objetivos ($Z_1$ vs. $Z_2$) generado por AMPL. |
| [`results/benchmark_a_feasible_region.png`](../results/benchmark_a_feasible_region.png) | Gráfico de región factible ($x_1$ vs. $x_2$) generado por AMPL. |
| [`results/benchmark_a_pyomo_objective_space.png`](../results/benchmark_a_pyomo_objective_space.png) | Gráfico de espacio de objetivos ($Z_1$ vs. $Z_2$) generado por Pyomo. |
| [`results/benchmark_a_pyomo_feasible_region.png`](../results/benchmark_a_pyomo_feasible_region.png) | Gráfico de región factible ($x_1$ vs. $x_2$) generado por Pyomo. |
| [`requirements-ampl.txt`](../requirements-ampl.txt) | Dependencias fijadas para el stack AMPL (`amplpy`, `ampltools`, `matplotlib`). |
| [`requirements-pyomo.txt`](../requirements-pyomo.txt) | Dependencias fijadas para el stack Pyomo (`pyomo`, `highspy`, `matplotlib`). |
| [`requirements-ui.txt`](../requirements-ui.txt) | Dependencias fijadas para la interfaz (`streamlit`, `pytest`). |
| [`requirements-proposed-full-stack.txt`](../requirements-proposed-full-stack.txt) | Propuesta preliminar para fases posteriores (no instalado en este checkpoint). |
| [`pyproject.toml`](../pyproject.toml) | Configuración de empaquetado con dependencias validadas y configuración de `pytest`. |
| [`.gitignore`](../.gitignore) | Exclusiones de Git (entornos virtuales, temporales de solvers, logs, cachés). |
| [`README.md`](../README.md) | Documento principal con alcance, guía de inicio del MVP, licencias y limitaciones. |
| [`docs/UI_UX_REFINEMENT.md`](UI_UX_REFINEMENT.md) | Informe técnico de refinamiento UI/UX y modernización de Streamlit. |
| [`docs/UI_MVP_HARDENING.md`](UI_MVP_HARDENING.md) | Informe técnico de hardening del MVP de interfaz Streamlit y motor matemático. |
| [`docs/UI_MVP_VALIDATION.md`](UI_MVP_VALIDATION.md) | Informe técnico de validación del MVP de interfaz Streamlit. |
| [`docs/BENCHMARK_A.md`](BENCHMARK_A.md) | Informe técnico del Benchmark A multiobjetivo con AMPL. |
| [`docs/BENCHMARK_A_BACKEND_COMPARISON.md`](BENCHMARK_A_BACKEND_COMPARISON.md) | Informe comparativo técnico y de rendimiento: AMPL vs. Pyomo. |
| [`docs/STATUS.md`](STATUS.md) | Este documento (fotografía técnica actual). |
| [`docs/ENVIRONMENT.md`](ENVIRONMENT.md) | Guía detallada del entorno, instalación y diferencias de componentes. |
| [`docs/DECISIONS.md`](DECISIONS.md) | Registro histórico de decisiones técnicas y arquitectónicas (ADR). |
| [`docs/agent_logs/`](agent_logs/) | Auditoría y trazabilidad de interacciones y reportes del agente de IA. |

---

## 3. Estado de Validación de Componentes

### Componentes Validados en `.venv`:
- [x] Python `3.13.1` (entorno aislado)
- [x] `amplpy==0.18.0`, `ampltools==0.7.5`, `matplotlib==3.11.1`
- [x] `pyomo==6.10.1`, `highspy==1.15.1`
- [x] `streamlit==1.62.0`, `pytest==9.1.1`
- [x] Módulo AMPL Base (`ampl.exe` 20260809)
- [x] Módulo AMPL HiGHS (`highs.exe` 1.15.1)
- [x] Pyomo APPSI HiGHS (`highspy` 1.15.1)
- [x] Motor modular `src/solver_optimizador/` (LP monoobjetivo y biobjetivo)
- [x] Interfaz gráfica de usuario en Streamlit (`streamlit_app.py`)
- [x] Suite de pruebas automatizadas (6 tests `pytest` 100% PASS)
- [x] Optimización individual y cálculo de matriz de pagos (AMPL y Pyomo)
- [x] Método de suma ponderada normalizada (AMPL y Pyomo)
- [x] Detección de soluciones repetidas y clasificación de no dominancia de Pareto
- [x] Generación de gráficos 2D de espacio de objetivos y región factible
- [x] Comparativa técnica objetiva de backends con puntuación formal

### Componentes y Metodologías Todavía NO Validados:
- [ ] Método de $\varepsilon$-restricciones
- [ ] Integración de `pymoo` (algoritmos evolutivos como NSGA-II)
- [ ] IPOPT (ampl-module-ipopt / binarios IDAES / Pyomo ASL)
- [ ] SCIP (PySCIPOpt / ampl-module-scip)
- [ ] Variables enteras y binarias (MILP)
- [ ] Problemas no lineales continuos o enteros (NLP / MINLP)
- [ ] Decisión final sobre la arquitectura del sistema

---

## 4. Próximo Hito Previsto

* **Hito siguiente:** Método $\varepsilon$-restricciones con Pyomo + HiGHS (una vez aprobada la auditoría externa del MVP de interfaz).
