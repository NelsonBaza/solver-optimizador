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
