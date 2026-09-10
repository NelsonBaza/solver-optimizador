# Manual de uso del programa en consola

## 1. Qué hace el programa

El programa lee un problema de programación lineal con dos o más objetivos
desde un único archivo JSON, lo valida, lo convierte a una forma explícita y
dispersa, lo resuelve con Pyomo + HiGHS y muestra los resultados en PowerShell.
También guarda gráficos PNG de los puntos obtenidos y un libro Excel con todos
los resultados.

```text
problema.json
    ↓ validación y expansión, si existen familias
scripts/solve_model.py
    ↓ Pyomo + HiGHS
resultados en consola + gráficos y Excel en results/
```

Los únicos métodos multiobjetivo disponibles son:

1. método de las restricciones o *epsilon-constraint*, para dos o más
   objetivos;
2. método de ponderaciones normalizadas, exclusivamente para dos objetivos.

No hay que modificar `solve_model.py` para resolver otro ejercicio. Se cambia
el JSON.

## 2. Archivos y dependencias

Para usar la herramienta completa se necesita el repositorio, un archivo JSON
y el entorno Python del proyecto. Las dependencias principales ya declaradas
son Pyomo, HiGHS y Matplotlib.

Desde una instalación nueva:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Para abrir PowerShell en la carpeta del proyecto puede usar el Explorador de
Windows: abra `solver-optimizador`, haga clic en la barra de dirección, escriba
`powershell` y presione Enter. Compruebe el entorno con:

```powershell
.\.venv\Scripts\python.exe --version
```

Consulte todas las opciones con:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py --help
```

## 3. Ejecución recomendada: modo interactivo

La forma normal de uso es indicar solamente el JSON:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json
```

El programa muestra el nombre, tamaño y objetivos del modelo. Con dos objetivos
pregunta si desea ponderaciones o restricciones. Con tres o más informa que el
método disponible es restricciones. Si escoge restricciones:

1. explica qué es el objetivo principal;
2. permite escoger `Z1`, `Z2`, `Z3`, etc.;
3. pregunta un `r` independiente para cada objetivo restringido;
4. muestra el número total de corridas antes de resolver;
5. solicita confirmación con `¿Desea continuar? [S/n]:`.

Enter, `S` o `s` continúan. `N` o `n` cancelan sin llamar al solver. Una
respuesta inválida vuelve a solicitarse. El **objetivo principal** es la
función que el programa continúa optimizando directamente; las demás se
convierten en restricciones epsilon.

Ejemplo con tres objetivos: si `Z1` es principal, `r2=4` y `r3=6`, se ejecutan:

```text
(r2 + 1) × (r3 + 1) = 5 × 7 = 35 corridas
```

El programa advierte cuando la selección supera 500 corridas, pero no impone
un límite arbitrario.

## 4. Modo avanzado / ejecución reproducible

Los comandos completos no hacen preguntas y son apropiados para pruebas,
automatización o para reproducir un informe.

### Método de las restricciones

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6
```

En N objetivos, `--r` es el valor predeterminado para todos los restringidos.
La opción avanzada repetible `--r-objective K=R` sobrescribe uno de ellos:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema3.json --method epsilon --primary 1 --r 6 --r-objective 2=4 --r-objective 3=6
```

Para elegir Z2 como principal, cambie únicamente su índice y no le asigne un
`r` propio:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema3.json --method epsilon --primary 2 --r 6 --r-objective 1=4 --r-objective 3=6
```

### Ponderaciones normalizadas

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method weighted --num-weights 6
```

Ponderaciones rechaza claramente los modelos con tres o más objetivos.

### Sin gráfico

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6 --no-plot
```

El libro Excel se sigue creando. Para desactivar solo el Excel:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6 --no-excel
```

