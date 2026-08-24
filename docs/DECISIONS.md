# Registro Histórico de Decisiones Técnicas (ADR)

Este documento registra cronológicamente las decisiones de arquitectura, diseño e ingeniería adoptadas durante la evolución del proyecto.

---

## ADR-001: Aislamiento del Entorno Virtual (.venv)
* **Fecha:** 2026-08-23
* **Contexto:** Se requiere probar herramientas de optimización sin alterar el Python global de la máquina anfitriona ni mezclar dependencias de otros proyectos.
* **Decisión:** Crear y utilizar exclusivamente un entorno virtual `.venv` en la raíz del proyecto.
* **Consecuencias:** Se garantiza reproducibilidad estricta; el entorno `.venv` queda excluido del control de versiones mediante `.gitignore`.

---

## ADR-002: Prueba de Concepto Inicial con AMPL + amplpy + HiGHS
* **Fecha:** 2026-08-23
* **Contexto:** Evaluar la viabilidad de utilizar AMPL y su solver gratuito HiGHS mediante la API de Python `amplpy` en Python 3.13 sobre Windows.
* **Decisión:** Implementar una prueba de concepto mínima y aislada con `amplpy`, `ampl-module-base` y `ampl-module-highs`, postergando la decisión final de arquitectura y evitando la instalación de componentes adicionales hasta validar este stack.
* **Consecuencias:** Se valida el correcto funcionamiento de HiGHS dentro del ecosistema AMPL en Python 3.13 antes de diseñar abstracciones más complejas.

---

## ADR-003: Postergación de Instalación de Solvers Adicionales e Interfaz Gráfica
* **Fecha:** 2026-08-23
* **Contexto:** La instrucción maestra y el plan de desarrollo estipulan que el motor matemático y las pruebas de concepto deben validarse formalmente antes de construir interfaces o integrar librerías pesadas.
* **Decisión:** No instalar ni configurar por el momento IPOPT, SCIP, pymoo, Streamlit, ni frameworks de UI.
* **Consecuencias:** Se mantiene el repositorio limpio, ligero y enfocado en pruebas verificables paso a paso.

---

## ADR-004: Trazabilidad Integral y Registro de Informes de Agentes
* **Fecha:** 2026-08-23
* **Contexto:** Se requiere auditar las acciones, comandos ejecutados y afirmaciones técnicas realizadas por asistentes de inteligencia artificial a lo largo de las distintas fases del desarrollo.
* **Decisión:** Establecer una política obligatoria por la cual cada fase o benchmark relevante genere un informe Markdown en `docs/agent_logs/` antes de cada commit.
* **Consecuencias:** Permite comparar el código real con las afirmaciones del agente y asegura total transparencia y auditabilidad para terceros.

---

## ADR-005: Saneamiento de Checkpoint, Separación de Stack y Rigor en Licencias
* **Fecha:** 2026-08-23
* **Contexto:** La auditoría del primer checkpoint identificó que `requirements.txt` y `pyproject.toml` declaraban dependencias no validadas todavía, las versiones no estaban fijadas exactamente en `requirements-ampl.txt`, y no se distinguía con precisión la naturaleza propietaria de AMPL frente a la licencia libre de HiGHS.
* **Decisión:**
  1. Fijar versiones exactas en `requirements-ampl.txt` (`amplpy==0.18.0`, `ampltools==0.7.5`, `matplotlib==3.11.1`).
  2. Renombrar la propuesta de dependencias completas a `requirements-proposed-full-stack.txt` con encabezado aclaratorio de no instalación en este checkpoint.
  3. Ajustar `pyproject.toml` para reflejar únicamente las dependencias validadas.
  4. Precisar en la documentación que HiGHS es open source (MIT), mientras que AMPL es software propietario con modalidades de uso gratuito/académico.
* **Consecuencias:** El repositorio presenta total coherencia técnica entre archivos de configuración, entorno real y documentación, eliminando ambigüedades antes de abordar el Benchmark A.

---

## ADR-006: Evaluación de AMPL + HiGHS tras Benchmark A Multiobjetivo
* **Fecha:** 2026-08-23
* **Contexto:** Se completó el Benchmark A biobjetivo lineal con suma ponderada normalizada para evaluar la ergonomía de AMPL como backend matemático.
* **Decisión:**
  * AMPL + HiGHS **continúa como candidato válido** para el backend exacto de optimización LP/MILP gracias a su rápida parametrización y capacidad de alternar objetivos (`objective Obj; solve;`).
  * Sin embargo, **NO se adopta todavía como arquitectura definitiva**, dado que toda la lógica de análisis multiobjetivo (matriz de pagos, rangos de normalización, detección de repetidos, filtrado de Pareto y renderizado gráfico) tuvo que programarse en Python.
  * Se requiere contrastar estos resultados con una prueba equivalente en Pyomo o backends de modelado abiertos antes de tomar la decisión de arquitectura definitiva.
* **Consecuencias:** Se mantiene la apertura arquitectónica y se documenta la evidencia experimental del esfuerzo de desarrollo requerido con AMPL.
