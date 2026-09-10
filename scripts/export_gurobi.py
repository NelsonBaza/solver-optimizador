"""Genera un entregable académico Gurobi autocontenido para epsilon-constraint."""

from __future__ import annotations

import argparse
from pathlib import Path
from pprint import pformat
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from solver_optimizador import (  # noqa: E402
    build_biobjective_problem_from_state,
    deserialize_model,
)


GENERATED_TEMPLATE = r'''"""
Problema: __PROBLEM_NAME_DOC__
Método: Método de las restricciones (epsilon-constraint)
Solver: Gurobi

Archivo académico autocontenido generado desde el modelo canónico del proyecto.
No necesita el JSON original ni utiliza Pyomo, HiGHS o solver_optimizador.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

import gurobipy as gp
from gurobipy import GRB
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ==================================================
# 1. CONFIGURACIÓN
# ==================================================

PRIMARY_OBJECTIVE = __PRIMARY_OBJECTIVE__
R = __R_VALUE__
TOL = 1e-6
SHOW_GUROBI_LOG = False
PLOT_FILE = Path(__file__).with_name(__PLOT_FILE_NAME__)


# ==================================================
# 2. DATOS DEL PROBLEMA
# ==================================================

PROBLEM_NAME = __PROBLEM_NAME__
PLOT_TITLE = __PLOT_TITLE__
VARIABLES = __VARIABLES__
OBJECTIVES = __OBJECTIVES__
CONSTRAINTS = __CONSTRAINTS__


# ==================================================
# 3. CONSTRUCCIÓN DEL MODELO
# ==================================================

def expresion_lineal(coeficientes, variables):
    """Construye una expresión lineal dispersa."""
    return gp.quicksum(
        coeficiente * variables[nombre]
        for nombre, coeficiente in coeficientes.items()
    )


def construir_modelo(nombre="modelo_epsilon"):
    """Construye siempre un modelo limpio con las restricciones originales."""
    modelo = gp.Model(nombre)
    modelo.Params.OutputFlag = 1 if SHOW_GUROBI_LOG else 0
    variables = {
        nombre: modelo.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=nombre)
        for nombre in VARIABLES
    }

    for restriccion in CONSTRAINTS:
        lhs = expresion_lineal(restriccion["coefficients"], variables)
        operador = restriccion["operator"]
        if operador == "<=":
            modelo.addConstr(lhs <= restriccion["rhs"], name=restriccion["name"])
        elif operador == ">=":
            modelo.addConstr(lhs >= restriccion["rhs"], name=restriccion["name"])
        else:
            modelo.addConstr(lhs == restriccion["rhs"], name=restriccion["name"])
    return modelo, variables


# ==================================================
# 4. FUNCIONES OBJETIVO
# ==================================================

def expresion_objetivo(indice, variables):
    return expresion_lineal(OBJECTIVES[indice - 1]["coefficients"], variables)


def sentido_gurobi(indice):
    return (
        GRB.MAXIMIZE
        if OBJECTIVES[indice - 1]["sense"] == "MAX"
        else GRB.MINIMIZE
    )


def evaluar_objetivos(solucion):
    """Evalúa Z1 y Z2 desde exactamente el mismo vector x publicado."""
    return {
        f"Z{indice}": sum(
            coeficiente * solucion.get(nombre, 0.0)
            for nombre, coeficiente in objetivo["coefficients"].items()
        )
        for indice, objetivo in enumerate(OBJECTIVES, start=1)
    }


def nombre_estado(codigo):
    estados = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
    }
    return estados.get(codigo, f"STATUS_{codigo}")


def extraer_solucion(modelo, variables):
    if modelo.Status != GRB.OPTIMAL:
        return None
    return {nombre: float(variables[nombre].X) for nombre in VARIABLES}


# ==================================================
# 5. MATRIZ DE PAGOS
# ==================================================

def resolver_ancla(indice_primario):
    """Optimiza Zi y desempata con el otro objetivo, fijando Zi exactamente."""
    indice_secundario = 2 if indice_primario == 1 else 1

    modelo, variables = construir_modelo(f"ancla_Z{indice_primario}_primaria")
    objetivo_primario = expresion_objetivo(indice_primario, variables)
    modelo.setObjective(objetivo_primario, sentido_gurobi(indice_primario))
    modelo.optimize()
    estado_primario = nombre_estado(modelo.Status)
    solucion_primaria = extraer_solucion(modelo, variables)
    if solucion_primaria is None:
        modelo.dispose()
        return {"status": estado_primario, "x": None, "Z1": None, "Z2": None}

    valor_primario = evaluar_objetivos(solucion_primaria)[f"Z{indice_primario}"]
    modelo.dispose()

    # Segundo modelo limpio: conserva el óptimo primario y optimiza el restante.
    modelo, variables = construir_modelo(f"ancla_Z{indice_primario}_desempate")
    objetivo_primario = expresion_objetivo(indice_primario, variables)
    modelo.addConstr(
        objetivo_primario == valor_primario,
        name=f"fijar_optimo_Z{indice_primario}",
    )
    modelo.setObjective(
        expresion_objetivo(indice_secundario, variables),
        sentido_gurobi(indice_secundario),
    )
    modelo.optimize()
    solucion = extraer_solucion(modelo, variables)
    if solucion is None:
        # El primer resultado sigue siendo una ancla válida si falla el desempate.
        solucion = solucion_primaria
        estado = estado_primario
    else:
        estado = nombre_estado(modelo.Status)
    modelo.dispose()
    valores = evaluar_objetivos(solucion)
    return {"status": estado, "x": solucion, **valores}


def calcular_matriz_pagos():
    """Cada fila procede de optimizaciones Gurobi reales."""
    matriz = {
        "opt_Z1": resolver_ancla(1),
        "opt_Z2": resolver_ancla(2),
    }
    fallidas = [nombre for nombre, fila in matriz.items() if fila["x"] is None]
    if fallidas:
        raise RuntimeError(
            "No fue posible construir la matriz de pagos: " + ", ".join(fallidas)
        )
    return matriz


# ==================================================
# 6. NIVELES EPSILON
# ==================================================

def generar_niveles_epsilon(z_min, z_max, r):
    """E_t = Z_min + (t/r)(Z_max - Z_min), para t = 0, ..., r."""
    if not isinstance(r, int) or isinstance(r, bool) or r < 1:
        raise ValueError("R debe ser un entero mayor o igual que 1.")
    niveles = [z_min + (t / r) * (z_max - z_min) for t in range(r + 1)]
    niveles[0] = z_min
    niveles[-1] = z_max
    return niveles


# ==================================================
# 7. BARRIDO EPSILON
# ==================================================

def ejecutar_barrido(niveles):
    indice_restringido = 2 if PRIMARY_OBJECTIVE == 1 else 1
    objetivo_restringido = OBJECTIVES[indice_restringido - 1]
    corridas = []

    for t, nivel in enumerate(niveles):
        inicio = time.perf_counter()
        # Se construye un modelo nuevo: ninguna restricción epsilon se acumula.
        modelo, variables = construir_modelo(f"epsilon_t_{t}")
        expresion_restringida = expresion_objetivo(indice_restringido, variables)
        if objetivo_restringido["sense"] == "MAX":
            modelo.addConstr(
                expresion_restringida >= nivel,
                name=f"epsilon_Z{indice_restringido}_t_{t}",
            )
            operador = ">="
        else:
            modelo.addConstr(
                expresion_restringida <= nivel,
                name=f"epsilon_Z{indice_restringido}_t_{t}",
            )
            operador = "<="

        modelo.setObjective(
            expresion_objetivo(PRIMARY_OBJECTIVE, variables),
            sentido_gurobi(PRIMARY_OBJECTIVE),
        )
        modelo.optimize()
        estado = nombre_estado(modelo.Status)
        solucion = extraer_solucion(modelo, variables)
        corrida = {
            "run_index": t,
            "t": t,
            "E": nivel,
            "operator": operador,
            "status": estado,
            "x": solucion,
            "Z1": None,
            "Z2": None,
            "execution_time_sec": time.perf_counter() - inicio,
        }
        if solucion is not None:
            corrida.update(evaluar_objetivos(solucion))
        corridas.append(corrida)
        modelo.dispose()
    return corridas


# ==================================================
# 8. RESULTADOS Y PARETO
# ==================================================

def soluciones_unicas(corridas):
    unicas = []
    for corrida in corridas:
        if corrida["status"] != "OPTIMAL" or corrida["x"] is None:
            continue
        repetida = None
        for solucion in unicas:
            mismo_x = all(
                abs(corrida["x"][nombre] - solucion["x"][nombre]) <= TOL
                for nombre in VARIABLES
            )
            mismos_objetivos = (
                abs(corrida["Z1"] - solucion["Z1"]) <= TOL
                and abs(corrida["Z2"] - solucion["Z2"]) <= TOL
            )
            if mismo_x and mismos_objetivos:
                repetida = solucion
                break
        if repetida is not None:
            repetida["run_indices"].append(corrida["run_index"])
            repetida["epsilon_levels"].append(corrida["E"])
            continue
        unicas.append(
            {
                "id": f"S{len(unicas) + 1}",
                "x": dict(corrida["x"]),
                "Z1": corrida["Z1"],
                "Z2": corrida["Z2"],
                "run_indices": [corrida["run_index"]],
                "epsilon_levels": [corrida["E"]],
                "pareto_status": "No evaluada",
            }
        )
    return unicas


def no_peor(candidato, referencia, sentido):
    if sentido == "MAX":
        return candidato >= referencia - TOL
    return candidato <= referencia + TOL


def estrictamente_mejor(candidato, referencia, sentido):
    if sentido == "MAX":
        return candidato > referencia + TOL
    return candidato < referencia - TOL


def clasificar_pareto(unicas):
    for solucion in unicas:
        solucion["pareto_status"] = "No dominada"
        for candidata in unicas:
            if candidata is solucion:
                continue
            no_peor_z1 = no_peor(
                candidata["Z1"], solucion["Z1"], OBJECTIVES[0]["sense"]
            )
            no_peor_z2 = no_peor(
                candidata["Z2"], solucion["Z2"], OBJECTIVES[1]["sense"]
            )
            mejor_z1 = estrictamente_mejor(
                candidata["Z1"], solucion["Z1"], OBJECTIVES[0]["sense"]
            )
            mejor_z2 = estrictamente_mejor(
                candidata["Z2"], solucion["Z2"], OBJECTIVES[1]["sense"]
            )
            if no_peor_z1 and no_peor_z2 and (mejor_z1 or mejor_z2):
                solucion["pareto_status"] = f"Dominada por {candidata['id']}"
                break
    return unicas


def numero(valor):
    if valor is None:
        return "-"
    return f"{valor:.10g}"


def imprimir_resultados(matriz, indice_restringido, z_min, z_max, niveles, corridas, unicas):
    print("\nMatriz de pagos")
    print("  ancla       Z1             Z2")
    for nombre, fila in matriz.items():
        print(f"  {nombre:<10} {fila['Z1']:>14.6f} {fila['Z2']:>14.6f}")

    print(f"\nZ{indice_restringido}_min = {numero(z_min)}")
    print(f"Z{indice_restringido}_max = {numero(z_max)}")
    print(f"r = {R}")
    print("Fórmula: E_t = Z_min + (t/r)(Z_max - Z_min)")
    print("Niveles E = [" + ", ".join(numero(valor) for valor in niveles) + "]")

    print("\nCorridas epsilon")
    print("  t | E            | operador | estado       | Z1             | Z2")
    for corrida in corridas:
        print(
            f"  {corrida['t']:>1} | {numero(corrida['E']):<12} | "
            f"{corrida['operator']:^8} | {corrida['status']:<12} | "
            f"{numero(corrida['Z1']):>14} | {numero(corrida['Z2']):>14}"
        )
        if corrida["x"] is not None:
            print("    Variables:")
            for nombre in VARIABLES:
                print(f"      {nombre:<16} = {numero(corrida['x'][nombre])}")

    print(f"\nSoluciones únicas: {len(unicas)}")
    for solucion in unicas:
        print(
            f"  {solucion['id']}: Z1={numero(solucion['Z1'])}; "
            f"Z2={numero(solucion['Z2'])}; {solucion['pareto_status']}"
        )

    no_dominadas = [s for s in unicas if s["pareto_status"] == "No dominada"]
    print("\nSoluciones no dominadas obtenidas por el barrido:")
    for solucion in no_dominadas:
        print(f"  {solucion['id']}: ({numero(solucion['Z1'])}, {numero(solucion['Z2'])})")


# ==================================================
# 9. GRÁFICO
# ==================================================

def disposicion_etiquetas(puntos):
    if not puntos:
        return []
    xs = [punto["Z1"] for punto in puntos]
    ys = [punto["Z2"] for punto in puntos]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_rango = x_max - x_min
    y_rango = y_max - y_min
    posiciones = []
    for indice, punto in enumerate(puntos):
        x_ratio = 0.5 if x_rango == 0 else (punto["Z1"] - x_min) / x_rango
        y_ratio = 0.5 if y_rango == 0 else (punto["Z2"] - y_min) / y_rango
        dx = 10 if x_ratio <= 0.2 else -10 if x_ratio >= 0.8 else (10 if indice % 2 == 0 else -10)
        dy = 12 if y_ratio <= 0.2 else -12 if y_ratio >= 0.8 else (12 if indice % 4 < 2 else -12)
        posiciones.append((dx, dy))
    return posiciones


def crear_grafico(unicas):
    validas = [solucion for solucion in unicas if solucion["x"] is not None]
    no_dominadas = [
        solucion for solucion in validas if solucion["pareto_status"] == "No dominada"
    ]
    dominadas = [
        solucion for solucion in validas if solucion["pareto_status"] != "No dominada"
    ]
    figura, eje = plt.subplots(figsize=(10, 6.5))
    if dominadas:
        eje.scatter(
            [s["Z1"] for s in dominadas],
            [s["Z2"] for s in dominadas],
            color="#7f8c8d", marker="x", s=60,
            label="Soluciones dominadas obtenidas", zorder=3,
        )
    if no_dominadas:
        ordenadas = sorted(no_dominadas, key=lambda solucion: solucion["Z1"])
        eje.plot(
            [s["Z1"] for s in ordenadas],
            [s["Z2"] for s in ordenadas],
            color="#4f97c9", linewidth=1.5, zorder=2,
        )
        eje.scatter(
            [s["Z1"] for s in no_dominadas],
            [s["Z2"] for s in no_dominadas],
            color="#d62728", edgecolor="white", linewidth=0.8, s=72,
            label="Soluciones no dominadas obtenidas", zorder=4,
        )

    for solucion, (dx, dy) in zip(validas, disposicion_etiquetas(validas)):
        niveles = ",".join(numero(valor) for valor in solucion["epsilon_levels"])
        eje.annotate(
            f"{solucion['id']}\nE={niveles}",
            xy=(solucion["Z1"], solucion["Z2"]),
            xytext=(dx, dy), textcoords="offset points", fontsize=8,
            ha="left" if dx > 0 else "right",
            va="bottom" if dy > 0 else "top",
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "#bbbbbb", "alpha": 0.9},
            arrowprops={"arrowstyle": "-", "color": "#999999", "lw": 0.6},
            zorder=5,
        )

    sentido_z1 = OBJECTIVES[0]["sense"]
    sentido_z2 = OBJECTIVES[1]["sense"]
    eje.set_title(
        f"Frontera de Pareto — {PLOT_TITLE}\n"
        f"Método de las restricciones | Z1 {sentido_z1} · Z2 {sentido_z2}"
    )
    eje.set_xlabel(f"Z1 — {OBJECTIVES[0]['name']} ({sentido_z1})")
    eje.set_ylabel(f"Z2 — {OBJECTIVES[1]['name']} ({sentido_z2})")
    eje.margins(x=0.06, y=0.1)
    eje.grid(True, linestyle="--", linewidth=0.6, alpha=0.45)
    if validas:
        eje.legend(loc="best")
    figura.tight_layout()
    figura.savefig(PLOT_FILE, format="png", dpi=160, bbox_inches="tight", pad_inches=0.2)
    plt.close(figura)
    print(f"\nGráfico guardado en: {PLOT_FILE}")


def main():
    if PRIMARY_OBJECTIVE not in (1, 2):
        raise ValueError("PRIMARY_OBJECTIVE debe ser 1 o 2.")
    version = ".".join(str(parte) for parte in gp.gurobi.version())
    indice_restringido = 2 if PRIMARY_OBJECTIVE == 1 else 1
    print("=" * 72)
    print("MÉTODO DE LAS RESTRICCIONES — GUROBI")
    print("=" * 72)
    print(f"Gurobi version: {version}")
    print(f"Problema: {PROBLEM_NAME}")
    print("Método: epsilon-constraint")
    print(f"Objetivo principal: Z{PRIMARY_OBJECTIVE} ({OBJECTIVES[PRIMARY_OBJECTIVE - 1]['sense']})")
    print(f"Objetivo restringido: Z{indice_restringido} ({OBJECTIVES[indice_restringido - 1]['sense']})")
    print(f"Configuración: PRIMARY_OBJECTIVE={PRIMARY_OBJECTIVE}; R={R}")

    matriz = calcular_matriz_pagos()
    valores_restringidos = [fila[f"Z{indice_restringido}"] for fila in matriz.values()]
    z_min = min(valores_restringidos)
    z_max = max(valores_restringidos)
    niveles = generar_niveles_epsilon(z_min, z_max, R)
    corridas = ejecutar_barrido(niveles)
    unicas = clasificar_pareto(soluciones_unicas(corridas))
    imprimir_resultados(
        matriz, indice_restringido, z_min, z_max, niveles, corridas, unicas
    )
    crear_grafico(unicas)


if __name__ == "__main__":
    main()
'''


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("debe ser un entero") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("debe ser mayor o igual que 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exporta un modelo biobjetivo JSON como un programa académico "
            "Gurobi autocontenido del método epsilon-constraint."
        )
    )
    parser.add_argument("model_file", type=Path, help="modelo JSON 1.0 o 1.1")
    parser.add_argument(
        "--method",
        choices=("epsilon",),
        default="epsilon",
        help="método exportado (único valor vigente: epsilon)",
    )
    parser.add_argument(
        "--primary",
        choices=(1, 2),
        type=int,
        default=1,
        help="objetivo principal: 1 o 2 (predeterminado: 1)",
    )
    parser.add_argument(
        "--r",
        type=_positive_integer,
        default=6,
        help="número de intervalos epsilon (predeterminado: 6)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="archivo .py de salida; de forma predeterminada se crea junto al JSON",
    )
    return parser


