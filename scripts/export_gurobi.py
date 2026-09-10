"""Genera un entregable Gurobi compacto y autocontenido para epsilon-constraint."""

from __future__ import annotations

import argparse
from collections import defaultdict
import keyword
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata


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
PRIMARY_OBJECTIVE = __PRIMARY_OBJECTIVE__
R = __R_VALUE__
TOL = 1e-6
SHOW_GUROBI_LOG = False
PLOT_FILE = Path(__file__).with_name(__PLOT_FILE_NAME__)

PROBLEM_NAME = __PROBLEM_NAME__
PLOT_TITLE = __PLOT_TITLE__
SENSES = (__SENSE_1__, __SENSE_2__)
OBJECTIVE_NAMES = (__OBJECTIVE_NAME_1__, __OBJECTIVE_NAME_2__)


# 2. DATOS COMPACTOS DEL PROBLEMA
__DATA_DECLARATIONS__


# 3. MODELO GUROBI: VARIABLES, RESTRICCIONES Y OBJETIVOS
def construir_modelo(nombre="modelo_epsilon"):
    m = gp.Model(nombre)
    m.Params.OutputFlag = int(SHOW_GUROBI_LOG)

__VARIABLE_DECLARATIONS__

__VARIABLE_LOOKUP__

__CONSTRAINT_DECLARATIONS__

    # Funciones objetivo originales, visibles en la formulación.
    Z1 = __OBJECTIVE_1__
    Z2 = __OBJECTIVE_2__
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
__PRINT_VARIABLES__
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
        description="Exporta un modelo biobjetivo como programa Gurobi epsilon compacto."
    )
    parser.add_argument("model_file", type=Path, help="modelo JSON 1.0 o 1.1")
    parser.add_argument("--method", choices=("epsilon",), default="epsilon")
    parser.add_argument("--primary", choices=(1, 2), type=int, default=1)
    parser.add_argument("--r", type=_positive_integer, default=6)
    parser.add_argument("--output", type=Path, help="archivo .py de salida")
    return parser


def _sparse(coefficients: dict[str, float]) -> dict[str, float]:
    return {
        name: float(value)
        for name, value in coefficients.items()
        if float(value) != 0.0
    }


def load_canonical_biobjective(model_file: Path) -> dict[str, Any]:
    """Carga 1.0/1.1 y deriva datos del mismo problema canónico del solver."""

    loaded = deserialize_model(model_file.read_text(encoding="utf-8"))
    objectives = loaded.get("objectives")
    if loaded.get("problem_type") != "Biobjetivo" or not isinstance(objectives, list):
        raise ValueError("El exportador Gurobi admite problemas Biobjetivo.")
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
        "description": loaded["metadata"].get("description", ""),
        "plot_title": loaded["metadata"].get("plot_title")
        or loaded["metadata"]["name"],
        "variables": list(problem.variables),
        "objectives": [
            {
                "name": objective.name,
                "sense": "MAX" if objective.sense.value == "max" else "MIN",
                "coefficients": _sparse(objective.coefficients),
            }
            for objective in (problem.objective1, problem.objective2)
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


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.15g}"


def _python_identifier(value: str, prefix: str = "v") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    candidate = re.sub(r"\W+", "_", ascii_value).strip("_") or prefix
    if candidate[0].isdigit() or keyword.iskeyword(candidate):
        candidate = f"{prefix}_{candidate}"
    return candidate


def _numbered_variable(name: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"([A-Za-z_][A-Za-z_]*)([1-9]\d*)", name)
    return (match.group(1), int(match.group(2))) if match else None


def _linear_expression(terms: list[tuple[float, str]]) -> str:
    pieces: list[str] = []
    for coefficient, reference in terms:
        sign = "-" if coefficient < 0 else "+"
        magnitude = abs(coefficient)
        term = reference if magnitude == 1.0 else f"{_number(magnitude)} * {reference}"
        if not pieces:
            pieces.append(term if coefficient > 0 else f"-{term}")
        else:
            pieces.append(f" {sign} {term}")
    return "".join(pieces) if pieces else "0"


