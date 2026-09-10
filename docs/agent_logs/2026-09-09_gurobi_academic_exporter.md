# Registro del agente: exportador académico Gurobi

Fecha: 2026-09-09

Repositorio: `NelsonBaza/solver-optimizador`

Rama: `feat/gurobi-academic-exporter`

SHA base: `ff26875c30e6c63cc05df58c5f4eb5c6b52827e7`

## Alcance ejecutado

Se integró primero `fix/pareto-plot-presentation` en `main` mediante
fast-forward verificado y se envió `main@ff26875` a GitHub. La rama del
exportador se creó después desde ese commit.

Se añadió un generador que carga JSON 1.0 o 1.1 mediante el loader oficial,
construye el problema biobjetivo canónico y escribe un programa Gurobi concreto.
El programa generado no replica el sistema de validación del proyecto: contiene
solo los datos ya validados y la implementación académica necesaria.

## Decisiones

- Alcance deliberadamente biobjetivo, lineal, continuo y no negativo.
- Único método exportado: epsilon-constraint.
- Un modelo Gurobi nuevo por corrida para impedir acumulación de restricciones.
- Dos optimizaciones por ancla: objetivo de la fila y desempate con el otro
  objetivo manteniendo exactamente el óptimo primario.
- Datos canónicos dispersos embebidos como literales Python.
- Configuración visible (`PRIMARY_OBJECTIVE`, `R`, `SHOW_GUROBI_LOG`).
- Matplotlib en backend `Agg` y salida PNG junto al archivo.
- Ningún `setObjectiveN`, peso, normalización ni dependencia Gurobi del proyecto.

## Hallazgos durante pruebas

La primera ejecución de las pruebas nuevas tuvo cinco fallos en código de test:
cuatro lecturas omitían UTF-8 en Windows y una comparación usaba `pytest.approx`
sobre una lista anidada. Se corrigieron las pruebas para leer UTF-8 y comparar
las columnas Z1/Z2 por separado. El exportador y los valores esperados no se
modificaron por esos fallos. La ejecución final del archivo de pruebas fue
`20 passed, 1 skipped`.

## Gurobi disponible

`find_spec("gurobipy")` devolvió `None`. No se instaló ninguna dependencia ni se
buscó una licencia. En consecuencia, no se ejecutó el entregable con Gurobi y
no se atribuyen resultados Gurobi. La regresión numérica se comprobó con el
backend oficial Pyomo + HiGHS sobre la misma representación canónica.

## Resultado verificable

- Archivo: `entregas/hidroelectrica_restricciones_gurobi.py`.
- Tamaño: 20230 bytes.
- Líneas: 518.
- Variables/restricciones: 24/28.
- Configuración: Z1 principal, Z2 restringido, `R=6`.
- Matriz esperada desde el backend oficial: `(6701.25,40)` y
  `(21416.25,100)`.
- Niveles esperados: 40, 50, 60, 70, 80, 90 y 100.
- Siete puntos esperados: los aprobados de la regresión hidroeléctrica.
- AST, `compile`, `py_compile`, portabilidad estructural y reproducibilidad del
  archivo versionado: correctos.
- Suite completa: 346 passed, 0 failed, 1 skipped por ausencia de Gurobi.

## Protección del producto vigente

El diff es vacío para el backend matemático Pyomo/HiGHS, los dos scripts de
`exports/`, Streamlit y `pyproject.toml`. El archivo no versionado
`models/planeacion_agregada_biobjetivo.json`, ajeno a esta tarea, se preservó y
se excluyó de todos los cambios.

## Comandos principales

```powershell
.\.venv\Scripts\python.exe scripts\export_gurobi.py models\hidroelectrica_biobjetivo.json --method epsilon --primary 1 --r 6 --output entregas\hidroelectrica_restricciones_gurobi.py
.\.venv\Scripts\python.exe -m py_compile entregas\hidroelectrica_restricciones_gurobi.py
.\.venv\Scripts\python.exe -m pytest tests\test_gurobi_exporter.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_epsilon_constraint.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_multiobjective_epsilon.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_solve_model_cli.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_pareto_plot_cli.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_academic_console_scripts.py -q
.\.venv\Scripts\python.exe -m compileall -q src scripts exports tests entregas
.\.venv\Scripts\python.exe -m pytest -q
```