El script Gurobi también se genera por defecto. Para omitir únicamente esa
salida:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6 --no-gurobi-script
```

## 5. Significado de las opciones

- `model_file`: ruta de `problema.json`.
- `--method epsilon`: selecciona el método de las restricciones.
- `--method weighted`: selecciona ponderaciones normalizadas.
- `--primary K`: usa ZK como objetivo principal; debe existir en el modelo.
- `--r`: número global de intervalos epsilon para cada objetivo restringido.
- `--r-objective K=R`: cambia `r` solo para ZK; puede repetirse, no admite el
  objetivo principal y exige `R >= 1`.
- `--num-weights`: número de pares uniformes `(alpha1, alpha2)`. Debe ser al
  menos 2.
- `--no-plot`: resuelve y muestra resultados, pero no crea PNG.
- `--no-excel`: resuelve y muestra resultados, pero no crea el libro `.xlsx`.
- `--no-gurobi-script`: resuelve normalmente, pero no crea el `.py` autónomo.

Por defecto, consola, gráfico, Excel y script Gurobi están activos e
independientes. El PNG se llama `results/<modelo>_<metodo>_pareto.png`; el libro
se llama `results/<modelo>_<metodo>.xlsx`; y el script se llama
`results/<modelo>_<metodo>_gurobi.py`. El Excel se construye desde las corridas
ya resueltas. El generador Gurobi usa el problema y la configuración ya
disponibles, sin llamar nuevamente al optimizador Pyomo.

Las opciones `--primary`, `--r` y `--r-objective` corresponden a epsilon. La
opción `--num-weights` corresponde a ponderaciones. Si se omite `--method` en
una entrada que no es una terminal interactiva, el programa termina con un
error útil en vez de esperar indefinidamente.

## 6. Cómo entender los resultados

### Objetivos y matriz de pagos

- **Z1, Z2, ..., Zp:** las medidas que se quieren optimizar.
- **Sentido MIN/MAX:** indica si un valor menor o mayor es preferible.
- **Objetivo principal:** el que se optimiza directamente en epsilon.
- **Objetivos restringidos:** todos los no principales, exigidos mediante sus
  niveles E.
- **Matriz de pagos:** matriz `p × p`; cada fila se obtiene optimizando
  individualmente un objetivo. Si hay empate, se fijan los valores alcanzados
  y se optimizan los demás por índice, respetando sus sentidos.
- **Zk_min y Zk_max:** menor y mayor valor observado en la columna k de la
  matriz de pagos. Son extremos observados, no se presentan como nadir exacto.

### Método de las restricciones

Cada objetivo restringido Zk tiene su propio `r_k`. Los niveles se calculan:

```text
E_k,t = Zk_min + (t/r_k)(Zk_max - Zk_min),  t = 0, ..., r_k
```

Si Zk es MAX, se agrega `Zk(x) >= E_k,t`; si es MIN, se agrega
`Zk(x) <= E_k,t`. Cada combinación cartesiana de niveles produce una
resolución completa. El total es el producto de todos los `(r_k + 1)`. No se
usan pesos ni normalización.

### Ponderaciones normalizadas

Una **ponderación** asigna importancia mediante `alpha1` y `alpha2`, con suma
igual a 1. Los dos objetivos se orientan a una escala común:

```text
Objetivo MAX: Nk = (Zk - Zk_min) / (Zk_max - Zk_min)
Objetivo MIN: Nk = (Zk_max - Zk) / (Zk_max - Zk_min)
W = alpha1*N1 + alpha2*N2
```

- `N1` y `N2` son los valores normalizados.
- `W` es la función ponderada que se maximiza.
- Un peso como `(0.8, 0.2)` da mayor importancia a Z1.

### Soluciones únicas, repetidas y Pareto

Una **solución repetida** aparece cuando varias corridas producen el mismo
vector de variables y todos los objetivos dentro de tolerancia. Las corridas
originales siguen en la salida; solo se agrupan en el resumen.

Una **solución no dominada** no tiene otra solución obtenida que sea igual o
mejor en todos los objetivos y estrictamente mejor en al menos uno, respetando
cada sentido MIN/MAX. El informe las llama **soluciones no dominadas obtenidas
por el barrido**: un barrido finito no demuestra que contenga toda la frontera
continua.

## 7. Cómo leer los gráficos

Con dos objetivos, el eje horizontal es Z1 y el vertical Z2. Los puntos rojos
representan soluciones no dominadas; los puntos dominados, si existen, se
muestran con otra marca. La línea conecta los puntos no dominados por Z1.
Esta línea facilita la lectura de las **soluciones obtenidas por el barrido**;
no afirma que todos los segmentos intermedios sean siempre parte de la
frontera para cualquier modelo.

Las etiquetas epsilon muestran el identificador (`S1`, `S2`, etc.) y el nivel
E. Las etiquetas ponderadas muestran el identificador (`A`, `B`, etc.) y los
valores de `alpha1` que generaron esa solución. Los desplazamientos son
deterministas.

Los campos opcionales `name` de cada objetivo evitan rótulos redundantes como
`Z1 — Z1`. El campo opcional `metadata.plot_title` permite un título gráfico
corto; `metadata.name` conserva el nombre completo mostrado en consola.

No debe interpretarse que “arriba y a la derecha” siempre es mejor: si un
objetivo es MIN, la dirección preferida es hacia valores menores.

Con tres o más objetivos no se presenta un plano como si fuera toda la
frontera. Se crea una proyección del objetivo principal contra cada objetivo
restringido, por ejemplo `Z1_vs_Z2` y `Z1_vs_Z3`. La condición dominada/no
dominada se calcula usando **todos** los objetivos. Los títulos dicen
“Proyección de soluciones multiobjetivo”. `--no-plot` desactiva todas las
imágenes.

## 8. Un único formato JSON

El usuario trabaja siempre con un solo `problema.json`.

- El esquema 1.0 histórico describe variables, objetivos y restricciones
  explícitos. Continúa siendo compatible sin cambios.
- El esquema 1.1 recomendado permite usar contenido explícito, indexado o una
  mezcla.
- En 1.1, `problem.type = "Multiobjetivo"` exige tres o más elementos en la
  lista ordenada `objectives`. La misma lista admite exactamente dos para
  `Biobjetivo`. El campo histórico `bio_objectives` sigue admitido, pero no
  puede aparecer junto con `objectives`.

El flujo interno del esquema 1.1 es:

```text
JSON 1.1
  → validar conjuntos, parámetros, referencias y linealidad
  → expandir familias 1D/2D
  → variables y restricciones canónicas dispersas
  → problem_builder
  → Pyomo + HiGHS
