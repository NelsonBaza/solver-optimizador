# Registro del agente: consola, JSON unificado y gráficos de Pareto

Fecha: 2026-09-09

Repositorio: `NelsonBaza/solver-optimizador`

Rama: `feat/console-usability-unified-models`

Base: `c7b45aff04557338cf4534189066501e219b545b`

## Alcance ejecutado

1. Se leyó `AGENTS.md` antes de modificar el repositorio.
2. Se comprobó que `feat/academic-console-scripts` estaba un commit adelante y
   cero detrás de `main`.
3. Se validaron 254 pruebas antes de integrar.
4. Al no existir una herramienta de PR utilizable, se realizó el fast-forward
   autorizado, se actualizó `main` y se repitieron compilación y 254 pruebas.
5. Se creó esta rama desde el `main` integrado.
6. Se añadió el compilador del esquema JSON 1.1, conservando la carga 1.0.
7. Se amplió el parser seguro existente para índices 1D y 2D.
8. Se añadió la generación headless del gráfico de Pareto al runner oficial.
9. Se añadieron ejemplos 1D, 2D, documentación de usuario, pruebas y evidencia.

## Decisiones técnicas

- `deserialize_model()` es el punto único de entrada para 1.0 y 1.1.
- El esquema 1.1 se compila al estado explícito que ya recibe
  `problem_builder`; no se introdujo un segundo runner.
- La sintaxis indexada se procesa mediante `ast`, sin `eval()` ni `exec()`.
- El alcance dimensional es deliberadamente 1D/2D.
- Los parámetros indexados deben estar completos; no se rellenan faltantes de
  forma silenciosa.
- La representación canónica elimina coeficientes cero y conserva procedencia.
- Matplotlib usa `Agg`; el gráfico se guarda por defecto y `--no-plot` lo
  desactiva.
- Las etiquetas usan desplazamientos deterministas y los puntos no dominados
  se distinguen y conectan ordenados por `(Z1, Z2)`.

## Evidencia observada

- Ejemplo 1D: 40 variables y 40 restricciones generadas.
- Ejemplo 2D mixto: 1 + 6 variables y 2 + 6 restricciones.
- Hidroeléctrica epsilon: siete niveles `40..100` y siete puntos esperados.
- Hidroeléctrica ponderada: seis corridas, cuatro vectores únicos.
- PNG epsilon: `results/hidroelectrica_biobjetivo_epsilon_pareto.png`.
- PNG ponderado: `results/hidroelectrica_biobjetivo_weighted_pareto.png`.
- Suite final: 283 aprobadas, 0 fallidas, un aviso conocido de `.pytest_cache`.

El detalle reproducible se conserva en
`docs/audit_evidence/console_unified_models_pareto_validation.txt`.

## Archivos excluidos deliberadamente

No se modificaron funcionalmente los dos scripts de `exports/`, Streamlit ni
las formulaciones matemáticas de epsilon, ponderaciones o el solver LP.
