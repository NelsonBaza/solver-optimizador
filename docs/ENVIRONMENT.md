# Guía del Entorno de Ejecución y Reproducibilidad

Este documento detalla la arquitectura de dependencias, la separación de componentes y el procedimiento paso a paso para recrear el entorno de ejecución en Windows.

---

## 1. Clasificación de Componentes

Para garantizar la reproducibilidad y evitar confusiones, los componentes del proyecto se dividen estrictamente en tres categorías:

```text
┌─────────────────────────────────────────────────────────────────┐
│                      SISTEMA OPERATIVO                          │
│  Windows 11 / Windows Server (64-bit AMD64)                     │
│  Python 3.13.1 nativo (C:\Users\...\Python313\python.exe)       │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Crea y aísla
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ENTORNO VIRTUAL (.venv)                       │
│  Intérprete: .venv\Scripts\python.exe                           │
│  Paquetes pip (requirements-ampl.txt):                          │
│    - amplpy (0.18.0)                                            │
│    - ampltools (0.7.5)                                          │
│    - requests, certifi, urllib3, idna, charset-normalizer       │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Gestiona vía amplpy.modules
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MÓDULOS BINARIOS AMPL                       │
│  Descargados en .venv\Lib\site-packages\                        │
│    - ampl-module-base   (bin\ampl.exe, v20260809)               │
│    - ampl-module-highs  (bin\highs.exe, v1.15.1 - 20260813)     │
└─────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> `requirements-ampl.txt` instala el paquete de integración `amplpy` mediante `pip`. Los ejecutables de **AMPL Engine** y **HiGHS** son gestionados como módulos binarios de AMPL y se instalan mediante el comando `amplpy.modules.install('highs')`.

---

## 2. Recreación del Entorno Paso a Paso

### Paso 1: Requisitos Previos
- Disponer de Python 3.13 de 64 bits instalado en el sistema operativo.
- PowerShell o Command Prompt en Windows.

### Paso 2: Creación del Entorno Virtual Aislado
Desde la raíz del proyecto (`E:\AI\solver-optimizador`):
```powershell
python -m venv .venv
```

### Paso 3: Activación en PowerShell (Opcional)
Si la política de ejecución de scripts de PowerShell lo permite:
```powershell
.\.venv\Scripts\Activate.ps1
```
*Alternativamente, se puede invocar directamente el ejecutable del entorno sin necesidad de activación global de shell:*
```powershell
& ".\.venv\Scripts\python.exe" <comando>
```

### Paso 4: Instalación de Dependencias Python
```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-ampl.txt
```

### Paso 5: Instalación de los Módulos Binarios de AMPL
```powershell
& ".\.venv\Scripts\python.exe" -c "from amplpy import modules; modules.install('highs')"
```

---

## 3. Verificación del Entorno

Para comprobar que los binarios están en sus rutas correctas y son detectados por `amplpy`:

```powershell
& ".\.venv\Scripts\python.exe" -c "from amplpy import modules; modules.load(); print('AMPL path:', modules.find('ampl')); print('HiGHS path:', modules.find('highs'))"
```

Salida esperada:
```text
AMPL path: E:\AI\solver-optimizador\.venv\Lib\site-packages\ampl_module_base\bin\ampl.exe
HiGHS path: E:\AI\solver-optimizador\.venv\Lib\site-packages\ampl_module_highs\bin\highs.exe
```

---

## 4. Requisitos de Licencia

* **HiGHS:** Es un solver de código abierto bajo licencia MIT, 100% gratuito tanto en su versión nativa como en el módulo para AMPL.
* **AMPL:** Para problemas académicos pequeños y pruebas de concepto de evaluación no requiere activación de licencia comercial. No se incluyeron credenciales, tokens ni archivos de licencia en el repositorio.