```

El solver recibe siempre la forma canónica y no sabe qué filas se escribieron
a mano. El orden de `objectives` define Z1, Z2, ..., Zp; `name` es opcional.

### Ejemplo técnico de tres objetivos

```json
{
  "schema_version": "1.1",
  "metadata": {"name": "Ejemplo técnico de tres objetivos"},
  "problem": {
    "type": "Multiobjetivo",
    "variables": ["x", "y"],
    "objectives": [
      {"name": "Producción X", "sense": "Maximizar", "coefficients": {"x": 1}},
      {"name": "Producción Y", "sense": "Maximizar", "coefficients": {"y": 1}},
      {"name": "Uso total", "sense": "Minimizar", "coefficients": {"x": 1, "y": 1}}
    ],
    "constraints": [
      {"name": "Total", "coefficients": {"x": 1, "y": 1}, "operator": "<=", "rhs": 10}
    ]
  }
}
```

El archivo completo y verificable es `models/ejemplo_tres_objetivos.json`.

## 9. Problema pequeño con dos variables

Guarde este contenido como `problema.json`:

```json
{
  "schema_version": "1.1",
  "metadata": {"name": "Ejemplo pequeño"},
  "problem": {
    "type": "Biobjetivo",
    "variables": ["x", "y"],
    "bio_objectives": {
      "obj1": {
        "sense": "Maximizar",
        "coefficients": {"x": 3, "y": 1}
      },
      "obj2": {
        "sense": "Maximizar",
        "coefficients": {"x": 1, "y": 3}
      }
    },
    "constraints": [
      {
        "name": "Capacidad",
        "coefficients": {"x": 1, "y": 1},
        "operator": "<=",
        "rhs": 10
      }
    ]
  }
}
```

Los coeficientes son dispersos: no es necesario escribir las variables cuyo
coeficiente es cero.

## 10. Cuándo usar restricciones explícitas

Use `constraints` cuando una regla es única o excepcional. Ejemplo:

```json
{
  "name": "CasoEspecial",
  "coefficients": {"X[1,1]": 1},
  "operator": ">=",
  "rhs": 1
}
```

En coeficientes explícitos puede referirse a una variable indexada como
`X[1,1]` o por su nombre expandido `X_1_1`.

## 11. Conjuntos, parámetros y variables indexadas

Un **conjunto** es un rango entero inclusivo:

```json
"sets": {
  "J": {"start": 1, "end": 40},
  "M": {"start": 1, "end": 3}
}
```

Un **parámetro escalar** tiene un único valor:

```json
"capacidad": {"value": 10}
```

Un **parámetro indexado** exige un valor para cada elemento de su dominio:

```json
"demanda": {
  "indices": ["j"],
  "sets": ["J"],
  "values": {"1": 8, "2": 9, "3": 7}
}
```

Para dos índices, las claves se separan por coma:

```json
"costo": {
  "indices": ["j", "m"],
  "sets": ["J", "M"],
  "values": {"1,1": 1.2, "1,2": 1.5, "2,1": 1.1, "2,2": 1.4}
}
```

Una variable 1D genera `X_1`, `X_2`, etc.:

```json
{"name": "X", "indices": ["j"], "sets": ["J"]}
```

Una variable 2D genera el producto cartesiano, por ejemplo `X_1_1`, `X_1_2`,
`X_2_1` y `X_2_2`:

```json
{"name": "X", "indices": ["j", "m"], "sets": ["J", "M"]}
```

## 12. Muchas restricciones repetitivas: ejemplo 1D

Si `J=1..40`, esta única familia genera 40 restricciones:

```json
{
  "name": "Limite",
  "indices": ["j"],
  "sets": ["J"],
  "expression": "X[j] <= capacidad[j]"
}
```

El ejemplo completo está en `models/ejemplo_familias_1d.json`. La salida
canónica contiene `Limite_1` hasta `Limite_40` y nunca almacena los miles de
ceros de una matriz densa.

Para usar una referencia anterior, limite el rango para que exista `j-1`:

```json
{
  "name": "Enlace",
  "indices": ["j"],
  "sets": ["J"],
  "index_ranges": {"j": {"start": 2}},
  "expression": "X[j] - X[j-1] <= paso"
}
```

## 13. Regla sobre dos índices

Con `J=1..3` y `M=1..2`, esta familia genera seis restricciones:

```json
{
  "name": "Cota",
  "indices": ["j", "m"],
  "sets": ["J", "M"],
  "expression": "X[j,m] <= capacidad"
}
```

Los nombres resultantes son `Cota_1_1`, `Cota_1_2`, `Cota_2_1`, `Cota_2_2`,
`Cota_3_1` y `Cota_3_2`. Esto es una validación técnica del producto
cartesiano, no la formulación de un ejercicio real de máquinas paralelas. El
archivo completo es `models/ejemplo_familias_2d.json`.

## 14. Cómo mezclar explícito e indexado

Dentro del mismo objeto `problem` escriba ambos campos:

```json
"constraints": [
  {
    "name": "CasoEspecial",
    "coefficients": {"X[1,1]": 1},
    "operator": ">=",
    "rhs": 1
  }
],
"constraint_families": [
  {
    "name": "Cota",
    "indices": ["j", "m"],
    "sets": ["J", "M"],
    "expression": "X[j,m] <= capacidad"
  }
]
```

Los objetivos también pueden mezclar coeficientes explícitos e indexados:

```json
"obj1": {
  "sense": "Maximizar",
  "coefficients": {"reserva": 0.1},
  "indexed_terms": [
    {
      "variable_family": "X",
      "indices": ["j", "m"],
      "sets": ["J", "M"],
      "coefficient": "costo[j,m]"
    }
  ]
}
```

## 15. Seguridad y linealidad

Se permiten números finitos, parámetros, variables, suma, resta,
multiplicación por una expresión numérica, división por constante y los
operadores `<=`, `>=` y `=`. No se ejecuta Python desde el JSON.

Se rechazan, entre otros:

```text
X[j] * Y[j]       producto entre variables
X[j] ** 2         potencia
X[j] / Y[j]       división por variable
open("archivo")   llamada a función
```

## 16. Ejemplo hidroeléctrico

El modelo histórico explícito se ejecuta así:

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6
```

