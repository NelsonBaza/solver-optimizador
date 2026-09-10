# Registro del agente — CLI interactivo y epsilon multiobjetivo

**Fecha:** 2026-09-09

**Repositorio:** `NelsonBaza/solver-optimizador`

**Rama:** `feat/interactive-multiobjective-epsilon`

**Base:** `370cd17271632ec4842ea24befa8ea0e6667ff6a`

## Alcance ejecutado

1. Se leyó `AGENTS.md` y la documentación técnica aplicable.
2. Se comprobó la relación lineal entre `main@c7b45af` y
   `feat/console-usability-unified-models@370cd17`.
3. Se validó la rama anterior con 283 pruebas, se integró por fast-forward, se
   subió `main` y se repitieron compilación y 283 pruebas.
4. Se creó esta rama desde `main@370cd17`.
5. Se incorporó el modo interactivo con validación y reintentos, conservando el
   modo avanzado no interactivo.
6. Se añadió una representación interna ordenada para dos o más objetivos y un
   motor epsilon separado para N objetivos.
7. Se amplió JSON 1.1 con `Multiobjetivo` y `objectives`, manteniendo 1.0 y
   `bio_objectives`.
8. Se añadieron proyecciones 2D para N objetivos sin llamarlas frontera
   completa.
9. Se añadieron modelo, pruebas, manual y evidencia reproducible.

## Evidencia observada

- Ejemplo técnico MAX/MAX/MIN: matriz 3×3
  `(8,2,10)`, `(2,8,10)`, `(0,0,0)`.
- `Z1` principal, `r2=4`, `r3=6`: 35 corridas, 14 infactibles registradas,
  20 soluciones únicas y 20 no dominadas obtenidas.
- Prueba TTY real: se escogió `Z2` como principal y se confirmaron 4 corridas.
- Prueba no TTY: falta de `--method` devuelve código 2 sin pedir entrada.
- Hidroeléctrica: niveles `[40,50,60,70,80,90,100]` y los siete pares
  históricos sin cambio.
- Suite final: 322 aprobadas, 0 fallidas; `compileall` con código 0.

Durante la última revisión, una ejecución intermedia detectó que el texto de
ayuda había cambiado de “gráfico PNG” a “gráficos PNG”, rompiendo una aserción
de compatibilidad. Se restauró la frase singular, se mantuvo la referencia a
las proyecciones y se repitieron la prueba afectada y la suite completa.

## Interpretación

La lista genérica de objetivos reduce las variantes internas sin cambiar el
contrato histórico. El motor nuevo reutiliza `solve_lp`, las restricciones y
la fórmula de niveles validada; no usa pesos. La matriz de pagos usa una
optimización real por ancla y desempate lexicográfico determinista, fijando en
cada etapa los valores anteriores.

El crecimiento es multiplicativo: `producto(r_k + 1)`. Se informa antes de
resolver y se advierte sobre más de 500 corridas sin imponer un límite duro.

## Conclusión

El cambio queda aislado al runner, modelo general, epsilon N-dimensional,
loader/builder, proyecciones, documentación, fixtures y pruebas. No se modificó
funcionalmente ponderaciones, epsilon biobjetivo, HiGHS, Streamlit ni los
scripts académicos de `exports/`.

La evidencia completa y los comandos exactos están en
`docs/audit_evidence/interactive_multiobjective_epsilon_validation.txt`.
