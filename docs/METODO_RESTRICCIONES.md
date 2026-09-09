# Método de las restricciones (ε-constraint)

**Estado:** implementación de backend validada para programación lineal
biobjetivo. No está integrada en Streamlit.

## 1. Definición

El método de las restricciones selecciona uno de los dos objetivos como función
objetivo principal y convierte el otro en una restricción paramétrica. Para
`Z1` principal y `Z2` restringido, cada corrida resuelve:

```text
Optimizar Z1(x)

sujeto a:
    Z2(x) >= E_2,t       si Z2 es MAX
    x pertenece a X
```

`X` contiene **todas** las restricciones del modelo original. Si el objetivo
restringido es de minimización, la restricción paramétrica cambia a:

```text
Z2(x) <= E_2,t
```

La implementación permite seleccionar `primary_objective=1` o
`primary_objective=2`. El objetivo restante pasa a ser el restringido.

## 2. Significado de k, t y r

- `k` identifica el objetivo convertido en restricción (`1` o `2`).
- `r` es el número entero de intervalos del rango y debe satisfacer `r >= 1`.
- `t` identifica el nivel de la corrida, con `t = 0, 1, ..., r`.

Por tanto, un barrido siempre envía `r + 1` problemas completos al solver.

## 3. Matriz de pagos y fórmula exacta de E

Antes del barrido se optimizan individualmente `Z1` y `Z2` sobre el modelo
original. Se reutiliza la selección secundaria vigente de las anclas: después
de obtener el óptimo individual, puede escogerse un representante eficiente de
la misma cara óptima manteniendo exactamente fijo el valor primario. Esta etapa
es únicamente preprocesamiento de la matriz de pagos.

Para el objetivo restringido `Zk`, sus dos valores en las filas de la matriz de
pagos determinan:

```text
Zk_min = menor valor numérico de Zk en las anclas
Zk_max = mayor valor numérico de Zk en las anclas
```

Los niveles se generan, sin redondeo interno, mediante:

```text
E_k,t = Zk_min + (t/r)(Zk_max - Zk_min),  t = 0, 1, ..., r
```

En particular, `E_k,0` conserva exactamente `Zk_min` y `E_k,r` conserva
exactamente `Zk_max`. La fórmula numérica no se invierte para objetivos MIN.
Solo cambia el operador de la restricción:

| Sentido de Zk | Restricción agregada |
|---|---|
| MAX | `Zk(x) >= E_k,t` |
| MIN | `Zk(x) <= E_k,t` |

Un rango nulo es válido: los `r + 1` niveles son iguales y las corridas se
conservan, aunque normalmente conduzcan a una única solución detectada como
repetida.

## 4. Diferencia frente al método de ponderaciones

El método ε-constraint no utiliza pesos, suma ponderada ni normalización. Cada
nivel agrega una restricción explícita al modelo y mantiene el sentido original
del objetivo principal. En cambio, el método de ponderaciones normalizadas
construye y maximiza una función escalar `W` a partir de ambos objetivos.

La matriz de pagos es preprocesamiento común, pero sus filas nunca sustituyen
las corridas ε. Incluso los niveles extremos se resuelven nuevamente mediante
`solve_lp`.

## 5. Procedimiento implementado

1. Validar el problema, `primary_objective`, `r` y la tolerancia.
2. Obtener los óptimos individuales y construir la matriz de pagos.
3. Calcular los extremos numéricos del objetivo restringido.
4. Generar exactamente `r + 1` niveles con la fórmula académica.
5. Para cada `t`, crear un `LPProblem` con todas las restricciones originales y
   una restricción ε adicional.
6. Resolver cada problema independientemente con Pyomo + HiGHS mediante
   `solve_lp`.
7. Reconstruir `Z1` y `Z2` desde el mismo vector completo `x` publicado.
8. Registrar corridas no óptimas o infactibles sin detener el resto del barrido.
9. Detectar soluciones repetidas dentro de `tol` sin eliminar las corridas.
10. Clasificar dominancia de Pareto respetando por separado los sentidos de
    `Z1` y `Z2`.

## 6. API y estructura del resultado

```python
from solver_optimizador import (
    generate_epsilon_levels,
    solve_biobjective_epsilon_constraint,
)

levels = generate_epsilon_levels(z_min=80.0, z_max=169.0, r=5)
solution = solve_biobjective_epsilon_constraint(
    problem,
    primary_objective=1,
    r=5,
    tol=1e-6,
)
```

`EpsilonConstraintSolution` contiene:

- `individual_optima` y `payoff_matrix`;
- `objective_ranges` con mínimos, máximos y amplitudes numéricas;
- `primary_objective`, `constrained_objective`, `r` y `epsilon_levels`;
- `runs`, sin eliminar ninguna corrida original;
- `unique_solutions`, `pareto_classification` y
  `nondominated_solutions`;
- tiempos de preprocesamiento, barrido y total;
- notas sobre fallos o corridas infactibles.

Cada elemento de `runs` registra:

```text
run_index, t, primary_objective, constrained_objective,
E, constraint_operator, status, status_message, raw_termination,
x, Z1, Z2, execution_time_sec
```

Para una corrida no óptima, `x`, `Z1` y `Z2` son `None`; el estado y la
terminación permanecen registrados.

## 7. Demostración reproducible: Benchmark A

Desde PowerShell en la raíz del repositorio:

```powershell
& ".\.venv\Scripts\python.exe" scripts\demo_metodo_restricciones.py
```

El script ejecuta ambos sentidos de selección del objetivo principal con
`r=5`. Para `Z1` principal restringe `Z2` en:

```text
80.0, 97.8, 115.6, 133.4, 151.2, 169.0
```

Para `Z2` principal restringe `Z1` en:

```text
390.0, 512.0, 634.0, 756.0, 878.0, 1000.0
```

En cada barrido muestra objetivos, sentidos, óptimos individuales, matriz de
pagos, extremos, fórmula, tabla de las 6 corridas, soluciones únicas y frontera
no dominada obtenida. Los decimales mostrados son formato de presentación; los
valores internos no se redondean.
