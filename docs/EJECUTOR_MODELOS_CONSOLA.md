# Ejecutor general de modelos multiobjetivo en consola

`scripts/solve_model.py` carga modelos JSON compatibles con los esquemas 1.0 y
1.1 del repositorio y ejecuta los métodos multiobjetivo disponibles sin
depender de Streamlit. El esquema 1.1 es el recomendado para modelos nuevos:
permite combinar contenido explícito e indexado en un único `problema.json`.

## Flujo de carga

El runner realiza explícitamente estas operaciones:

1. lee el archivo como JSON UTF-8;
2. valida y normaliza el contenido mediante `deserialize_model()`;
3. exige que el modelo tenga dos o más objetivos;
4. normaliza los objetivos a una lista ordenada y construye un
   `MultiobjectiveProblem` mediante
   `build_multiobjective_problem_from_state()`;
5. para dos objetivos conserva los motores validados; para tres o más usa
   `solve_multiobjective_epsilon_constraint()`;
6. presenta matriz de pagos, corridas completas, variables, valores objetivo,
   soluciones únicas y clasificación Pareto;
7. genera por defecto el PNG biobjetivo o proyecciones 2D para N objetivos;
8. exporta los mismos resultados, sin volver a resolver, a un libro Excel.

Cuando el archivo es 1.1, entre los pasos 2 y 3 se expanden conjuntos,
parámetros, variables indexadas, términos indexados y familias de restricciones.
El resultado es la misma representación canónica explícita y dispersa que
recibe el `problem_builder`; el solver no distingue el origen de cada fila.

El modelo no está codificado dentro del script. El nombre, las variables, los
objetivos y las restricciones proceden del archivo entregado como argumento.
Un objetivo puede declarar `name` para mostrar un eje descriptivo y
`metadata.plot_title` puede definir un título gráfico corto. El nombre completo
de `metadata.name` siempre se conserva en la salida de consola.

## Uso interactivo recomendado

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json
```

Sin `--method`, y únicamente si stdin es una terminal, el runner pregunta el
método aplicable, objetivo principal, intervalos y confirmación. Reintenta las
entradas sencillas inválidas. En stdin no interactivo, omitir `--method`
produce un error de uso con código 2 y nunca bloquea CI.

## Modo avanzado y reproducible

```text
solve_model.py MODEL_FILE --method {epsilon,weighted}
               [--primary K] [--r INT] [--r-objective K=R]
               [--num-weights INT] [--no-plot] [--no-excel]
```

- `model_file`: ruta del JSON.
- `--method epsilon`: método de las restricciones.
- `--primary K`: objetivo principal de ε-constraint; por defecto `1`.
- `--r INT`: intervalos globales para cada objetivo restringido; por defecto
  `6`.
- `--r-objective K=R`: sobrescritura repetible por objetivo restringido.
- `--method weighted`: ponderaciones normalizadas existentes.
- `--num-weights INT`: cantidad de pesos uniformes, al menos `2`; por defecto
  `6`.
- `--no-plot`: desactiva la creación del PNG. Sin esta opción, el archivo se
  guarda en `results/<modelo>_<metodo>_pareto.png` usando un backend headless.
- `--no-excel`: desactiva únicamente el libro. Sin esta opción se guarda
  `results/<modelo>_<metodo>.xlsx`. `--no-plot` no desactiva el Excel.

Con `p` objetivos, epsilon ejecuta el producto de `(r_k + 1)` para los `p-1`
objetivos restringidos. Cada combinación es una resolución real. Un objetivo
MAX genera `Zk(x) >= E_k,t` y uno MIN genera `Zk(x) <= E_k,t`.
Ponderaciones continúa admitiendo exactamente dos objetivos y su formulación
normalizada no cambió.

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
results/hidroelectrica_biobjetivo_epsilon.xlsx
```

## Libro Excel de resultados

El libro se construye después del solver a partir del objeto de resultados ya
obtenido. No vuelve a optimizar, no cambia tolerancias, niveles, pesos ni
clasificación Pareto. Sus hojas estables son:

- `Resumen`: modelo, método, objetivos, configuración, conteos y tiempos;
- `Matriz_pagos`: anclas, estados, objetivos y variables disponibles;
- `Corridas`: todas las corridas, incluidas las no óptimas;
- `Variables`: una fila por corrida y una columna por variable;
- `No_dominadas`: exactamente las soluciones que el backend ya clasificó como
  no dominadas obtenidas;
- `Restricciones`: evaluación de restricciones originales y epsilon desde el
  vector `x` ya publicado, con holgura y actividad.

Las celdas almacenan números, no textos redondeados. El formato visual limita
la cantidad de decimales mostrados, pero conserva el valor numérico admitido
por Excel. Cada hoja tiene encabezados destacados, autofiltro, fila congelada y
anchos ajustados.

## Entrada unificada 1.1

Un solo objeto `problem` puede incluir simultáneamente:

- `variables` y `constraints` explícitas;
- `sets` y `parameters`;
- `variable_families` de una o dos dimensiones;
- `indexed_terms` dentro de cada objetivo;
- `constraint_families` de una o dos dimensiones.

Para tres o más objetivos, el esquema 1.1 usa una lista ordenada:

```json
"type": "Multiobjetivo",
"objectives": [
  {"name": "Costo", "sense": "Minimizar", "coefficients": {"x": 4}},
  {"name": "Servicio", "sense": "Maximizar", "coefficients": {"y": 1}},
  {"name": "Uso", "sense": "Minimizar", "coefficients": {"x": 1, "y": 1}}
]
```

El orden define Z1, Z2, ..., Zp. Para `Biobjetivo`, `objectives` también se
acepta con exactamente dos elementos. `bio_objectives` sigue siendo compatible;
ambos campos juntos se rechazan para evitar ambigüedad. La matriz de pagos
general contiene `p × p` valores y sus extremos observados alimentan los
niveles epsilon.

Con tres o más objetivos se guardan proyecciones del principal contra cada
restringido, como `results/modelo_epsilon_Z1_vs_Z2.png`. La dominancia se
calcula en las `p` dimensiones; el gráfico no se presenta como la frontera
completa.

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
