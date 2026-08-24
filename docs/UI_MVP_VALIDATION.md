# Informe de Validación: MVP de Interfaz Web (Streamlit)

**Fecha:** 23 de agosto de 2026  
**Componente:** Interfaz de usuario Streamlit (`streamlit_app.py`) y motor matemático modular (`src/solver_optimizador/`)  
**Backend:** Pyomo 6.10.1 + HiGHS 1.15.1 (APPSI / `highspy`)  
**Framework Web:** Streamlit 1.62.0  
**Test Runner:** pytest 9.1.1  

---

## 1. Arquitectura y Separación de Responsabilidades

Se implementó una arquitectura modular desacoplada para garantizar que la interfaz gráfica sea únicamente una capa de captura y presentación, mientras que toda la formulación matemática y resolución reside en el núcleo:

```text
┌────────────────────────────────────────────────────────┐
│               Capa de Interfaz (UI)                   │
│                  streamlit_app.py                      │
│   (Captura de datos, tablas dinámicas, presentación)   │
└───────────────────────────┬────────────────────────────┘
                            │
              Estructuras de Datos Fuertemente Tipadas
              (LPProblem, LinearObjective, Constraint)
                            │
┌───────────────────────────▼────────────────────────────┐
│             Capa de Dominio y Motores                  │
│               src/solver_optimizador/                  │
├───────────────────────────┬────────────────────────────┤
│  lp_models.py             │  lp_solver.py              │
│  - Definición de clases   │  - Pyomo ConcreteModel     │
│  - Enums (Sense, Operator)│  - APPSI HiGHS             │
│  - Validaciones de entrada│  - Slacks y holguras       │
├───────────────────────────┼────────────────────────────┤
│  multiobjective.py        │  plotting.py               │
│  - Matriz de pagos        │  - Región factible 2D      │
│  - Rangos de normalización│  - Espacio de objetivos 2D │
│  - Barrido de pesos       │  - Polígonos de vértices   │
│  - Dominancia de Pareto   │                            │
└───────────────────────────┴────────────────────────────┘
```

---

## 2. Flujo de Usuario

1. **Selección de Tipo de Problema:** El usuario selecciona *Monoobjetivo* o *Biobjetivo* en la barra lateral, o carga uno de los ejemplos preconfigurados.
2. **Definición de Variables:** Se indica el número de variables continuas ($x_1, \dots, x_n \ge 0$).
3. **Configuración de Objetivos:**
   * *Monoobjetivo:* Selección de sentido (Maximizar/Minimizar) y coeficientes lineales $c_j$.
   * *Biobjetivo:* Selección de sentidos independientes para $Z_1$ y $Z_2$, coeficientes, y modalidad de ponderaciones (*Barrido automático uniforme* de $N$ combinaciones o *Ponderación única personalizada* $\alpha_1, \alpha_2$).
4. **Definición de Restricciones:** Tabla interactiva editable para ingresar filas con nombre, coeficientes por variable, operador ($\le, \ge, =$) y lado derecho (RHS).
5. **Resolución:** Al pulsar **Resolver Problema**, el motor valida las entradas, formula el modelo Pyomo, ejecuta HiGHS en memoria y entrega los resultados estructurados.
6. **Visualización de Resultados:**
   * *Monoobjetivo:* Métricas clave ($Z^*, x^*$), tabla de holguras y estado activo de restricciones, y gráfico 2D de región factible.
   * *Biobjetivo:* Pestañas con matriz de pagos, rangos, tabla de corridas ponderadas, tabla de soluciones únicas con estatus de Pareto, y gráficos interactivos (Espacio de Objetivos y Región Factible 2D).

---

## 3. Pruebas Realizadas y Resultados