def _sparse(coefficients: dict[str, float]) -> dict[str, float]:
    return {
        name: float(value)
        for name, value in coefficients.items()
        if float(value) != 0.0
    }


def _format_records(records: list[dict[str, Any]]) -> str:
    """Mantiene un registro por línea para que los datos embebidos sean legibles."""

    if not records:
        return "[]"
    return "[\n" + ",\n".join(f"    {record!r}" for record in records) + "\n]"


def load_canonical_biobjective(model_file: Path) -> dict[str, Any]:
    """Carga 1.0/1.1 y deriva datos del mismo problema canónico del solver."""

    loaded = deserialize_model(model_file.read_text(encoding="utf-8"))
    objectives = loaded.get("objectives")
    if loaded.get("problem_type") != "Biobjetivo" or not isinstance(objectives, list):
        raise ValueError(
            "El exportador académico Gurobi admite problemas Biobjetivo."
        )
    if len(objectives) != 2:
        raise ValueError("El exportador requiere exactamente dos objetivos.")

    problem = build_biobjective_problem_from_state(
        var_names=loaded["var_names"],
        obj1_sense=objectives[0]["sense"],
        obj1_coeffs=objectives[0]["coefficients"],
        obj2_sense=objectives[1]["sense"],
        obj2_coeffs=objectives[1]["coefficients"],
        canonical_constraints=loaded["constraints_data"],
        obj1_name=objectives[0]["name"],
        obj2_name=objectives[1]["name"],
    )
    problem.validate()
    return {
        "problem_name": loaded["metadata"]["name"],
        "plot_title": loaded["metadata"].get("plot_title")
        or loaded["metadata"]["name"],
        "variables": list(problem.variables),
        "objectives": [
            {
                "id": f"Z{index}",
                "name": objective.name,
                "sense": "MAX" if objective.sense.value == "max" else "MIN",
                "coefficients": _sparse(objective.coefficients),
            }
            for index, objective in enumerate(
                (problem.objective1, problem.objective2), start=1
            )
        ],
        "constraints": [
            {
                "name": constraint.name,
                "coefficients": _sparse(constraint.coefficients),
                "operator": constraint.operator.value,
                "rhs": float(constraint.rhs),
            }
            for constraint in problem.constraints
        ],
    }


