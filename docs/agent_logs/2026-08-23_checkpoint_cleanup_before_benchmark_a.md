# Informe de Agente: Saneamiento Técnico del Checkpoint AMPL + HiGHS

* **Fecha de ejecución:** 2026-08-23
* **ID de Registro:** `2026-08-23_checkpoint_cleanup_before_benchmark_a`
* **Entorno:** Windows 11 / Server x86_64, Python 3.13.1, `.venv` aislado

---

## 1. Solicitud

Corregir los hallazgos de auditoría sobre el checkpoint reproducible AMPL + HiGHS antes de proceder con el Benchmark A:
1. Fijar versiones exactas verificadas en `requirements-ampl.txt`.
2. Separar claramente el stack actualmente validado del stack futuro propuesto (`requirements-proposed-full-stack.txt` y `pyproject.toml`).
3. Corregir y precisar la descripción de licencias (HiGHS como open source MIT, AMPL como software propietario con modalidad gratuita/académica).
4. Asegurar coherencia documental completa entre todos los archivos del repositorio.
5. Re-ejecutar pruebas de verificación y registrar la decisión técnica (ADR-005).

---

## 2. Hallazgos Corregidos

1. **Fijación Estricta de Dependencias:**
   * Se sustituyeron los operadores `>=` en `requirements-ampl.txt` por versiones fijadas exactas: `amplpy==0.18.0` y `ampltools==0.7.5`.
2. **Separación de Stack Actual vs. Futuro:**
   * Se renombró `requirements.txt` a `requirements-proposed-full-stack.txt` y se le agregó un encabezado explícito indicando que es una propuesta para fases posteriores y no debe instalarse en este checkpoint.
   * Se actualizó `pyproject.toml` para declarar únicamente las dependencias validadas (`amplpy==0.18.0`, `ampltools==0.7.5`) y mover las futuras a `[project.optional-dependencies].proposed`.
3. **Precisión Conceptual y Legal de Licencias:**
   * Se corrigió la redacción general en `README.md`, `docs/STATUS.md` y `docs/ENVIRONMENT.md`:
     * HiGHS: Software libre y de código abierto (*open source*, licencia MIT).
     * AMPL: Software comercial propietario con modalidades de uso gratuito y académico sujetas a sus términos de licencia.
     * amplpy: Paquete e interfaz oficial en Python (BSD 3-Clause).
4. **Coherencia Documental Global:**
   * Se actualizaron `README.md`, `docs/STATUS.md`, `docs/ENVIRONMENT.md` y `docs/DECISIONS.md` (ADR-005) reflejando de forma inequívoca qué está validado actualmente y qué queda pendiente para fases posteriores.

---

## 3. Archivos Modificados / Renombrados

* `requirements-ampl.txt` (versiones fijadas exactas).
* `requirements-proposed-full-stack.txt` (creado a partir de `requirements.txt` con encabezado aclaratorio).
* `requirements.txt` (eliminado del control de versiones para evitar ambigüedad).
* `pyproject.toml` (dependencias principales alineadas con el entorno validado).
* `README.md` (licencias precisadas y alcances actualizados).
* `docs/STATUS.md` (inventario y estado de componentes actualizado).
* `docs/ENVIRONMENT.md` (guía de reproducción y licencias actualizada).
* `docs/DECISIONS.md` (incorporación de ADR-005).
* `docs/agent_logs/2026-08-23_checkpoint_cleanup_before_benchmark_a.md` (este registro de auditoría).

---

## 4. Verificación Realizada

Se ejecutó `verify_ampl_highs.py` utilizando el intérprete `.venv\Scripts\python.exe`:

```text
=================================================================
VERIFICACIÓN DE ENTORNO: AMPL + amplpy + HiGHS
=================================================================
Intérprete Python: E:\AI\solver-optimizador\.venv\Scripts\python.exe
Versión de Python: 3.13.1 (tags/v3.13.1:0671451, Dec  3 2024, 19:06:28) [MSC v.1942 64 bit (AMD64)]
Versión de amplpy: 0.18.0
Módulos AMPL cargados: ['base', 'highs']
Versión de AMPL Engine: 20260809
Solver configurado: highs

Ejecutando optimización con HiGHS...
HiGHS 1.15.1:               HiGHS 1.15.1: optimal solution; objective 10
0 simplex iterations
0 barrier iterations
-----------------------------------------------------------------
RESULTADOS PROGRAMÁTICOS:
  Estado del solver (solve_result)     : solved
  Código numérico (solve_result_num)   : 0
  Valor de x                           : 2.0000
  Valor de y                           : 2.0000
  Valor de Función Objetivo Z          : 10.0000
-----------------------------------------------------------------
[ÉXITO] Todas las aserciones matemáticas y programáticas pasaron correctamente.
=================================================================
```

---

## 5. Estado Final

El checkpoint base AMPL + HiGHS queda completamente saneado, documentado, con licencias rigurosamente clasificadas y con versiones fijadas, listo para proceder a la siguiente fase de auditoría o al Benchmark A biobjetivo.

---

## 6. Respuesta Final Emitida al Usuario

```text
1. commit SHA: (Se registrará tras git commit)
2. archivos modificados: requirements-ampl.txt, requirements-proposed-full-stack.txt, requirements.txt (eliminado), pyproject.toml, README.md, docs/STATUS.md, docs/ENVIRONMENT.md, docs/DECISIONS.md, docs/agent_logs/2026-08-23_checkpoint_cleanup_before_benchmark_a.md.
3. resultado de la prueba AMPL + HiGHS: solved (solve_result_num=0), x=2.0, y=2.0, Z=10.0 (aserciones 100% OK).
4. confirmación de que el stack actual y el stack futuro quedaron separados: CONFIRMADO (requirements-ampl.txt contiene únicamente amplpy y ampltools fijados; requirements-proposed-full-stack.txt contiene la propuesta futura con encabezado de no instalación; pyproject.toml alineado).
5. confirmación de que la descripción de licencias fue corregida: CONFIRMADO (HiGHS = open source MIT; AMPL = software propietario con modalidad de uso gratuito/académico; amplpy = interfaz Python BSD 3-Clause).
6. ruta del nuevo informe en docs/agent_logs/: docs/agent_logs/2026-08-23_checkpoint_cleanup_before_benchmark_a.md.
7. cualquier problema pendiente: Ninguno. El checkpoint está completamente saneado y detenido conforme a las instrucciones.
```
