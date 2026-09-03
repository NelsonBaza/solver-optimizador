# Auditoría técnica y matemática integral — Fase 1

**Repositorio:** `solver-optimizador`
**Fecha de ejecución:** 2026-09-02
**Alcance:** diagnóstico reproducible; no se modificó código de producción ni se cambió el backend.

### Historial de corrección — Fase 1B

La primera redacción local, todavía no versionada, contenía una inconsistencia grave en Benchmark A: en la sección 8.2 y en el snippet del apéndice escribía `x1 + 2x2 <= 180`, aunque el modelo real del repositorio es `2.5x1 + x2 <= 250`. Los vértices y objetivos publicados correspondían al modelo real, no a la ecuación escrita. Esta versión corrige ambas apariciones, añade el peso `(0.5,0.5)` y reemplaza el snippet informal por el oráculo exacto versionado `tools/audit/verify_benchmark_a_exact.py`.

El script temporal usado durante la primera auditoría y su salida cruda no se conservaron. Por ello no es posible certificar retrospectivamente si aquella ejecución usó la restricción correcta: los puntos reportados son incompatibles con la ecuación errónea, pero por sí solos no prueban cómo fueron calculados. La ejecución original se clasifica como **no auditable**, no como evidencia independiente confirmada. La evidencia válida a partir de Fase 1B es el script versionado y su salida preservada en `docs/audit_evidence/fase1b_validation.txt`.

## 1. Resumen ejecutivo

La aplicación resuelve correctamente los tres casos numéricos contrastados —el ejemplo monoobjetivo, Benchmark A y el modelo hidroeléctrico de 24 variables— cuando se interpreta exactamente el modelo que hoy construye el código: programación lineal continua, con todas las variables no negativas y sin cotas o dominios configurables. Eso no demuestra, por sí solo, que la aplicación represente siempre el problema que el usuario cree haber introducido.

El flujo básico UI → normalización → builder → Pyomo/HiGHS funciona para los ejemplos cubiertos. La suite completa pasó: 69 de 69 pruebas. Sin embargo, la auditoría encontró un defecto **CRÍTICO** de trazabilidad numérica y varios hallazgos **ALTOS**:

1. El solver redondea cada variable a seis decimales antes de publicarla. El objetivo y los LHS se calculan con valores internos no redondeados, por lo que un mismo resultado puede contradecirse a sí mismo y parecer infactible al reconstruirlo.
2. La versión auditada del módulo denominado “método de ponderaciones” era un procedimiento híbrido: usaba selección lexicográfica para construir anclas y sustituir pesos extremos, y una suma por rangos sin desplazamiento en los pesos interiores. `AUD-HIGH-01` fue corregido en Fase 2B.
3. La interpretación declara “degeneración” para cualquier ejecución única con pesos `(0.5, 0.5)`, aunque el óptimo sea único.
4. La UI puede perder silenciosamente ediciones de restricciones al cambiar la estructura de variables, porque la tabla editada no se sincroniza con `session_state.constraints_data`.
5. La gráfica 2D puede sombrear un triángulo como región factible aunque el politopo sea no acotado.
6. La validación JSON acepta `Infinity` y la validación de nombres no impide colisiones con componentes reservados de Pyomo.
7. `<` y `>` no son capacidades reales: una ruta los rechaza y otra los transforma silenciosamente en `<=` y `>=`.
8. El fixture hidroeléctrico es algebraicamente consistente, pero el repositorio no contiene una especificación física externa con unidades que permita certificar que `PH_t = 2.4525 T_t` y `GH_t = PH_t` sean las conversiones pretendidas. Tampoco modela explícitamente duración de periodo, capacidad térmica, rampas, costo/penalización de vertimiento ni una meta terminal distinta de `V_4 >= 40`.

La primera corrección estableció el contrato numérico de resultados en Fase 2A. Fase 2B alinea la implementación y la documentación con la suma ponderada normalizada. Los demás hallazgos permanecen abiertos.

## 2. Método y límites de la auditoría

Se revisaron:

- `README.md`, `pyproject.toml`, `.gitignore`, `streamlit_app.py`;
- todos los módulos de `src/solver_optimizador/`;
- todos los archivos de `tests/` y `tests/fixtures/`;
- la documentación y los registros históricos de `docs/`;
- los scripts de benchmark y verificación de la raíz;
- el estado de Git y los patrones de archivos sensibles versionados.

Se realizaron cuatro tipos de comprobación:

1. Ejecución de la suite existente.
2. Reconstrucción algebraica independiente y enumeración exacta de vértices para los modelos pequeños.
3. Segunda formulación indexada del modelo hidroeléctrico en AMPL, resuelta con HiGHS, sin reutilizar el builder de la aplicación.
4. Casos adversariales pequeños para precisión, pesos, infinitos, nombres reservados y regiones no acotadas.

Gurobi no está disponible en el `.venv` actual y no se detectó una instalación de sistema con las comprobaciones detalladas en 3.2. Al no encontrarse una instalación, no fue posible evaluar una licencia. Por tanto no se usó como oráculo independiente. Tampoco están disponibles mediante Pyomo GLPK, CBC, SCIP, IPOPT, CPLEX o Xpress. La segunda comprobación hidroeléctrica de Fase 1 utilizó una formulación AMPL separada con el motor HiGHS; esto aporta independencia del builder y adaptador Pyomo, pero no independencia del algoritmo de optimización. Su script temporal no fue preservado, por lo que esa corrida se considera evidencia histórica no reproducible. La derivación algebraica versionada cubre los valores principales, pero una futura ejecución cruzada deberá quedar automatizada y versionada.

No existe en el repositorio un enunciado fuente completo del ejercicio hidroeléctrico, con unidades y convenciones físicas. Por ello se puede certificar la coherencia algebraica del fixture y describir sus supuestos, pero no certificar que sea fiel a un enunciado externo ausente.

## 3. Reproducibilidad del entorno y las pruebas

### 3.1 Entorno observado

| Componente | Versión / disponibilidad |
|---|---:|
| Python | 3.13.1 |
| Pyomo | 6.10.1 |
| highspy / HiGHS embebido | 1.15.1 |
| Streamlit | 1.62.0 |
| pytest | 9.1.1 |
| amplpy | 0.18.0 |
| ampltools | 0.7.5 |
| `appsi_highs` | disponible |
| `highs` mediante Pyomo | disponible |
| Ejecutable `highs` en PATH | no disponible |
| Gurobi en `.venv` | `gurobipy` no importable |
| Gurobi de sistema | no detectado por las comprobaciones de Fase 1B |
| GLPK, CBC, SCIP, IPOPT, CPLEX, Xpress | no disponibles |

Comandos de identificación:

```powershell
Get-Command python
python --version
python -c "import pyomo, highspy, streamlit, pytest; print(pyomo.__version__, highspy.Highs().version(), streamlit.__version__, pytest.__version__)"
```

El intérprete activo fue `.venv\Scripts\python.exe`; no se instaló ni actualizó ninguna dependencia.

### 3.2 Diagnóstico explícito de Gurobi en Windows

Comandos ejecutados:

```powershell
where.exe gurobi_cl
where.exe python
where.exe py
py -0p
python -c "import gurobipy; print(gurobipy.gurobi.version())"
```

También se inspeccionaron las ubicaciones convencionales de Python y Gurobi, las claves de desinstalación de Windows y los nombres de variables de entorno relacionados, sin imprimir posibles valores sensibles. Se encontró además el intérprete base `Python313`, que se probó directamente.

| Caso | Diagnóstico |
|---|---|
| A. Gurobi no disponible en `.venv` | **Confirmado:** `ModuleNotFoundError: No module named 'gurobipy'`. |
| B. Gurobi no instalado en el sistema | **No se detectó instalación:** `gurobi_cl` no está en PATH; no existe `py`; no hubo entrada de desinstalación, directorio convencional ni variable de entorno detectada. Esta conclusión está limitada a esas comprobaciones, no a un escaneo exhaustivo de todos los discos. |
| C. Instalado en otro intérprete | **No detectado:** el único intérprete adicional hallado, Python 3.13.1 base, tampoco puede importar `gurobipy`. |
| D. Instalado pero sin licencia utilizable | **No evaluable:** no se encontró instalación desde la cual ejecutar una prueba de licencia. |

### 3.3 Suite completa

Comando:

```powershell
python -m pytest -ra -W default
```

Resultado:

| Métrica | Resultado |
|---|---:|
| Tests recolectados | 69 |
| PASS | 69 |
| FAIL | 0 |
| SKIP | 0 |
| Warnings | 1 |
| Tiempo informado por pytest (Fase 1B) | 7.65 s |
| Tiempo de pared observado por el ejecutor | 8.7 s |

Warning observado:

```text
PytestCacheWarning: could not create cache path .pytest_cache\v\cache\nodeids: [WinError 5] Acceso denegado
```

No afecta los asserts, pero impide que pytest actualice su caché en esta ejecución. La corrida inicial de Fase 1 había informado 10.03 s; Fase 1B repitió la suite y preservó la salida nueva completa en `docs/audit_evidence/fase1b_validation.txt`.

### 3.4 Comprobaciones adicionales

```powershell
python -m compileall -q src streamlit_app.py
python -m streamlit run streamlit_app.py --server.headless true --server.port 8517 --browser.gatherUsageStats false
```

- Compilación: correcta.
- Arranque: correcto; el servidor quedó escuchando en el puerto 8517 y se detuvo después de verificarlo.
- El barrido de nombres versionados no encontró `.env`, llaves, licencias o archivos de credenciales según los patrones auditados.
- `.gitignore` excluye `.venv`, cachés, `.env`, variantes `.env.*`, licencias y logs de solvers. Como efecto lateral, el patrón `.env.*` también impediría versionar normalmente un `.env.example`.
- No hay formateador, linter ni comprobador de tipos configurados en `pyproject.toml`; por tanto no se puede reportar su ejecución.

### 3.5 Validación POST-FIX de Fase 2A

La corrección de `AUD-CRIT-01` añadió siete casos, elevando la suite a **76 PASS, 0 FAIL, 0 SKIP**, con el mismo warning de caché. El verificador canónico y el oráculo exacto de Benchmark A terminaron en PASS. La salida completa está en `docs/audit_evidence/aud_crit_01_fix_validation.txt`.

### 3.6 Validación POST-FIX de Fase 2B

