# Suite de Optimización Matemática — MVP de Optimización Lineal

Este repositorio contiene el desarrollo y evaluación de una suite gratuita y de código abierto para formulación, resolución, análisis y visualización de problemas de optimización matemática en Python, orientada a uso académico, docente y de investigación.

> [!IMPORTANT]
> **Backend provisional:** `Pyomo + HiGHS` (adoptado provisionalmente según [ADR-007](docs/DECISIONS.md#adr-007-pyomo--highs-como-backend-exacto-provisional)).  
> **Backend comparativo de referencia:** `AMPL + HiGHS` (conservado y validado).

---

## 🚀 MVP de Interfaz Web (Streamlit)

El proyecto incluye una aplicación web interactiva en Streamlit que permite formular, resolver y visualizar problemas lineales continuos sin necesidad de programar en Python.

### Cómo Iniciar la Interfaz Web:
```powershell
& ".\.venv\Scripts\python.exe" -m streamlit run streamlit_app.py
```
La aplicación se abrirá automáticamente en su navegador en:  
**`http://localhost:8501`**

### Alcance y Capacidades Actuales del MVP:
* **Programación Lineal Monoobjetivo (LP):**
  * Variables continuas no negativas ($x_i \ge 0$).
  * Sentido de optimización: Maximizar o Minimizar.
  * Captura interactiva de coeficientes y restricciones lineales ($\le, \ge, =$).
  * Reporte de solución óptima, valor objetivo, estado del solver, holguras y restricciones activas.
  * Gráfico 2D de la región factible y vértice óptimo (cuando $n_{\text{vars}} = 2$).
* **Programación Lineal Biobjetivo (LP):**
  * Definición de dos funciones objetivo lineales ($Z_1, Z_2$) con sentidos independientes (Max/Min).
  * Optimización individual y construcción separada de la **matriz de pagos**. Puede seleccionarse un representante eficiente con el óptimo primario fijado; esta regla de anclaje no sustituye ninguna corrida ponderada ni demuestra unicidad.
  * Cálculo dinámico de **rangos de normalización** ($\Delta Z_k = Z_{k,\max} - Z_{k,\min}$).
  * Método de **ponderaciones normalizadas**: para MAX, $N_k=(Z_k-Z_{k,\min})/\Delta Z_k$; para MIN, $N_k=(Z_{k,\max}-Z_k)/\Delta Z_k$; cada alternativa resuelve $\max W=\alpha_1N_1+\alpha_2N_2$.
  * Los pesos extremos $(1,0)$ y $(0,1)$ también se resuelven como problemas ponderados; no se sustituyen por filas de la matriz de pagos.
  * Modalidades: **Barrido uniforme automático** ($N$ combinaciones) o **Ponderación única personalizada**.
  * Detección de soluciones repetidas y clasificación de **no dominancia de Pareto** sobre el conjunto discreto.
  * Gráficos interactivos: espacio de objetivos ($Z_1$ vs. $Z_2$) y región factible 2D.
* **Ejemplos Precargados en la Interfaz:**
  * **Ejemplo 1 (Monoobjetivo):** $\text{MAX } Z = 3x_1 + 2x_2$, s.a. $x_1 + x_2 \le 4, x_1 \le 2, x_2 \le 3 \implies (x^*=(2,2), Z^*=10)$.
  * **Ejemplo 2 (Benchmark A Biobjetivo):** $\text{MAX } Z_1 = 10x_1 + 3x_2, \text{MAX } Z_2 = 0.8x_1 + 1.3x_2$, s.a. $x_1 + x_2 \le 130, 2.5x_1 + x_2 \le 250 \implies 3$ soluciones únicas no dominadas: $A(0,130), B(80,50), C(100,0)$.

### Qué Todavía NO Puede Resolver (Limitaciones Actuales):
* Variables enteras o binarias (MILP).
* Problemas no lineales continuos o enteros (NLP / MINLP).
* Método de $\varepsilon$-restricciones (programado para el siguiente hito).
* Algoritmos metaheurísticos / evolutivos (NSGA-II / pymoo).
* Programación por metas o programación compromiso.

---

## 📦 Estructura del Código

```text
solver-optimizador/
│
├── src/
│   └── solver_optimizador/
│       ├── __init__.py           # Exportaciones del paquete
│       ├── lp_models.py          # Estructuras de datos (Problem, Objective, Constraint, Solution)
│       ├── lp_solver.py          # Motor LP monoobjetivo (Pyomo + APPSI HiGHS)
│       ├── multiobjective.py     # Motor multiobjetivo (matriz de pagos, pesos, Pareto)
│       └── plotting.py           # Visualización 2D (region factible y espacio de objetivos)
│
├── streamlit_app.py              # Interfaz de usuario en Streamlit
├── tests/
│   └── test_lp_core.py           # Pruebas unitarias del motor matematico
│
├── benchmark_a_pyomo.py          # Benchmark A ejecutable con Pyomo
├── benchmark_a_multiobjective.py # Benchmark A ejecutable con AMPL
├── verify_ampl_highs.py          # Verificacion base de AMPL
│
├── requirements-pyomo.txt        # Dependencias de Pyomo + HiGHS
├── requirements-ui.txt           # Dependencias de Streamlit + pytest
├── requirements-ampl.txt         # Dependencias de AMPL + HiGHS
├── pyproject.toml                # Configuracion de proyecto y dependencias
└── docs/                         # Documentacion tecnica, ADRs y logs de agentes
```

---

## 🧪 Ejecución de Pruebas Unitarias

Para ejecutar la suite de pruebas del motor matemático:
```powershell
& ".\.venv\Scripts\python.exe" -m pytest
```

---

## 📚 Documentación Técnica

* [`docs/STATUS.md`](docs/STATUS.md): Fotografía técnica del estado actual del proyecto.
* [`docs/DECISIONS.md`](docs/DECISIONS.md): Registro histórico de decisiones arquitectónicas (ADR-001 a ADR-007).
* [`docs/METODO_PONDERACIONES.md`](docs/METODO_PONDERACIONES.md): Especificación matemática normativa de la suma ponderada normalizada.
* [`docs/LEXICOGRAPHIC_PAYOFF_MATRIX.md`](docs/LEXICOGRAPHIC_PAYOFF_MATRIX.md): Documento histórico sobre la selección secundaria de anclas; no define el método vigente.
* [`docs/END_TO_END_JSON_STREAMLIT_SOLVER_AUDIT.md`](docs/END_TO_END_JSON_STREAMLIT_SOLVER_AUDIT.md): Auditoría de sincronización de modelos entre UI y solver.
* [`docs/BENCHMARK_A_BACKEND_COMPARISON.md`](docs/BENCHMARK_A_BACKEND_COMPARISON.md): Comparativa exhaustiva Pyomo vs. AMPL.
* [`docs/PERSISTENCE_CONSTRAINT_NORMALIZATION_FIX.md`](docs/PERSISTENCE_CONSTRAINT_NORMALIZATION_FIX.md): Normalización canónica de restricciones y corrección de persistencia JSON.
* [`docs/CUSTOM_VARIABLES_AND_MODEL_LOADING.md`](docs/CUSTOM_VARIABLES_AND_MODEL_LOADING.md): Nombres personalizados de variables y carga atómica de modelos JSON.
* [`docs/MODEL_PERSISTENCE_AND_GENERAL_PLOTS.md`](docs/MODEL_PERSISTENCE_AND_GENERAL_PLOTS.md): Persistencia de modelos JSON y gráficos para $N$ variables.
* [`docs/RESULT_INTERPRETATION_AND_PLOT_REFINEMENT.md`](docs/RESULT_INTERPRETATION_AND_PLOT_REFINEMENT.md): Informe técnico de mejora de gráficos e interpretación base automática.
* [`docs/UI_UX_REFINEMENT.md`](docs/UI_UX_REFINEMENT.md): Informe de refinamiento UI/UX y modernización en Streamlit.
* [`docs/UI_MVP_HARDENING.md`](docs/UI_MVP_HARDENING.md): Informe de hardening técnico de la interfaz y motor matemático.
* [`docs/UI_MVP_VALIDATION.md`](docs/UI_MVP_VALIDATION.md): Informe de validación del MVP de interfaz.
* [`docs/agent_logs/`](docs/agent_logs/): Registro detallado de auditoría de cada hito.