def _infer_bounds(
    variables: list[str], constraints: list[dict[str, Any]]
) -> tuple[dict[str, tuple[float, float | None]], list[dict[str, Any]], int]:
    """Convierte cotas de una sola variable en bounds Gurobi equivalentes."""

    bounds: dict[str, list[float | None]] = {
        variable: [0.0, None] for variable in variables
    }
    remaining: list[dict[str, Any]] = []
    folded = 0
    for constraint in constraints:
        coefficients = constraint["coefficients"]
        if len(coefficients) != 1:
            remaining.append(constraint)
            continue
        variable, coefficient = next(iter(coefficients.items()))
        value = float(constraint["rhs"]) / coefficient
        operator = constraint["operator"]
        if coefficient < 0:
            operator = {"<=": ">=", ">=": "<=", "=": "="}[operator]
        if operator in (">=", "="):
            bounds[variable][0] = max(float(bounds[variable][0]), value)
        if operator in ("<=", "="):
            current = bounds[variable][1]
            bounds[variable][1] = value if current is None else min(float(current), value)
        folded += 1
    normalized = {
        variable: (float(values[0]), None if values[1] is None else float(values[1]))
        for variable, values in bounds.items()
    }
    return normalized, remaining, folded


def _variable_layout(canonical: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for variable in canonical["variables"]:
        parsed = _numbered_variable(variable)
        if parsed:
            grouped[parsed[0]].append(parsed[1])
    groups = {
        family: tuple(sorted(indices))
        for family, indices in grouped.items()
        if len(indices) >= 2 and len(indices) == len(set(indices))
    }
    grouped_variables = {
        f"{family}{index}" for family, indices in groups.items() for index in indices
    }
    scalars = [v for v in canonical["variables"] if v not in grouped_variables]

    semantic_text = unicodedata.normalize(
        "NFKD", canonical["problem_name"] + " " + canonical.get("description", "")
    ).encode("ascii", "ignore").decode("ascii").lower()
    unique_domains = {indices for indices in groups.values()}
    shared_domain = None
    if len(unique_domains) == 1:
        indices = next(iter(unique_domains))
        if indices == tuple(range(indices[0], indices[-1] + 1)):
            shared_domain = "periodos" if "period" in semantic_text else "indices"

    used_names: set[str] = set()
    group_info: dict[str, dict[str, Any]] = {}
    data_lines: list[str] = []
    if shared_domain:
        indices = next(iter(unique_domains))
        data_lines.append(f"{shared_domain} = range({indices[0]}, {indices[-1] + 1})")

    for family, indices in groups.items():
        py_name = _python_identifier(family, "familia")
        while py_name in used_names:
            py_name += "_"
        used_names.add(py_name)
        if shared_domain:
            domain_name = shared_domain
        else:
            domain_name = _python_identifier(f"indices_{family}", "indices")
            if indices == tuple(range(indices[0], indices[-1] + 1)):
                domain_value = f"range({indices[0]}, {indices[-1] + 1})"
            else:
                domain_value = repr(indices)
            data_lines.append(f"{domain_name} = {domain_value}")
        group_info[family] = {
            "indices": indices,
            "py_name": py_name,
            "domain": domain_name,
        }

    scalar_info: dict[str, str] = {}
    for variable in scalars:
        py_name = _python_identifier(variable)
        while py_name in used_names:
            py_name += "_"
        used_names.add(py_name)
        scalar_info[variable] = py_name

    accessors = dict(scalar_info)
    for family, info in group_info.items():
        for index in info["indices"]:
            accessors[f"{family}{index}"] = f"{info['py_name']}[{index}]"
    return {
        "groups": group_info,
        "scalars": scalar_info,
        "accessors": accessors,
        "data_lines": data_lines,
    }


def _group_bound_arguments(
    indexed_names: list[tuple[int, str]],
    bounds: dict[str, tuple[float, float | None]],
) -> str:
    lower = [(index, bounds[name][0]) for index, name in indexed_names]
    upper = [(index, bounds[name][1]) for index, name in indexed_names]
    parts: list[str] = []
    if len({value for _, value in lower}) == 1:
        parts.append(f"lb={_number(lower[0][1])}")
    else:
        values = ", ".join(f"{index}: {_number(value)}" for index, value in lower)
        parts.append(f"lb={{{values}}}")
    finite_upper = {value for _, value in upper}
    if len(finite_upper) == 1 and upper[0][1] is not None:
        parts.append(f"ub={_number(float(upper[0][1]))}")
    elif len(finite_upper) > 1:
        values = ", ".join(
            f"{index}: {'GRB.INFINITY' if value is None else _number(value)}"
            for index, value in upper
        )
        parts.append(f"ub={{{values}}}")
    return ", ".join(parts)


def _constraint_template(
    constraint: dict[str, Any],
    position: int,
    layout: dict[str, Any],
) -> tuple[Any, ...] | None:
    match = re.fullmatch(r"(.+?)(\d+)", constraint["name"])
    if not match:
        return None
    base, index_text = match.groups()
    index = int(index_text)
    terms: list[tuple[str, int, float]] = []
    for variable, coefficient in constraint["coefficients"].items():
        parsed = _numbered_variable(variable)
        if not parsed or parsed[0] not in layout["groups"]:
            return None
        family, variable_index = parsed
        terms.append((family, variable_index - index, float(coefficient)))
    return (base.rstrip("_"), constraint["operator"], tuple(terms), index, position)


def _indexed_reference(layout: dict[str, Any], family: str, offset: int) -> str:
    py_name = layout["groups"][family]["py_name"]
    if offset == 0:
        return f"{py_name}[t]"
    sign = "+" if offset > 0 else "-"
    return f"{py_name}[t {sign} {abs(offset)}]"


def _render_constraints(
    constraints: list[dict[str, Any]],
    layout: dict[str, Any],
) -> tuple[list[str], list[str]]:
    candidates: dict[tuple[Any, ...], list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for position, constraint in enumerate(constraints):
        template = _constraint_template(constraint, position, layout)
        if template:
            base, operator, terms, index, original_position = template
            candidates[(base, operator, terms)].append(
                (original_position, index, constraint)
            )

    grouped_positions: set[int] = set()
    render_items: list[tuple[int, list[str], list[str]]] = []
    used_data_names: set[str] = set()
    for (base, operator, terms), members in candidates.items():
        if len(members) < 2 or len({member[1] for member in members}) != len(members):
            continue
        members.sort(key=lambda member: member[1])
        indices = [member[1] for member in members]
        group_terms = [
            (coefficient, _indexed_reference(layout, family, offset))
            for family, offset, coefficient in terms
        ]
        lhs = _linear_expression(group_terms)
        rhs_values = [float(member[2]["rhs"]) for member in members]
        data_lines: list[str] = []
        if len(set(rhs_values)) == 1:
            rhs = _number(rhs_values[0])
        else:
            data_name = _python_identifier(base.lower() + "_rhs", "rhs")
            while data_name in used_data_names:
                data_name += "_"
            used_data_names.add(data_name)
            mapping = ", ".join(
                f"{index}: {_number(value)}"
                for index, value in zip(indices, rhs_values)
            )
            data_lines.append(f"{data_name} = {{{mapping}}}")
            rhs = f"{data_name}[t]"
        if indices == list(range(indices[0], indices[-1] + 1)):
            iterator = f"range({indices[0]}, {indices[-1] + 1})"
        else:
            iterator = repr(tuple(indices))
        python_operator = "==" if operator == "=" else operator
        lines = [
            f"    m.addConstrs(({lhs} {python_operator} {rhs} for t in {iterator}),",
            f"                 name={base!r})",
        ]
        positions = {member[0] for member in members}
        grouped_positions.update(positions)
        render_items.append((min(positions), lines, data_lines))

    for position, constraint in enumerate(constraints):
        if position in grouped_positions:
            continue
        terms = [
            (float(coefficient), layout["accessors"][variable])
            for variable, coefficient in constraint["coefficients"].items()
        ]
        python_operator = (
            "==" if constraint["operator"] == "=" else constraint["operator"]
        )
        line = (
            f"    m.addConstr({_linear_expression(terms)} "
            f"{python_operator} {_number(float(constraint['rhs']))}, "
            f"name={constraint['name']!r})"
        )
        render_items.append((position, [line], []))

    render_items.sort(key=lambda item: item[0])
    constraint_lines: list[str] = []
    data_lines: list[str] = []
    for _, lines, data in render_items:
        constraint_lines.extend(lines)
        data_lines.extend(data)
    return constraint_lines, data_lines


def _render_objective(
    coefficients: dict[str, float], layout: dict[str, Any]
) -> str:
    if len(coefficients) == 1:
        variable, coefficient = next(iter(coefficients.items()))
        return _linear_expression(
            [(float(coefficient), layout["accessors"][variable])]
        )
    parsed_terms = [
        (_numbered_variable(variable), float(coefficient))
        for variable, coefficient in coefficients.items()
    ]
    if parsed_terms and all(parsed is not None for parsed, _ in parsed_terms):
        families = {parsed[0] for parsed, _ in parsed_terms if parsed is not None}
        values = {coefficient for _, coefficient in parsed_terms}
        if len(families) == 1 and len(values) == 1:
            family = next(iter(families))
            info = layout["groups"].get(family)
            objective_indices = tuple(
                sorted(parsed[1] for parsed, _ in parsed_terms if parsed is not None)
            )
            if info and objective_indices == info["indices"]:
                coefficient = next(iter(values))
                total = (
                    f"gp.quicksum({info['py_name']}[t] for t in {info['domain']})"
                )
                if coefficient == 1.0:
                    return total
                if coefficient == -1.0:
                    return f"-{total}"
                return f"{_number(coefficient)} * {total}"
    return _linear_expression(
        [
            (float(coefficient), layout["accessors"][variable])
            for variable, coefficient in coefficients.items()
        ]
    )


def build_render_plan(canonical: dict[str, Any]) -> dict[str, Any]:
    """Compila datos canónicos a sentencias Gurobi directas y legibles."""

    layout = _variable_layout(canonical)
    bounds, remaining_constraints, folded_bounds = _infer_bounds(
        canonical["variables"], canonical["constraints"]
    )
    variable_lines: list[str] = []
    lookup_lines = ["    x = {}"]
    print_lines: list[str] = []

    for family, info in layout["groups"].items():
        indexed_names = [
            (index, f"{family}{index}") for index in info["indices"]
        ]
        bound_args = _group_bound_arguments(indexed_names, bounds)
        variable_lines.append(
            f"    {info['py_name']} = m.addVars({info['domain']}, {bound_args}, "
            f"name={family!r})"
        )
        lookup_lines.append(
            f"    x.update({{f\"{family}{{t}}\": {info['py_name']}[t] "
            f"for t in {info['domain']}}})"
        )
        print_lines.append(
            f"            print(\"  {family} =\", "
            f"[numero(corrida['x'][f\"{family}{{t}}\"]) for t in {info['domain']}])"
        )

    for variable, py_name in layout["scalars"].items():
        lower, upper = bounds[variable]
        args = [f"lb={_number(lower)}"]
        if upper is not None:
            args.append(f"ub={_number(upper)}")
        variable_lines.append(
            f"    {py_name} = m.addVar({', '.join(args)}, name={variable!r})"
        )
        lookup_lines.append(f"    x[{variable!r}] = {py_name}")
        print_lines.append(
            f"            print(\"  {variable} =\", numero(corrida['x'][{variable!r}]))"
        )

    constraint_lines, rhs_data = _render_constraints(
        remaining_constraints, layout
    )
    data_lines = [*layout["data_lines"], *rhs_data]
    data_lines.append(
        f"# {len(canonical['constraints'])} restricciones canónicas: "
        f"{folded_bounds} expresadas como cotas y "
        f"{len(remaining_constraints)} como ecuaciones/inecuaciones."
    )
    return {
        "data_declarations": "\n".join(data_lines),
        "variable_declarations": "\n".join(variable_lines),
        "variable_lookup": "\n".join(lookup_lines),
        "constraint_declarations": "\n".join(constraint_lines),
        "objective_1": _render_objective(
            canonical["objectives"][0]["coefficients"], layout
        ),
        "objective_2": _render_objective(
            canonical["objectives"][1]["coefficients"], layout
        ),
        "print_variables": "\n".join(print_lines),
        "folded_bounds": folded_bounds,
        "direct_constraints": len(remaining_constraints),
    }


def render_gurobi_script(
    canonical: dict[str, Any], primary: int, r: int, output_name: str
) -> str:
    plan = build_render_plan(canonical)
    doc_name = canonical["problem_name"].replace("\n", " ").replace('"""', "'''")
    replacements = {
        "__PROBLEM_NAME_DOC__": doc_name,
        "__PRIMARY_OBJECTIVE__": str(primary),
        "__R_VALUE__": str(r),
        "__PLOT_FILE_NAME__": repr(Path(output_name).stem + "_pareto.png"),
        "__PROBLEM_NAME__": repr(canonical["problem_name"]),
        "__PLOT_TITLE__": repr(canonical["plot_title"]),
        "__SENSE_1__": repr(canonical["objectives"][0]["sense"]),
        "__SENSE_2__": repr(canonical["objectives"][1]["sense"]),
        "__OBJECTIVE_NAME_1__": repr(canonical["objectives"][0]["name"]),
        "__OBJECTIVE_NAME_2__": repr(canonical["objectives"][1]["name"]),
        "__DATA_DECLARATIONS__": plan["data_declarations"],
        "__VARIABLE_DECLARATIONS__": plan["variable_declarations"],
        "__VARIABLE_LOOKUP__": plan["variable_lookup"],
        "__CONSTRAINT_DECLARATIONS__": plan["constraint_declarations"],
        "__OBJECTIVE_1__": plan["objective_1"],
        "__OBJECTIVE_2__": plan["objective_2"],
        "__PRINT_VARIABLES__": plan["print_variables"],
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
    source = render_gurobi_script(
        load_canonical_biobjective(model_file), primary, r, output_file.name
    )
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
            args.model_file, output, primary=args.primary, r=args.r
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