Debe producir:

```text
E2 = [40, 50, 60, 70, 80, 90, 100]
V4=40  -> Z1=6701.25
V4=50  -> Z1=9153.75
V4=60  -> Z1=11606.25
V4=70  -> Z1=14058.75
V4=80  -> Z1=16511.25
V4=90  -> Z1=18963.75
V4=100 -> Z1=21416.25
```

El gráfico queda en:

```text
results/hidroelectrica_biobjetivo_epsilon_pareto.png
```

El libro completo queda en:

```text
results/hidroelectrica_biobjetivo_epsilon.xlsx
```

## 17. Cómo leer el libro Excel

El libro contiene seis hojas:

1. `Resumen`: nombre, archivo, método, objetivos, configuración, conteos y
   tiempos.
2. `Matriz_pagos`: una fila por ancla, valores de todos los objetivos y las
   variables disponibles.
3. `Corridas`: todas las resoluciones realizadas. En epsilon muestra `t` y `E`;
   con tres o más objetivos usa `t_Zk` y `E_Zk`; en ponderaciones muestra
   `alpha1`, `alpha2`, `N1`, `N2` y `W`.
4. `Variables`: una fila por corrida y una columna por variable. Una corrida
   infactible conserva su fila con las variables vacías.
5. `No_dominadas`: las soluciones que el backend ya clasificó como soluciones
   no dominadas obtenidas por el barrido, junto con sus generadores y variables.