Se ejecutó la suite completa de pruebas unitarias mediante `pytest`:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
```

### Resultados de la Suite (`tests/test_lp_core.py`):
| Identificador de Prueba | Propósito de la Prueba | Resultado | Detalle Matemático Verificado |
| :--- | :--- | :---: | :--- |
| `test_single_objective_max` | Ejemplo 1 monoobjetivo MAX | **PASS** | $\text{MAX } Z = 3x_1 + 2x_2 \implies x^* = (2.0, 2.0), Z^* = 10.0$, holguras correctas. |
| `test_single_objective_min` | Caso A monoobjetivo MIN | **PASS** | $\text{MIN } Z = x_1 + 2x_2 \implies x^* = (3.0, 1.0), Z^* = 5.0$, holguras correctas. |
| `test_biobjective_benchmark_a` | Benchmark A académico biobjetivo MAX/MAX | **PASS** | $Z_1^* = (100, 0, 1000, 80)$, $Z_2^* = (0, 130, 390, 169)$, $\Delta Z = (610, 89)$, 6 pesos, 3 soluciones únicas no dominadas. |
| `test_biobjective_max_min` | Caso B biobjetivo MAX/MIN | **PASS** | MAX $2x_1+x_2$, MIN $x_1+3x_2$, óptimos en $(4,0)$ y $(0,0)$, rangos $(8, 4)$, ponderaciones válidas. |
| `test_biobjective_min_min` | Caso C biobjetivo MIN/MIN | **PASS** | MIN $2x_1+x_2$, MIN $x_1+2x_2$, óptimos en $(0,4)$ y $(4,0)$, rangos $(4, 4)$, no dominadas. |
| `test_infeasible_problem` | Detección de infactibilidad | **PASS** | Detecta estado `infeasible` sin lanzar excepciones de ejecución. |
| `test_unbounded_problem` | Detección de no acotamiento | **PASS** | Detecta estado `unbounded` de forma limpia. |
| `test_invalid_weights_validation` | Generación y validación de pesos | **PASS** | Valida $N \ge 2$, rechaza pesos negativos o cuya suma difiera de 1.0. |
| `test_zero_range_handling` | Tratamiento de rango nulo ($\Delta Z=0$) | **PASS** | Detiene el barrido de forma controlada sin división por cero ni falsos $W$. |
| `test_special_constraint_names` | Nombres con caracteres especiales | **PASS** | Soporta `"Demanda ≥ mínima #1"`, `"Capacidad (A+B)"` sin conflictos en Pyomo. |
| `test_non_finite_inputs_validation` | Validación de entradas numéricas finitas | **PASS** | Rechaza `NaN`, `inf`, `-inf` en objetivos, restricciones y RHS. |
| `test_plotting_functions` | Robustez de funciones gráficas | **PASS** | Retorna Figure en 2D acotado, None en $>2$ vars y no falla ante degeneraciones. |

**Total:** 12 pruebas ejecutadas, 12 aprobadas (100% PASS en 1.03s).

---

## 4. Validación de Seguridad y Ergonomía

* **Cero uso de `eval()` o `exec()`:** Todas las expresiones lineales se construyen programáticamente mediante sumatorias de términos lineales sobre estructuras de datos de Python y objetos `pyo.Var` de Pyomo.
* **Manejo Seguro de Errores del Solver:** Se configuró `solver.config.load_solution = False` para que problemas infactibles o no acotados devuelvan estados descriptivos amigables en lugar de interrumpir la aplicación con *tracebacks*.
* **Tratamiento Explícito de Rango Nulo:** Si un objetivo presenta rango nulo ($\Delta Z_k \approx 0$) entre los óptimos individuales, el motor no realiza división por cero ni sustitución arbitraria; detiene el barrido ponderado e informa la causa metodológica.
* **Validación de Números Finitos:** Toda entrada numérica es verificada mediante `is_finite_number()` para rechazar `NaN` o valores infinitos.

---

## 5. Limitaciones Actuales del MVP

1. **Variables Continuas Exclusivamente:** No soporta variables binarias ni enteras ($x_i \in \mathbb{R}_{\ge 0}$).
2. **Problemas Lineales Exclusivamente:** No soporta funciones no lineales, cuadráticas ni multiplicaciones entre variables.
3. **Visualización 2D Restringida:** El gráfico de región factible se genera únicamente cuando el número de variables es exactamente 2.
4. **Aproximación Discreta de Pareto:** El método de ponderaciones genera una aproximación discreta de soluciones no dominadas; no garantiza obtener la frontera de Pareto continua completa.
5. **Métodos Multiobjetivo Adicionales:** No incluye todavía $\varepsilon$-restricciones, programación por metas ni algoritmos evolutivos (NSGA-II).

---

## 6. Estado y Pendientes

> [!NOTE]
> El estado actual certifica que el sistema se encuentra **sin defectos críticos conocidos dentro del alcance de las pruebas automatizadas**. Esto no equivale a un producto completamente validado para producción o docencia masiva sin pruebas de usuario previas.

### Pendientes fuera del alcance actual:
- Pruebas de usuario con ejercicios reales de clase y casos docentes.
- Validación visual empírica de una mayor variedad de regiones factibles complejas o degeneradas.
- Implementación de métodos multiobjetivo complementarios ($\varepsilon$-restricciones).
- Incorporación de variables enteras (MILP) y modelos no lineales (NLP / MINLP).

