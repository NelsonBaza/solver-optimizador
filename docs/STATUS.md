# Estado Técnico del Proyecto (Snapshot)

* **Fecha de corte:** 2026-08-23
* **Sistema Operativo:** Windows 11 / Windows Server (64-bit, `x86_64`)
* **Python (Global):** `3.13.1` (MSC v.1942 64-bit AMD64)
* **Python (.venv):** `3.13.1` (`E:\AI\solver-optimizador\.venv\Scripts\python.exe`)
* **Gestor de paquetes (pip en .venv):** `24.3.1`
* **amplpy:** `0.18.0` (fijado en `requirements-ampl.txt`)
* **ampltools:** `0.7.5` (fijado en `requirements-ampl.txt`)
* **AMPL Engine (`ampl-module-base`):** `20260809` (módulo binario propietario con modalidad gratuita/académica)
* **HiGHS Solver (`ampl-module-highs`):** `1.15.1` (módulo AMPL `20260813`, solver open source MIT)

---

## 1. Resultado de la Prueba de Verificación

Se ejecutó [`verify_ampl_highs.py`](../verify_ampl_highs.py) con aserciones programáticas estrictas:

```text
Modelo:
  max Z = 3*x + 2*y
  s.a. x + y <= 4, x <= 2, y <= 3, x,y >= 0

Resultados:
  - Estado del solver (solve_result): solved
  - Código numérico (solve_result_num): 0
  - Iteraciones Simplex: 0
  - Variables: x = 2.0000, y = 2.0000
  - Función Objetivo Z: 10.0000
  - Validación de Aserciones: PASSED (100% OK)
```

---

## 2. Inventario de Archivos Principales

| Archivo / Carpeta | Descripción |
| :--- | :--- |
| [`verify_ampl_highs.py`](../verify_ampl_highs.py) | Script de prueba y verificación reproducible con aserciones programáticas. |
| [`requirements-ampl.txt`](../requirements-ampl.txt) | Dependencias fijadas y verificadas del entorno actual (`amplpy==0.18.0`, `ampltools==0.7.5`). |
| [`requirements-proposed-full-stack.txt`](../requirements-proposed-full-stack.txt) | Propuesta preliminar de dependencias para fases futuras (no instalado en este checkpoint). |
| [`pyproject.toml`](../pyproject.toml) | Configuración de empaquetado alineada exclusivamente con el entorno validado. |
| [`.gitignore`](../.gitignore) | Exclusiones de Git (entornos virtuales, temporales de solvers, logs, cachés). |
| [`README.md`](../README.md) | Documento principal con alcance, licencias, instrucciones y limitaciones. |
| [`docs/STATUS.md`](STATUS.md) | Este documento (fotografía técnica actual). |
| [`docs/ENVIRONMENT.md`](ENVIRONMENT.md) | Guía detallada del entorno, instalación y diferencias de componentes. |
| [`docs/DECISIONS.md`](DECISIONS.md) | Registro histórico de decisiones técnicas y arquitectónicas (ADR). |
| [`docs/agent_logs/`](agent_logs/) | Auditoría y trazabilidad de interacciones y reportes del agente de IA. |

---

## 3. Estado de Validación de Componentes

### Componentes Validados en `.venv`:
- [x] Python `3.13.1` (entorno aislado)
- [x] `amplpy==0.18.0`
- [x] `ampltools==0.7.5`
- [x] Módulo AMPL Base (`ampl.exe` 20260809)
- [x] Módulo AMPL HiGHS (`highs.exe` 1.15.1)
- [x] Script de prueba `verify_ampl_highs.py`

### Componentes y Metodologías Todavía NO Validados:
- [ ] Benchmark A (problema biobjetivo)
- [ ] Métodos multiobjetivo (matriz de pagos, puntos ideal y nadir)
- [ ] Método de suma ponderada y normalización
- [ ] Método de $\varepsilon$-restricciones
- [ ] Análisis de dominancia de Pareto
- [ ] IPOPT (ampl-module-ipopt / binarios IDAES / Pyomo ASL)
- [ ] SCIP (PySCIPOpt / ampl-module-scip)
- [ ] Pyomo (backend alternativo)
- [ ] pymoo (algoritmos evolutivos multiobjetivo como NSGA-II)
- [ ] Streamlit (interfaz gráfica interactiva)
- [ ] Decisión final sobre la arquitectura del sistema

---

## 4. Clasificación de Licencias y Advertencias

1. **HiGHS:** Software libre y de código abierto (*open source*, licencia MIT).
2. **AMPL:** Software comercial propietario. Dispone de licencias de evaluación académica y comunitarias (AMPL Community Edition) sujetas a sus términos de servicio.
3. **Módulos AMPL:** La función `modules.load()` debe llamarse antes de instanciar `AMPL()` para registrar los binarios en el `PATH` del proceso.

---

## 5. Próximo Hito Previsto

* **Hito siguiente:** Formulación y resolución del **Benchmark A (Problema Biobjetivo)** para comparar la resolución monoobjetivo individual, construcción de matriz de pagos y puntos ideal/nadir.
