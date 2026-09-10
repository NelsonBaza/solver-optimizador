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

### Entrada de modelos grandes

El editor manual se conserva para modelos pequeños. Para modelos con decenas o
cientos de restricciones, la aplicación permite:

- pegar tablas anchas desde Excel o Google Sheets usando tabulador, coma o punto y coma;
- importar CSV UTF-8/UTF-8-SIG y seleccionar hojas de archivos XLSX sin macros;
- importar matrices dispersas en formato `constraint,variable,coefficient,operator,rhs`;
- declarar nombres de variables en bloque;
- pegar o importar coeficientes de objetivos monoobjetivo y biobjetivo;
- validar y previsualizar antes de aplicar el lote de forma atómica;
- descargar las restricciones vigentes como CSV disperso.

Ejemplo ancho:

```csv
name,x1,x2,operator,rhs
R1,1,1,<=,130
R2,2.5,1,<=,250
```

Solo se muestran las primeras 20 restricciones en las vistas previas; el modelo
completo se conserva y se envía al builder. Consulte
[`docs/ENTRADA_ESCALABLE_MODELOS.md`](docs/ENTRADA_ESCALABLE_MODELOS.md).

### Modelos indexados y multiperiodo

La ruta **Modelo indexado / Familias** permite definir rangos enteros, parámetros
escalares o por período, familias de variables, objetivos estructurados y
familias de restricciones. Por ejemplo, `T=1..1000` y cinco reglas generan unas
5.000 restricciones explícitas sin escribirlas una por una.

Las referencias `t-1` y `t+1` se validan contra los límites, las expresiones no
lineales o ejecutables se rechazan y la expansión conserva coeficientes
dispersos y procedencia. La vista previa no modifica el modelo; **Aplicar modelo
indexado** reemplaza el estado explícito de forma atómica. Consulte
[`docs/MODELADO_INDEXADO.md`](docs/MODELADO_INDEXADO.md).

En consola, el esquema JSON unificado 1.1 permite combinar en un solo
`problema.json` variables y restricciones explícitas con familias indexadas 1D
o 2D. El producto cartesiano se expande a la misma representación canónica
dispersa antes de construir el problema Pyomo. El esquema 1.0 continúa siendo
compatible sin cambios.

### Qué Todavía NO Puede Resolver (Limitaciones Actuales):
* Variables enteras o binarias (MILP).
* Problemas no lineales continuos o enteros (NLP / MINLP).
* Algoritmos metaheurísticos / evolutivos (NSGA-II / pymoo).
* Programación por metas o programación compromiso.

### Método de las restricciones en backend

El método de $\varepsilon$-restricciones está disponible en el backend para
problemas LP con dos o más objetivos, cualquiera de ellos como principal y
sentidos MAX/MIN independientes. El barrido usa el producto cartesiano de los
niveles de todos los objetivos restringidos. Permanece deliberadamente fuera
de Streamlit. La API biobjetivo original y su demostración del Benchmark A se
conservan:

```powershell
& ".\.venv\Scripts\python.exe" scripts\demo_metodo_restricciones.py
```

Consulte la formulación y la estructura completa del resultado en
[`docs/METODO_RESTRICCIONES.md`](docs/METODO_RESTRICCIONES.md).

### Ejecutor general de modelos en consola

Los modelos con dos o más objetivos pueden resolverse sin la interfaz gráfica
mediante `scripts/solve_model.py`. En una terminal, el uso recomendado es
interactivo:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json
```

El modo avanzado conserva comandos no interactivos reproducibles:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6
```

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method weighted --num-weights 6
```

Por defecto, cada ejecución correcta guarda el gráfico de la frontera obtenida
en `results/<modelo>_<metodo>_pareto.png`. Use `--no-plot` para desactivarlo.
El mismo runner acepta JSON 1.0 explícito y JSON 1.1 explícito, indexado o mixto:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\ejemplo_familias_2d.json --method weighted --num-weights 6
```

El esquema 1.1 también admite `problem.type="Multiobjetivo"` con una lista
ordenada `objectives` de tres o más elementos. En ese caso epsilon permite un
`r_k` distinto mediante `--r-objective K=R` y genera proyecciones 2D del
objetivo principal contra cada objetivo restringido. Ponderaciones continúa
siendo exclusivamente biobjetivo.

El modelo hidroeléctrico biobjetivo corregido está versionado en formato
disperso dentro de `models/`. Consulte
[`docs/EJECUTOR_MODELOS_CONSOLA.md`](docs/EJECUTOR_MODELOS_CONSOLA.md).

### Scripts académicos portables

Para evaluaciones que requieren entregar únicamente un programa y su modelo,
`exports/` contiene dos ejecutores autónomos, sin imports internos del
repositorio:

