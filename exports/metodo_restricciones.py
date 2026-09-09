#!/usr/bin/env python3
"""Script academico portable para el metodo de las restricciones.

Uso:
    python metodo_restricciones.py problema.json --primary 1 --r 6

El archivo es autonomo respecto del repositorio: solo requiere Python, Pyomo
y HiGHS (paquete ``highspy``). Las variables del esquema 1.0 son continuas y
no negativas.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs


SENTIDOS = {"Maximizar", "Minimizar"}
OPERADORES = {"<=", ">=", "="}


def _numero_finito(valor: Any, campo: str) -> float:
    if isinstance(valor, bool):
        raise ValueError(f"{campo} debe ser numerico.")
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{campo} debe ser numerico.") from exc
    if not math.isfinite(numero):
        raise ValueError(f"{campo} debe ser finito.")
    return numero


def _leer_coeficientes(
    datos: Any, variables: list[str], campo: str
) -> dict[str, float]:
    if not isinstance(datos, dict):
        raise ValueError(f"{campo} debe ser un objeto JSON.")
    desconocidas = sorted(set(datos) - set(variables))
    if desconocidas:
        raise ValueError(f"{campo} contiene variables desconocidas: {desconocidas}")
    # El formato es disperso: una variable ausente tiene coeficiente cero.
    return {
        variable: _numero_finito(datos.get(variable, 0.0), f"{campo}.{variable}")
        for variable in variables
    }


def cargar_problema(ruta: str | Path) -> dict[str, Any]:
    """Lee y valida los campos esenciales del esquema JSON 1.0."""

    ruta = Path(ruta)
    try:
        documento = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"No se pudo leer '{ruta}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido en '{ruta}': {exc}") from exc

    if not isinstance(documento, dict) or str(documento.get("schema_version")) != "1.0":
        raise ValueError("Se requiere un documento con schema_version '1.0'.")
    formulacion = documento.get("problem")
    if not isinstance(formulacion, dict) or formulacion.get("type") != "Biobjetivo":
        raise ValueError("El JSON debe contener un problema de tipo 'Biobjetivo'.")

    variables = formulacion.get("variables")
    if not isinstance(variables, list) or not variables:
        raise ValueError("problem.variables debe ser una lista no vacia.")
    if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) for v in variables):
        raise ValueError("Cada variable debe ser un identificador valido de Python/Pyomo.")
    if len(set(variables)) != len(variables):
        raise ValueError("Los nombres de variables no pueden repetirse.")

    objetivos_json = formulacion.get("bio_objectives")
    if not isinstance(objetivos_json, dict):
        raise ValueError("Falta problem.bio_objectives.")
    objetivos: list[dict[str, Any]] = []
    for indice, clave in enumerate(("obj1", "obj2"), start=1):
        datos = objetivos_json.get(clave)
        if not isinstance(datos, dict):
            raise ValueError(f"Falta bio_objectives.{clave}.")
        sentido = datos.get("sense")
        if sentido not in SENTIDOS:
            raise ValueError(f"El sentido de Z{indice} debe ser Maximizar o Minimizar.")
        objetivos.append(
            {
                "sense": sentido,
                "coefficients": _leer_coeficientes(
                    datos.get("coefficients", {}), variables, f"coeficientes de Z{indice}"
                ),
            }
        )

    restricciones_json = formulacion.get("constraints")
    if not isinstance(restricciones_json, list) or not restricciones_json:
        raise ValueError("problem.constraints debe ser una lista no vacia.")
    restricciones: list[dict[str, Any]] = []
    for indice, datos in enumerate(restricciones_json, start=1):
        if not isinstance(datos, dict):
            raise ValueError(f"La restriccion {indice} debe ser un objeto JSON.")
        operador = datos.get("operator")
        if operador not in OPERADORES:
            raise ValueError(f"Operador invalido en la restriccion {indice}: {operador}")
        restricciones.append(
            {
                "name": str(datos.get("name") or f"Restriccion_{indice}"),
                "coefficients": _leer_coeficientes(
                    datos.get("coefficients", {}),
                    variables,
                    f"coeficientes de la restriccion {indice}",
                ),
                "operator": operador,
                "rhs": _numero_finito(datos.get("rhs"), f"rhs de la restriccion {indice}"),
            }
        )

    metadata = documento.get("metadata", {})
    nombre = metadata.get("name", "Modelo biobjetivo") if isinstance(metadata, dict) else "Modelo biobjetivo"
    return {
        "name": str(nombre),
        "variables": list(variables),
        "objectives": objetivos,
        "constraints": restricciones,
    }


def _expresion_lineal(
    coeficientes: dict[str, float], variables_pyomo: dict[str, pyo.Var]
) -> Any:
    terminos = [
        coeficiente * variables_pyomo[nombre]
        for nombre, coeficiente in coeficientes.items()
        if coeficiente != 0.0
    ]
    if terminos:
        return pyo.quicksum(terminos)
    return 0.0 * next(iter(variables_pyomo.values()))


def _construir_modelo_base(
    problema: dict[str, Any], restricciones_extra: list[dict[str, Any]] | None = None
) -> tuple[pyo.ConcreteModel, dict[str, pyo.Var]]:
    modelo = pyo.ConcreteModel(name="Problema_LP")
    variables_pyomo: dict[str, pyo.Var] = {}
    for nombre in problema["variables"]:
        variable = pyo.Var(name=nombre, within=pyo.NonNegativeReals)
        setattr(modelo, nombre, variable)
        variables_pyomo[nombre] = variable

    restricciones = [*problema["constraints"], *(restricciones_extra or [])]
    for indice, restriccion in enumerate(restricciones):
        expresion = _expresion_lineal(restriccion["coefficients"], variables_pyomo)
        if restriccion["operator"] == "<=":
            relacion = expresion <= restriccion["rhs"]
        elif restriccion["operator"] == ">=":
            relacion = expresion >= restriccion["rhs"]
        else:
            relacion = expresion == restriccion["rhs"]
        setattr(modelo, f"con_{indice}", pyo.Constraint(expr=relacion))
    return modelo, variables_pyomo


def _estado(terminacion: Any) -> str:
    texto = str(terminacion).lower()
    if "optimal" in texto:
        return "optimal"
    if "infeasible" in texto and "unbounded" in texto:
        return "infeasible_or_unbounded"
    if "infeasible" in texto:
        return "infeasible"
    if "unbounded" in texto:
        return "unbounded"
    return "error"


def _evaluar_objetivo(
    objetivo: dict[str, Any], solucion: dict[str, float]
) -> float:
    return sum(
        objetivo["coefficients"].get(variable, 0.0) * solucion[variable]
        for variable in solucion
    )


def _resolver_objetivo(
    problema: dict[str, Any],
    indice_objetivo: int,
    restricciones_extra: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inicio = time.perf_counter()
    modelo, variables_pyomo = _construir_modelo_base(problema, restricciones_extra)
    objetivo = problema["objectives"][indice_objetivo - 1]
    expresion = sum(
        objetivo["coefficients"].get(nombre, 0.0) * variables_pyomo[nombre]
        for nombre in problema["variables"]
    )
    sentido = pyo.maximize if objetivo["sense"] == "Maximizar" else pyo.minimize
    modelo.obj = pyo.Objective(expr=expresion, sense=sentido)

    solver = Highs()
    solver.config.load_solution = False
    try:
        resultado = solver.solve(modelo)
        estado = _estado(resultado.termination_condition)
        terminacion = str(resultado.termination_condition)
    except Exception as exc:  # HiGHS informa aqui errores de ejecucion.
        return {
            "status": "error",
            "termination": "exception",
            "error": str(exc),
            "x": None,
            "value": None,
            "time_sec": time.perf_counter() - inicio,
        }

    solucion = None
    valor = None
    if estado == "optimal":
        if resultado.solution_loader:
            resultado.solution_loader.load_vars()
        solucion = {
            nombre: float(pyo.value(variables_pyomo[nombre]))
            for nombre in problema["variables"]
        }
        valor = _evaluar_objetivo(objetivo, solucion)
    return {
        "status": estado,
        "termination": terminacion,
        "x": solucion,
        "value": valor,
        "time_sec": time.perf_counter() - inicio,
    }


def _construir_ancla(
    problema: dict[str, Any], indice_primario: int, tolerancia: float
) -> dict[str, Any]:
    """Optimiza Zi y luego el otro objetivo sobre la cara Zi = Zi*."""

    primario = problema["objectives"][indice_primario - 1]
    indice_secundario = 2 if indice_primario == 1 else 1
    resultado_primario = _resolver_objetivo(problema, indice_primario)
    if resultado_primario["status"] != "optimal":
        return {**resultado_primario, "Z1": None, "Z2": None}

    restriccion_exacta = {
        "name": f"ancla_Z{indice_primario}",
        "coefficients": dict(primario["coefficients"]),
        "operator": "=",
        "rhs": resultado_primario["value"],
    }
    representante = _resolver_objetivo(
        problema, indice_secundario, [restriccion_exacta]
    )
    solucion = resultado_primario["x"]
    if representante["status"] == "optimal":
        valor_primario = _evaluar_objetivo(primario, representante["x"])
        if abs(valor_primario - resultado_primario["value"]) <= tolerancia:
            solucion = representante["x"]

    return {
        "status": "optimal",
        "x": solucion,
        "primary_optimal": resultado_primario["value"],
        "Z1": _evaluar_objetivo(problema["objectives"][0], solucion),
        "Z2": _evaluar_objetivo(problema["objectives"][1], solucion),
    }


def construir_matriz_pagos(
    problema: dict[str, Any], tolerancia: float = 1e-6
) -> dict[str, dict[str, Any]]:
    ancla_z1 = _construir_ancla(problema, 1, tolerancia)
    ancla_z2 = _construir_ancla(problema, 2, tolerancia)
    if ancla_z1["status"] != "optimal" or ancla_z2["status"] != "optimal":
        raise RuntimeError("No fue posible construir los dos extremos individuales.")
    return {"opt_Z1": ancla_z1, "opt_Z2": ancla_z2}


def generar_niveles_epsilon(z_min: float, z_max: float, r: int) -> list[float]:
    if isinstance(r, bool) or not isinstance(r, int) or r < 1:
        raise ValueError("r debe ser un entero mayor o igual que 1.")
    z_min = _numero_finito(z_min, "z_min")
    z_max = _numero_finito(z_max, "z_max")
    if z_min > z_max:
        raise ValueError("z_min no puede ser mayor que z_max.")
    niveles = [z_min + (t / r) * (z_max - z_min) for t in range(r + 1)]
    niveles[0] = z_min
    niveles[-1] = z_max
    return niveles


def _misma_solucion(
    primera: dict[str, Any], segunda: dict[str, Any], variables: list[str], tolerancia: float
) -> bool:
    return (
        all(abs(primera["x"][v] - segunda["x"][v]) <= tolerancia for v in variables)
        and abs(primera["Z1"] - segunda["Z1"]) <= tolerancia
        and abs(primera["Z2"] - segunda["Z2"]) <= tolerancia
    )


def _clasificar_pareto(
    soluciones: list[dict[str, Any]], sentidos: list[str], tolerancia: float
) -> dict[str, dict[str, Any]]:
    for solucion in soluciones:
        solucion["pareto_status"] = "No dominada"
        for candidata in soluciones:
            if candidata is solucion:
                continue
            no_peor = []
            mejor = []
            for clave, sentido in zip(("Z1", "Z2"), sentidos):
                if sentido == "Maximizar":
                    no_peor.append(candidata[clave] >= solucion[clave] - tolerancia)
                    mejor.append(candidata[clave] > solucion[clave] + tolerancia)
                else:
                    no_peor.append(candidata[clave] <= solucion[clave] + tolerancia)
                    mejor.append(candidata[clave] < solucion[clave] - tolerancia)
            if all(no_peor) and any(mejor):
                solucion["pareto_status"] = f"Dominada (por {candidata['id']})"
                break
    return {
        s["id"]: {
            "x": s["x"],
            "Z1": s["Z1"],
            "Z2": s["Z2"],
            "status": s["pareto_status"],
            "run_indices": s["run_indices"],
            "epsilon_levels": s["epsilon_levels"],
        }
        for s in soluciones
    }


def resolver_metodo_restricciones(
    problema: dict[str, Any], primary: int = 1, r: int = 6, tolerancia: float = 1e-6
) -> dict[str, Any]:
    """Aplica epsilon-constraint sin pesos ni normalizacion."""

    if isinstance(primary, bool) or primary not in (1, 2):
        raise ValueError("primary debe ser 1 o 2.")
    generar_niveles_epsilon(0.0, 0.0, r)
    restringido = 2 if primary == 1 else 1
    matriz = construir_matriz_pagos(problema, tolerancia)
    rangos = {
        f"Z{k}_{extremo}": funcion(
            matriz["opt_Z1"][f"Z{k}"], matriz["opt_Z2"][f"Z{k}"]
        )
        for k in (1, 2)
        for extremo, funcion in (("min", min), ("max", max))
    }
    prefijo = f"Z{restringido}"
    niveles = generar_niveles_epsilon(
        rangos[f"{prefijo}_min"], rangos[f"{prefijo}_max"], r
    )
    objetivo_restringido = problema["objectives"][restringido - 1]
    operador = ">=" if objetivo_restringido["sense"] == "Maximizar" else "<="

    corridas: list[dict[str, Any]] = []
    for t, epsilon in enumerate(niveles):
        restriccion_epsilon = {
            "name": f"epsilon_Z{restringido}_t_{t}",
            "coefficients": dict(objetivo_restringido["coefficients"]),
            "operator": operador,
            "rhs": epsilon,
        }
        resultado = _resolver_objetivo(problema, primary, [restriccion_epsilon])
        corrida = {
            "run_index": t,
            "t": t,
            "primary_objective": primary,
            "constrained_objective": restringido,
            "E": epsilon,
            "constraint_operator": operador,
            "status": resultado["status"],
            "x": resultado["x"],
            "Z1": None,
            "Z2": None,
            "execution_time_sec": resultado["time_sec"],
        }
        if resultado["x"] is not None:
            corrida["Z1"] = _evaluar_objetivo(problema["objectives"][0], resultado["x"])
            corrida["Z2"] = _evaluar_objetivo(problema["objectives"][1], resultado["x"])
        corridas.append(corrida)

    unicas: list[dict[str, Any]] = []
    for corrida in corridas:
        if corrida["status"] != "optimal" or corrida["x"] is None:
            continue
        repetida = next(
            (u for u in unicas if _misma_solucion(corrida, u, problema["variables"], tolerancia)),
            None,
        )
        if repetida:
            repetida["run_indices"].append(corrida["run_index"])
            repetida["epsilon_levels"].append(corrida["E"])
            repetida["count"] += 1
        else:
            unicas.append(
                {
                    "id": f"S{len(unicas) + 1}",
                    "x": dict(corrida["x"]),
                    "Z1": corrida["Z1"],
                    "Z2": corrida["Z2"],
                    "count": 1,
                    "run_indices": [corrida["run_index"]],
                    "epsilon_levels": [corrida["E"]],
                    "pareto_status": "No evaluada",
                }
            )

    clasificacion = _clasificar_pareto(
        unicas, [o["sense"] for o in problema["objectives"]], tolerancia
    )
    return {
        "payoff_matrix": matriz,
        "objective_ranges": rangos,
        "primary_objective": primary,
        "constrained_objective": restringido,
        "r": r,
        "epsilon_levels": niveles,
        "runs": corridas,
        "unique_solutions": unicas,
        "pareto_classification": clasificacion,
        "nondominated_solutions": [s for s in unicas if s["pareto_status"] == "No dominada"],
    }


def _formatear_objetivo(objetivo: dict[str, Any]) -> str:
    terminos = [
        f"{coef:g} {variable}"
        for variable, coef in objetivo["coefficients"].items()
        if coef != 0.0
    ]
    return " + ".join(terminos).replace("+ -", "- ") or "0"


def _formatear_vector(solucion: dict[str, float], variables: list[str]) -> str:
    return ", ".join(f"{v}={solucion[v]:.6f}" for v in variables)


def mostrar_resultados(ruta: Path, problema: dict[str, Any], resultado: dict[str, Any]) -> None:
    print("=" * 110)
    print("METODO DE LAS RESTRICCIONES / EPSILON-CONSTRAINT")
    print("=" * 110)
    print(f"Archivo: {ruta}")
    print(f"Modelo: {problema['name']}")
    print(f"Variables ({len(problema['variables'])}): {', '.join(problema['variables'])}")
    print(f"Restricciones originales: {len(problema['constraints'])}")
    for indice, objetivo in enumerate(problema["objectives"], start=1):
        print(f"Z{indice} = {_formatear_objetivo(objetivo)} [{objetivo['sense'].upper()}]")

    print("\nMatriz de pagos")
    print("ancla      |             Z1 |             Z2")
    for nombre, ancla in resultado["payoff_matrix"].items():
        print(f"{nombre:<11}| {ancla['Z1']:14.6f} | {ancla['Z2']:14.6f}")

    restringido = resultado["constrained_objective"]
    prefijo = f"Z{restringido}"
    print(f"\nObjetivo principal: Z{resultado['primary_objective']}")
    print(f"Objetivo restringido: {prefijo}")
    print(f"{prefijo}_min = {resultado['objective_ranges'][prefijo + '_min']:.12g}")
    print(f"{prefijo}_max = {resultado['objective_ranges'][prefijo + '_max']:.12g}")
    print(f"r = {resultado['r']}")
    print("Formula: E_k,t = Zk_min + (t/r)(Zk_max - Zk_min), t=0,...,r")
    print(f"Niveles E{restringido} = {[round(v, 10) for v in resultado['epsilon_levels']]}")

    print("\nTabla completa de corridas")
    print("t | E | estado | variables | Z1 | Z2")
    for corrida in resultado["runs"]:
        vector = "-" if corrida["x"] is None else _formatear_vector(corrida["x"], problema["variables"])
        z1 = "-" if corrida["Z1"] is None else f"{corrida['Z1']:.6f}"
        z2 = "-" if corrida["Z2"] is None else f"{corrida['Z2']:.6f}"
        print(f"{corrida['t']} | {corrida['E']:.6f} | {corrida['status']} | {vector} | {z1} | {z2}")

    print(f"\nSoluciones unicas ({len(resultado['unique_solutions'])})")
    for solucion in resultado["unique_solutions"]:
        print(
            f"{solucion['id']}: corridas={solucion['run_indices']}; "
            f"Z1={solucion['Z1']:.6f}; Z2={solucion['Z2']:.6f}; "
            f"{solucion['pareto_status']}"
        )
        print(f"  x = {_formatear_vector(solucion['x'], problema['variables'])}")

    print("\nClasificacion Pareto")
    for identificador, datos in resultado["pareto_classification"].items():
        print(f"{identificador}: Z1={datos['Z1']:.6f}; Z2={datos['Z2']:.6f} -> {datos['status']}")
    print("\nSoluciones no dominadas obtenidas")
    for solucion in resultado["nondominated_solutions"]:
        print(f"{solucion['id']}: (Z1, Z2)=({solucion['Z1']:.6f}, {solucion['Z2']:.6f})")


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Metodo portable de las restricciones")
    parser.add_argument("model_file", type=Path, help="Problema biobjetivo en JSON esquema 1.0")
    parser.add_argument("--primary", type=int, choices=(1, 2), default=1, help="Objetivo principal")
    parser.add_argument("--r", type=int, default=6, help="Numero de intervalos (r >= 1)")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    argumentos = crear_parser().parse_args(argv)
    try:
        problema = cargar_problema(argumentos.model_file)
        resultado = resolver_metodo_restricciones(problema, argumentos.primary, argumentos.r)
        mostrar_resultados(argumentos.model_file, problema, resultado)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
