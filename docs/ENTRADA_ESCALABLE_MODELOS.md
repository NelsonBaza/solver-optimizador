# Entrada escalable de modelos lineales

**Vigencia:** Fase 3A

**Backend actual:** Pyomo + APPSI HiGHS

La interfaz de captura no define el modelo matemático. Todos los mecanismos de
entrada siguen el mismo flujo:

```text
entrada -> parser/importador -> validación -> restricciones canónicas dispersas
        -> problem_builder -> Pyomo/APPSI HiGHS
```

`constraint_import.py` no importa Streamlit, Pyomo ni HiGHS. Por ello, la misma
representación podrá alimentar un adaptador Gurobi u otros backends en el futuro.
Gurobi no se necesita para importar matrices y esta fase no afirma que esté
instalado.

## Representación canónica

Cada restricción se almacena como:

```python
{
    "name": "R1",
    "coefficients": {"x1": 2.0, "x500": 5.0},
    "operator": "<=",
    "rhs": 10.0,
}
```

Los coeficientes cero no se guardan. Una matriz de 1.000 restricciones, 100
variables y dos términos por fila contiene 2.000 entradas, no 100.000.

### Restricciones constantes

Una restricción canónica puede no contener términos variables, por ejemplo
`{"coefficients": {}, "operator": "<=", "rhs": 10.0}`. Se conserva como la
restricción matemática `0 <= 10`; no se elimina ni se convierte en un booleano
de Python. Las variantes `0 >= b` y `0 = b` mantienen igualmente su semántica,
incluidos los casos infactibles. Si el modelo es óptimo, la restricción continúa
apareciendo en los resultados con su LHS y holgura correspondientes.

El formato ancho representa formalmente `A x op b`. Por ejemplo:

```text
A = [[2,3,0], [0,1,4], [1,0,-2]]
op = [<=, >=, =]
b = [20,15,7]
```

se transforma en tres restricciones canónicas algebraicamente equivalentes.

## 1. Modo manual

“Manual — recomendado para modelos pequeños” conserva el editor de filas,
incluyendo añadir, editar y eliminar restricciones con `<=`, `>=` o `=`. Los
cambios se aplican como un lote mediante “Aplicar cambios manuales”.

Para evitar matrices inmanejables, la edición celda a celda se deshabilita al
superar 100 restricciones, 100 variables o 2.000 celdas coeficiente. El modelo
completo permanece en `session_state`; solo cambia la forma de editarlo.

## 2. Pegado desde Excel, Sheets, CSV o TSV

Formato ancho:

```csv
name,x1,x2,x3,operator,rhs
R1,2,3,0,<=,20
R2,0,1,4,>=,15
R3,1,0,-2,=,7
```

Se detectan coma, punto y coma o tabulador. La UI separa validar, previsualizar
y aplicar. Previsualizar nunca modifica el modelo y un lote con errores nunca se
aplica parcialmente.

## 3. CSV

Se aceptan `.csv` UTF-8 y UTF-8-SIG, con coma o punto y coma. El usuario puede
indicar punto o coma decimal. El contenido puede ser ancho o disperso; el parser
lo detecta por las cabeceras.

## 4. XLSX

Se aceptan únicamente libros `.xlsx`. Se enumeran las hojas y el usuario elige
una. El lector trata OOXML como datos, no ejecuta macros, vínculos ni fórmulas.
Si una fórmula no contiene valor almacenado, se rechaza con un error explícito.
No se aceptan `.xlsm` ni formatos binarios arbitrarios. Existen límites de 20
MiB comprimidos, 100 MiB descomprimidos y dos millones de celdas.

## 5. Matriz dispersa

Formato long/tripleta:

```csv
constraint,variable,coefficient,operator,rhs
R1,x1,2,<=,20
R1,x7,5,<=,20
R1,x18,-1,<=,20
R2,x4,3,>=,15
R2,x21,7,>=,15
```

Las filas se agrupan por `constraint`. Operador y RHS deben ser consistentes en
todas las tripletas. Un par `(constraint, variable)` duplicado es un error y no
se suma silenciosamente.

## 6. Variables en bloque

La sección de variables admite nombres separados por coma, punto y coma,
tabulador o salto de línea. Se rechazan vacíos, duplicados, nombres reservados y
nombres fuera del patrón `[A-Za-z_][A-Za-z0-9_]*`.

Las importaciones de restricciones detectan variables automáticamente. Antes de
aplicar se elige entre:

1. validar contra las variables actuales;
2. usar las variables detectadas.

La segunda opción conserva coeficientes de objetivos para nombres existentes,
inicializa las variables nuevas en cero, elimina referencias que dejaron de
existir e invalida resultados anteriores.

## 7. Objetivos en bloque

Monoobjetivo:

```csv
variable,coefficient
x1,10
x2,5
x50,-2
```

Biobjetivo:

```csv
variable,Z1,Z2
x1,10,0.8
x2,3,1.3
x50,-2,5
```

Puede pegarse texto o cargar un CSV. La previsualización informa variables
reconocidas, desconocidas, duplicados y valores inválidos. Al aplicar
explícitamente, variables omitidas reciben coeficiente cero.

## 8. Validación y seguridad

Se rechazan `NaN`, `Infinity`, `-Infinity`, números inválidos, operadores fuera
de `<=`, `>=`, `=`, nombres vacíos y duplicados. No se utiliza `eval`, `exec` ni
interpretación de código. Los archivos XLSX nunca se ejecutan.

### Salvaguarda temporal de nombres

Todas las rutas de Fase 3A —bloque, formatos ancho y disperso, editor manual y
JSON— usan una única validación. Se rechazan, sin distinguir mayúsculas, las
colisiones Pyomo conocidas `active`, `component`, `component_map`, `display`,
`index`, `model`, `name`, `obj`, `parent_component` y `pprint`.

Esta lista es una salvaguarda temporal y no se considera exhaustiva. El hallazgo
AUD-HIGH-06 permanece abierto hasta implementar IDs internos seguros separados
de los nombres visibles del usuario.

## 9. Aplicación atómica y trazabilidad

`apply_constraint_import`, `apply_variable_import` y `apply_objective_import`
actualizan el estado solo después de una validación completa. Al aplicar:

- se actualizan variables, objetivos o `constraints_data`;
- se invalida `last_solution` y su firma;
- se incrementa `editor_version`;
- se guardan tipo de fuente, archivo, hoja, formato, fecha y conteos;
- no se guarda el binario XLSX.

El JSON 1.0 existente sigue siendo compatible. Sus restricciones pueden usar
diccionarios dispersos y se expanden únicamente al abrir un editor manual.

## 10. Vista previa y modelo completo

Las vistas muestran como máximo 20 restricciones y permiten filtrar por nombre.
El texto “Vista previa: 20 de N” no implica truncamiento: resolver, exportar y
firmar usan todas las restricciones aplicadas.

El botón “Descargar restricciones CSV” produce formato disperso para permitir
el ciclo importar → editar externamente → volver a importar sin pérdida
matemática.

## Punto de extensión para Fase 3B

`import_constraint_table(headers, rows, ...)` es el límite de integración. Una
futura expansión de conjuntos, parámetros y familias indexadas deberá generar
filas explícitas y entregarlas a ese contrato, obteniendo exactamente las mismas
restricciones canónicas que CSV, XLSX, matriz dispersa o modo manual. Esta fase
no implementa `sets`, `forall`, `prev(t)` ni un AST de expresiones.