6. `Restricciones`: lado izquierdo, operador, lado derecho, holgura y condición
   activa, evaluados desde el mismo vector de variables de cada corrida óptima.

Los números siguen siendo celdas numéricas. El aspecto puede mostrar menos
decimales, pero la exportación no redondea deliberadamente los valores. Si la
escritura del Excel falla, la consola lo informa como error de exportación; no
lo presenta como fallo del solver ni elimina un gráfico ya creado.

## 17.1 Cómo usar el script Gurobi generado

El archivo `*_gurobi.py` es una traducción autónoma del modelo continuo y de
la configuración seleccionada. Contiene los coeficientes necesarios y no lee el
JSON ni importa el proyecto. Generarlo no requiere Gurobi; ejecutarlo requiere
`gurobipy`, `matplotlib` y una licencia que Gurobi pueda localizar normalmente.

```powershell
py -3.12 results\planeacion_agregada_biobjetivo_epsilon_gurobi.py
```

Esta ejecución vuelve a resolver realmente con Gurobi: calcula sus propias
anclas, matriz de pagos, niveles o pesos, corridas y soluciones no dominadas.
Para dos objetivos guarda `*_gurobi_pareto.png`. Para más objetivos guarda
proyecciones del objetivo principal; si existen exactamente dos variables y la
región es representable y acotada, también guarda
`*_gurobi_region_factible.png`.

## 18. Qué entregar en una evaluación

Para una entrega académica portable puede copiar únicamente:

```text
metodo_restricciones.py + problema.json
```

o:

```text
metodo_ponderaciones.py + problema.json
```

Esos scripts están en `exports/` y permanecen estables. En esta etapa aceptan
el formato explícito compatible que ya tenían; todavía no incorporan gráficos
ni expansión del esquema 1.1. Para modelos indexados 1D/2D y gráficos, la
referencia es `scripts/solve_model.py` dentro del proyecto.

