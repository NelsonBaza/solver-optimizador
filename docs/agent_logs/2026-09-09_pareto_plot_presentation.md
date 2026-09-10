# Registro del agente: presentación de gráficos de Pareto

Fecha: 2026-09-09

Repositorio: `NelsonBaza/solver-optimizador`

Rama: `fix/pareto-plot-presentation`

SHA base: `c28bc321b6a0bfcb2235073d4f65037fbe96f77d`

## Alcance

Se integró primero, mediante fast-forward verificado, la rama auditada
`feat/interactive-multiobjective-epsilon` en `main`. La nueva rama se creó desde
ese `main` actualizado. El trabajo posterior se limitó a presentación de
gráficos, metadatos descriptivos, documentación y pruebas.

## Evidencia observada

- Relación previa: `370cd172` → `c28bc321`, un commit adelante y cero detrás.
- Antes y después de integrar: 322 pruebas aprobadas y cero fallidas.
- El modelo hidroeléctrico conserva 24 variables, 28 restricciones y todos sus
  coeficientes originales.
- Epsilon con `r=6` produjo los niveles 40, 50, 60, 70, 80, 90 y 100 y los
  puntos `(6701.25,40)`, `(9153.75,50)`, `(11606.25,60)`,
  `(14058.75,70)`, `(16511.25,80)`, `(18963.75,90)` y `(21416.25,100)`.
- Ponderaciones mantuvo 6 corridas, los extremos aprobados y 4 soluciones
  únicas.
- Suite final: 326 aprobadas, 0 fallidas y el warning conocido de
  `.pytest_cache`.

## Decisiones de implementación

- Se añadieron nombres opcionales a Z1 y Z2 y un `metadata.plot_title` corto;
  `metadata.name` permanece completo en consola.
- Se centralizaron los textos del gráfico para evitar títulos y ejes
  redundantes.
- La colocación de anotaciones usa posición normalizada respecto de los bordes;
  no usa azar ni dependencias nuevas.
- Coordenadas visualmente coincidentes se agrupan con precisión de presentación
  y reciben separaciones deterministas.
- La línea biobjetivo se conserva y la documentación limita su interpretación a
  conectar las soluciones obtenidas por el barrido.

Una prueba nueva detectó inicialmente que dos coordenadas ponderadas diferían
solo por ruido numérico y, por tanto, no compartían desplazamiento. La agrupación
se corrigió redondeando únicamente la clave de presentación a nueve decimales;
los valores matemáticos publicados no se redondean ni se alteran.

## Inspección visual

Se abrieron los PNG epsilon y ponderado. Se verificaron título, ejes, leyenda,
etiquetas, márgenes y conectores. En particular, `S7 / E=100` queda debajo y a
la izquierda del extremo superior derecho. No se observaron cortes ni
solapamientos obvios. Las proyecciones N-dimensionales conservan su semántica y
su título de proyección.

## Protección de alcance

El diff contra la base es vacío para `streamlit_app.py`, `exports/`,
`epsilon_constraint.py` y `multiobjective.py`. No se añadieron métodos,
solvers ni dependencias. Una copia local previa y no versionada del PNG epsilon
se preservó en `stash@{0}` y no se incorporó al cambio.

## Comandos ejecutados

```powershell
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6
.\.venv\Scripts\python.exe scripts\solve_model.py models\hidroelectrica_biobjetivo.json --method weighted --num-weights 6
.\.venv\Scripts\python.exe -m pytest tests\test_epsilon_constraint.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_weighted_method.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_solve_model_cli.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_academic_console_scripts.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_unified_model.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_pareto_plot_cli.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_multiobjective_epsilon.py -q
.\.venv\Scripts\python.exe -m compileall -q src scripts exports tests
.\.venv\Scripts\python.exe -m pytest -q
```
