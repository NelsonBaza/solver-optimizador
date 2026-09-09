# Ejecutor general de modelos biobjetivo en consola

**Fecha:** 2026-09-09

**Rama:** `feat/console-model-runner-hydroelectric`

**Base:** `c2bc2a60f69ee403370f950bccbbde98c6d87852`

## Evidencia observada

- El esquema JSON 1.0 acepta coeficientes dispersos y `deserialize_model()`
  completa los ceros ausentes al construir el estado canónico.
- El modelo aprobado contiene 24 variables, 28 restricciones, objetivo de costo
  térmico MIN y volumen final MAX.
- El barrido ε con `primary=1` y `r=6` produjo los niveles exactos de 40 a 100
  en incrementos de 10.
- Los siete valores de costo coinciden con la relación
  `Z1=245.25*V4-3108.75` y con los extremos conocidos.
- La ejecución ponderada produjo seis corridas óptimas y conservó los extremos
  validados.
- La suite final aprobó 245 pruebas y no se modificó Streamlit.

La evidencia de comandos y resultados está en
[`../audit_evidence/console_model_runner_validation.txt`](../audit_evidence/console_model_runner_validation.txt).

## Interpretación

El runner puede mantenerse independiente de cualquier modelo concreto: el JSON
se deserializa y el mismo builder que usa el backend transforma sus datos en un
`BiobjectiveProblem`. La selección del método se limita a despachar el problema
construido a las dos funciones públicas ya validadas.

El fixture monoobjetivo histórico no debía modificarse ni utilizarse como nuevo
modelo porque contiene coeficientes cero explícitos y carece de Z2. Se creó un
archivo biobjetivo separado con la misma formulación aprobada y almacenamiento
estrictamente disperso.

## Conclusión

El ejecutor carga y resuelve modelos biobjetivo del esquema vigente desde
consola con ε-constraint o ponderaciones. La validación hidroeléctrica reproduce
la frontera conocida sin agregar restricciones ni supuestos.

## Cambios implementados

- Runner general `scripts/solve_model.py` con argumentos validados y salida
  completa.
- Modelo hidroeléctrico biobjetivo disperso en `models/`.
- Pruebas estructurales, matemáticas, de regresión y subprocess para ambos
  métodos.
- Documentación de uso y evidencia reproducible.
- Actualización mínima del README; `streamlit_app.py` permanece intacto.