def render_gurobi_script(
    canonical: dict[str, Any],
    primary: int,
    r: int,
    output_name: str,
) -> str:
    """Renderiza código Python determinista y comprueba su sintaxis."""

    replacements = {
        "__PROBLEM_NAME_DOC__": canonical["problem_name"],
        "__PRIMARY_OBJECTIVE__": str(primary),
        "__R_VALUE__": str(r),
        "__PLOT_FILE_NAME__": repr(Path(output_name).stem + "_pareto.png"),
        "__PROBLEM_NAME__": repr(canonical["problem_name"]),
        "__PLOT_TITLE__": repr(canonical["plot_title"]),
        "__VARIABLES__": pformat(
            canonical["variables"], width=96, compact=True, sort_dicts=False
        ),
        "__OBJECTIVES__": _format_records(canonical["objectives"]),
        "__CONSTRAINTS__": _format_records(canonical["constraints"]),
    }
    source = GENERATED_TEMPLATE
    for marker, value in replacements.items():
        source = source.replace(marker, value)
    compile(source, output_name, "exec")
    return source


def export_gurobi_script(
    model_file: Path,
    output_file: Path,
    primary: int = 1,
    r: int = 6,
) -> Path:
    if primary not in (1, 2):
        raise ValueError("primary debe ser 1 o 2.")
    if isinstance(r, bool) or not isinstance(r, int) or r < 1:
        raise ValueError("r debe ser un entero mayor o igual que 1.")
    if output_file.suffix.lower() != ".py":
        raise ValueError("El archivo de salida debe tener extensión .py.")
    canonical = load_canonical_biobjective(model_file)
    source = render_gurobi_script(canonical, primary, r, output_file.name)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(source, encoding="utf-8", newline="\n")
    return output_file


def main() -> int:
    args = build_parser().parse_args()
    output = args.output or args.model_file.with_name(
        f"{args.model_file.stem}_restricciones_gurobi.py"
    )
    try:
        generated = export_gurobi_script(
            args.model_file,
            output,
            primary=args.primary,
            r=args.r,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("Exportación Gurobi académica completada.")
    print(f"Archivo: {generated}")
    print("El archivo generado no necesita el JSON original.")
    print("Dependencias de ejecución: gurobipy y matplotlib.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
