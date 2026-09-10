"""
Problema: Generación Hidroeléctrica Biobjetivo Corregida - 4 Períodos
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

PRIMARY_OBJECTIVE = 1
R = 6
TOL = 1e-6
SHOW_GUROBI_LOG = False
PLOT_FILE = Path(__file__).with_name('hidroelectrica_restricciones_gurobi_pareto.png')


# ==================================================
# 2. DATOS DEL PROBLEMA
# ==================================================

PROBLEM_NAME = 'Generación Hidroeléctrica Biobjetivo Corregida - 4 Períodos'
PLOT_TITLE = 'Generación hidroeléctrica'
VARIABLES = ['T1', 'T2', 'T3', 'T4', 'V1', 'V2', 'V3', 'V4', 'S1', 'S2', 'S3', 'S4', 'PH1', 'PH2', 'PH3',
 'PH4', 'GH1', 'GH2', 'GH3', 'GH4', 'GT1', 'GT2', 'GT3', 'GT4']
OBJECTIVES = [
    {'id': 'Z1', 'name': 'Costo de generación térmica', 'sense': 'MIN', 'coefficients': {'GT1': 100.0, 'GT2': 100.0, 'GT3': 100.0, 'GT4': 100.0}},
    {'id': 'Z2', 'name': 'Volumen final del embalse V4 (UH)', 'sense': 'MAX', 'coefficients': {'V4': 1.0}}
]
CONSTRAINTS = [
    {'name': 'Balance_H1', 'coefficients': {'V1': 1.0, 'T1': 1.0, 'S1': 1.0}, 'operator': '=', 'rhs': 90.0},
    {'name': 'Balance_H2', 'coefficients': {'V2': 1.0, 'V1': -1.0, 'T2': 1.0, 'S2': 1.0}, 'operator': '=', 'rhs': 20.0},
    {'name': 'Balance_H3', 'coefficients': {'V3': 1.0, 'V2': -1.0, 'T3': 1.0, 'S3': 1.0}, 'operator': '=', 'rhs': 15.0},
    {'name': 'Balance_H4', 'coefficients': {'V4': 1.0, 'V3': -1.0, 'T4': 1.0, 'S4': 1.0}, 'operator': '=', 'rhs': 10.0},
    {'name': 'Turb_Pot_1', 'coefficients': {'PH1': 1.0, 'T1': -2.4525}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Turb_Pot_2', 'coefficients': {'PH2': 1.0, 'T2': -2.4525}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Turb_Pot_3', 'coefficients': {'PH3': 1.0, 'T3': -2.4525}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Turb_Pot_4', 'coefficients': {'PH4': 1.0, 'T4': -2.4525}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Pot_Ene_1', 'coefficients': {'GH1': 1.0, 'PH1': -1.0}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Pot_Ene_2', 'coefficients': {'GH2': 1.0, 'PH2': -1.0}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Pot_Ene_3', 'coefficients': {'GH3': 1.0, 'PH3': -1.0}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Pot_Ene_4', 'coefficients': {'GH4': 1.0, 'PH4': -1.0}, 'operator': '=', 'rhs': 0.0},
    {'name': 'Demanda_P1', 'coefficients': {'GH1': 1.0, 'GT1': 1.0}, 'operator': '=', 'rhs': 60.0},
    {'name': 'Demanda_P2', 'coefficients': {'GH2': 1.0, 'GT2': 1.0}, 'operator': '=', 'rhs': 80.0},
    {'name': 'Demanda_P3', 'coefficients': {'GH3': 1.0, 'GT3': 1.0}, 'operator': '=', 'rhs': 70.0},
    {'name': 'Demanda_P4', 'coefficients': {'GH4': 1.0, 'GT4': 1.0}, 'operator': '=', 'rhs': 90.0},
    {'name': 'V_Min_1', 'coefficients': {'V1': 1.0}, 'operator': '>=', 'rhs': 40.0},
    {'name': 'V_Min_2', 'coefficients': {'V2': 1.0}, 'operator': '>=', 'rhs': 40.0},
    {'name': 'V_Min_3', 'coefficients': {'V3': 1.0}, 'operator': '>=', 'rhs': 40.0},
    {'name': 'V_Min_4', 'coefficients': {'V4': 1.0}, 'operator': '>=', 'rhs': 40.0},
    {'name': 'V_Max_1', 'coefficients': {'V1': 1.0}, 'operator': '<=', 'rhs': 100.0},
    {'name': 'V_Max_2', 'coefficients': {'V2': 1.0}, 'operator': '<=', 'rhs': 100.0},
    {'name': 'V_Max_3', 'coefficients': {'V3': 1.0}, 'operator': '<=', 'rhs': 100.0},
    {'name': 'V_Max_4', 'coefficients': {'V4': 1.0}, 'operator': '<=', 'rhs': 100.0},
    {'name': 'T_Max_1', 'coefficients': {'T1': 1.0}, 'operator': '<=', 'rhs': 70.0},
    {'name': 'T_Max_2', 'coefficients': {'T2': 1.0}, 'operator': '<=', 'rhs': 70.0},
    {'name': 'T_Max_3', 'coefficients': {'T3': 1.0}, 'operator': '<=', 'rhs': 70.0},
    {'name': 'T_Max_4', 'coefficients': {'T4': 1.0}, 'operator': '<=', 'rhs': 70.0}
]


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