La corrección de `AUD-HIGH-01` añadió 20 casos recolectados y elevó la suite a
**96 PASS, 0 FAIL, 0 SKIP**, con el mismo warning de caché. El oráculo exacto de
la suma ponderada normalizada, el verificador contra producción, el oráculo de
Benchmark A y el contrato de integridad numérica terminaron en PASS. La salida
reproducible está en
`docs/audit_evidence/aud_high_01_weighted_method_validation.txt`.

## 4. Separación entre validación de software y validación matemática

### A. Validación de software

El recorrido observado es:

```text
widgets Streamlit
  → valores locales y session_state
  → normalize_constraints / model_io
  → build_single_objective_problem o build_biobjective_problem
  → dataclasses de lp_models
  → construcción Pyomo
  → APPSI Highs
  → dataclasses/diccionarios de resultado
  → interpretación y gráficas
```

La suite demuestra, dentro de sus ejemplos, que:

- el JSON se carga y llega al builder;
- los ejemplos incluidos producen resultados esperados;
- el adaptador puede distinguir estados básicos;
- Streamlit puede arrancar y cargar los modelos probados;
- las funciones de gráficas retornan objetos `Figure`.

La suite no demuestra que:

- una tabla interactiva preserve todas las ediciones ante cambios estructurales;
- la región sombreada sea geométricamente correcta;
- los números esperados de fixtures sean un oráculo independiente;
- “degeneración” o “óptimo único” hayan sido demostrados;
- el resultado redondeado siga siendo factible;
- el modelo hidroeléctrico coincida con un enunciado físico externo;
- existan dominios enteros/binarios/libres o cotas configurables;
- `<` y `>` se manejen matemáticamente como desigualdades estrictas.

### B. Validación matemática

Para cada caso se reconstruyó el modelo sin usar como única verdad los asserts ni los números de fixtures. Los modelos pequeños se resolvieron enumerando exactamente sus vértices candidatos. El modelo hidroeléctrico se redujo algebraicamente. En Fase 1 también se volvió a formular con conjuntos/parámetros en AMPL, pero al no preservarse el script ni el stdout esa corrida se conserva solo como observación histórica, no como evidencia reproducible.

Conclusión: los valores de referencia de los tres casos son correctos para las ecuaciones efectivas actuales. A la vez, varias afirmaciones de interpretación, precisión y alcance son incorrectas o no están demostradas.

## 5. Auditoría del flujo completo

### 5.1 UI y `session_state`

- Los widgets principales usan claves versionadas, mecanismo que permite recargar modelos sin que claves anteriores reinyecten valores obsoletos.
- `_clear_widget_keys()` (`streamlit_app.py:118-125`) no limpia nada: su cuerpo es `pass`. El flujo funciona hoy por incremento de `editor_version`, pero la función y la documentación inducen a creer que existe una limpieza explícita.
- La tabla de restricciones produce `edited_df` y una representación canónica local, pero no asigna el resultado a `st.session_state.constraints_data` (`streamlit_app.py:586-617`). Resolver y descargar usan la variable local del rerun actual; al renombrar o cambiar el número de variables, el código reconstruye restricciones desde el estado antiguo (`streamlit_app.py:377-403`). Una edición aún no sincronizada puede perderse.
- La entrada masiva no existe. La tabla dinámica es funcional para pocos renglones, pero no es una arquitectura viable para 20–100+ restricciones y 100 columnas de coeficientes.
- La vista previa limita deliberadamente a 15 restricciones. Esto es una decisión de presentación, no pérdida del modelo, siempre que se etiquete inequívocamente como vista parcial.
- Los nombres se validan como no vacíos y únicos, pero no se transforman a identificadores internos seguros. Nombres como `name` o `component_map` chocan con atributos reservados de Pyomo; `obj` puede provocar reemplazo de componente.

### 5.2 Normalización, persistencia y builder

- Las filas UI planas y las restricciones canónicas anidadas convergen en `normalize_constraints()`.
- Un coeficiente ausente para una variable declarada se convierte en cero. Es conveniente para matrices dispersas, pero debe quedar registrado como normalización, no como corrección silenciosa de un error de importación.
- Coeficientes de variables no declaradas se descartan en la normalización, sin advertencia. Esto puede transformar el modelo.
- `num_vars` importado no se contrasta con `len(var_names)`; al deserializar se recalcula. Un archivo inconsistente se acepta y su metadato se cambia silenciosamente.
- `validate_model_dict()` comprueba convertibilidad numérica, pero no finitud en todos los coeficientes. Un objetivo con `Infinity` fue aceptado por la validación y conservado al deserializar; el fallo se posterga a otra capa.
- El esquema no representa dominio, cota inferior/superior, objetivo con constante, unidades, conjuntos, parámetros, familias, procedencia ni opciones del solver.
- `problem_builder.py` vuelve a normalizar y crea los objetos de dominio. No añade variables ni restricciones matemáticas, pero hereda los defaults silenciosos anteriores.
- `signature.py` convierte algunos valores inválidos a cero y redondea `custom_a1` a cuatro decimales. En la UI actual el slider reduce el riesgo, pero una futura entrada de mayor precisión podría no invalidar resultados obsoletos.

### 5.3 Modelo, solver y resultados

- Todas las variables se crean como `pyo.NonNegativeReals`.
- Solo existen variables continuas no negativas, sin cotas configurables. No existen variables libres, enteras o binarias como capacidad del modelo.
- `<=`, `>=` y `=` se traducen correctamente cuando llegan como miembros de `Operator`.
- `<` y `>` se convierten silenciosamente a `<=` y `>=` en `Operator.from_str()`, mientras `model_io` los rechaza. El comportamiento depende de la puerta de entrada.
- No se configura tolerancia de factibilidad u optimalidad de HiGHS. El parámetro `tol` del adaptador se usa solo para etiquetar restricciones activas.
- Se devuelve solución solo cuando la terminación contiene `optimal`; otros estados no conservan posibles incumbentes.
- El mapeo de estado se basa en texto y no expone un contrato completo de estados, primal/dual status, gap, condición de carga o rayos de no acotación.
- La holgura está bien definida para desigualdades. Para igualdad se devuelve el valor absoluto del residuo, magnitud útil pero no una holgura algebraica con signo.
- Todas las igualdades se marcan activas por construcción si satisfacen tolerancia. Llamarlas automáticamente “cuellos de botella” es una interpretación excesiva.
- Las cotas implícitas `x >= 0` no aparecen en los resultados de restricciones ni en la lista de activas.
- El redondeo destructivo observado en Fase 1 fue eliminado en Fase 2A; los datos canónicos conservan precisión de punto flotante y la vista formatea copias.

### 5.4 Interpretación y gráficas

- Fase 2B retiró la inferencia automática de degeneración basada únicamente en el peso 0.5 y la etiqueta de óptimo único basada en ausencia de cambio secundario.
- El resultado registra selección secundaria y preservación del objetivo primario, pero no intenta certificar unicidad o multiplicidad; esa capacidad sigue pendiente en `AUD-HIGH-02`.
- La gráfica factible 2D construye el casco de intersecciones factibles finitas. No comprueba rayos de recesión; un conjunto no acotado con varios vértices se sombrea como un polígono cerrado.
- La gráfica objetivo une puntos no dominados muestreados. Es una aproximación del barrido, no una prueba de la frontera continua; una línea puede sugerir cobertura donde no se resolvieron puntos intermedios.

## 6. Capacidades reales de `lp_models.py` y `lp_solver.py`

| Capacidad | Estado real | Observación |
|---|---|---|
| Variables continuas | Sí | Único tipo implementado. |
| No negatividad | Sí, obligatoria | Añadida implícitamente a toda variable. |
| Límite inferior personalizado | No | Solo cero implícito. |
| Límite superior personalizado | No | Puede emularse con una restricción, no como atributo. |
| Variable libre | No | Requeriría transformación manual no documentada. |
| Variable entera | No | No existe en el esquema ni builder. |
| Variable binaria | No | No existe en el esquema ni builder. |
| `<=` | Sí | Traducción correcta. |
| `>=` | Sí | Traducción correcta. |
| `=` | Sí | Traducción correcta. |
| `<`, `>` | No | Rechazo en JSON/UI o relajación silenciosa en API. |
| Tolerancias del solver | No configurables | `tol` solo clasifica activas. |
| Infactible | Parcial | Estado textual, sin certificado ni IIS. |
| No acotado | Parcial | Estado textual, sin rayo; tests aceptan estado ambiguo. |
| Holguras | Sí, explícitas | No incluye cotas de variables; igualdad usa residuo absoluto. |
| Restricciones activas | Parcial | Tolerancia posprocesada y solo restricciones explícitas. |
| Precisión íntegra | Sí desde Fase 2A | Datos canónicos sin redondeo destructivo. |
| Incumbente no óptimo | No | Se descarta. |
| Duales / costos reducidos | No expuestos | El adaptador APPSI tiene APIs que el proyecto no usa. |

## 7. Auditoría matemática de `multiobjective.py`

### 7.1 Modelo genérico efectivo

Para variables `x >= 0` y región factible `X`, los dos objetivos son:

```text
Z1(x) = c1ᵀx
Z2(x) = c2ᵀx
```

Cada objetivo conserva su sentido declarado `MAX` o `MIN` en las optimizaciones individuales.

### 7.2 Anclas de la matriz de pagos

Para el ancla de `Z1`, el código ejecuta como preprocesamiento:

```text
1. optimizar Z1(x) sobre X;
2. fijar c1ᵀx = Z1*;
3. optimizar Z2(x) con su propio sentido sobre esa cara óptima;
4. verificar que el valor primario se preservó dentro de la tolerancia numérica.
```

Para el ancla de `Z2` intercambia los papeles. La selección secundaria queda registrada en metadatos, no se usa para afirmar unicidad o multiplicidad y no reemplaza ninguna corrida ponderada.

La matriz de pagos efectiva es:

```text
                 Z1                 Z2
ancla Z1         Z1(x¹)             Z2(x¹)
ancla Z2         Z1(x²)             Z2(x²)
```

Los rangos se calculan como el máximo menos el mínimo numérico de esas dos filas:

```text
R1 = max(Z1a, Z1b) - min(Z1a, Z1b)
R2 = max(Z2a, Z2b) - min(Z2a, Z2b)
```

### 7.3 Función ponderada: PRE-FIX y Fase 2B

Antes de Fase 2B, para pesos interiores el código maximizaba:

```text
W_pre(x; α1, α2) = α1 · s1 · Z1(x)/R1 + α2 · s2 · Z2(x)/R2
```

