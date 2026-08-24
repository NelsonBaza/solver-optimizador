# Suite de Optimización Matemática — Prueba de Concepto AMPL + HiGHS

Este repositorio contiene una prueba de concepto (PoC) para evaluar herramientas gratuitas, académicamente gratuitas y/o de código abierto orientadas a la formulación, resolución y análisis de problemas de optimización matemática en Python con fines académicos, docentes y de investigación.

> [!IMPORTANT]
> **La arquitectura definitiva del proyecto todavía NO está decidida.**
> En este momento se está evaluando la viabilidad, ergonomía y desempeño de **AMPL**, **amplpy** y el solver **HiGHS**. Posteriormente se evaluarán alternativas y complementos como **Pyomo**, **IPOPT**, **SCIP**, **pymoo** y métodos multiobjetivo.

---

## Naturaleza y Clasificación de Licencias

Para total rigor conceptual y legal:
* **HiGHS:** Software libre y de código abierto (*open source*, licencia MIT).
* **AMPL:** Software comercial propietario que ofrece modalidades de uso gratuito y académico sujetas a los términos y condiciones de su licencia (AMPL Community Edition / Academic License).
* **amplpy:** Paquete e interfaz oficial en Python para interactuar con el entorno AMPL.

---

## Estado Actual de Validación

### Validado Actualmente:
- ✅ Python `3.13.1` en Windows (entorno aislado `.venv`)
- ✅ `amplpy==0.18.0` y `ampltools==0.7.5`
- ✅ **AMPL Engine** (`ampl-module-base` v20260809)
- ✅ **HiGHS Solver** (`ampl-module-highs` v20260813 / HiGHS 1.15.1)
- ✅ Script de verificación reproducible [`verify_ampl_highs.py`](verify_ampl_highs.py) con aserciones programáticas.

### Todavía NO Validado:
- ❌ Benchmark A (problema biobjetivo)
- ❌ Métodos multiobjetivo (matriz de pagos, puntos ideal/nadir)
- ❌ Método de suma ponderada y normalización
- ❌ Método de $\varepsilon$-restricciones
- ❌ Clasificación y filtrado de soluciones de Pareto (dominancia, no dominancia, repetidas)
- ❌ Integración de `pymoo` y algoritmos evolutivos (NSGA-II)
- ❌ Integración de `IPOPT` y `SCIP`
- ❌ Interfaz gráfica de usuario (Streamlit)
- ❌ Decisión final de arquitectura (AMPL vs. Pyomo vs. APIs directas)

---

## Instalación y Configuración del Entorno Validado

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

### 3. Instalar las dependencias exactas validadas
```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-ampl.txt
```

### 4. Descargar e instalar el módulo solver HiGHS para AMPL
```powershell
& ".\.venv\Scripts\python.exe" -c "from amplpy import modules; modules.install('highs')"
```

> [!NOTE]
> El archivo [`requirements-proposed-full-stack.txt`](requirements-proposed-full-stack.txt) contiene una propuesta preliminar para fases posteriores y **no** debe instalarse en este checkpoint.

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

## Regla Permanente de Trazabilidad para Agentes

> **Regla Obligatoria:** Cada fase, benchmark o cambio arquitectónico relevante desarrollado por un asistente de IA debe generar un informe Markdown exhaustivo dentro de `docs/agent_logs/` antes del commit final correspondiente.
>
> Los nombres deben seguir la convención: `YYYY-MM-DD_<descripcion_tarea>.md`.

Consulte la carpeta [`docs/`](docs/) para acceder al estado técnico detallado ([`STATUS.md`](docs/STATUS.md)), guía de entorno ([`ENVIRONMENT.md`](docs/ENVIRONMENT.md)), registro de decisiones ([`DECISIONS.md`](docs/DECISIONS.md)) y los registros de auditoría de agentes ([`agent_logs/`](docs/agent_logs/)).
