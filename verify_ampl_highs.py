"""
Script de verificación independiente para AMPL + amplpy + HiGHS en Python.

Este script valida:
1. Importación e inicialización de amplpy y sus módulos en el entorno virtual.
2. Detección y configuración del solver gratuito HiGHS.
3. Resolución del problema de optimización lineal de prueba:
   MAX Z = 3*x + 2*y
   s.a.
       x + y <= 4
       x <= 2
       y <= 3
       x >= 0, y >= 0
4. Verificación programática de la solución óptima (x=2.0, y=2.0, Z=10.0).
"""

import sys
import os
from typing import Tuple, Dict, Any


def run_verification() -> Dict[str, Any]:
    print("=" * 65)
    print("VERIFICACIÓN DE ENTORNO: AMPL + amplpy + HiGHS")
    print("=" * 65)

    # 1. Información del intérprete
    print(f"Intérprete Python: {sys.executable}")
    print(f"Versión de Python: {sys.version}")

    # 2. Carga de amplpy y módulos
    try:
        import amplpy
        from amplpy import AMPL, modules
    except ImportError as exc:
        print(f"[ERROR] No se pudo importar amplpy: {exc}")
        sys.exit(1)

    print(f"Versión de amplpy: {amplpy.__version__}")

    # Cargar rutas de binarios de módulos AMPL instalados
    modules.load()
    installed_mods = modules.installed()
    print(f"Módulos AMPL cargados: {installed_mods}")

    if "highs" not in installed_mods:
        print("[ERROR] El módulo 'highs' no está instalado en amplpy.modules.")
        sys.exit(1)

    # 3. Inicialización de la sesión AMPL
    ampl = AMPL()
    try:
        ampl_ver = str(ampl.get_value("_version"))
        print(f"Versión de AMPL Engine: {ampl_ver}")

        # 4. Configurar HiGHS como solver
        ampl.option["solver"] = "highs"
        selected_solver = ampl.option["solver"]
        print(f"Solver configurado: {selected_solver}")

        # 5. Declarar modelo de prueba
        model_ampl = """
        reset;
        var x >= 0, <= 2;
        var y >= 0, <= 3;
        maximize Z: 3*x + 2*y;
        s.t. c1: x + y <= 4;
        """
        ampl.eval(model_ampl)

        # 6. Resolver problema
        print("\nEjecutando optimización con HiGHS...")
        ampl.solve()

        # 7. Recuperar y verificar resultados programáticamente
        solve_result = str(ampl.get_value("solve_result"))
        solve_result_num = int(ampl.get_value("solve_result_num"))
        x_val = float(ampl.get_variable("x").value())
        y_val = float(ampl.get_variable("y").value())
        z_val = float(ampl.get_objective("Z").value())

        print("-" * 65)
        print("RESULTADOS PROGRAMÁTICOS:")
        print(f"  Estado del solver (solve_result)     : {solve_result}")
        print(f"  Código numérico (solve_result_num)   : {solve_result_num}")
        print(f"  Valor de x                           : {x_val:.4f}")
        print(f"  Valor de y                           : {y_val:.4f}")
        print(f"  Valor de Función Objetivo Z          : {z_val:.4f}")
        print("-" * 65)

        # Validaciones de aserción matemática
        assert solve_result == "solved", f"Estado no óptimo: {solve_result}"
        assert solve_result_num == 0, f"Código de solver inesperado: {solve_result_num}"
        assert abs(x_val - 2.0) < 1e-6, f"x esperado 2.0, obtenido {x_val}"
        assert abs(y_val - 2.0) < 1e-6, f"y esperado 2.0, obtenido {y_val}"
        assert abs(z_val - 10.0) < 1e-6, f"Z esperado 10.0, obtenido {z_val}"

        print("[ÉXITO] Todas las aserciones matemáticas y programáticas pasaron correctamente.")
        print("=" * 65)

        return {
            "python_version": sys.version,
            "amplpy_version": amplpy.__version__,
            "ampl_version": ampl_ver,
            "solver": "HiGHS",
            "solve_result": solve_result,
            "x": x_val,
            "y": y_val,
            "Z": z_val,
        }

    finally:
        ampl.close()


if __name__ == "__main__":
    run_verification()
