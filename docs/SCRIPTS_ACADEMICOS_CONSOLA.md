# Scripts académicos portables de consola

## Qué se entrega

Cada método puede entregarse como un par de archivos independiente del
repositorio:

- restricciones: `metodo_restricciones.py` + `problema.json`;
- ponderaciones: `metodo_ponderaciones.py` + `problema.json`.

Los archivos de este repositorio se encuentran en `exports/`. No importan el
paquete `solver_optimizador`, no usan Streamlit y no contienen un problema
particular. Solo necesitan Python 3.10 o posterior, Pyomo y HiGHS.

Las versiones verificadas y declaradas en `pyproject.toml` se instalan con:

```console
python -m pip install pyomo==6.10.1 highspy==1.15.1
```

## Qué representa el JSON

El JSON usa exactamente el esquema 1.0 del proyecto. Declara el nombre del
modelo, variables, dos objetivos y restricciones lineales. Todas las variables
son continuas y no negativas. Los coeficientes se almacenan en forma dispersa:
una variable ausente en `coefficients` tiene coeficiente cero.

Ejemplo mínimo con dos variables:

```json
{
  "schema_version": "1.0",
  "metadata": {"name": "Ejemplo MAX MAX"},
  "problem": {
    "type": "Biobjetivo",
    "num_vars": 2,
    "variables": ["x", "y"],
    "bio_objectives": {
      "obj1": {
        "sense": "Maximizar",
        "coefficients": {"x": 1}
      },
      "obj2": {
        "sense": "Maximizar",
        "coefficients": {"y": 1}
      }
    },
    "constraints": [
      {
        "name": "capacidad",
        "coefficients": {"x": 1, "y": 1},
        "operator": "<=",
        "rhs": 10
      }
    ]
  }
}
```

Para crear otro modelo se cambian únicamente los datos del JSON. Los sentidos
admitidos son `Maximizar` y `Minimizar`; los operadores son `<=`, `>=` y `=`.
Cada coeficiente y lado derecho debe ser numérico y finito. Los nombres de
variables deben ser identificadores sin espacios y no pueden repetirse.

## Método de las restricciones

Ejecución desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe exports\metodo_restricciones.py models\hidroelectrica_biobjetivo.json --primary 1 --r 6
```

Ejecución después de copiar solo el script y el JSON a otra carpeta:

```console
python metodo_restricciones.py problema.json --primary 1 --r 6
```

El script obtiene los óptimos individuales, construye la matriz de pagos y
restringe el objetivo que no fue elegido como principal. Usa exactamente:

```text
E_k,t = Zk_min + (t/r)(Zk_max - Zk_min),  t = 0, ..., r
```

Por tanto resuelve `r + 1` LP completos. Para un objetivo restringido MAX
agrega `Zk(x) >= E_k,t`; para uno MIN agrega `Zk(x) <= E_k,t`. Las corridas no
se borran al resumir duplicados.

## Método de ponderaciones normalizadas

Ejecución desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe exports\metodo_ponderaciones.py models\hidroelectrica_biobjetivo.json --num-weights 6
```

Ejecución después de copiar solo el script y el JSON a otra carpeta:

```console
python metodo_ponderaciones.py problema.json --num-weights 6
```

Después de la matriz de pagos se calculan los rangos
`Delta Zk = Zk_max - Zk_min`. Cada objetivo queda orientado a maximización:

```text
MAX: Nk = (Zk - Zk_min) / Delta Zk
MIN: Nk = (Zk_max - Zk) / Delta Zk
W   = alpha1*N1 + alpha2*N2
```

Las combinaciones uniformes van de `(0, 1)` a `(1, 0)`. Cada combinación
resuelve realmente `max W`. En los pesos extremos, el script conserva `W*` y
selecciona un representante eficiente optimizando el objetivo cuyo peso es
cero, igual que el backend oficial.

## Ejemplo hidroeléctrico

`models/hidroelectrica_biobjetivo.json` contiene 24 variables y 28
restricciones en formato disperso. Para restricciones con `--primary 1 --r 6`
se obtienen niveles de almacenamiento final:

```text
E2 = [40, 50, 60, 70, 80, 90, 100]
```

La frontera reproducida es:

| V4 | Z1 |
|---:|---:|
| 40 | 6701.25 |
| 50 | 9153.75 |
| 60 | 11606.25 |
| 70 | 14058.75 |
| 80 | 16511.25 |
| 90 | 18963.75 |
| 100 | 21416.25 |

Estos puntos satisfacen `Z1 = 245.25*V4 - 3108.75`. Con seis ponderaciones,
el método normalizado reproduce los mismos resultados por corrida que el
backend; debido a que esta frontera es lineal, las combinaciones uniformes
seleccionan sus dos extremos eficientes, con distintos representantes de las
caras óptimas cuando existe degeneración en las variables.

## Diferencia entre los ejecutores

`scripts/solve_model.py` es la herramienta completa del proyecto. Reutiliza el
deserializador, builders, tipos y motores oficiales instalados desde `src/` y
permite elegir el método mediante `--method`.

`exports/metodo_restricciones.py` y `exports/metodo_ponderaciones.py` son
segundas implementaciones deliberadamente autocontenidas, visibles y portables para
una evaluación académica. Cada una incluye solo la lectura esencial del JSON,
la construcción Pyomo, el método correspondiente y su informe en consola.

Las pruebas automáticas comparan numéricamente ambas implementaciones con el
backend oficial sobre Benchmark A, el modelo hidroeléctrico y problemas
artificiales MAX/MAX y MAX/MIN. También copian únicamente un `.py` y el JSON a
un directorio temporal, verifican que `solver_optimizador` no sea importable y
ejecutan el método desde allí.
