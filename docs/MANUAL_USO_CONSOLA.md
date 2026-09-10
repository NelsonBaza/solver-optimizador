# Manual de uso del programa en consola

## 1. Qué hace el programa

El programa lee un problema de programación lineal biobjetivo desde un único
archivo JSON, lo valida, lo convierte a una forma explícita y dispersa, lo
resuelve con Pyomo + HiGHS y muestra los resultados en PowerShell. También
guarda un gráfico PNG de los puntos obtenidos en el espacio de objetivos.

```text
problema.json
    ↓ validación y expansión, si existen familias
scripts/solve_model.py
    ↓ Pyomo + HiGHS
tablas en consola + results/..._pareto.png
```

Los únicos métodos multiobjetivo disponibles son:

1. método de las restricciones o *epsilon-constraint*;
2. método de ponderaciones normalizadas.

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

## 3. Ejecuciones básicas

### Método de las restricciones

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6
```

### Ponderaciones normalizadas

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method weighted --num-weights 6
```

### Sin gráfico

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py problema.json --method epsilon --primary 1 --r 6 --no-plot
```

## 4. Significado de las opciones

- `model_file`: ruta de `problema.json`.
- `--method epsilon`: selecciona el método de las restricciones.
- `--method weighted`: selecciona ponderaciones normalizadas.
- `--primary 1`: usa Z1 como objetivo principal; Z2 se vuelve restricción.
- `--primary 2`: usa Z2 como objetivo principal; Z1 se vuelve restricción.
- `--r`: número de intervalos epsilon. Produce exactamente `r + 1` corridas.
- `--num-weights`: número de pares uniformes `(alpha1, alpha2)`. Debe ser al
  menos 2.
- `--no-plot`: resuelve y muestra tablas, pero no crea el PNG.

Las opciones `--primary` y `--r` corresponden a epsilon. La opción
`--num-weights` corresponde a ponderaciones.

## 5. Cómo entender los resultados

### Objetivos y matriz de pagos

- **Z1 y Z2:** las dos medidas que se quieren optimizar.
- **Sentido MIN/MAX:** indica si un valor menor o mayor es preferible.
- **Objetivo principal:** el que se optimiza directamente en epsilon.
- **Objetivo restringido:** el que se exige mediante un nivel E.
- **Matriz de pagos:** contiene el resultado de optimizar individualmente Z1 y
  Z2. Sus filas permiten calcular los extremos numéricos de cada objetivo.
- **Zk_min y Zk_max:** menor y mayor valor observado para el objetivo k en las
  anclas de la matriz de pagos.

### Método de las restricciones

Los niveles se calculan exactamente como:

```text
E_k,t = Zk_min + (t/r)(Zk_max - Zk_min),  t = 0, ..., r
```

Si el objetivo restringido es MAX, el modelo agrega `Zk(x) >= E_k,t`. Si es
MIN, agrega `Zk(x) <= E_k,t`. Cada nivel produce una resolución completa; no
se usan pesos ni normalización.

### Ponderaciones normalizadas

Una **ponderación** asigna importancia mediante `alpha1` y `alpha2`, con suma
igual a 1. Los objetivos se orientan a una escala común:

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
vector de variables y los mismos objetivos dentro de tolerancia. Las corridas
originales siguen en la tabla; solo se agrupan en el resumen.

Una **solución no dominada** no tiene otra solución obtenida que sea igual o
mejor en ambos objetivos y estrictamente mejor en al menos uno, respetando los
sentidos MIN/MAX. El conjunto de esas soluciones aproxima la **frontera de
Pareto** obtenida por el barrido.

## 6. Cómo leer el gráfico

El eje horizontal es Z1 y el vertical Z2. Los puntos rojos representan
soluciones no dominadas; los puntos dominados, si existen, se muestran con otra
marca. La línea conecta los puntos no dominados ordenados por Z1.

Las etiquetas epsilon muestran el identificador (`S1`, `S2`, etc.) y el nivel
E. Las etiquetas ponderadas muestran el identificador (`A`, `B`, etc.) y los
valores de `alpha1` que generaron esa solución. Los desplazamientos de etiquetas
son deterministas para evitar colocarlas todas sobre los puntos.

No debe interpretarse que “arriba y a la derecha” siempre es mejor: si un
objetivo es MIN, la dirección preferida para ese eje es hacia valores menores.
El título del gráfico recuerda los sentidos.

## 7. Un único formato JSON

El usuario trabaja siempre con un solo `problema.json`.

- El esquema 1.0 histórico describe variables, objetivos y restricciones
  explícitos. Continúa siendo compatible sin cambios.
- El esquema 1.1 recomendado permite usar solo elementos explícitos, solo
  familias indexadas o una mezcla de ambos.

El flujo interno del esquema 1.1 es:

```text
JSON 1.1
  → validar conjuntos, parámetros, referencias y linealidad
  → expandir familias 1D/2D
  → variables y restricciones canónicas dispersas
  → problem_builder
  → Pyomo + HiGHS
```

El solver recibe siempre la última forma y no sabe qué filas se escribieron a
mano.

## 8. Problema pequeño con dos variables

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

## 9. Cuándo usar restricciones explícitas

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

## 10. Conjuntos, parámetros y variables indexadas

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

## 11. Muchas restricciones repetitivas: ejemplo 1D

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

## 12. Regla sobre dos índices

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

## 13. Cómo mezclar explícito e indexado

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

## 14. Seguridad y linealidad

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

## 15. Ejemplo hidroeléctrico

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

## 16. Qué entregar en una evaluación

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

## 17. Errores frecuentes

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
- **Peso inválido:** `--num-weights` debe ser entero y al menos 2; los pares
  internos son no negativos y suman 1.
- **Rango de normalización nulo:** las dos anclas dan el mismo valor para algún
  objetivo; no se puede aplicar la normalización vigente.

## 18. QUIERO HACER...

| Quiero hacer... | Use... |
|---|---|
| Resolver por restricciones | `--method epsilon` |
| Resolver por ponderaciones | `--method weighted` |
| Hacer Z1 objetivo principal | `--primary 1` |
| Hacer Z2 objetivo principal | `--primary 2` |
| Obtener 11 niveles E | `--r 10` |
| Obtener 8 combinaciones de pesos | `--num-weights 8` |
| Resolver otro ejercicio | Cambie el JSON, no `solve_model.py` |
| Escribir 40 reglas iguales | Use una familia indexada 1D |
| Crear una regla por cada par trabajo-máquina | Use dos índices y dos conjuntos |
| Agregar una excepción a una familia | Añada una restricción explícita al mismo JSON |
| No generar gráfico | `--no-plot` |
| Ver todas las opciones | `--help` |

## 19. Glosario corto

- **Conjunto:** rango de enteros usado para expandir una familia.
- **Índice:** símbolo que toma valores de un conjunto, como `j` o `m`.
- **Parámetro:** dato fijo escalar o indexado.
- **Familia:** plantilla que genera variables, términos o restricciones.
- **Representación dispersa:** almacena solo coeficientes distintos de cero.
- **Ancla:** solución individual usada en la matriz de pagos.
- **Epsilon:** nivel impuesto al objetivo restringido.
- **Peso:** importancia relativa de un objetivo normalizado.
- **Dominancia:** comparación de soluciones respetando todos los sentidos.
- **Frontera de Pareto:** conjunto de soluciones no dominadas obtenidas.
