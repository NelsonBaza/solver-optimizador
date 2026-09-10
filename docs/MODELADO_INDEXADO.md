# Modelado indexado y JSON unificado

**Vigencia:** Fase 3B
**Backend de resolución:** Pyomo + APPSI HiGHS

El modelado indexado permite escribir una regla una vez y expandirla sobre uno
o dos conjuntos ordenados de enteros. La compilación es solver-agnostic: no
crea objetos Pyomo ni llama al solver.

```text
problema.json (esquema 1.1)
  -> validación y parser lineal seguro
  -> variables y restricciones explícitas canónicas dispersas
  -> problem_builder existente
  -> Pyomo / APPSI HiGHS
```

## Conceptos

- **Conjunto:** rango entero inclusivo, por ejemplo `T = 1..24`.
- **Parámetro escalar:** dato único, por ejemplo `V0 = 80`.
- **Parámetro indexado:** exactamente un dato para cada índice o par de índices,
  como `demanda[t]` o `costo[j,m]`. No se rellenan faltantes con cero.
- **Variable indexada:** una familia como `V[T]` o `X[J,M]`, que genera nombres
  canónicos como `V_24` o `X_3_2`.
- **Familia de restricciones:** una expresión y un rango que se aplican a cada
  índice.
- **Expansión:** transformación determinista de familias a la representación
  explícita consumida por los builders actuales.

Por ejemplo, con `T=1..24`, la familia:

```text
Demanda[t]: GH[t] + GT[t] >= demanda[t]
```

equivale a generar 24 restricciones, `Demanda_1` a `Demanda_24`.

## Dos rutas compatibles

La especificación indexada histórica de la interfaz continúa siendo 1D y usa
`indexed_schema_version = "1.0"`. No se modificó su significado ni su API.

La herramienta principal de consola acepta además `schema_version = "1.1"`.
Este es el formato recomendado para usuarios nuevos y combina en el mismo
objeto `problem`:

### Contrato del esquema 1.1

| Ruta | Obligatorio | Contenido |
|---|---|---|
| `schema_version` | Sí | Literal `"1.1"` |
| `metadata` | No | `name` y `description` |
| `problem.type` | Sí | `Monoobjetivo`, `Biobjetivo` o `Multiobjetivo` |
| `problem.variables` | No | Nombres de variables explícitas |
| `problem.sets` | No | Rangos enteros inclusivos `start..end` |
| `problem.parameters` | No | Valores escalares o tablas 1D/2D completas |
| `problem.variable_families` | No | Familias sobre uno o dos conjuntos |
| `problem.bio_objectives` | Para biobjetivo | `obj1` y `obj2`, cada uno con sentido, coeficientes explícitos y/o `indexed_terms` |
| `problem.objectives` | Para multiobjetivo | Lista ordenada de al menos tres objetivos; también admite exactamente dos en un `Biobjetivo` nuevo |
| `problem.constraints` | No | Restricciones explícitas dispersas |
| `problem.constraint_families` | No | Expresiones lineales sobre uno o dos índices |

Las listas explícitas y las familias son opcionales por separado, pero su
combinación debe producir al menos una variable y una restricción. Los campos
no presentes equivalen a colecciones vacías, no a un segundo tipo de archivo.

```json
{
  "sets": {"J": {"start": 1, "end": 3}, "M": {"start": 1, "end": 2}},
  "parameters": {
    "capacidad": {"value": 5},
    "costo": {
      "indices": ["j", "m"],
      "sets": ["J", "M"],
      "values": {"1,1": 1, "1,2": 1.2, "2,1": 1.4, "2,2": 1.6,
                 "3,1": 1.8, "3,2": 2}
    }
  },
  "variables": ["reserva"],
  "variable_families": [
    {"name": "X", "indices": ["j", "m"], "sets": ["J", "M"]}
  ],
  "constraints": [
    {"name": "Especial", "coefficients": {"X[1,1]": 1},
     "operator": ">=", "rhs": 1}
  ],
  "constraint_families": [
    {"name": "Cota", "indices": ["j", "m"], "sets": ["J", "M"],
     "expression": "X[j,m] <= capacidad"}
  ]
}
```

## Especificación y nombres expandidos

Cada conjunto es entero, ordenado, inclusivo y no vacío. Una familia admite una
o dos dimensiones y genera el producto cartesiano cuando declara dos. Las
variables son continuas y no negativas. Las convenciones canónicas son
`FAMILIA_INDICE` y `FAMILIA_INDICE1_INDICE2`.

Una familia declara nombre, conjunto, símbolo de índice, límites opcionales y
expresión. Una condición inicial se expresa acotando el rango:

```text
BalanceInicial | T | t | 1 | 1 | V[t] + Turb[t] = V0 + aporte[t]
Balance        | T | t | 2 | 24 | V[t] - V[t-1] + Turb[t] = aporte[t]
```

