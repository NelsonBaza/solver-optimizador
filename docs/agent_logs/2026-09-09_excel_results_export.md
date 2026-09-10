# Registro del agente: exportación Excel de resultados

Fecha: 2026-09-09

Repositorio: `NelsonBaza/solver-optimizador`

Rama: `feat/excel-results-export`

SHA base: `ff26875c30e6c63cc05df58c5f4eb5c6b52827e7`

## Alcance

Se añadió una capa de presentación con `openpyxl` que recibe exclusivamente el
problema y el resultado ya calculado. La CLI guarda por defecto un `.xlsx`
independiente del PNG y permite omitirlo con `--no-excel`.

## Decisiones

- Seis hojas estables para resumen, matriz, corridas, variables, no dominadas y
  restricciones.
- Adaptación centralizada para epsilon biobjetivo, epsilon N-dimensional y
  ponderaciones biobjetivo.
- Ninguna llamada a solver dentro del exportador.
- Ninguna reclasificación Pareto; se consumen `nondominated_solutions` o el
  estado ya asignado por el backend de ponderaciones.
- Restricciones evaluadas con `LinearConstraint.evaluate_lhs()` y
  `calculate_slack()` sobre el mismo `x` publicado.
- Actividad mediante la misma regla estricta `abs(slack) < tol` del solver.
- Números escritos como números; el formato de celda no cambia su valor.
- Errores de gráfico y Excel se reportan de forma independiente después de una
  optimización correcta.

## Hallazgos

La primera prueba de lectura usó incorrectamente `Workbook` como context
manager. Openpyxl había creado correctamente los archivos; se corrigió el
helper para cerrar el libro de manera explícita. Una prueba histórica esperaba
que `--no-plot` no crease el directorio `results`; se actualizó porque ahora ese
modo debe producir Excel y omitir solo el PNG.

El formato XLSX conserva números de Excel. En valores como
`11606.249999999998`, Excel puede reabrir `11606.25` debido a su precisión
numérica estándar; no existe redondeo explícito en producción y las pruebas usan
una tolerancia de serialización apropiada.

## Protección de cambios locales previos

Al iniciar existían PNG locales y archivos de la rama Gurobi fuera de `main`.
No forman parte de esta funcionalidad. Se preservaron sin incorporarlos al
commit de Excel. El JSON de planeación agregada sí quedó dentro del alcance por
instrucción expresa; su contenido no se modificó y su SHA-256 observado es
`C9322DD1679A8716ED6009575EA8DF400DCDF3DBD5EC8A0281CDBCDDB3261C61`.

## Validación

La línea base fue `326 passed, 0 failed`. Las pruebas nuevas cubren los tres
tipos de resultado, MIN/MIN, MAX/MIN, infactibles, precisión, formato y opciones
CLI. Los comandos manuales y tamaños quedan detallados en
`docs/audit_evidence/excel_results_export_validation.txt`.

Validación final: `compileall` correcto y `343 passed, 0 failed`; permanece el
warning conocido de permisos al crear `.pytest_cache`.
