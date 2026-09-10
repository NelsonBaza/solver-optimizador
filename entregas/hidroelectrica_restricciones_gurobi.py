"""
Problema: Generación Hidroeléctrica Biobjetivo Corregida - 4 Períodos
Método de las restricciones (epsilon-constraint) con Gurobi.
Archivo autocontenido: no necesita el JSON ni el repositorio original.
"""

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


# 1. CONFIGURACIÓN FÁCIL DE EDITAR
PRIMARY_OBJECTIVE = 1
R = 6
TOL = 1e-6
SHOW_GUROBI_LOG = False
PLOT_FILE = Path(__file__).with_name('hidroelectrica_restricciones_gurobi_pareto.png')

PROBLEM_NAME = 'Generación Hidroeléctrica Biobjetivo Corregida - 4 Períodos'
PLOT_TITLE = 'Generación hidroeléctrica'
SENSES = ('MIN', 'MAX')
OBJECTIVE_NAMES = ('Costo de generación térmica', 'Volumen final del embalse V4 (UH)')


# 2. DATOS COMPACTOS DEL PROBLEMA
periodos = range(1, 5)
balance_h_rhs = {2: 20, 3: 15, 4: 10}
demanda_p_rhs = {1: 60, 2: 80, 3: 70, 4: 90}
# 28 restricciones canónicas: 12 expresadas como cotas y 16 como ecuaciones/inecuaciones.


# 3. MODELO GUROBI: VARIABLES, RESTRICCIONES Y OBJETIVOS
def construir_modelo(nombre="modelo_epsilon"):
    m = gp.Model(nombre)
    m.Params.OutputFlag = int(SHOW_GUROBI_LOG)

    T = m.addVars(periodos, lb=0, ub=70, name='T')
    V = m.addVars(periodos, lb=40, ub=100, name='V')
    S = m.addVars(periodos, lb=0, name='S')
    PH = m.addVars(periodos, lb=0, name='PH')
    GH = m.addVars(periodos, lb=0, name='GH')
    GT = m.addVars(periodos, lb=0, name='GT')

    x = {}
    x.update({f"T{t}": T[t] for t in periodos})
    x.update({f"V{t}": V[t] for t in periodos})
    x.update({f"S{t}": S[t] for t in periodos})
    x.update({f"PH{t}": PH[t] for t in periodos})
    x.update({f"GH{t}": GH[t] for t in periodos})
    x.update({f"GT{t}": GT[t] for t in periodos})

    m.addConstr(V[1] + T[1] + S[1] == 90, name='Balance_H1')
    m.addConstrs((V[t] - V[t - 1] + T[t] + S[t] == balance_h_rhs[t] for t in range(2, 5)),
                 name='Balance_H')
    m.addConstrs((PH[t] - 2.4525 * T[t] == 0 for t in range(1, 5)),
                 name='Turb_Pot')
    m.addConstrs((GH[t] - PH[t] == 0 for t in range(1, 5)),
                 name='Pot_Ene')
    m.addConstrs((GH[t] + GT[t] == demanda_p_rhs[t] for t in range(1, 5)),
                 name='Demanda_P')

    # Funciones objetivo originales, visibles en la formulación.
    Z1 = 100 * gp.quicksum(GT[t] for t in periodos)
    Z2 = V[4]
    return m, x, Z1, Z2


# 4. RESOLUCIÓN AUXILIAR Y MATRIZ DE PAGOS
def valor(expresion):
    """Evalúa tanto variables simples como expresiones lineales."""
    return float(expresion.X if isinstance(expresion, gp.Var) else expresion.getValue())


def optimizar(indice_objetivo, fijar=None, epsilon=None):
    m, x, Z1, Z2 = construir_modelo()
    objetivos = (Z1, Z2)
    if fijar is not None:
        indice, valor = fijar
        m.addConstr(objetivos[indice - 1] == valor, name=f"fijar_Z{indice}")
    if epsilon is not None:
        indice, nivel = epsilon
        if SENSES[indice - 1] == "MAX":
            m.addConstr(objetivos[indice - 1] >= nivel, name=f"epsilon_Z{indice}")
        else:
            m.addConstr(objetivos[indice - 1] <= nivel, name=f"epsilon_Z{indice}")

    sentido = GRB.MAXIMIZE if SENSES[indice_objetivo - 1] == "MAX" else GRB.MINIMIZE
    m.setObjective(objetivos[indice_objetivo - 1], sentido)
    inicio = time.perf_counter()
    m.optimize()
    estados = {
        GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED", GRB.INF_OR_UNBD: "INF_OR_UNBD",
    }
    resultado = {
        "status": estados.get(m.Status, f"STATUS_{m.Status}"),
        "x": None, "Z1": None, "Z2": None,
        "time": time.perf_counter() - inicio,
    }
    if m.Status == GRB.OPTIMAL:
        resultado.update(
            x={nombre: float(variable.X) for nombre, variable in x.items()},
            Z1=valor(Z1), Z2=valor(Z2),
        )
    m.dispose()
    return resultado