No hay una sintaxis especial `if`. Una referencia como `V[t-1]` debe existir;
si el rango comienza en `t=1`, la compilación falla indicando que `V[0]` está
fuera del conjunto. Los índices no se envuelven circularmente.

## Objetivos

Los objetivos pueden mezclar `coefficients` explícitos e `indexed_terms`. Cada
término indexado indica familia, símbolos, conjuntos, rango opcional y un
coeficiente numérico o paramétrico:

```text
Z | Minimizar | GT | T | 1 | 24 | costo[t]
```

Un rango `4..4` permite modelar un objetivo terminal como `MAX V_4`. Uno, dos
o más objetivos se normalizan internamente a una lista ordenada; los builders
monoobjetivo y biobjetivo existentes se conservan y el builder general recibe
la lista completa. `Multiobjetivo` exige al menos tres objetivos. No se permite
definir simultáneamente `bio_objectives` y `objectives`.

El método epsilon admite dos o más objetivos. El algoritmo de ponderaciones
permanece exclusivamente biobjetivo y no fue modificado.

## Sintaxis lineal permitida

Se admiten literales finitos, parámetros escalares e indexados, variables
indexadas, paréntesis, suma, resta, producto por un valor numérico, división por
una constante numérica y relaciones `<=`, `>=`, `=`. Ejemplos:

```text
2 * X[t] <= capacidad[t]
costo[t] * X[t] + eta * Y[t] >= demanda[t]
X[t] / 3600 = Y[t]
V[t] - V[t-1] + Turb[t] = aporte[t]
```

El parser usa el árbol sintáctico únicamente para inspección estática. No usa
`eval()` ni `exec()` y no ejecuta el contenido introducido.

## Sintaxis rechazada

Se rechazan productos o divisiones entre variables, potencias, llamadas,
atributos y cualquier intento de ejecutar código. Ejemplos inválidos:

```text
X[t] * Y[t]
X[t] ** 2
X[t] / Y[t]
sin(X[t])
open("archivo")
__import__("modulo")
```

## Parámetros y validación

Los datos deben ser finitos. Para un parámetro indexado se exige exactamente
un valor por elemento del conjunto: índices ausentes, sobrantes o duplicados
son errores. También se validan nombres, referencias, rangos, sentidos y
linealidad antes de producir salida.

La representación expandida es dispersa. Por ejemplo:

```python
{
    "name": "Balance_3",
    "coefficients": {"V_3": 1.0, "V_2": -1.0, "Turb_3": 1.0},
    "operator": "=",
    "rhs": 15.0,
}
```

No se guardan miles de coeficientes cero.

## Trazabilidad y aplicación atómica

La salida conserva metadatos `variable -> familia/índice` y
`restricción -> familia/índice/expresión fuente`, además de conteos y densidad.
La vista previa está limitada a 20 elementos pero la aplicación y el solver
reciben todo el modelo.

La especificación fuente histórica de la UI usa su propio
`indexed_schema_version = "1.0"`. Para consola, el esquema unificado 1.1 guarda
la fuente explícita e indexada en un solo archivo y compila todo antes de llamar
al builder.
Si luego se edita el modelo explícito por la ruta manual, CSV, XLSX o dispersa,
`indexed_source_status` cambia a `stale`; la interfaz no afirma que ambas fuentes
sigan sincronizadas.

### Sincronización de la vista previa

“Validar y compilar” crea una fotografía matemática de todos los campos visibles,
incluido el contenido efectivo de un CSV de parámetros si está cargado. La
aplicación guarda junto a esa fotografía una firma SHA-256 determinista de nombre,
descripción, conjuntos, parámetros, variables, objetivos y restricciones.

Antes de habilitar “Aplicar modelo indexado”, la interfaz reconstruye nuevamente
la especificación visible y compara su firma. Si cualquier dato cambió desde la
compilación —también un archivo CSV o JSON—, el botón queda bloqueado y se solicita
validar y compilar otra vez. Al pulsar aplicar se repite la comparación como última
barrera; un desacuerdo no modifica variables, restricciones, solución ni versión
del editor.

Esta vigencia de la *preview* no es lo mismo que el estado de la fuente aplicada:

- `indexed_compile_preview_signature` vincula la fotografía compilada con los
  campos indexados actuales;
- `indexed_source_status` indica si una especificación ya aplicada continúa
  sincronizada con el modelo explícito después de posibles ediciones manuales.

## Ejemplos y alcance

La interfaz incluye una planificación académica de producción de seis períodos.
También existe una especificación hidroeléctrica usada únicamente para probar
equivalencia algebraica con el fixture vigente (24 variables, 28 restricciones,
`Z*=6701.25`). Esa prueba no certifica fidelidad física al enunciado fuente.

El esquema 1.1 de consola soporta uno y dos índices, incluidos desplazamientos
como `j-1` cuando la referencia permanece dentro del conjunto. No soporta aún
dimensión arbitraria, conjuntos no enteros, dominios binarios/enteros,
expresiones no lineales ni un lenguaje algebraico general. El backend continúa
siendo Pyomo + HiGHS.