Esa fórmula omitía el origen de la escala. Desde Fase 2B se define:

```text
MAX: N_k(x) = (Z_k(x) - Zk_min) / (Zk_max - Zk_min)
MIN: N_k(x) = (Zk_max - Z_k(x)) / (Zk_max - Zk_min)
W(x) = α1 N1(x) + α2 N2(x)
resolver MAX W(x), sujeto a x ∈ X
```

Para un par de pesos fijo y rangos no nulos, el desplazamiento no cambia el `argmax`, pero sí cambia el valor y la interpretación de `N_k` y `W`. La implementación Fase 2B calcula y publica `Z1`, `Z2`, `N1`, `N2` y `W` desde el mismo vector canónico.

### 7.4 Pesos y casos borde

- Los pesos generados automáticamente suman uno salvo el redondeo decimal esperado.
- Los pesos personalizados se aceptan si su suma está a menos de `1e-3` de uno. `(0.5004, 0.5004)` fue aceptado y almacenado con suma `1.0008`; no se renormaliza.
- Desde Fase 2B, `(1,0)` y `(0,1)` también ejecutan el problema `MAX W`. Si se selecciona un representante eficiente dentro de la misma cara `W*`, se fija y verifica `W*` y se registra la regla en metadatos.
- Si un rango es menor que `1e-7`, se cancela todo el barrido. Esto evita división por cero, pero también rechaza casos válidos donde un objetivo es constante/redundante y el otro aún puede optimizarse.
- Las soluciones se deduplican con tolerancia fija `1e-4`, no con el `tol` recibido.
- La dominancia se evalúa correctamente respecto de los sentidos, pero solo entre los puntos muestreados y deduplicados.
- La suma ponderada en un problema convexo lineal encuentra puntos soportados. Un muestreo finito no enumera automáticamente toda la frontera ni toda la multiplicidad de óptimos.

### 7.5 Dictamen sobre el nombre del método

Desde Fase 2B, el método utilizado para generar alternativas es estrictamente la **suma ponderada normalizada**. La optimización individual y la selección secundaria de representantes son preprocesamiento de la matriz de pagos. Ninguna ancla sustituye una corrida y esos metadatos no se usan para afirmar unicidad.

La API multiobjetivo nativa de Gurobi también distingue objetivos combinados por pesos y prioridades jerárquicas; no son el mismo método. La documentación oficial describe ambos modos por separado: [Gurobi — Multiple Objectives](https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html).

## 8. Reproducción independiente de resultados

### 8.1 Ejemplo monoobjetivo

Modelo reconstruido:

```text
max Z = 3x1 + 2x2
s.a. x1 + x2 <= 4
     x1 <= 2
     x2 <= 3
     x1, x2 >= 0
```

Enumeración exacta de vértices:

```text
(0,0), (0,3), (1,3), (2,0), (2,2)
```

| Magnitud | Aplicación | Cálculo independiente | Comparación |
|---|---:|---:|---|
| `x1` | 2 | 2 | coincide |
| `x2` | 2 | 2 | coincide |
| `Z` | 10 | 10 | coincide |
| Activas explícitas | `x1+x2<=4`, `x1<=2` | mismas | coincide |
| Factible | sí | sí | coincide |

### 8.2 Benchmark A biobjetivo

Modelo:

```text
max Z1 = 10x1 + 3x2
max Z2 = 0.8x1 + 1.3x2
s.a. x1 + x2 <= 130
     2.5x1 + x2 <= 250
     x1, x2 >= 0
```

Vértices exactos: `(0,0)`, `(0,130)`, `(80,50)`, `(100,0)`.

Extremos:

| Extremo | `(x1,x2)` | `Z1` | `Z2` | Activas |
|---|---:|---:|---:|---|
| `Z1` | `(100,0)` | 1000 | 80 | segunda restricción y `x2=0` |
| `Z2` | `(0,130)` | 390 | 169 | primera restricción y `x1=0` |

Rangos: `R1=610`, `R2=89`.

| `(α1,α2)` | Punto independiente | `Z1` | `Z2` | `W` normalizado | Factible |
|---|---:|---:|---:|---:|---|
| `(0,1)` | `(0,130)` | 390 | 169 | 1 | sí |
| `(0.2,0.8)` | `(0,130)` | 390 | 169 | 0.8 | sí |
| `(0.4,0.6)` | `(80,50)` | 950 | 129 | 0.697550 | sí |
| `(0.5,0.5)` | `(80,50)` | 950 | 129 | 0.734297 | sí |
| `(0.6,0.4)` | `(80,50)` | 950 | 129 | 0.771044 | sí |
| `(0.8,0.2)` | `(80,50)` | 950 | 129 | 0.844539 | sí |
| `(1,0)` | `(100,0)` | 1000 | 80 | 1 | sí |

La aplicación Fase 2B coincide con esos puntos y valores. Antes de la corrección los `W` publicados eran respectivamente `1.898876`, `1.646970`, `1.492614`, `1.503408`, `1.514202`, `1.535789`, `1.639344`: las decisiones coincidían en este benchmark, pero la escala contradecía la normalización declarada.

Para `(0.5,0.5)`, los valores escalares en los vértices muestran que `(80,50)` es el único óptimo entre ellos y, por linealidad, no existe una arista óptima paralela. La afirmación automática de degeneración por observar `α1=0.5` fue retirada en Fase 2B; la capacidad general de probar unicidad o multiplicidad sigue pendiente en `AUD-HIGH-02`.

### 8.3 Modelo hidroeléctrico

La formulación indexada temporal de Fase 1, separada del builder pero cuyo script no se preservó, reportó:

```text
T = [24.4648318043, 31.9928644241, 28.5423037717, 10]
V = [65.5351681957, 53.5423037717, 40, 40]
S = [0, 0, 0, 0]
PH = GH = [60, 78.4625, 70, 24.525]
GT = [0, 1.5375, 0, 65.475]
sum(T) = 95
sum(GT) = 67.0125
Z = 100·sum(GT) = 6701.25
```

Máximo residuo de igualdad observado en aquella corrida: `1.42e-14`. La aplicación coincide a seis decimales. Están activas las 16 igualdades, `V_Min_3`, `V_Min_4` y, como cotas implícitas no reportadas, `S1..S4=0`, `GT1=0`, `GT3=0`. Estos valores numéricos históricos son compatibles con la siguiente demostración algebraica versionada, que es la evidencia actualmente reproducible.

Demostración algebraica independiente:

```text
sum(I_t) = 135
V4 = 135 - sum(T_t) - sum(S_t)
V4 >= 40, S_t >= 0  ⇒  sum(T_t) <= 95
GT_t = D_t - 2.4525 T_t
Z = 100·sum(GT_t) = 30000 - 245.25·sum(T_t)
```

Minimizar `Z` equivale a maximizar `sum(T_t)`. El máximo es 95 con `sum(S)=0` y `V4=40`, luego:

```text
Z* = 30000 - 245.25·95 = 6701.25
```

El vector presentado es **un** óptimo, no se ha demostrado que sea el único. La función objetivo depende del turbinamiento total, por lo que pueden existir distribuciones temporales alternativas con el mismo costo.

## 9. Auditoría específica del fixture hidroeléctrico

La intención se reconstruyó de `tests/fixtures/hydroelectric_full_24_vars.json`, `tests/test_hydroelectric_e2e.py`, los tests previos reducidos y la documentación. No se encontró un enunciado físico externo.

| Elemento | Formulación del fixture | Formulación efectiva del solver | Observación | Posible error |
|---|---|---|---|---|
| Variables | 24: `T,V,S,PH,GH,GT` para `t=1..4` | Las mismas 24, continuas y no negativas | El esquema no guarda tipo, unidades ni cotas por variable | El usuario no puede declarar libres/enteras/binarias; las unidades no son auditables |
| `T_t` | Agua turbinada; aparece en balance y `PH_t=2.4525T_t`; `T_t<=70` | Igual, más `T_t>=0` implícito | `T_t<=70` es redundante aquí porque demanda y `GT>=0` imponen una cota menor | Puede ocultar que la capacidad efectiva proviene de otra ecuación |
| `V_t` | Volumen final de periodo; `40<=V_t<=100` | Igual, además dominio no negativo redundante | `V0=0` está embebido en la primera igualdad, no como parámetro | Si el volumen inicial pretendido no era cero, cambia todo el problema |
| `S_t` | Vertimiento en balance | Continua, no negativa, sin cota ni penalización | El óptimo observado usa cero | Si el vertimiento tiene capacidad/costo, falta modelarlo |
| `PH_t` | `PH_t - 2.4525T_t = 0` | Igual | Conversión agua→potencia | Coeficiente y unidades no pueden validarse sin enunciado |
| `GH_t` | `GH_t - PH_t = 0` | Igual | Potencia hidroeléctrica copiada a generación/energía | Equivale a factor de duración/conversión 1; puede confundir MW con MWh |
| `GT_t` | Generación térmica residual | Continua no negativa, sin máximo ni rampas | Permite cubrir toda demanda térmicamente | Puede faltar capacidad térmica, mínimo técnico, rampas o costo temporal |
| Balance hídrico | `T1+V1+S1=90`; `Tt-V(t-1)+Vt+St=I_t` | Exactamente esas igualdades | Equivale a `Vt=V(t-1)+I_t-T_t-S_t` con `V0=0` | Estado inicial implícito; no hay pérdidas/evaporación |
| Relación agua-potencia | `PH_t=2.4525T_t` | Exacta | Algebraicamente coherente | Falta definición física de 2.4525 |
| Relación potencia-energía | `GH_t=PH_t` | Exacta | Identidad | Correcta solo si la duración/factor está normalizado a 1 |
| Demanda | `GH_t+GT_t=D_t`, `D=[60,80,70,90]` | Exacta | Igualdad por periodo | No hay pérdidas, reservas ni déficit permitido/penalizado |
| Límites del embalse | `40<=V_t<=100` | Dos restricciones explícitas por periodo | Correctos respecto del fixture | `V4>=40` es la única condición terminal; puede no ser la política pretendida |
| Turbinamiento máximo | `T_t<=70` | Igual | No hay mínimo ni rampas | Límite redundante para estos datos; no prueba que se aplique en casos generales |
| No negatividad | No escrita como filas | Añadida a las 24 variables por `NonNegativeReals` | Es una modificación implícita respecto de la tabla | Correcta solo si todas las variables debían ser no negativas; no queda trazabilidad |
| Función objetivo | `min 100·sum(GT_t)` | Exactamente esa función | Costo térmico constante en los cuatro periodos | No hay costo hidro, vertimiento, arranque, déficit ni costo variable por periodo |

