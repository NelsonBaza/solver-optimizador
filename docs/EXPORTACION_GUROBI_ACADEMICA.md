# Exportación académica Gurobi del método de las restricciones

## Propósito

El proyecto conserva `scripts/solve_model.py` con **Pyomo + HiGHS** como su
solver general y fuente de verdad. La exportación Gurobi es una capacidad
adicional para preparar un entregable académico de un problema concreto:

```text
problema.json
    ↓ scripts/export_gurobi.py
archivo_academico_gurobi.py
```

El archivo resultante contiene sus variables, restricciones y objetivos como
sentencias Gurobi directas, además de matriz de pagos, niveles epsilon, barrido,
clasificación de Pareto y gráfico. No necesita el JSON original ni ningún
módulo de este repositorio al ejecutarse.

## Generar el archivo

Desde PowerShell, en la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe scripts\export_gurobi.py `
    models\hidroelectrica_biobjetivo.json `
    --method epsilon `
    --primary 1 `
    --r 6 `
    --output entregas\hidroelectrica_restricciones_gurobi.py
```

`--method` solo admite `epsilon` en esta etapa. Si se omite `--output`, el
exportador crea `<modelo>_restricciones_gurobi.py` junto al JSON.

El exportador admite modelos biobjetivo JSON 1.0 y 1.1. Los modelos 1.1 con
familias se validan y expanden primero a la representación canónica dispersa
usada por el solver general. La primera versión del entregable Gurobi es
deliberadamente biobjetivo y de variables continuas no negativas.

Antes de escribir el archivo, el exportador reconoce de forma general familias
unidimensionales numeradas y restricciones con el mismo patrón. Cuando puede
hacerlo de manera segura genera `addVars`, `addConstrs` y comprensiones; en los
demás casos emite `addVar` y `addConstr` directos. No contiene una condición
especial basada en el nombre del modelo y el entregable no interpreta listas
genéricas de restricciones en tiempo de ejecución.

## Ejecutar el entregable

El profesor solo necesita recibir:

```text
hidroelectrica_restricciones_gurobi.py
```

En un Python que tenga Gurobi y Matplotlib disponibles:

```powershell
python -m pip install gurobipy matplotlib
python entregas\hidroelectrica_restricciones_gurobi.py
```

`gurobipy` requiere una licencia Gurobi válida para resolver. La instalación y
la licencia son responsabilidad del entorno donde se ejecuta el entregable. El
exportador puede generar el archivo aunque `gurobipy` no esté instalado.

El script académico desactiva el log detallado de Gurobi mediante:

```python
SHOW_GUROBI_LOG = False
```

Puede cambiarse a `True` si el profesor desea revisar el log del optimizador.

## Configuración editable

Al inicio del archivo generado aparecen:

```python
PRIMARY_OBJECTIVE = 1
R = 6
```

- `PRIMARY_OBJECTIVE = 1`: Z1 se optimiza y Z2 se restringe.
- `PRIMARY_OBJECTIVE = 2`: Z2 se optimiza y Z1 se restringe.
- `R`: número de intervalos; siempre se ejecutan `R + 1` problemas epsilon.

Para entregar otra configuración se recomienda volver a ejecutar el exportador,
aunque estos dos valores también son fáciles de editar manualmente.

## Formulación visible

El archivo no utiliza `setObjectiveN` como sustituto del método. Primero resuelve
cada objetivo individualmente y calcula una matriz de pagos real. Para elegir
un representante determinista de una cara óptima, fija exactamente el valor del
objetivo de la fila y optimiza el otro objetivo en su sentido original.

Después calcula mediante código:

```text
E_t = Z_min + (t/r)(Z_max - Z_min),  t = 0, ..., r
```

Para cada nivel construye un modelo Gurobi nuevo. Si el objetivo restringido es
MAX agrega `Zk >= E`; si es MIN agrega `Zk <= E`. Finalmente optimiza el objetivo
principal mediante `model.setObjective(...)` y `model.optimize()`.

Construir un modelo limpio en cada corrida evita acumular restricciones epsilon
de niveles anteriores. Las corridas infactibles o no acotadas se registran sin
cancelar el barrido completo.

## Salida y gráfico

La consola muestra:

- versión de Gurobi y configuración;
- matriz de pagos calculada;
- rango observado del objetivo restringido;
- niveles epsilon;
- estado, variables, Z1 y Z2 de cada corrida;
- soluciones únicas;
- soluciones no dominadas obtenidas por el barrido.

Los valores objetivo se reconstruyen desde el mismo vector de variables que se
publica. La clasificación respeta los sentidos MAX/MIN y usa una tolerancia
numérica.

El PNG se guarda junto al `.py`. Para el ejemplo hidroeléctrico será:

```text
entregas/hidroelectrica_restricciones_gurobi_pareto.png
```

La línea del gráfico conecta las soluciones no dominadas obtenidas; no afirma
que todos los segmentos sean siempre la frontera continua de cualquier modelo.

## Caso hidroeléctrico de referencia

La exportación versionada usa:

```python
PRIMARY_OBJECTIVE = 1
R = 6
```

Su formulación embebida procede directamente de
`models/hidroelectrica_biobjetivo.json`: 24 variables, 28 restricciones,
`MIN Z1 = 100 sum(GT_t)` y `MAX Z2 = V4`.

En el archivo generado se leen directamente estructuras como estas:

```python
periodos = range(1, 5)
T = m.addVars(periodos, lb=0, ub=70, name="T")
V = m.addVars(periodos, lb=40, ub=100, name="V")
m.addConstrs(PH[t] == 2.4525 * T[t] for t in periodos)
Z1 = 100 * gp.quicksum(GT[t] for t in periodos)
Z2 = V[4]
```

Las 12 restricciones simples de cotas se expresan naturalmente como límites de
`T` y `V`; las otras 16 se muestran como ecuaciones Gurobi. Esta representación
es matemáticamente equivalente a las 28 restricciones canónicas originales.
Las variables de cada corrida se imprimen agrupadas por familia (`T`, `V`, `S`,
`PH`, `GH` y `GT`).

La revisión de compacidad redujo el ejemplo de 518 a 278 líneas y de 20 230 a
11 081 bytes, sin minificar el código ni retirar pasos del método.

La regresión validada por el backend general es:

```text
Matriz de pagos:
opt_Z1 = (6701.25, 40)
opt_Z2 = (21416.25, 100)

E2 = [40, 50, 60, 70, 80, 90, 100]

(6701.25, 40)
(9153.75, 50)
(11606.25, 60)
(14058.75, 70)
(16511.25, 80)
(18963.75, 90)
(21416.25, 100)
```

En el entorno usado para desarrollar esta etapa `gurobipy` no estaba instalado;
por ello el archivo fue validado sintáctica y estructuralmente, pero esos
resultados no se presentan como una ejecución real de Gurobi en dicho entorno.

## Diferencia entre los dos productos

| Producto | Propósito | Dependencias en ejecución |
|---|---|---|
| `scripts/solve_model.py` | Herramienta general del proyecto | proyecto, Pyomo, HiGHS, Matplotlib |
| `.py` generado | Entregable académico concreto | Gurobi, Matplotlib, Python estándar |

El exportador no modifica `lp_solver.py`, no convierte Gurobi en dependencia del
proyecto y no sustituye el flujo normal Pyomo + HiGHS.
