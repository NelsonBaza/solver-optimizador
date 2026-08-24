# Registro de Implementación: MVP de Interfaz Streamlit para Programación Lineal

**Fecha:** 23 de agosto de 2026  
**Autor:** Antigravity (Google DeepMind)  
**Objetivo:** Desarrollar una interfaz gráfica funcional en Streamlit para Programación Lineal continua monoobjetivo y biobjetivo (método de ponderaciones normalizado), desacoplando el motor matemático de la interfaz y verificando el núcleo con pruebas unitarias.

---

## 1. Alcance y Requisitos
* **Alcance:**
  * Programación Lineal continua ($x \ge 0$).
  * Modalidades: Monoobjetivo (Max/Min) y Biobjetivo ($Z_1, Z_2$ Max/Min).
  * Backend matemático provisional: `Pyomo 6.10.1` + `HiGHS 1.15.1` (`highspy` APPSI).
  * Método multiobjetivo: Suma ponderada normalizada mediante rangos de la matriz de pagos.
  * Visualización 2D para región factible ($n=2$) y espacio de objetivos ($m=2$).
  * Ejemplos precargados interactivos.
  * Cero uso de `eval()` o `exec()`.
* **Exclusiones estrictas:**
  * No implementar $\varepsilon$-restricciones, pymoo/NSGA-II, NLP, MINLP, IPOPT, SCIP, variables enteras ni arquitecturas de plugins complejas.

---

## 2. Diseño y Estructura Creada

Se estructuró el proyecto separando estrictamente la interfaz de la lógica matemática:

* **`src/solver_optimizador/`**:
  * `__init__.py`: Exportaciones del paquete.
  * `lp_models.py`: Estructuras de datos (`Sense`, `Operator`, `LinearObjective`, `LinearConstraint`, `LPProblem`, `BiobjectiveProblem`, `LPSolution`, `MultiobjectiveSolution`).
  * `lp_solver.py`: Formulación y resolución de LP monoobjetivo con Pyomo + HiGHS.
  * `multiobjective.py`: Motor biobjetivo (óptimos individuales, matriz de pagos, rangos, barrido de pesos, detección de soluciones únicas y clasificación de no dominancia).
  * `plotting.py`: Generación de figuras 2D (región factible y espacio de objetivos).
* **`streamlit_app.py`**: Interfaz de usuario interactiva en Streamlit.
* **`tests/test_lp_core.py`**: Suite de pruebas unitarias con `pytest`.

---

## 3. Dependencias Instaladas y Fijadas
* `streamlit==1.62.0`
* `pytest==9.1.1`
* Se creó `requirements-ui.txt` y se actualizaron `pyproject.toml` y `[tool.pytest.ini_options]`.

---

## 4. Hallazgos y Correcciones Durante el Desarrollo
1. **Configuración de carga de soluciones en APPSI HiGHS:**
   * Al ejecutar pruebas de infactibilidad y no acotamiento, Pyomo APPSI lanzaba por defecto un `RuntimeError` al intentar cargar variables inexistentes (`load_solution = True`).
   * **Solución:** Se configuró `solver.config.load_solution = False`. De este modo, el solver retorna el `termination_condition` limpio (`infeasible`, `unbounded`), y únicamente cuando el estado es `optimal` se invoca `results.solution_loader.load_vars()`.

---

## 5. Resultados de Pruebas Unitarias
Se ejecutaron 6 pruebas unitarias con `pytest`:
* `test_single_objective_example`: **PASS** ($x_1=2, x_2=2, Z=10$, holguras correctas).
* `test_biobjective_benchmark_a`: **PASS** ($Z_1^*=1000, Z_2^*=169$, rangos 610 y 89, 6 corridas, 3 soluciones únicas no dominadas).
* `test_infeasible_problem`: **PASS** (retorna estado infactible sin excepciones).
* `test_unbounded_problem`: **PASS** (retorna estado no acotado de forma limpia).
* `test_weight_combinations_generator`: **PASS** (valida generación y rechaza pesos no válidos).
* `test_model_validation_errors`: **PASS** (valida restricciones de integridad).

---

## 6. Resultado Final
* La interfaz gráfica inicia limpiamente con:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m streamlit run streamlit_app.py
  ```
* El repositorio mantiene total trazabilidad, higiene de dependencias y pruebas al 100%.
