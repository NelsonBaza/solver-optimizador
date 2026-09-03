# Modelado indexado y familias unidimensionales

**Vigencia:** Fase 3B
**Backend de resolución:** Pyomo + APPSI HiGHS

El modelado indexado permite escribir una regla una vez y expandirla sobre un
conjunto ordenado de enteros. La especificación y su compilador son
solver-agnostic: no crean objetos Pyomo ni llaman al solver.

```text
especificación indexada
  -> validación y parser lineal seguro
  -> variables y restricciones explícitas canónicas dispersas
  -> problem_builder existente
  -> Pyomo / APPSI HiGHS
```

## Conceptos

- **Conjunto:** rango entero inclusivo, por ejemplo `T = 1..24`.
- **Parámetro escalar:** dato único, por ejemplo `V0 = 80`.
- **Parámetro indexado:** exactamente un dato para cada índice, como
  `demanda[t]`. No se rellenan faltantes con cero.
- **Variable indexada:** una familia como `V[T]`, que genera `V_1` a `V_24`.
- **Familia de restricciones:** una expresión y un rango que se aplican a cada
  índice.
- **Expansión:** transformación determinista de familias a la representación
  explícita consumida por los builders actuales.

Por ejemplo, con `T=1..24`, la familia:

```text
Demanda[t]: GH[t] + GT[t] >= demanda[t]
```

equivale a generar 24 restricciones, `Demanda_1` a `Demanda_24`.

## Especificación soportada

En esta fase cada conjunto es unidimensional, entero, ordenado, inclusivo y no
vacío. Las variables generadas son continuas y no negativas, igual que en el
motor vigente. La convención de nombre explícito es `FAMILIA_INDICE`, por
ejemplo `GT_12`.

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

Los objetivos se definen mediante términos estructurados, no mediante
comprensiones Python. Cada término indica familia, conjunto, rango y un
coeficiente numérico o paramétrico:

```text
Z | Minimizar | GT | T | 1 | 24 | costo[t]
```

Un rango `4..4` permite modelar un objetivo terminal como `MAX V_4`. Uno o dos
objetivos se compilan respectivamente hacia los builders monoobjetivo o
biobjetivo. El algoritmo de ponderaciones no fue modificado.

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

El parser usa el árbol sintáctico únicamente para inspección estática. No
ejecuta el contenido introducido.

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

La especificación fuente usa su propio `indexed_schema_version = "1.0"` y se
puede descargar/cargar como JSON, separada del JSON explícito histórico. La
aplicación sólo reemplaza el estado después de validar y compilar por completo.
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

No se soportan todavía índices múltiples `(i,j)`, arcos, conjuntos arbitrarios,
dominios enteros/binarios, cotas personalizadas, expresiones no lineales ni un
lenguaje algebraico general. El backend sigue siendo Pyomo + HiGHS; no se
integró Gurobi. AUD-HIGH-06 permanece abierto hasta separar IDs internos de los
nombres visibles.