```powershell
.\.venv\Scripts\python.exe exports\metodo_restricciones.py models\hidroelectrica_biobjetivo.json --primary 1 --r 6
.\.venv\Scripts\python.exe exports\metodo_ponderaciones.py models\hidroelectrica_biobjetivo.json --num-weights 6
```

Cada archivo puede copiarse fuera del repositorio junto con un JSON de esquema
1.0. Consulte [`docs/SCRIPTS_ACADEMICOS_CONSOLA.md`](docs/SCRIPTS_ACADEMICOS_CONSOLA.md).

### Exportación académica a Gurobi

De forma adicional, un modelo biobjetivo JSON 1.0 o 1.1 puede convertirse en un
único programa Gurobi autocontenido del método epsilon-constraint:

```powershell
.\.venv\Scripts\python.exe scripts\export_gurobi.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6 --output entregas\hidroelectrica_restricciones_gurobi.py
```

La generación no requiere `gurobipy`; su ejecución posterior sí requiere
Gurobi, una licencia válida y Matplotlib. El backend general continúa siendo
Pyomo + HiGHS. Consulte
[`docs/EXPORTACION_GUROBI_ACADEMICA.md`](docs/EXPORTACION_GUROBI_ACADEMICA.md).

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
│       ├── epsilon_constraint.py # Método de restricciones para LP biobjetivo
│       ├── multiobjective_epsilon.py # Epsilon-constraint para N objetivos
│       ├── unified_model.py      # Compilador JSON 1.1 explícito/indexado 1D-2D
│       ├── pareto_plot.py        # Gráficos PNG headless de frontera de Pareto
│       ├── constraint_import.py  # Parseo tabular ancho/disperso y XLSX solver-agnostic
│       ├── input_application.py  # Aplicacion atomica de lotes a estado
│       ├── indexed_model.py      # Especificacion indexada serializable
│       ├── indexed_expression.py # Parser lineal estatico y seguro
│       ├── indexed_compiler.py   # Expansion solver-agnostic a forma canonica
│       ├── indexed_application.py# Aplicacion atomica y control de fuente
│       └── plotting.py           # Visualización 2D (region factible y espacio de objetivos)
│
├── streamlit_app.py              # Interfaz de usuario en Streamlit
├── tests/
│   └── test_lp_core.py           # Pruebas unitarias del motor matematico
│
├── benchmark_a_pyomo.py          # Benchmark A ejecutable con Pyomo
├── benchmark_a_multiobjective.py # Benchmark A ejecutable con AMPL
├── scripts/
│   ├── demo_metodo_restricciones.py # Demostración ε-constraint en consola
│   └── solve_model.py                # Ejecutor general de modelos JSON
├── exports/
│   ├── metodo_restricciones.py       # Script académico portable ε-constraint
│   └── metodo_ponderaciones.py       # Script académico portable normalizado
├── models/
│   ├── hidroelectrica_biobjetivo.json # Modelo biobjetivo disperso de 4 períodos
│   ├── ejemplo_familias_1d.json       # Ejemplo 1.1 con 40 filas generadas
│   ├── ejemplo_familias_2d.json       # Ejemplo 1.1 mixto sobre J × M
│   └── ejemplo_tres_objetivos.json    # Ejemplo técnico MAX/MAX/MIN
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
* [`docs/METODO_RESTRICCIONES.md`](docs/METODO_RESTRICCIONES.md): Formulación, API y demostración del método de las restricciones en backend.
* [`docs/EJECUTOR_MODELOS_CONSOLA.md`](docs/EJECUTOR_MODELOS_CONSOLA.md): Carga y resolución general de modelos JSON desde consola.
* [`docs/MANUAL_USO_CONSOLA.md`](docs/MANUAL_USO_CONSOLA.md): Manual para preparar JSON, resolver y leer tablas y gráficos.
* [`docs/SCRIPTS_ACADEMICOS_CONSOLA.md`](docs/SCRIPTS_ACADEMICOS_CONSOLA.md): Entrega, dependencias, formato y uso de los dos scripts académicos portables.
* [`docs/EXPORTACION_GUROBI_ACADEMICA.md`](docs/EXPORTACION_GUROBI_ACADEMICA.md): Generación y ejecución de entregables Gurobi autocontenidos para epsilon-constraint.
* [`docs/ENTRADA_ESCALABLE_MODELOS.md`](docs/ENTRADA_ESCALABLE_MODELOS.md): Formatos ancho/disperso, CSV/XLSX y aplicación atómica de modelos grandes.
* [`docs/MODELADO_INDEXADO.md`](docs/MODELADO_INDEXADO.md): Conjuntos, parámetros, familias, sintaxis segura, expansión y trazabilidad.
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
