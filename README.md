# Suite de Optimización Matemática — Prueba de Concepto AMPL + HiGHS

Este repositorio contiene una prueba de concepto (PoC) para evaluar herramientas gratuitas y de código abierto orientadas a la formulación, resolución y análisis de problemas de optimización matemática en Python con fines académicos, docentes y de investigación.

> [!IMPORTANT]
> **La arquitectura definitiva del proyecto todavía NO está decidida.**
> En esta fase se está evaluando la viabilidad, ergonomía y rendimiento de **AMPL**, **amplpy** y el solver gratuito **HiGHS**. Posteriormente se evaluarán alternativas y complementos como **Pyomo**, **IPOPT**, **SCIP**, **pymoo** y métodos multiobjetivo.

---

## Estado Actual

Actualmente se encuentra verificado y validado un entorno reproducible mínimo en Python 3.13 sobre Windows que integra:
- **`amplpy`** como interfaz de conexión en Python.
- **AMPL Engine** (`ampl-module-base`).
- **HiGHS Solver** (`ampl-module-highs`) para optimización lineal continua (LP) y entera mixta (MILP).

El modelo de verificación resuelve de forma determinista y programática el problema de prueba lineal estándar.

---

## Instalación y Configuración del Entorno

El entorno virtual `.venv` **no está versionado** en el repositorio para mantener la higiene y portabilidad del código. Para reproducir el entorno desde cero:

### 1. Clonar el repositorio
```powershell
git clone https://github.com/NelsonBaza/solver-optimizador.git
cd solver-optimizador
```

### 2. Crear el entorno virtual en Python 3.13
```powershell
python -m venv .venv
```

### 3. Instalar dependencias Python
```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-ampl.txt
```

### 4. Descargar e instalar el módulo solver HiGHS para AMPL
```powershell
& ".\.venv\Scripts\python.exe" -c "from amplpy import modules; modules.install('highs')"
```

---

## Ejecución del Script de Verificación

Ejecutar el script de prueba programática dentro del entorno virtual:

```powershell
& ".\.venv\Scripts\python.exe" verify_ampl_highs.py
```

### Modelo de Prueba Ejecutado:
$$\begin{aligned}
\text{Maximizar } & Z = 3x + 2y \\
\text{s.a. } & x + y \le 4 \\
& x \le 2 \\
& y \le 3 \\
& x \ge 0, \; y \ge 0
\end{aligned}$$

### Resultado Esperado:
- **Estado:** `solved` (`solve_result_num = 0`, *optimal solution found*)
- **Variables:** $x = 2.0$, $y = 2.0$
- **Función Objetivo:** $Z = 10.0$

---

## Limitaciones Actuales y Alcance Pendiente

Aclaraciones explícitas sobre el estado actual del repositorio:
- ❌ **No existe interfaz gráfica** (Streamlit u otra).
- ❌ **No se ha implementado el Benchmark A** (problema biobjetivo).
- ❌ **No se ha implementado la matriz de pagos** ni cálculo de puntos ideal/nadir.
- ❌ **No se ha implementado el método de suma ponderada** ni normalización multiobjetivo.
- ❌ **No se ha implementado el método de $\varepsilon$-restricciones**.
- ❌ **No se ha integrado NSGA-II** ni librerías evolutivas (`pymoo`).
- ❌ **No se ha tomado la decisión final de arquitectura** entre AMPL, Pyomo, APIs directas u otros backends.

---

## Regla Permanente de Trazabilidad para Agentes

> **Regla Obligatoria:** Cada fase, benchmark o cambio arquitectónico relevante desarrollado por un asistente de IA debe generar un informe Markdown exhaustivo dentro de `docs/agent_logs/` antes del commit final correspondiente.
>
> Los nombres deben seguir la convención: `YYYY-MM-DD_<descripcion_tarea>.md`.

Consulte la carpeta [`docs/`](docs/) para acceder al estado técnico detallado ([`STATUS.md`](docs/STATUS.md)), guía de entorno ([`ENVIRONMENT.md`](docs/ENVIRONMENT.md)), registro de decisiones ([`DECISIONS.md`](docs/DECISIONS.md)) y los registros de auditoría de agentes ([`agent_logs/`](docs/agent_logs/)).
