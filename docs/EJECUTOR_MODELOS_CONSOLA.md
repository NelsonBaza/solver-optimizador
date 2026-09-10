# Ejecutor general de modelos biobjetivo en consola

`scripts/solve_model.py` carga modelos JSON compatibles con los esquemas 1.0 y
1.1 del repositorio y ejecuta los métodos multiobjetivo disponibles sin
depender de Streamlit. El esquema 1.1 es el recomendado para modelos nuevos:
permite combinar contenido explícito e indexado en un único `problema.json`.

## Flujo de carga

El runner realiza explícitamente estas operaciones:

1. lee el archivo como JSON UTF-8;
2. valida y normaliza el contenido mediante `deserialize_model()`;
3. exige que `problem.type` sea `Biobjetivo`;
4. construye un `BiobjectiveProblem` mediante
   `build_biobjective_problem_from_state()`;
5. despacha a `solve_biobjective_epsilon_constraint()` o
   `solve_biobjective_weighted()` según `--method`;
6. presenta matriz de pagos, corridas completas, variables, valores objetivo,
   soluciones únicas y clasificación Pareto;
7. genera por defecto un PNG del espacio de objetivos y la frontera obtenida.

Cuando el archivo es 1.1, entre los pasos 2 y 3 se expanden conjuntos,
parámetros, variables indexadas, términos indexados y familias de restricciones.
El resultado es la misma representación canónica explícita y dispersa que
recibe el `problem_builder`; el solver no distingue el origen de cada fila.

El modelo no está codificado dentro del script. El nombre, las variables, los
objetivos y las restricciones proceden del archivo entregado como argumento.

## Uso

```text
solve_model.py MODEL_FILE --method {epsilon,weighted}
               [--primary {1,2}] [--r INT] [--num-weights INT] [--no-plot]
```

- `model_file`: ruta del JSON.
- `--method epsilon`: método de las restricciones.
- `--primary {1,2}`: objetivo principal de ε-constraint; por defecto `1`.
- `--r INT`: cantidad de intervalos, con `r >= 1`; por defecto `6`.
- `--method weighted`: ponderaciones normalizadas existentes.
- `--num-weights INT`: cantidad de pesos uniformes, al menos `2`; por defecto
  `6`.
- `--no-plot`: desactiva la creación del PNG. Sin esta opción, el archivo se
  guarda en `results/<modelo>_<metodo>_pareto.png` usando un backend headless.

Ejemplos obligatorios desde PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6
```

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method weighted --num-weights 6
```

La ayuda completa está disponible con:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py --help
```

## Modelo hidroeléctrico de validación

`models/hidroelectrica_biobjetivo.json` contiene 24 variables y las 28
restricciones originales del modelo corregido de cuatro períodos. El JSON usa
representación dispersa: los objetivos y restricciones almacenan únicamente
coeficientes distintos de cero.

Objetivos:

```text
MIN Z1 = 100 GT1 + 100 GT2 + 100 GT3 + 100 GT4
MAX Z2 = V4
```

El barrido `--method epsilon --primary 1 --r 6` produce:

| t | E2 | Z1 | Z2 |
|---:|---:|---:|---:|
| 0 | 40 | 6701.25 | 40 |
| 1 | 50 | 9153.75 | 50 |
| 2 | 60 | 11606.25 | 60 |
| 3 | 70 | 14058.75 | 70 |
| 4 | 80 | 16511.25 | 80 |
| 5 | 90 | 18963.75 | 90 |
| 6 | 100 | 21416.25 | 100 |

Las siete corridas satisfacen, dentro de tolerancia numérica:

```text
Z1 = 245.25 * V4 - 3108.75,  40 <= V4 <= 100
```

Los extremos de la matriz de pagos son `(Z1,Z2)=(6701.25,40)` y
`(21416.25,100)`.

La ejecución epsilon también crea:

```text
results/hidroelectrica_biobjetivo_epsilon_pareto.png
```

## Entrada unificada 1.1

Un solo objeto `problem` puede incluir simultáneamente:

- `variables` y `constraints` explícitas;
- `sets` y `parameters`;
- `variable_families` de una o dos dimensiones;
- `indexed_terms` dentro de cada objetivo;
- `constraint_families` de una o dos dimensiones.

Las referencias explícitas a una variable expandida pueden usar `X_1_2` o la
forma legible `X[1,2]`. Los parámetros indexados 2D escriben sus claves como
`"1,2"`. Los límites opcionales por índice se declaran en `index_ranges`.

Consulte los ejemplos versionados:

- `models/ejemplo_familias_1d.json`: 40 restricciones generadas;
- `models/ejemplo_familias_2d.json`: mezcla explícita/indexada y producto
  cartesiano `J × M`.

El esquema histórico 1.0 mantiene exactamente su significado y continúa
cargando sin migración. La especificación indexada independiente usada por la
interfaz conserva su compatibilidad; el formato unificado 1.1 se incorpora en
esta etapa a la herramienta principal de consola.

El manual paso a paso para usuarios está en `docs/MANUAL_USO_CONSOLA.md`.
