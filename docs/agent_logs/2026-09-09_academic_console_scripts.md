# Registro de agente — scripts académicos portables

## Alcance

Se integraron mediante fast-forward los dos commits previamente validados en
`main` y se creó `feat/academic-console-scripts` desde `main@08f36dd`. La nueva
rama añade dos implementaciones pedagógicas que pueden ejecutarse fuera del
repositorio con solo el script correspondiente y un JSON de esquema 1.0.

## Decisiones

- Se conservaron como únicos métodos las ponderaciones normalizadas y
  epsilon-constraint.
- Cada script contiene su lectura JSON y construcción Pyomo porque debe poder
  entregarse de forma individual; compartir un helper externo rompería el
  requisito `.py + .json`.
- No se usaron clases ni infraestructura de persistencia/UI.
- La matriz de pagos aplica el mismo desempate lexicográfico del backend:
  primero se fija exactamente el óptimo primario y luego se optimiza el otro
  objetivo.
- Los pesos extremos resuelven primero `W` y luego seleccionan un representante
  eficiente sobre la cara `W = W*`, en consonancia con `multiobjective.py`.
- El redondeo se limita a presentación. Z1, Z2, N1, N2 y W se reconstruyen
  desde el mismo vector completo publicado.

## Archivos de producción no modificados

- `streamlit_app.py`
- `src/solver_optimizador/epsilon_constraint.py`
- `src/solver_optimizador/multiobjective.py`
- `src/solver_optimizador/lp_solver.py`
- `models/hidroelectrica_biobjetivo.json`

## Verificación

La evidencia completa, comandos, resultados hidroeléctricos y conteos se
encuentran en
`docs/audit_evidence/academic_console_scripts_validation.txt`.