## 19. Errores frecuentes

- **Archivo no encontrado:** revise la ruta y la extensión `.json`.
- **JSON inválido:** revise comas, llaves, corchetes y comillas dobles.
- **Variable desconocida:** declare la variable o corrija la referencia; use
  `X[1,2]` o `X_1_2` solo si ese índice existe.
- **Operador inválido:** use exclusivamente `<=`, `>=` o `=`.
- **Parámetro incompleto:** un parámetro indexado necesita exactamente un valor
  para cada elemento del conjunto o producto cartesiano.
- **Índice fuera de rango:** ajuste el conjunto o `index_ranges`; `j-1` no es
  válido en `j=1` si el conjunto empieza en 1.
- **Modelo infactible:** ninguna solución satisface todas las restricciones.
- **Modelo no acotado:** falta una cota y el objetivo puede mejorar sin límite.
- **r inválido:** `--r` debe ser entero y al menos 1.
- **r por objetivo inválido:** use `K=R`, no repita ZK y no asigne r al
  objetivo principal.
- **Objetivo principal inválido:** el índice debe existir en la lista
  `objectives`.
- **Peso inválido:** `--num-weights` debe ser entero y al menos 2; los pares
  internos son no negativos y suman 1.
- **Rango de normalización nulo:** las dos anclas dan el mismo valor para algún
  objetivo; no se puede aplicar la normalización vigente.
- **No se puede guardar Excel:** cierre el libro si está abierto en otra
  aplicación y compruebe permisos de escritura en `results/`.
- **Gurobi no ejecuta el script:** compruebe `gurobipy` y la licencia mediante
  las herramientas oficiales. La generación del archivo no necesita Gurobi.

## 20. QUIERO HACER...

| Quiero hacer... | Use... |
|---|---|
| Resolver con ayuda paso a paso | Ejecute solo `python scripts\solve_model.py problema.json` |
| Resolver por restricciones de forma reproducible | `--method epsilon` |
| Resolver por ponderaciones de forma reproducible | `--method weighted` |
| Hacer Z1 objetivo principal | `--primary 1` |
| Hacer Z2 objetivo principal | `--primary 2` |
| Hacer Z3 objetivo principal | `--primary 3` |
| Obtener 11 niveles E | `--r 10` |
| Usar cuatro intervalos solo para Z2 | `--r-objective 2=4` |
| Obtener 8 combinaciones de pesos | `--num-weights 8` |
| Resolver otro ejercicio | Cambie el JSON, no `solve_model.py` |
| Escribir 40 reglas iguales | Use una familia indexada 1D |
| Crear una regla por cada par trabajo-máquina | Use dos índices y dos conjuntos |
| Agregar una excepción a una familia | Añada una restricción explícita al mismo JSON |
| No generar gráfico | `--no-plot` |
| No generar Excel | `--no-excel` |
| No generar el script Gurobi | `--no-gurobi-script` |
| Ver todas las opciones | `--help` |

## 21. Glosario corto

- **Conjunto:** rango de enteros usado para expandir una familia.
- **Índice:** símbolo que toma valores de un conjunto, como `j` o `m`.
- **Parámetro:** dato fijo escalar o indexado.
- **Familia:** plantilla que genera variables, términos o restricciones.
- **Representación dispersa:** almacena solo coeficientes distintos de cero.
- **Ancla:** solución individual usada en la matriz de pagos.
- **Epsilon:** nivel impuesto al objetivo restringido.
- **r_k:** número de intervalos del objetivo restringido Zk; genera `r_k + 1`
  niveles.
- **Proyección:** gráfico de dos objetivos de un resultado evaluado en N
  dimensiones; no representa por sí solo toda la frontera.
- **Peso:** importancia relativa de un objetivo normalizado.
- **Dominancia:** comparación de soluciones respetando todos los sentidos.
- **Frontera de Pareto:** conjunto de soluciones no dominadas obtenidas.
