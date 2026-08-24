# Normalización Canónica de Restricciones y Corrección de Persistencia

**Fecha:** 24 de agosto de 2026  
**Módulos:** `src/solver_optimizador/model_io.py`, `src/solver_optimizador/__init__.py`, `streamlit_app.py`  
**Pruebas:** `tests/test_model_io.py`, `tests/test_custom_variables.py`

---

## 1. Causa Raíz del Bug

Durante una prueba con el modelo:
$$\max Z = 10x_1 + 15x_2$$
sujeto a:
$$\begin{cases} 5x_1 + 4x_2 \le 15 \\ 3x_1 + x_2 \le 20 \end{cases}$$

El archivo JSON descargado exportó erróneamente las restricciones con ceros:
```json
{
  "name": "Restriccion 1",
  "coefficients": {
    "x1": 0.0,
    "x2": 0.0
  },
  "operator": "<=",
  "rhs": 0.0
}
```

### Origen Técnico:
La tabla editable `st.data_editor` devuelve diccionarios planos con claves en español correspondientes a las columnas de la interfaz:
```python
{
    "Nombre": "Restriccion 1",
    "x1": 5.0,
    "x2": 4.0,
    "Operador": "<=",
    "RHS": 15.0
}
```
Por su parte, `serialize_model()` buscaba exclusivamente la clave anidada `c.get("coefficients", {})` y claves en minúscula (`c.get("name")`, `c.get("operator")`, `c.get("rhs")`). Al no encontrarlas, utilizaba silenciosamente valores por defecto (`0.0`), borrando los coeficientes reales.

---

## 2. Función de Normalización Canónica: `normalize_constraints`

Se creó la función `normalize_constraints(raw_constraints, var_names)` en `src/solver_optimizador/model_io.py`, la cual actúa como única fuente de verdad y puente entre la UI y el núcleo matemático.

### Formatos Soportados:
1. **Formato Plano de UI:**
   ```python
   {"Nombre": "R1", "x1": 5.0, "x2": 4.0, "Operador": "<=", "RHS": 15.0}
   ```
2. **Formato Canónico Anidado:**
   ```python
   {"name": "R1", "coefficients": {"x1": 5.0, "x2": 4.0}, "operator": "<=", "rhs": 15.0}
   ```

### Salida Garantizada (Estructura Canónica Única):
```python
{
    "name": "R1",
    "coefficients": {
        "x1": 5.0,
        "x2": 4.0
    },
    "operator": "<=",
    "rhs": 15.0
}
```

### Comportamiento ante Formatos Inválidos:
* Se eliminó el uso de ceros por defecto silenciosos ante claves faltantes.
* Si falta el operador o el lado derecho (RHS), o si el operador no es válido (`<=`, `>=`, `=`), lanza `ValueError` explícito bloqueando la resolución y la descarga.

---

## 3. Unificación en el Flujo de la Aplicación

La estructura canónica normalizada se emplea uniformemente en todos los procesos:
```
st.data_editor (UI)
       ↓
normalize_constraints(raw_ui_records, var_names)
       ↓
canonical_constraints
  ├── Resolución: LinearConstraint(name, coeffs, op, rhs)
  ├── Firma Matemática: build_model_signature(..., constraints_data=canonical_constraints)
  └── Exportación JSON: serialize_model(curr_export_dict)
```

---

## 4. Filtrado de Filas Dinámicas Vacías y Validación

Para soportar tablas con `num_rows="dynamic"` en `st.data_editor`:
* Se implementó `is_empty_constraint_row(row, var_names)` que distingue filas completamente vacías (`None`, `NaN`, cadenas vacías) de filas parcialmente diligenciadas o con ceros válidos.
* Las filas totalmente vacías son ignoradas automáticamente por `normalize_constraints`, permitiendo al usuario ver la fila de inserción sin bloquear los botones **Resolver** y **Descargar**.
* Las filas incompletas generan errores descriptivos (ej. `La restricción 'R3' no especifica un operador`).
* La interfaz muestra un aviso visible si existen errores de validación.

---

## 5. Validación y Pruebas Automatizadas

1. **Caso Exacto $\max 10x_1 + 15x_2$ (`test_exact_bug_case_10x1_15x2_preservation`):**
   * Coeficientes y RHS preservados fielmente en el JSON crudo.
   * Round-trip completo con coincidencia exacta de $Z^*$ y firma matemática.
2. **Nombres Personalizados (`test_custom_variable_names_ui_format_normalization`):**
   * Normalización de registros planos con variables como `T1, GT1`.
3. **Caso Hidroeléctrico 24 Variables (`test_hydroelectric_full_24_vars_model`):**
   * 24 variables y 28 restricciones en formato plano de UI exportadas y cargadas sin pérdida ($Z^* = 6701.25$).
4. **Filtrado de Fila Vacía (`test_empty_dynamic_constraint_row_filtering` y `test_mono_model_min_15x1_23x2_with_trailing_empty_row`):**
   * Dos restricciones reales + fila vacía dinámica se resuelven y guardan exactamente como 2 restricciones.
5. **Validación de Errores (`test_normalize_constraints_validation_errors` y `test_partially_filled_constraint_row_produces_clear_error`):**
   * Detección y rechazo de restricciones malformadas o incompletas.
