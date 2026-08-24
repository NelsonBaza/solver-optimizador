# Estado Técnico del Proyecto (Snapshot)

* **Fecha de corte:** 2026-08-23
* **Sistema Operativo:** Windows 11 / Windows Server (64-bit, `x86_64`)
* **Python (Global):** `3.13.1` (MSC v.1942 64-bit AMD64)
* **Python (.venv):** `3.13.1` (`E:\AI\solver-optimizador\.venv\Scripts\python.exe`)
* **Gestor de paquetes (pip en .venv):** `24.3.1`
* **amplpy:** `0.18.0` (fijado en `requirements-ampl.txt`)
* **ampltools:** `0.7.5` (fijado en `requirements-ampl.txt`)
* **matplotlib:** `3.11.1` (fijado en `requirements-ampl.txt`)
* **AMPL Engine (`ampl-module-base`):** `20260809`
* **HiGHS Solver (`ampl-module-highs`):** `1.15.1` (módulo AMPL `20260813`, solver open source MIT)

---

## 1. Estado de los Benchmarks y Pruebas

| Prueba / Benchmark | Script Asociado | Estado | Resultado Resumido |
| :--- | :--- | :---: | :--- |
| **Baseline Monoobjetivo** | [`verify_ampl_highs.py`](../verify_ampl_highs.py) | **PASS** | $x=(2.0, 2.0), Z=10.0$ (HiGHS 1.15.1, `solve_result=solved`). |
| **Benchmark A (Biobjetivo)** | [`benchmark_a_multiobjective.py`](../benchmark_a_multiobjective.py) | **PASS** | Matriz de pagos validada, rangos $\Delta Z=(610, 89)$, 6 ejecuciones ponderadas, 3 soluciones únicas no dominadas detectadas y verificadas contra referencia académica. |

---

## 2. Inventario de Archivos Principales

| Archivo / Carpeta | Descripción |
| :--- | :--- |
| [`verify_ampl_highs.py`](../verify_ampl_highs.py) | Script de verificación reproducible del entorno base. |
| [`benchmark_a_multiobjective.py`](../benchmark_a_multiobjective.py) | Script ejecutable del Benchmark A con aserciones, gráficos y exportación JSON. |
| [`results/benchmark_a_results.json`](../results/benchmark_a_results.json) | Resultados estructurados del Benchmark A. |
| [`results/benchmark_a_objective_space.png`](../results/benchmark_a_objective_space.png) | Gráfico de espacio de objetivos ($Z_1$ vs. $Z_2$). |
| [`results/benchmark_a_feasible_region.png`](../results/benchmark_a_feasible_region.png) | Gráfico de región factible ($x_1$ vs. $x_2$) con vértices óptimos. |
| [`requirements-ampl.txt`](../requirements-ampl.txt) | Dependencias fijadas y verificadas del entorno actual (`amplpy`, `ampltools`, `matplotlib`). |
| [`requirements-proposed-full-stack.txt`](../requirements-proposed-full-stack.txt) | Propuesta preliminar para fases posteriores (no instalado en este checkpoint). |
| [`pyproject.toml`](../pyproject.toml) | Configuración de empaquetado del proyecto. |
| [`.gitignore`](../.gitignore) | Exclusiones de Git (entornos virtuales, temporales de solvers, logs, cachés). |
| [`README.md`](../README.md) | Documento principal con alcance, licencias, instrucciones y limitaciones. |
| [`docs/BENCHMARK_A.md`](BENCHMARK_A.md) | Informe técnico completo del Benchmark A multiobjetivo. |
| [`docs/STATUS.md`](STATUS.md) | Este documento (fotografía técnica actual). |
| [`docs/ENVIRONMENT.md`](ENVIRONMENT.md) | Guía detallada del entorno, instalación y diferencias de componentes. |
| [`docs/DECISIONS.md`](DECISIONS.md) | Registro histórico de decisiones técnicas y arquitectónicas (ADR). |
| [`docs/agent_logs/`](agent_logs/) | Auditoría y trazabilidad de interacciones y reportes del agente de IA. |

---

## 3. Estado de Validación de Componentes

### Componentes Validados en `.venv`:
- [x] Python `3.13.1` (entorno aislado)
- [x] `amplpy==0.18.0`, `ampltools==0.7.5`, `matplotlib==3.11.1`
- [x] Módulo AMPL Base (`ampl.exe` 20260809)
- [x] Módulo AMPL HiGHS (`highs.exe` 1.15.1)
- [x] Optimización individual y cálculo de matriz de pagos
- [x] Método de suma ponderada normalizada
- [x] Detección de soluciones repetidas y clasificación de no dominancia de Pareto
- [x] Generación de gráficos 2D de espacio de objetivos y región factible

### Componentes y Metodologías Todavía NO Validados:
- [ ] Método de $\varepsilon$-restricciones
- [ ] Integración de `pymoo` (algoritmos evolutivos como NSGA-II)
- [ ] IPOPT (ampl-module-ipopt / binarios IDAES / Pyomo ASL)
- [ ] SCIP (PySCIPOpt / ampl-module-scip)
- [ ] Pyomo (como backend comparativo frente a AMPL)
- [ ] Interfaz gráfica de usuario (Streamlit)
- [ ] Decisión final sobre la arquitectura del sistema

---

## 4. Próximo Hito Previsto

* **Hito siguiente:** Auditoría externa del Benchmark A y posterior evaluación del método de $\varepsilon$-restricciones o comparación de backend con Pyomo.