### 9.1 ¿Las variables añadidas cambian el modelo reducido?

El test histórico reducido usa `T1..T4, GT1..GT4`, demanda `2.4525T_t+GT_t=D_t` y cotas acumuladas `sum_{i<=t}T_i <= [50,70,85,95]`.

Al eliminar `V`, `S`, `PH` y `GH` del fixture completo:

- `PH` y `GH` son alias algebraicos;
- con aportes acumulados `[90,110,125,135]` y `V_t>=40`, aparecen exactamente las cotas acumuladas `[50,70,85,95]`;
- `V_t<=100` no endurece la proyección en `T,GT` porque el vertimiento no negativo y sin cota puede absorber excedentes;
- por tanto, para estos datos las variables añadidas amplían la representación y su multiplicidad, pero no cambian la proyección factible `T,GT` ni el óptimo de costo.

Esto es una equivalencia algebraica del fixture actual, no una validación de fidelidad física.

### 9.2 Biobjetivo hidroeléctrico

Para `Z1=min 100·sum(GT)` y `Z2=max V4`:

- extremo costo: `(Z1,Z2)=(6701.25,40)`;
- extremo volumen, con desempate por menor costo: `V4=100`, `sum(T)=35`, `S=0`, `Z1=21416.25`;
- frontera: `Z1 = 245.25·V4 - 3108.75`, para `40<=V4<=100`.

Con utilidades desplazadas, el peso `(0.5,0.5)` hace constante la suma sobre esa frontera; aquí sí existe multiplicidad. El problema es que la interpretación generaliza esa propiedad especial a cualquier modelo con peso 0.5.

### 9.3 Especificación hidroeléctrica pendiente de aprobación

El estado certificable sigue siendo únicamente: **algebraicamente consistente con el fixture actual**. No se afirma que el modelo sea físicamente correcto ni fiel al ejercicio definitivo.

Antes de certificarlo deberá crearse y versionarse una especificación aprobada que incluya, como mínimo:

- variables y significado;
- unidades y dimensión temporal;
- datos y procedencia;
- ecuaciones;
- restricciones y condiciones iniciales/finales;
- función objetivo;
- interpretación física;
- versión original del enunciado;
- versión corregida aprobada y registro de diferencias.

Esta auditoría no inventa esa especificación ni propone valores faltantes.

## 10. Tests posiblemente incorrectos o insuficientes

No se encontró un assert numérico central que deba invertirse: `10`, los valores de Benchmark A y `6701.25` son correctos para sus modelos efectivos. Sí hay tests que dan una seguridad matemática que no poseen:

1. `tests/test_hydroelectric_e2e.py` compara el JSON con objetos generados por el mismo builder y después exige números codificados del mismo fixture. Verifica transporte y regresión, no un oráculo físico independiente.
2. El test que presenta como exhaustivos los 28 operadores/RHS no contrasta completamente los coeficientes de `Turb_Pot_*` y `Pot_Ene_*`. El nombre/intención del test excede su cobertura.
3. Los tests lexicográficos hidroeléctricos reutilizan las mismas ecuaciones y constantes. Son regresiones válidas, pero no validación independiente.
4. El test de interpretación con peso 0.5 permite que la heurística produzca “degeneración”; debe sustituirse por una prueba real de multiplicidad y añadir el control Benchmark A, donde `(0.5,0.5)` tiene óptimo único.
5. Los tests de infeasible/unbounded aceptan un estado conjunto o ambiguo. Deben comprobar el contrato exacto que se decida soportar y, si el solver no distingue por presolve, documentar la segunda corrida necesaria.
6. Los tests de plotting verifican principalmente el tipo `Figure`; no detectan el sombreado falso de una región no acotada.
7. No existe una prueba de interacción que edite restricciones y luego cambie nombres/cantidad de variables para verificar persistencia.
8. El test monoobjetivo de minimización con solo restricciones `<=` y variables no negativas tiene como solución trivial cero; es demasiado débil para revelar errores de sentido o signo.

Principio de corrección: si en el futuro un oráculo independiente contradice un fixture, debe corregirse el test y no deformarse el modelo para conservar el número histórico.

## 11. Arquitectura propuesta para entrada masiva e indexada

### 11.1 Contrato canónico independiente del solver

La UI, los importadores y un lenguaje de familias deben compilar hacia una representación canónica versionada. Esa representación no debe contener objetos Pyomo ni Gurobi.

```text
ModelSpec
├── metadata: id, name, version, description, units/provenance
├── sets: nombre → elementos tipados y ordenados
├── parameters: nombre, índices, valores, unidad, fuente
├── variables: nombre/base, índices, dominio, lb, ub, unidad
├── objectives: nombre, sentido, expresión lineal, prioridad/peso opcional
├── constraints: nombre estable, índices, lhs lineal, operador, rhs
└── solve_options: tolerancias y límites portables + opciones por backend
```

Cada expresión lineal compilada debe usar términos dispersos:

```json
{
  "constant": 0,
  "terms": [
    {"variable": "V", "index": [2], "coefficient": 1},
    {"variable": "V", "index": [1], "coefficient": -1}
  ]
}
```

Reglas necesarias:

- números finitos únicamente;
- IDs internos distintos de etiquetas visibles;
- no descartar columnas/variables desconocidas;
- trazabilidad `source_row`, archivo, hoja, familia e índice;
- validación estructural antes de expansión y matemática después;
- reporte de cuántas filas se aceptaron, rechazaron, normalizaron y generaron;
- hash de la representación expandida para vincular entrada, solve y resultado;
- serialización determinista y esquema versionado con migraciones.

### 11.2 Modos de entrada

**A. Manual actual.** Conservar para problemas pequeños; añadir validación por celda, persistencia real y vista de errores.

**B. Pegado masivo.** Área tabular que acepte texto copiado de Excel, CSV o TSV. Debe detectar delimitador y mostrar una previsualización antes de incorporar:

```text
name,x1,x2,x3,operator,rhs
R1,2,3,0,<=,20
R2,0,1,4,>=,15
R3,1,0,-2,=,7
```

**C. CSV.** Importación UTF-8, elección de separador/decimal, encabezados obligatorios, reporte de filas y descarga de plantilla.

**D. XLSX.** Selección de hoja, fila de encabezado y rango; lectura en memoria; no ejecutar macros ni fórmulas externas. Guardar valores importados y procedencia, no una dependencia viva del libro.

**E. Forma matricial.** Tres entradas coordinadas: matriz dispersa/densa `A`, vector de operadores `op` y vector `b`; comprobaciones `A.shape=(m,n)`, `len(op)=len(b)=m`, nombres de filas/columnas y finitud. Aunque el rótulo sea `Ax<=b`, el vector `op` debe permitir `<=`, `>=`, `=`.

**F–H. Familias, parámetros y generación.** El usuario declara conjuntos y parámetros una vez y una plantilla genera restricciones concretas:

```text
set T = 1..24
param aporte[T]
param demanda[T]

forall t in T:
  balance_agua[t]: V[t] = (t == first(T) ? V0 : V[prev(t)])
                            + aporte[t] - T[t] - S[t]
  demanda[t]: GH[t] + GT[t] = demanda[t]
```

No se recomienda evaluar `eval()` ni Python arbitrario. Debe definirse un AST limitado: suma, resta, multiplicación escalar, índices, acceso a parámetros y funciones seguras como `prev/first`. El compilador realiza:

```text
declaraciones
  → parseo a AST
  → validación de símbolos/dimensiones
  → expansión determinista por índices
  → ConstraintSpec[] con provenance=(familia, índice)
  → adaptador del solver
```

La UI debe permitir revisar “2 familias → 48 restricciones generadas”, inspeccionar cualquier instancia y volver de una restricción fallida a su parámetro/fila fuente.

### 11.3 Escalabilidad

- Conservar matrices dispersas de extremo a extremo.
- No renderizar 100 columnas completas por defecto; usar mapeo de columnas y vistas paginadas/filtradas.
- Validar y expandir fuera del script monolítico de Streamlit, con funciones puras y cacheables.
- Para modelos muy grandes, ofrecer resumen y muestreo sin truncar silenciosamente el objeto canónico.
- Separar `ModelSpec` de `ExpandedModel`; las familias compactas pueden persistirse y la expansión llevar su propio hash.

## 12. Evaluación de backends

| Alternativa | Ventajas | Desventajas | Impacto código/tests | Escalabilidad/modelos grandes | Multiobjetivo | Mantenimiento |
|---|---|---|---|---|---|---|
| **A. Mantener Pyomo + HiGHS** | Stack actual; abierto; LP/MIP/QP; mínima migración; APPSI permite resoluciones persistentes | No aporta por sí solo esquema canónico/UI masiva; multiobjetivo debe orquestarse; capacidades avanzadas dependen del solver | Bajo para continuar; alto si se corrigen capas sin separarlas | Buena para LP/MIP dispersos; hace falta construir eficientemente | Barridos y lexicografía propios | Menor cambio inmediato, pero persiste acoplamiento si no se crea dominio canónico |
| **B. Añadir Gurobi opcional detrás de Pyomo** | Conserva modelos Pyomo; backend de alto rendimiento opcional; menor duplicación que gurobipy directo | Licencia/disponibilidad; no usa toda la API matricial/multiobjetivo nativa; diferencias de estados/tolerancias | Medio; suite parametrizada por backend y contratos comunes | Alta si la formulación Pyomo es eficiente | Se puede mantener orquestación portable o usar capacidades específicas con cautela | Razonable si las extensiones se encapsulan |
| **C. Migrar completamente a gurobipy** | API matricial, MIP y multiobjetivo nativo potentes; control fino | Dependencia total de licencia/producto; rompe disponibilidad actual; migración y reescritura; reduce portabilidad | Muy alto; reescribir builders, estados, tests y despliegue | Excelente en entornos licenciados | Excelente, pero la semántica de prioridades/pesos debe seguir explícita | Mayor riesgo de lock-in y soporte de instalaciones |
| **D. Capa solver-agnostic con adaptadores** | Separa intención del usuario de sintaxis de solver; permite Pyomo/HiGHS hoy, Gurobi opcional y futuros backends; facilita oráculos cruzados | Inversión inicial; hay que definir el subconjunto común y extensiones; riesgo de crear una abstracción demasiado ambiciosa | Alto inicialmente; después los tests se dividen en contrato canónico, compilador y adaptadores | La mejor base si usa estructuras dispersas y expansión controlada | Permite declarar método a nivel de servicio y mapear capacidades de cada backend | Mejor sostenibilidad si se mantiene un contrato pequeño y versionado |

