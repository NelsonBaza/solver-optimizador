# Método de ponderaciones normalizadas

**Estado:** especificación matemática normativa
**Vigencia:** Fase 2B — corrección de `AUD-HIGH-01`

Este documento define el método utilizado por `solver-optimizador` para generar
alternativas de un problema lineal biobjetivo. La optimización que genera cada
alternativa es exclusivamente la **suma ponderada normalizada**.

## 1. Problema biobjetivo

Sean dos objetivos lineales `Z1(x)` y `Z2(x)`, cada uno con sentido `MAX` o
`MIN`, sujetos a la misma región factible original `X`:

```text
x pertenece a X
```

La construcción de la matriz de pagos es un preprocesamiento. No constituye una
corrida del barrido y no sustituye la resolución de ningún peso.

## 2. Optimización individual y matriz de pagos

Cada objetivo se optimiza individualmente sobre `X`, respetando su sentido. La
fila asociada a `Zk` conserva exactamente su valor óptimo primario y registra los
valores de ambos objetivos en el representante elegido.

Si el solver devuelve un representante de una cara óptima que es desfavorable
para el otro objetivo, se permite una selección secundaria: se fija el óptimo
primario y se optimiza el objetivo restante según su sentido. Esta regla:

- se usa únicamente para construir una ancla eficiente y estable;
- queda registrada en metadatos de la ancla;
- no es el método que genera las alternativas ponderadas;
- no prueba unicidad ni caracteriza por sí sola toda la multiplicidad;
- debe preservar el valor óptimo del objetivo primario.

Para dos objetivos, la matriz de pagos tiene la forma:

| Ancla | Z1 | Z2 |
|---|---:|---:|
| óptimo individual de Z1 | `Z1(x¹)` | `Z2(x¹)` |
| óptimo individual de Z2 | `Z1(x²)` | `Z2(x²)` |

De estas anclas se obtienen, para cada objetivo `k`:

```text
Zk_min = min(Zk(x¹), Zk(x²))
Zk_max = max(Zk(x¹), Zk(x²))
Delta_Zk = Zk_max - Zk_min
```

La política vigente detiene el barrido cuando algún rango es nulo o menor que
el umbral ya existente. La política general de rango cero pertenece a
`AUD-MED-03` y no se redefine en esta fase.

## 3. Normalización orientada al beneficio

La normalización siempre se orienta para que un valor mayor represente mejor
desempeño.

Para un objetivo `MAX`:

```text
Nk(x) = (Zk(x) - Zk_min) / Delta_Zk
```

Para un objetivo `MIN`:

```text
Nk(x) = (Zk_max - Zk(x)) / Delta_Zk
```

En los límites de la escala, `Nk=0` representa el extremo menos favorable y
`Nk=1` el más favorable. No son valores normativos `Zk/Delta_Zk` ni
`-Zk/Delta_Zk`: aunque el desplazamiento constante puede conservar el `argmax`
en algunos casos, cambia el valor publicado de `Nk` y de `W`.

## 4. Pesos y función escalar

Los pesos deben cumplir:

```text
alpha1 >= 0
alpha2 >= 0
alpha1 + alpha2 = 1
```

Limitación vigente: la API histórica acepta una desviación de suma de hasta
`1e-3` y redondea pesos personalizados a seis decimales. Fase 2B garantiza que
los pesos almacenados son exactamente los que se usan para construir y
reconstruir `W`, pero no corrige esa política; permanece documentada como
`AUD-MED-04`.

La función ponderada es:

```text
W(x) = alpha1*N1(x) + alpha2*N2(x)
```

Cada corrida resuelve:

```text
MAX W(x)
sujeto a x perteneciente a X
```

Todos los pesos, incluidos `(1,0)` y `(0,1)`, pasan por esta optimización. Las
anclas de la matriz de pagos nunca se copian como sustituto de una corrida.

Si una función `W` tiene varios óptimos, puede aplicarse una regla secundaria
para elegir un representante, siempre que se fije y preserve `W*`. Esa regla se
registra en `selection_metadata`, no se presenta como otro método y no permite
afirmar unicidad.

## 5. Resultado canónico de una corrida

Cada corrida almacena como mínimo:

```text
run_index, alpha1, alpha2, x, Z1, Z2, N1, N2, W, status
```

Cuando existe una selección posterior entre óptimos de la misma `W`, también
incluye `selection_metadata`. `Z1`, `Z2`, `N1`, `N2` y `W` se reconstruyen desde
el mismo vector `x` publicado, sin redondeo destructivo:

```text
W = alpha1*N1 + alpha2*N2
```

El redondeo o la notación científica pertenecen únicamente a presentación.

## 6. Clasificación posterior

Después de resolver las ponderaciones se pueden agrupar alternativas repetidas
y clasificar dominancia dentro del conjunto discreto obtenido. Esta etapa no
modifica las corridas ni demuestra que se haya reconstruido toda la frontera de
Pareto. La política general de tolerancias de deduplicación y Pareto permanece
fuera del alcance de Fase 2B.

## 7. Benchmark A normativo

```text
MAX Z1 = 10*x1 + 3*x2
MAX Z2 = 0.8*x1 + 1.3*x2

x1 + x2 <= 130
2.5*x1 + x2 <= 250
x1,x2 >= 0
```

Matriz de pagos:

| Ancla | x | Z1 | Z2 |
|---|---:|---:|---:|
| óptimo Z1 | `(100,0)` | 1000 | 80 |
| óptimo Z2 | `(0,130)` | 390 | 169 |

Por tanto:

```text
N1 = (Z1 - 390) / 610
N2 = (Z2 - 80) / 89
W  = alpha1*N1 + alpha2*N2
```

| alpha1 | alpha2 | x | Z1 | Z2 |
|---:|---:|---:|---:|---:|
| 0.0 | 1.0 | `(0,130)` | 390 | 169 |
| 0.2 | 0.8 | `(0,130)` | 390 | 169 |
| 0.4 | 0.6 | `(80,50)` | 950 | 129 |
| 0.5 | 0.5 | `(80,50)` | 950 | 129 |
| 0.6 | 0.4 | `(80,50)` | 950 | 129 |
| 0.8 | 0.2 | `(80,50)` | 950 | 129 |
| 1.0 | 0.0 | `(100,0)` | 1000 | 80 |

El peso `(0.5,0.5)` no implica por sí mismo degeneración ni multiplicidad.

## 8. Caso hidroeléctrico MIN/MAX

Para las anclas eficientes actualmente documentadas:

```text
Z1 = MIN costo térmico
Z2 = MAX V4

mejor costo:   (Z1,Z2) = (6701.25,40)
mejor reserva: (Z1,Z2) = (21416.25,100)
```

La normalización es:

```text
N1 = (21416.25 - Z1) / 14715
N2 = (Z2 - 40) / 60
```

Sobre la frontera documentada `Z1 = 245.25*Z2 - 3108.75`:

```text
N1 = (100 - Z2) / 60
N2 = (Z2 - 40) / 60
```

Por ello, `(0.2,0.8)` y `(0.4,0.6)` favorecen la reserva máxima; `(0.6,0.4)` y
`(0.8,0.2)` favorecen el costo mínimo. Para `(0.5,0.5)`, cualquier resultado
aceptado debe ser factible, pertenecer a esa frontera y satisfacer `W=0.5`; no
se exige un vector de variables concreto.

## 9. Método declarado

**Método utilizado para generar alternativas: suma ponderada normalizada.**

La selección secundaria de anclas y la eventual selección de representante
entre óptimos de una misma `W` son reglas auxiliares documentadas, no métodos
multiobjetivo alternativos.