def calcular_matriz_pagos():
    matriz = {}
    for indice in (1, 2):
        primera = optimizar(indice)
        if primera["status"] != "OPTIMAL":
            raise RuntimeError(f"No se pudo optimizar Z{indice}: {primera['status']}")
        otro = 2 if indice == 1 else 1
        # Desempate: fija el óptimo primario y optimiza el otro objetivo.
        fila = optimizar(otro, fijar=(indice, primera[f"Z{indice}"]))
        matriz[f"opt_Z{indice}"] = fila if fila["status"] == "OPTIMAL" else primera
    return matriz


# 5. NIVELES Y BARRIDO EPSILON
def generar_niveles_epsilon(z_min, z_max, r):
    # E_t = Z_min + (t/r)(Z_max - Z_min), para t=0,...,r.
    niveles = [z_min + (t / r) * (z_max - z_min) for t in range(r + 1)]
    niveles[0], niveles[-1] = z_min, z_max
    return niveles


def resolver_epsilon(niveles):
    restringido = 2 if PRIMARY_OBJECTIVE == 1 else 1
    corridas = []
    for t, E in enumerate(niveles):
        # optimizar() crea un modelo nuevo: las restricciones no se acumulan.
        resultado = optimizar(PRIMARY_OBJECTIVE, epsilon=(restringido, E))
        resultado.update(t=t, E=E)
        corridas.append(resultado)
    return corridas


# 6. SOLUCIONES ÚNICAS Y DOMINANCIA DE PARETO
def resumir_soluciones(corridas):
    unicas = []
    for corrida in corridas:
        if corrida["status"] != "OPTIMAL":
            continue
        repetida = next((s for s in unicas if
            all(abs(corrida["x"][v] - s["x"][v]) <= TOL for v in corrida["x"])
            and abs(corrida["Z1"] - s["Z1"]) <= TOL
            and abs(corrida["Z2"] - s["Z2"]) <= TOL), None)
        if repetida:
            repetida["niveles"].append(corrida["E"])
        else:
            unicas.append({
                "id": f"S{len(unicas) + 1}", "x": corrida["x"],
                "Z1": corrida["Z1"], "Z2": corrida["Z2"],
                "niveles": [corrida["E"]], "no_dominada": True,
            })

    def no_peor(a, b, sentido):
        return a >= b - TOL if sentido == "MAX" else a <= b + TOL

    def mejor(a, b, sentido):
        return a > b + TOL if sentido == "MAX" else a < b - TOL

    for s in unicas:
        s["no_dominada"] = not any(
            no_peor(c["Z1"], s["Z1"], SENSES[0])
            and no_peor(c["Z2"], s["Z2"], SENSES[1])
            and (mejor(c["Z1"], s["Z1"], SENSES[0])
                 or mejor(c["Z2"], s["Z2"], SENSES[1]))
            for c in unicas if c is not s
        )
    return unicas


# 7. SALIDA ACADÉMICA
def numero(valor):
    return "-" if valor is None else f"{valor:.10g}"


def imprimir(matriz, niveles, corridas, unicas):
    print("\nMatriz de pagos")
    for nombre, fila in matriz.items():
        print(f"  {nombre}: Z1={numero(fila['Z1'])}; Z2={numero(fila['Z2'])}")
    print("\nNiveles E = [" + ", ".join(numero(E) for E in niveles) + "]")
    print("\nCorridas")
    for corrida in corridas:
        print(f"t={corrida['t']}; E={numero(corrida['E'])}; "
              f"estado={corrida['status']}; Z1={numero(corrida['Z1'])}; "
              f"Z2={numero(corrida['Z2'])}")
        if corrida["x"]:
            print("  T =", [numero(corrida['x'][f"T{t}"]) for t in periodos])
            print("  V =", [numero(corrida['x'][f"V{t}"]) for t in periodos])
            print("  S =", [numero(corrida['x'][f"S{t}"]) for t in periodos])
            print("  PH =", [numero(corrida['x'][f"PH{t}"]) for t in periodos])
            print("  GH =", [numero(corrida['x'][f"GH{t}"]) for t in periodos])
            print("  GT =", [numero(corrida['x'][f"GT{t}"]) for t in periodos])
    print(f"\nSoluciones únicas: {len(unicas)}")
    for s in unicas:
        estado = "No dominada" if s["no_dominada"] else "Dominada"
        print(f"  {s['id']}: ({numero(s['Z1'])}, {numero(s['Z2'])}); {estado}")
    print("\nSoluciones no dominadas obtenidas por el barrido")
    for s in unicas:
        if s["no_dominada"]:
            print(f"  {s['id']}: ({numero(s['Z1'])}, {numero(s['Z2'])})")