**Recomendación:** alternativa D, implementada incrementalmente con Pyomo + HiGHS como primer adaptador; después B mediante un adaptador Gurobi opcional. No se recomienda C como primera acción.

HiGHS se presenta oficialmente como software para LP, MIP y QP a gran escala: [HiGHS](https://highs.dev/). APPSI ofrece interfaces persistentes y resolución eficiente tras modificaciones del modelo: [Pyomo APPSI](https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html), [APPSI Highs](https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.appsi.solvers.highs.Highs.html). Gurobi dispone de variables/restricciones matriciales y admite matrices dispersas en su API: [Gurobi Python Model API](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html). Su adopción debe considerar las restricciones de licencia aplicables; por ejemplo, las licencias WLS académicas están restringidas a uso académico: [Gurobi — Academic WLS restrictions](https://support.gurobi.com/hc/en-us/articles/34672988479633-What-are-the-restrictions-on-using-an-academic-WLS-license).

## 13. Hallazgos priorizados

### AUD-CRIT-01 — Resultado numérico internamente contradictorio

- **Severidad:** CRÍTICO
- **Archivo:** `src/solver_optimizador/lp_solver.py:96-121`; `src/solver_optimizador/multiobjective.py:128-129,335-338`
- **Función/líneas:** `solve_lp()`, `solve_lexicographic_extreme()`, barrido ponderado.
- **Comportamiento observado en Fase 1 (PRE-FIX):** variables, objetivo, LHS y holguras se redondeaban independientemente a seis decimales; en multiobjetivo se evaluaban objetivos sobre variables ya redondeadas.
- **Problema detectado:** el objeto devuelto no conserva una única solución numérica coherente.
- **Por qué es problemático:** rompe trazabilidad, reproducción, verificación de factibilidad y cualquier cálculo posterior; el error puede crecer con coeficientes grandes.
- **Ejemplo reproducible:** `max 1e9·x`, sujeto a `1e9·x = 1`, `x>=0`.
- **Resultado PRE-FIX:** `x=0.0`, `Z=1.0`, `LHS=1.0`; al reevaluar con el `x` publicado se obtiene `Z=0`, `LHS=0`.
- **Resultado esperado:** conservar `x≈1e-9` canónico; objetivo, LHS y holgura deben derivarse del mismo vector. Redondear únicamente en la vista.
- **Recomendación:** contrato de precisión completa, tolerancias explícitas, serialización segura y verificación de residuo antes de emitir `optimal`.
- **Tests a agregar/modificar:** escalas `1e-12..1e12`, reconstrucción `Z(x)`/`Ax`, factibilidad del resultado serializado y comparación UI sin alterar el dato base.

**Estado: CORREGIDO EN FASE 2A.**

- **Rama:** `codex/fix-aud-crit-01-numeric-integrity`.
- **Commit:** commit único de Fase 2A que contiene este documento; su SHA se obtiene con `git rev-parse HEAD` y se registra en la respuesta de publicación. Incluir el propio SHA dentro del mismo commit sería una referencia circular que alteraría ese SHA.
- **Estrategia aplicada:** se eliminaron redondeos de los datos matemáticos canónicos; `objective_value`, variables, LHS y holguras se reconstruyen desde el mismo vector de floats del solver. El barrido multiobjetivo conserva `x`, `Z1`, `Z2`, rangos y `W` sin redondeo de presentación. Los tiempos y la generación preexistente de pesos mantienen su comportamiento.
- **Tolerancia:** `is_active` continúa usando `abs(slack) < tol`; `LPSolution.activity_tolerance` registra el valor empleado sin modificar parámetros internos de HiGHS.
- **Presentación:** Streamlit y la interpretación formatean copias para lectura y emplean notación significativa/científica cuando corresponde, sin sobrescribir la solución.
- **Tests añadidos:** `tests/test_numeric_integrity.py`, con siete casos recolectados que cubren la igualdad escalada crítica, reconstrucción de objetivo, reconstrucción de LHS/holguras, escalas `1e-9`, `1` y `1e9`, extremos lexicográficos y una corrida ponderada escalada.
- **Evidencia PRE-FIX:** `docs/audit_evidence/fase1b_validation.txt`.
- **Evidencia POST-FIX:** `docs/audit_evidence/aud_crit_01_fix_validation.txt`.
- **Resultado POST-FIX:** `x=1.0000000000000001e-09`, `Z=1`, `LHS=1`; objetivo y LHS reconstruidos desde el `x` publicado también son `1`.

Ningún otro hallazgo de esta auditoría se marca como corregido en Fase 2A.

### AUD-HIGH-01 — Método multiobjetivo híbrido y valor `W` no documentado consistentemente

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/multiobjective.py:36-149,153-345`; `docs/LEXICOGRAPHIC_PAYOFF_MATRIX.md`; textos de UI/README.
- **Función/líneas:** extremos lexicográficos y `solve_biobjective_weighted()`.
- **Comportamiento observado en Fase 1 (PRE-FIX):** extremos/endpoints lexicográficos; pesos interiores con suma ponderada por rangos sin desplazamiento.
- **Problema detectado:** se presenta el conjunto como método de ponderaciones; una documentación usa utilidad desplazada que el código no calcula.
- **Por qué es problemático:** confunde dos métodos y hace que `W` tenga una escala distinta de la explicada, aunque los puntos interiores puedan coincidir.
- **Ejemplo reproducible:** Benchmark A; `W_code(0,1)=169/89=1.898876`, mientras la utilidad desplazada da `1`.
- **Resultado PRE-FIX:** mismas decisiones, valores `W` fuera de `[0,1]`; endpoints escogidos con prioridad secundaria.
- **Resultado esperado:** definir y nombrar separadamente optimización individual, desempate lexicográfico y suma ponderada; una sola fórmula de `W` en código, UI y docs.
- **Recomendación:** no cambiar números hasta fijar la especificación matemática; después separar servicios/métodos y versionar el significado de `W`.
- **Tests a agregar/modificar:** fórmula simbólica/numeral de `W`, MAX/MIN mixtos, endpoints con múltiples óptimos y comparación lexicográfico vs ponderado puro.

**Estado: CORREGIDO EN FASE 2B.**

- **Rama:** `codex/fix-aud-high-01-weighted-method`.
- **Commit:** commit único de Fase 2B; su SHA se obtiene con `git rev-parse HEAD` y se informa al publicar. No se inserta el propio SHA dentro del commit para evitar una referencia circular.
- **Fórmula anterior:** `W_pre=α1·s1·Z1/ΔZ1 + α2·s2·Z2/ΔZ2`, sin origen de escala; además los endpoints se copiaban desde las anclas.
- **Fórmula nueva:** para MAX, `Nk=(Zk-Zk_min)/ΔZk`; para MIN, `Nk=(Zk_max-Zk)/ΔZk`; todas las corridas resuelven `MAX W=α1N1+α2N2` sobre la región factible original.
- **Separación conceptual:** `_build_payoff_anchor()` selecciona representantes únicamente para construir la matriz de pagos. `solve_lexicographic_extreme()` se conserva como alias histórico de compatibilidad y no participa como sustituto del barrido.
- **Endpoints:** `(1,0)` y `(0,1)` pasan por HiGHS como funciones ponderadas. Una selección posterior, cuando aplica, conserva `W*` y queda registrada en `selection_metadata` sin afirmar unicidad.
- **Benchmark A:** reproduce las seis ponderaciones académicas y `(0.5,0.5)`; `N1=(Z1-390)/610`, `N2=(Z2-80)/89`.
- **Caso MAX/MIN:** se añadió prueba de orientación de MIN y un problema sencillo con óptimo ponderado único.
- **Hidroeléctrico:** usa `N1=(21416.25-Z1)/14715`, `N2=(Z2-40)/60`; los pesos `0.2/0.8` y `0.4/0.6` favorecen reserva, `0.6/0.4` y `0.8/0.2` favorecen costo, y `0.5/0.5` verifica factibilidad, frontera y `W≈0.5` sin exigir un vector.
- **Tests:** `tests/test_weighted_method.py` más ajustes explícitos a pruebas que dependían de la fórmula o interpretación anterior.
- **Oráculo independiente:** `tools/audit/verify_weighted_method_exact.py`, biblioteca estándar y `Fraction`, sin importar producción ni solver.
- **Evidencia:** `docs/audit_evidence/aud_high_01_weighted_method_validation.txt`.

`AUD-HIGH-02` permanece abierto: Fase 2B elimina inferencias falsas basadas solo en el peso y etiquetas de “óptimo único”, pero no implementa un certificado general de unicidad o multiplicidad.

### AUD-HIGH-02 — Degeneración y unicidad afirmadas sin prueba

**Estado: ABIERTO.** Fase 2B retiró las dos afirmaciones automáticas falsas que interferían con la presentación del método, pero no añadió un algoritmo general para demostrar degeneración, unicidad o multiplicidad.

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/interpretation.py:149-154`; `src/solver_optimizador/multiobjective.py:133-149`; `streamlit_app.py` presentación de multiplicidad.
- **Función/líneas:** interpretación biobjetivo y `has_alternative_optima`.
- **Comportamiento observado en Fase 1:** una ejecución única con `alpha1=0.5` se etiquetaba degenerada; ausencia de mejora secundaria se mostraba como óptimo único. Esas etiquetas automáticas se retiraron en Fase 2B, pero todavía no existe una prueba general que certifique unicidad o multiplicidad.
- **Problema detectado:** el peso no prueba degeneración y el algoritmo no prueba unicidad global.
- **Por qué es problemático:** entrega una conclusión matemática falsa al usuario.
- **Ejemplo reproducible:** Benchmark A con `(0.5,0.5)` tiene óptimo único `(80,50)`, pero `claims_degeneracy=true`.
- **Resultado observado en Fase 1:** falso positivo de degeneración; posibles falsos negativos de multiplicidad.
- **Resultado esperado:** “no evaluado” salvo que se ejecute una prueba de cara óptima/variación por variable o se obtenga certificado equivalente.
- **Recomendación:** separar “se encontró alternativa” de “se demostró unicidad”; quitar inferencia por peso.
- **Tests a agregar/modificar:** caso 0.5 único, caso 0.5 degenerado hidroeléctrico y extremos con cara óptima.

### AUD-HIGH-03 — Ediciones de restricciones no persistidas ante cambios estructurales

- **Severidad:** ALTO
- **Archivo:** `streamlit_app.py:377-403,586-617,704-750`
- **Función/líneas:** editor de variables/restricciones y sincronización de sesión.
- **Comportamiento actual:** se usa la tabla editada localmente para resolver, pero no se guarda en `session_state.constraints_data`; un cambio de variables reconstruye desde el estado anterior.
- **Problema detectado:** una secuencia válida de interacción puede perder coeficientes o filas sin confirmación.
- **Por qué es problemático:** el modelo resuelto puede diferir del que el usuario acaba de editar.
- **Ejemplo reproducible:** editar una restricción, después cambiar cantidad/renombrar variables y observar la reconstrucción desde `constraints_data` previo.
- **Resultado actual:** riesgo de restaurar valores anteriores.
- **Resultado esperado:** estado canónico sincronizado antes de cualquier migración estructural, con confirmación cuando haya columnas eliminadas.
- **Recomendación:** controlador de estado único y tests de transiciones, sin duplicar tabla local/estado.
- **Tests a agregar/modificar:** AppTest o prueba de controlador para editar→renombrar, editar→aumentar/disminuir `n`, descargar y resolver.

### AUD-HIGH-04 — Región no acotada dibujada como polígono cerrado

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/plotting.py:75-128`
- **Función/líneas:** `plot_feasible_region_2d()`.
- **Comportamiento actual:** calcula intersecciones factibles y sombrea su casco si hay al menos tres puntos.
- **Problema detectado:** no analiza el cono de recesión.
- **Por qué es problemático:** comunica visualmente una región factible distinta.
- **Ejemplo reproducible:** `x<=2`, `y>=x-1`, `y>=1-x`, `x,y>=0`; es no acotada hacia arriba, pero se añadió un `Polygon` triangular.
- **Resultado actual:** `patch_count=1` y falso cierre.
- **Resultado esperado:** no sombrear como cerrado; representar rayos/recorte explícito o indicar que la vista está truncada.
- **Recomendación:** clasificar acotación antes de construir el parche.
- **Tests a agregar/modificar:** regiones acotada, no acotada con 0/1/2/3+ vértices, vacía y degenerada; inspección geométrica, no solo tipo `Figure`.

### AUD-HIGH-05 — Validación JSON acepta números no finitos y normaliza inconsistencias silenciosamente

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/model_io.py:184-396`
- **Función/líneas:** `validate_model_dict()`, `deserialize_model()`.
- **Comportamiento actual:** comprueba conversión a `float`, no finitud en todas las rutas; ignora discrepancia de `num_vars`.
- **Problema detectado:** un objetivo con `Infinity` pasa la validación; metadatos incoherentes cambian sin aviso.
- **Por qué es problemático:** mueve errores de frontera al solver y oculta cambios del archivo de entrada.
- **Ejemplo reproducible:** coeficiente objetivo `Infinity` devuelve `(True, None)` y se deserializa como infinito.
- **Resultado actual:** archivo aceptado y fallo posterior/no estándar.
- **Resultado esperado:** rechazo temprano y reporte preciso de campo/fila; `num_vars == len(var_names)`.
- **Recomendación:** esquema estricto versionado, `math.isfinite`, política explícita de campos desconocidos y errores acumulados.
- **Tests a agregar/modificar:** NaN/±Inf en cada campo, num_vars discordante, variables desconocidas, claves extra y JSON estricto.

### AUD-HIGH-06 — Nombres visibles usados directamente como componentes Pyomo

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/lp_solver.py:46-63`; `src/solver_optimizador/multiobjective.py:304-327`; validación UI/builder.
- **Función/líneas:** construcción dinámica mediante `setattr`.
- **Comportamiento actual:** el nombre del usuario se usa como atributo del `ConcreteModel`.
- **Problema detectado:** colisiones con `name`, `component_map`, `obj` y otros nombres internos.
- **Por qué es problemático:** causa excepción fuera del bloque de manejo o reemplazo accidental de componentes.
- **Ejemplo reproducible:** variable `name`/`component_map` produce `ValueError`; `obj` genera advertencia de reemplazo al añadir el objetivo.
- **Resultado actual:** crash o modelo alterado.
- **Resultado esperado:** IDs internos seguros e independientes de la etiqueta del usuario.
- **Recomendación:** variables indexadas en un único componente Pyomo y mapa `canonical_id ↔ display_name`.
- **Tests a agregar/modificar:** nombres reservados, Unicode, espacios, signos, nombres muy largos y colisiones tras normalización.

### AUD-HIGH-07 — Desigualdades estrictas transformadas silenciosamente

- **Severidad:** ALTO
- **Archivo:** `src/solver_optimizador/lp_models.py:34-45`; `src/solver_optimizador/model_io.py` validación de operador.
- **Función/líneas:** `Operator.from_str()`.
- **Comportamiento actual:** `<→<=` y `>→>=` en API; JSON/UI solo admiten `<=`, `>=`, `=`.
- **Problema detectado:** comportamiento inconsistente y cambio matemático silencioso.
- **Por qué es problemático:** los conjuntos factibles no son iguales; una desigualdad estricta puede no alcanzar óptimo.
- **Ejemplo reproducible:** `Operator.from_str("<")` retorna `LE`.
- **Resultado actual:** relajación sin advertencia o rechazo según la ruta.
- **Resultado esperado:** rechazo uniforme con explicación, salvo una política explícita de aproximación con epsilon y advertencia.
- **Recomendación:** eliminar aliases silenciosos del contrato público.
- **Tests a agregar/modificar:** todas las rutas con `<`, `>`, espacios, Unicode y operadores inválidos.

### AUD-HIGH-08 — Fidelidad física hidroeléctrica no demostrable y supuestos implícitos

- **Severidad:** ALTO
- **Archivo:** `tests/fixtures/hydroelectric_full_24_vars.json`; `tests/test_hydroelectric_e2e.py`; documentación del ejemplo.
- **Función/líneas:** fixture y tests E2E.
- **Comportamiento actual:** implementa un modelo lineal coherente con `V0=0`, factor 2.4525, identidad potencia-energía y costo térmico uniforme.
- **Problema detectado:** el enunciado, unidades y supuestos no están versionados; no puede demostrarse que la intención física sea esa.
- **Por qué es problemático:** un resultado algebraicamente correcto puede representar el ejercicio equivocado.
- **Ejemplo reproducible:** cambiar duración de periodo de 1 a otra unidad invalidaría `GH=PH`; cambiar `V0` altera balances y costo.
- **Resultado actual:** `Z=6701.25`, correcto para el fixture.
- **Resultado esperado:** benchmark con enunciado, unidades, ecuaciones y valores esperados derivados independientemente.
- **Recomendación:** no cambiar el fixture hasta recuperar/aprobar la especificación fuente; luego registrar cada supuesto.
- **Tests a agregar/modificar:** residuo por ecuación, unidades/documentación, proyección contra modelo reducido y al menos un oráculo independiente versionado.

### AUD-HIGH-09 — Cobertura circular frente a corrección matemática

- **Severidad:** ALTO
- **Archivo:** `tests/test_hydroelectric_e2e.py`, `tests/test_lexicographic_payoff.py`, `tests/test_plotting*.py`, fixtures y scripts benchmark.
- **Función/líneas:** asserts de regresión y comparaciones builder↔fixture.
- **Comportamiento actual:** muchos resultados esperados provienen de las mismas ecuaciones/constantes y los tests visuales solo comprueban creación.
- **Problema detectado:** una misma equivocación puede existir en fixture, builder, docs y test y producir 69 PASS.
- **Por qué es problemático:** confunde no regresión con validación científica.
- **Ejemplo reproducible:** la heurística falsa de degeneración pasa en hidro y no tiene control no degenerado; el sombreado no acotado también pasa los tests actuales.
- **Resultado actual:** suite verde con errores semánticos demostrables.
- **Resultado esperado:** capas de tests: contrato, metamórficos, oráculos exactos/independientes, cross-solver opcional y UI.
- **Recomendación:** conservar regresiones útiles, etiquetarlas y añadir benchmarks derivados fuera del código bajo prueba.
- **Tests a agregar/modificar:** casos adversariales de este informe y datasets con procedencia/derivación.

### AUD-MED-01 — Dominio fijo y capacidades aparentes/inexistentes

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/lp_models.py`; `src/solver_optimizador/lp_solver.py:46-51`; `multiobjective.py:304-309`.
- **Función/líneas:** esquema de variables y construcción Pyomo.
- **Comportamiento actual:** todas las variables son continuas no negativas.
- **Problema detectado:** no hay contrato para cotas, libres, enteras o binarias.
- **Por qué es problemático:** introducir manualmente algunas cotas no emula dominios discretos ni variables libres de forma segura.
- **Ejemplo reproducible:** no existe campo para `x∈Z`, `x∈{0,1}`, `lb=-∞`, `ub=10`.
- **Resultado actual:** cualquier nombre se crea como `NonNegativeReals`.
- **Resultado esperado:** capacidad declarada explícitamente o límites claros en UI/docs.
- **Recomendación:** incluir dominio/cotas en la futura representación canónica antes de ampliar UI.
- **Tests a agregar/modificar:** compilación de cada dominio y equivalencia por adaptador.

### AUD-MED-02 — Estados y tolerancias del solver incompletos

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/lp_solver.py:65-132`; `multiobjective.py` solves directos.
- **Función/líneas:** solve y mapeo de terminación.
- **Comportamiento actual:** `tol` no configura HiGHS; solo `optimal` devuelve solución; mapeo textual limitado.
- **Problema detectado:** se mezclan tolerancia de reporte y tolerancias de solución; se pierden incumbentes y diagnósticos.
- **Por qué es problemático:** estados límite, time limit o infeasible-or-unbounded no tienen contrato reproducible.
- **Ejemplo reproducible:** tests aceptan más de un estado para casos diseñados como infeasible/unbounded.
- **Resultado actual:** información parcial.
- **Resultado esperado:** enum propio con terminación, factibilidad primal/dual, gap, incumbent y detalle original.
- **Recomendación:** adaptador de resultados por backend y opciones validadas.
- **Tests a agregar/modificar:** optimal, infeasible, unbounded, ambiguous, time limit con/sin incumbent y tolerancias.

### AUD-MED-03 — Rango cero cancela problemas reducibles

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/multiobjective.py:240-262`
- **Función/líneas:** validación de rangos.
- **Comportamiento actual:** si cualquier rango `<1e-7`, no se resuelve ningún peso.
- **Problema detectado:** un objetivo constante puede eliminarse de la escalarización sin impedir optimizar el otro.
- **Por qué es problemático:** rechaza modelos válidos y no distingue objetivos idénticos, constantes o payoff insuficiente.
- **Ejemplo reproducible:** `Z1=0`, `Z2=x`, `0<=x<=1`.
- **Resultado actual:** análisis cancelado.
- **Resultado esperado:** clasificación explícita y reducción segura, o mensaje metodológico específico.
- **Recomendación:** definir política matemática antes de implementar.
- **Tests a agregar/modificar:** uno/dos rangos cero, objetivos afines y sentidos mixtos.

### AUD-MED-04 — Pesos aceptados sin igualdad exacta ni renormalización

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/multiobjective.py:264-275`
- **Función/líneas:** validación de `weights`.
- **Comportamiento actual:** tolerancia de suma `1e-3`; luego redondea sin normalizar.
- **Problema detectado:** se incumple el contrato `α1+α2=1` anunciado.
- **Por qué es problemático:** `W` y comparaciones entre corridas cambian de escala.
- **Ejemplo reproducible:** `(0.5004,0.5004)` aceptado; suma almacenada `1.0008`.
- **Resultado actual:** pesos no convexos aceptados dentro de tolerancia.
- **Resultado esperado:** rechazo o renormalización explícita con valor original y efectivo.
- **Recomendación:** contrato único de precisión y suma.
- **Tests a agregar/modificar:** límites de tolerancia, pesos negativos mínimos, NaN/Inf y suma efectiva.

### AUD-MED-05 — Construcción Pyomo duplicada y divergente

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/lp_solver.py`; `src/solver_optimizador/multiobjective.py:304-345`.
- **Función/líneas:** builders internos de modelos.
- **Comportamiento actual:** multiobjetivo vuelve a crear variables/restricciones y maneja excepciones/estados de forma distinta.
- **Problema detectado:** dos adaptadores implícitos pueden evolucionar de manera diferente.
- **Por qué es problemático:** una corrección de dominios, nombres o estados puede aplicarse solo a un flujo.
- **Ejemplo reproducible:** `solve_lp` captura excepciones de solve; el barrido directo no usa el mismo contrato.
- **Resultado actual:** duplicación funcional.
- **Resultado esperado:** un adaptador Pyomo común y servicios matemáticos encima.
- **Recomendación:** resolver tras definir `ModelSpec`, no refactorizar antes de fijar matemáticas.
- **Tests a agregar/modificar:** equivalencia mono/bi de región factible y errores idénticos por backend.

### AUD-MED-06 — Diagnóstico de restricciones incompleto

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/lp_models.py:96-106`; `lp_solver.py:96-115`; interpretación/UI.
- **Función/líneas:** holguras y activas.
- **Comportamiento actual:** solo restricciones explícitas; igualdades siempre activas si factibles; no hay duales.
- **Problema detectado:** las cotas implícitas pueden determinar el óptimo sin aparecer; “activa” se interpreta como “cuello de botella”.
- **Por qué es problemático:** diagnóstico incompleto o causalmente exagerado.
- **Ejemplo reproducible:** Benchmark A extremo `(100,0)` depende de `x2=0`, pero esa cota no aparece como restricción activa.
- **Resultado actual:** lista parcial.
- **Resultado esperado:** cotas incluidas, residuo/tolerancia y lenguaje neutral; duales solo cuando estén disponibles y sean válidos.
- **Recomendación:** esquema uniforme de filas y bounds.
- **Tests a agregar/modificar:** actividad de lb/ub, igualdad redundante y escalas de tolerancia.

### AUD-MED-07 — Normalizaciones silenciosas pueden cambiar el modelo

- **Severidad:** MEDIO
- **Archivo:** `src/solver_optimizador/model_io.py`, `problem_builder.py`, `signature.py`.
- **Función/líneas:** normalización, deserialización y firma.
- **Comportamiento actual:** ausentes→0, extras descartados, algunos inválidos→0 en firma, nombres faltantes autogenerados.
- **Problema detectado:** no existe un reporte de transformación entrada→modelo.
- **Por qué es problemático:** un encabezado mal escrito puede eliminar coeficientes sin que el usuario lo sepa.
- **Ejemplo reproducible:** columna de una variable no declarada queda fuera de la salida canónica.
- **Resultado actual:** modelo aparentemente válido pero distinto.
- **Resultado esperado:** error o advertencia aceptada y provenance por campo.
- **Recomendación:** normalización tipada que devuelva `value + diagnostics`.
- **Tests a agregar/modificar:** columnas desconocidas, duplicadas, faltantes, valores vacíos y round-trip sin pérdida.

### AUD-MED-08 — Documentación histórica afirma propiedades no verificadas o ya desactualizadas

- **Severidad:** MEDIO
- **Archivo:** `docs/LEXICOGRAPHIC_PAYOFF_MATRIX.md`, `docs/UI_MVP_HARDENING.md`, `docs/STATUS.md`, `docs/agent_logs/*`, README.
- **Función/líneas:** fórmulas, conteos y afirmaciones de hardening.
- **Comportamiento actual:** conviven fórmula `W` desplazada/no desplazada, conteos antiguos, afirmación de no sombrear regiones no acotadas y limpieza de keys que hoy es `pass`.
- **Problema detectado:** la documentación no es una especificación confiable del código actual.
- **Por qué es problemático:** dificulta auditar intención y puede orientar tests/correcciones equivocadas.
- **Ejemplo reproducible:** `UI_MVP_HARDENING` afirma evitar sombreado no acotado; el caso adversarial sí genera polígono.
- **Resultado actual:** deriva documental.
- **Resultado esperado:** especificación vigente separada de logs históricos.
- **Recomendación:** no borrar historia; marcarla como histórica y crear documentos normativos versionados.
- **Tests a agregar/modificar:** ejemplos ejecutables de ecuaciones y chequeos de snippets críticos.

### AUD-MED-09 — Deuda de dependencias, empaquetado y archivo principal monolítico

- **Severidad:** MEDIO
- **Archivo:** `pyproject.toml`, `streamlit_app.py`, scripts raíz.
- **Función/líneas:** dependencias y arquitectura.
- **Comportamiento actual:** `numpy`/`pandas` se importan directamente pero llegan de forma transitiva; `pytest`, AMPL y herramientas están en dependencias duras; la app manipula `sys.path`; el archivo Streamlit supera mil líneas.
- **Problema detectado:** instalación frágil y separación insuficiente entre presentación, estado y servicios.
- **Por qué es problemático:** un cambio transitivo puede romper imports; aumenta costo de testear la entrada masiva.
- **Ejemplo reproducible:** una instalación que cambie dependencias transitivas no tiene contrato directo para pandas/numpy.
- **Resultado actual:** funciona en el entorno existente, sin lock ni perfiles claros.
- **Resultado esperado:** dependencias directas declaradas y grupos `app/dev/optional-ampl/optional-gurobi`.
- **Recomendación:** tratarlo después de la corrección matemática y de definir fronteras de módulos.
- **Tests a agregar/modificar:** instalación limpia mínima y smoke por extras.

### AUD-LOW-01 — Artefactos y scripts de benchmark pueden derivar

- **Severidad:** BAJO
- **Archivo:** `benchmark_a_multiobjective.py`, `benchmark_a_pyomo.py`, `verify_ampl_highs.py`, `results/*`.
- **Función/líneas:** utilidades históricas de raíz.
- **Comportamiento actual:** duplican parte de la lógica y escriben resultados versionados; uno representa ponderación pura y otro el flujo actual híbrido.
- **Problema detectado:** no hay declaración de cuál es normativo ni regeneración controlada.
- **Por qué es problemático:** artefactos pueden parecer evidencia actual cuando son históricos.
- **Ejemplo reproducible:** los endpoints coinciden en Benchmark A por unicidad, ocultando la diferencia metodológica.
- **Resultado actual:** resultados útiles pero ambiguos.
- **Resultado esperado:** benchmarks en carpeta dedicada, manifiesto de procedencia, comando reproducible y outputs generados identificados.
- **Recomendación:** clasificar después de crear oráculos independientes; no eliminar aún.
- **Tests a agregar/modificar:** test de regeneración y checksum/metadatos del benchmark.

### AUD-LOW-02 — `_clear_widget_keys` y patrón `.env.*`

- **Severidad:** BAJO
- **Archivo:** `streamlit_app.py:118-125`; `.gitignore`.
- **Función/líneas:** limpieza de widgets e ignores.
- **Comportamiento actual:** función vacía; `.env.*` también ignora `.env.example`.
- **Problema detectado:** intención y comportamiento difieren; falta excepción para plantilla de variables.
- **Por qué es problemático:** mantenimiento confuso y futura documentación de configuración incompleta.
- **Ejemplo reproducible:** llamar `_clear_widget_keys(state)` no cambia `state`; `git check-ignore .env.example` lo marcaría ignorado.
- **Resultado actual:** versionado de secretos protegido, pero plantilla también excluida.
- **Resultado esperado:** eliminar/implementar la función según diseño y usar `!.env.example` si se necesita plantilla falsa.
- **Recomendación:** resolver en fase de higiene, sin introducir valores reales.
- **Tests a agregar/modificar:** test unitario de la función si se conserva y verificación CI de archivos sensibles.

## 14. Deuda técnica consolidada

- Duplicación de construcción Pyomo entre monoobjetivo y multiobjetivo.
- `streamlit_app.py` concentra estado, importación, validación, resolución y render.
- Scripts de benchmark antiguos duplican fórmulas y no son oráculos claramente independientes.
- Documentación histórica mezclada con especificación vigente.
- Resultados generados versionados sin manifiesto reproducible.
- Dependencias de runtime/dev/optativas mezcladas; imports directos sostenidos transitivamente.
- Ausencia de linter, type checker, lock/reporte de entorno y matriz de solvers en CI.
- Tests que verifican regresiones del mismo fixture como si certificaran el planteamiento.
- Tests visuales estructurales, no semánticos.
- Validaciones distintas entre UI, JSON, dataclasses y solver.
- No existe representación canónica suficientemente expresiva para modelos grandes.

No se recomienda eliminar ninguno de estos archivos hasta mapear sus consumidores y convertir los benchmarks útiles en oráculos versionados.

## 15. Plan de corrección por fases

### FASE 1 — Corrección y validación matemática

1. Aprobar especificaciones formales de monoobjetivo, ponderado, lexicográfico e hidroeléctrico.
2. Corregir primero el contrato de precisión y coherencia del resultado.
3. Eliminar afirmaciones no demostradas de degeneración/unicidad.
4. Unificar política de `<`, `>`, tolerancias, estados y pesos.
5. Recuperar el enunciado hidroeléctrico con unidades y aprobar supuestos.
6. Añadir casos adversariales y pruebas metamórficas antes de cambiar resultados existentes.

**Criterio de salida:** cada resultado se puede reevaluar desde el vector publicado dentro de tolerancias declaradas y cada interpretación tiene evidencia calculada.

### FASE 2 — Representación canónica robusta

1. Definir `ModelSpec` versionado con IDs internos, dominios, cotas y expresiones dispersas.
2. Separar etiquetas visibles de identificadores del backend.
3. Crear validación finita/estructural y reporte de normalizaciones.
4. Diseñar migración desde JSON v1 sin pérdida silenciosa.

### FASE 3 — Benchmarks independientes de referencia

1. Formalizar ejemplos con ecuaciones, procedencia y derivación.
2. Incorporar enumeración exacta para LP pequeños.
3. Mantener formulaciones alternativas y cross-solver opcional.
4. Distinguir tests de regresión, contrato, propiedad y oráculo.

### FASE 4 — Separar claramente los métodos multiobjetivo

1. Servicios distintos para óptimos individuales, lexicográfico, suma ponderada y análisis de Pareto.
2. Definir normalización y significado de `W`.
3. Tratar rangos cero, endpoints y multiplicidad explícitamente.
4. Etiquetar la frontera como muestreada o exacta según evidencia.

### FASE 5 — Arquitectura de backends/solvers

1. Implementar interfaz de adaptador y resultado común.
2. Migrar Pyomo/HiGHS al primer adaptador sin cambiar matemáticas.
3. Añadir Gurobi opcional solo con pruebas de paridad y manejo de licencia.
4. Definir tabla de capacidades por backend y fallos explícitos.

### FASE 6 — Entrada masiva de restricciones

1. Pegado CSV/TSV desde Excel con preview.
2. Importadores CSV y XLSX.
3. Forma matricial `A/op/b` densa o dispersa.
4. Reporte de filas, campos y transformaciones; descarga de plantilla.

### FASE 7 — Restricciones indexadas, conjuntos y parámetros

1. AST lineal seguro, sin ejecución arbitraria.
2. Conjuntos/índices, parámetros y validación dimensional.
3. Expansión determinista con provenance familia→instancia.
4. Vista previa, conteo y diagnóstico de restricciones generadas.

### FASE 8 — Interfaz y experiencia de usuario

1. Separar controlador de estado del render Streamlit.
2. Conservar los modos manual, masivo, matricial e indexado.
3. Implementar estados de carga/error/vacío/confirmación y persistencia real.
4. Validar teclado, foco, contraste y anchos 375/768/1280/1440 px.
5. Mostrar precisión de presentación sin alterar valores canónicos.

## 16. Archivos que probablemente deberán modificarse después de aprobación

Primera ola matemática y de contrato:

- `src/solver_optimizador/lp_models.py`
- `src/solver_optimizador/lp_solver.py`
- `src/solver_optimizador/multiobjective.py`
- `src/solver_optimizador/interpretation.py`
- `src/solver_optimizador/model_io.py`
- `src/solver_optimizador/problem_builder.py`
- `src/solver_optimizador/plotting.py`
- `streamlit_app.py`
- tests de core, multiobjetivo, interpretación, plotting, persistencia e hidroeléctrico
- documentación normativa y fixtures, solo si el enunciado fuente los contradice

Arquitectura posterior:

- nuevos módulos para esquema canónico, validación, importadores, expansión indexada y adaptadores;
- `pyproject.toml` para extras/dependencias directas;
- posible reorganización de benchmarks y resultados.

## 17. Primera corrección ejecutada en Fase 2A

La rama aislada de **integridad numérica de resultados** implementa:

1. conservar valores internos sin redondeo en `LPSolution` y resultados multiobjetivo;
2. calcular objetivo, LHS y holguras desde el mismo vector publicado;
3. introducir formato/redondeo únicamente en Streamlit y exportaciones de presentación;
4. registrar tolerancias utilizadas;
5. añadir el caso `1e9·x=1` y pruebas de reevaluación como criterios de aceptación.

Esta corrección precede a la arquitectura nueva porque cualquier benchmark, adaptador o importador futuro necesita primero un resultado verificable y coherente. La rama no se integra en `main` hasta completar revisión externa.

## 18. Apéndice de reproducción independiente

### 18.1 Inventario de solvers desde Pyomo

```powershell
python -c "from pyomo.opt import SolverFactory; names=['appsi_highs','highs','gurobi','gurobi_direct','gurobi_persistent','glpk','cbc','scip','ipopt','cplex','xpress']; print({n: SolverFactory(n).available(exception_flag=False) for n in names})"
```

### 18.2 Oráculo exacto versionado de Benchmark A

El archivo `tools/audit/verify_benchmark_a_exact.py` no importa `solver_optimizador`, builders ni solvers. Enumera intersecciones, filtra factibilidad y evalúa objetivos y las siete ponderaciones requeridas con `fractions.Fraction`. Se conserva deliberadamente su valor `W` *legacy* de Fase 1B para que la evidencia histórica siga siendo reproducible; la ecuación normativa corregida y sus valores exactos se verifican por separado en la sección 18.4.

```powershell
python tools/audit/verify_benchmark_a_exact.py
```

La ejecución debe terminar con:

```text
RESULT: PASS (all exact Fraction assertions satisfied)
```

El stdout preservado está en `docs/audit_evidence/fase1b_validation.txt`.

### 18.3 Verificación versionada de integridad numérica

La salida PRE-FIX del antiguo verificador permanece inmutable en `docs/audit_evidence/fase1b_validation.txt`. En Fase 2A, `tools/audit/verify_numeric_integrity.py` se convirtió en verificador del contrato corregido. Sí usa `solve_lp`, por lo que es una comprobación de regresión del código bajo prueba, no un oráculo independiente del solver.

```powershell
python tools/audit/verify_numeric_integrity.py
```

La ejecución comprueba que `x≈1e-9` y que objetivo y LHS publicados y reconstruidos son aproximadamente uno. Termina con:

```text
RESULT: PASS (numeric integrity contract satisfied)
```

La salida POST-FIX se preserva en `docs/audit_evidence/aud_crit_01_fix_validation.txt`.

### 18.4 Oráculo exacto de suma ponderada normalizada

`tools/audit/verify_weighted_method_exact.py` usa únicamente biblioteca estándar
y `fractions.Fraction`; no importa producción, Pyomo ni HiGHS. Enumera los
vértices de Benchmark A y verifica `Z1`, `Z2`, `N1`, `N2`, `W`, los seis pesos
académicos y `(0.5,0.5)`.

```powershell
python tools/audit/verify_weighted_method_exact.py
```

Debe terminar con:

```text
RESULT: PASS (pure normalized weighted-sum oracle satisfied)
```

`tools/audit/verify_weighted_method_production.py` contrasta el mismo contrato
con el código bajo prueba y añade el caso hidroeléctrico. No se etiqueta como
oráculo independiente.

### 18.5 Segunda formulación hidroeléctrica indexada

Modelo AMPL utilizado conceptualmente, separado de las 28 filas del fixture:

```ampl
set PERIODS ordered;
param inflow {PERIODS};
param demand {PERIODS};
param factor > 0;
param thermal_cost >= 0;
param initial_volume;

var T {PERIODS} >= 0, <= 70;
var V {PERIODS} >= 40, <= 100;
var S {PERIODS} >= 0;
var PH {PERIODS} >= 0;
var GH {PERIODS} >= 0;
var GT {PERIODS} >= 0;

minimize TotalCost: thermal_cost * sum {t in PERIODS} GT[t];

subject to WaterBalance {t in PERIODS}:
    V[t] = (if ord(t) = 1 then initial_volume else V[prev(t)])
           + inflow[t] - T[t] - S[t];
subject to WaterToPower {t in PERIODS}: PH[t] = factor * T[t];
subject to PowerToEnergy {t in PERIODS}: GH[t] = PH[t];
subject to Demand {t in PERIODS}: GH[t] + GT[t] = demand[t];

data;
set PERIODS := 1 2 3 4;
param inflow := 1 90  2 20  3 15  4 10;
param demand := 1 60  2 80  3 70  4 90;
param factor := 2.4525;
param thermal_cost := 100;
param initial_volume := 0;
```

En la ejecución temporal de Fase 1 se registró `solve_result=solved`, `Z=6701.249999999997`, `sum(T)=95` y residuo máximo de igualdad `1.42e-14`. Como el script y stdout originales no fueron preservados, esa cifra se mantiene solo como observación histórica no reproducible, no como evidencia independiente suficiente. La demostración algebraica de la sección 8.3 sí está versionada; automatizar la formulación cruzada queda pendiente para el benchmark formal de Fase 3.

### 18.6 Casos adversariales mínimos

```text
Precisión:       max 1e9*x; 1e9*x = 1; x >= 0
Rango cero:      max Z1=0, max Z2=x; 0 <= x <= 1
No acotado 2D:   x<=2; y>=x-1; y>=1-x; x,y>=0
Peso inválido:   (alpha1,alpha2)=(0.5004,0.5004)
Nombres Pyomo:   name, component_map, obj
JSON no finito:  coeficiente de objetivo = Infinity
```

El caso de precisión se convirtió en prueba permanente en Fase 2A. Los demás casos deben abordarse únicamente en las fases correspondientes a sus hallazgos; siguen documentando el comportamiento observado.

---

**Estado de Fase 2B:** `AUD-CRIT-01` permanece corregido en `main` y
`AUD-HIGH-01` está corregido y validado en
`codex/fix-aud-high-01-weighted-method`. Fase 2B permanece únicamente en su rama
hasta revisión externa. `AUD-HIGH-02` y los demás hallazgos no abordados siguen
abiertos.
