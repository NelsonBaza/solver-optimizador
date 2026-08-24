# Estado Técnico del Proyecto (Snapshot)

* **Fecha de corte:** 2026-08-23
* **Sistema Operativo:** Windows 11 / Windows Server (64-bit, `x86_64`)
* **Python (Global):** `3.13.1` (MSC v.1942 64-bit AMD64)
* **Python (.venv):** `3.13.1` (`E:\AI\solver-optimizador\.venv\Scripts\python.exe`)
* **Gestor de paquetes (pip en .venv):** `24.3.1`
* **amplpy:** `0.18.0`
* **AMPL Engine (`ampl-module-base`):** `20260809`
* **HiGHS Solver (`ampl-module-highs`):** `1.15.1` (módulo AMPL `20260813`)

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
| [`requirements-ampl.txt`](../requirements-ampl.txt) | Dependencias de Python para la prueba de concepto (`amplpy`, `ampltools`). |
| [`requirements.txt`](../requirements.txt) | Referencia del stack científico evaluado para el proyecto global. |
| [`pyproject.toml`](../pyproject.toml) | Configuración de empaquetado del proyecto. |
| [`.gitignore`](../.gitignore) | Exclusiones de Git (entornos virtuales, temporales de solvers, logs, cachés). |
| [`README.md`](../README.md) | Documento principal con alcance, instrucciones y limitaciones. |
| [`docs/STATUS.md`](STATUS.md) | Este documento (fotografía técnica actual). |
| [`docs/ENVIRONMENT.md`](ENVIRONMENT.md) | Guía detallada del entorno, instalación y diferencias de componentes. |
| [`docs/DECISIONS.md`](DECISIONS.md) | Registro histórico de decisiones técnicas y arquitectónicas. |
| [`docs/agent_logs/`](agent_logs/) | Auditoría y trazabilidad de interacciones y reportes del agente de IA. |

---

## 3. Componentes Instalados vs. Pendientes

### Instalados en `.venv`:
- [x] Python `3.13.1` (entorno aislado)
- [x] `amplpy` 0.18.0
- [x] `ampltools` 0.7.5
- [x] Módulo AMPL Base (`ampl.exe` 20260809)
- [x] Módulo AMPL HiGHS (`highs.exe` 1.15.1)

### Pendientes para fases posteriores:
- [ ] IPOPT (ampl-module-ipopt / binarios IDAES / Pyomo ASL)
- [ ] SCIP (PySCIPOpt / ampl-module-scip)
- [ ] Pyomo (como backend comparativo frente a AMPL)
- [ ] pymoo (para algoritmos genéticos multiobjetivo como NSGA-II)
- [ ] Streamlit (interfaz gráfica interactiva)
- [ ] Benchmark A (problema biobjetivo con frontera de Pareto)

---

## 4. Problemas Encontrados y Advertencias

1. **Gestión de Ejecutables de Módulos:** `amplpy.modules` descarga binarios directamente en el directorio del paquete (`site-packages/ampl_module_*`). Es obligatorio llamar a `modules.load()` antes de instanciar `AMPL()` para que las rutas sean accesibles en el `PATH` del proceso.
2. **Compatibilidad Python 3.13:** Los paquetes `amplpy` y los módulos precompilados funcionan correctamente en Python 3.13 sobre Windows (x86_64).
3. **Licencia:** El solver HiGHS es software libre de código abierto. AMPL en modo base/evaluación permite resolver modelos pequeños sin requerir configuración adicional de licencias comerciales.

---

## 5. Próximo Hito / Benchmark Previsto

* **Hito siguiente:** Formulación y resolución del **Benchmark A (Problema Biobjetivo)** para comparar la resolución monoobjetivo individual, construcción de matriz de pagos y puntos ideal/nadir.