# 8. GRÁFICO
def crear_grafico(unicas):
    no_dominadas = [s for s in unicas if s["no_dominada"]]
    dominadas = [s for s in unicas if not s["no_dominada"]]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    if dominadas:
        ax.scatter([s["Z1"] for s in dominadas], [s["Z2"] for s in dominadas],
                   color="#7f8c8d", marker="x", label="Soluciones dominadas obtenidas")
    if no_dominadas:
        ordenadas = sorted(no_dominadas, key=lambda s: s["Z1"])
        ax.plot([s["Z1"] for s in ordenadas], [s["Z2"] for s in ordenadas],
                color="#4f97c9", linewidth=1.5)
        ax.scatter([s["Z1"] for s in no_dominadas], [s["Z2"] for s in no_dominadas],
                   color="#d62728", edgecolor="white", s=72,
                   label="Soluciones no dominadas obtenidas", zorder=3)

    xs, ys = [s["Z1"] for s in unicas], [s["Z2"] for s in unicas]
    for i, s in enumerate(unicas):
        xr = 0.5 if max(xs) == min(xs) else (s["Z1"] - min(xs)) / (max(xs) - min(xs))
        yr = 0.5 if max(ys) == min(ys) else (s["Z2"] - min(ys)) / (max(ys) - min(ys))
        dx = 10 if xr <= 0.2 else -10 if xr >= 0.8 else (10 if i % 2 == 0 else -10)
        dy = 12 if yr <= 0.2 else -12 if yr >= 0.8 else (12 if i % 4 < 2 else -12)
        ax.annotate(f"{s['id']}\nE={numero(s['niveles'][0])}", (s["Z1"], s["Z2"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=8,
                    ha="left" if dx > 0 else "right", va="bottom" if dy > 0 else "top",
                    bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "#bbbbbb"},
                    arrowprops={"arrowstyle": "-", "color": "#999999", "lw": 0.6})
    ax.set_title(f"Frontera de Pareto — {PLOT_TITLE}\n"
                 f"Método de las restricciones | Z1 {SENSES[0]} · Z2 {SENSES[1]}")
    ax.set_xlabel(f"Z1 — {OBJECTIVE_NAMES[0]} ({SENSES[0]})")
    ax.set_ylabel(f"Z2 — {OBJECTIVE_NAMES[1]} ({SENSES[1]})")
    ax.margins(x=0.06, y=0.1)
    ax.grid(True, linestyle="--", alpha=0.45)
    if unicas:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(PLOT_FILE, dpi=160, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print(f"\nGráfico guardado en: {PLOT_FILE}")


def main():
    if PRIMARY_OBJECTIVE not in (1, 2) or R < 1:
        raise ValueError("PRIMARY_OBJECTIVE debe ser 1 o 2 y R debe ser >= 1.")
    restringido = 2 if PRIMARY_OBJECTIVE == 1 else 1
    print("MÉTODO DE LAS RESTRICCIONES — GUROBI")
    print("Gurobi version:", ".".join(map(str, gp.gurobi.version())))
    print("Problema:", PROBLEM_NAME)
    print(f"Objetivo principal: Z{PRIMARY_OBJECTIVE}; restringido: Z{restringido}; R={R}")
    matriz = calcular_matriz_pagos()
    columna = [fila[f"Z{restringido}"] for fila in matriz.values()]
    niveles = generar_niveles_epsilon(min(columna), max(columna), R)
    corridas = resolver_epsilon(niveles)
    unicas = resumir_soluciones(corridas)
    imprimir(matriz, niveles, corridas, unicas)
    crear_grafico(unicas)


if __name__ == "__main__":
    main()
