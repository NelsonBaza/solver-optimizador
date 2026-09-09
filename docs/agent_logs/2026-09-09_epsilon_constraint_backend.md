# Implementación backend del método de las restricciones

**Fecha:** 2026-09-09

**Rama:** `feat/metodo-restricciones-console`

**Base:** `1eb065098cf51403e7f9672e2f37a4ef0dffa6c1`

## Evidencia observada

- La línea base contenía 209 pruebas aprobadas.
- La infraestructura vigente ya proporcionaba `BiobjectiveProblem`,
  `LinearObjective`, `LinearConstraint`, `LPProblem`, `solve_lp` y anclas
  lexicográficas para la matriz de pagos.
- El Benchmark A produjo las anclas `(Z1,Z2)=(1000,80)` y `(390,169)`.
- Los dos barridos con `r=5` produjeron 6 corridas óptimas, 6 soluciones únicas
  y 6 soluciones no dominadas cada uno.
- La suite final aprobó 234 pruebas; el único warning corresponde a permisos de
  escritura de `.pytest_cache` y no afecta los resultados.

La transcripción reproducible de comandos y resultados está en
[`../audit_evidence/epsilon_constraint_validation.txt`](../audit_evidence/epsilon_constraint_validation.txt).

## Interpretación

Las anclas existentes son matemáticamente reutilizables como preprocesamiento,
pero no pueden sustituir ninguna corrida del método. La forma menos invasiva de
preservar las ponderaciones fue mantener `multiobjective.py` intacto y construir
un `LPProblem` nuevo por nivel: restricciones originales más una única
restricción ε.

El sentido del objetivo restringido determina exclusivamente el operador
(`>=` para MAX, `<=` para MIN). Los niveles conservan en ambos casos la fórmula
numérica ascendente solicitada.

## Conclusión

La implementación satisface la formulación académica solicitada sin pesos ni
normalización. Conserva las corridas aun cuando sean repetidas o infactibles,
reconstruye ambos objetivos desde el mismo vector publicado y clasifica Pareto
con los sentidos originales.

## Cambios implementados

- Nuevo motor separado `epsilon_constraint.py` y exportaciones públicas.
- Pruebas de fórmula, operadores, preservación del modelo, trazabilidad de
  valores, infactibilidad, repetidos, Pareto, ambos barridos del Benchmark A y
  regresión integral.
- Demostración completa en consola para ambos objetivos principales.
- Especificación matemática y actualización mínima del README.
- Sin modificaciones a Streamlit, `solve_lp` ni el motor de ponderaciones.
