#!/usr/bin/env python3
"""Script academico portable para ponderaciones normalizadas.

Uso:
    python metodo_ponderaciones.py problema.json --num-weights 6

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
from pathlib import Path
from typing import Any

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs


SENTIDOS = {"Maximizar", "Minimizar"}
OPERADORES = {"<=", ">=", "="}
TOLERANCIA_RANGO = 1e-7


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
    except Exception as exc:
        return {"status": "error", "error": str(exc), "x": None, "value": None}

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
    return {"status": estado, "x": solucion, "value": valor}


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


def generar_ponderaciones(numero: int) -> list[tuple[float, float]]:
    if isinstance(numero, bool) or not isinstance(numero, int) or numero < 2:
        raise ValueError("num_weights debe ser un entero mayor o igual que 2.")
    return [
        (round(i / (numero - 1), 6), round(1.0 - i / (numero - 1), 6))
        for i in range(numero)
    ]


def normalizar(valor: float, z_min: float, z_max: float, sentido: str) -> float:
    rango = z_max - z_min
    if rango < TOLERANCIA_RANGO:
        raise ValueError("El rango de normalizacion debe ser positivo y no nulo.")
    if sentido == "Maximizar":
        return (valor - z_min) / rango
    return (z_max - valor) / rango


def _resolver_ponderacion(
    problema: dict[str, Any],
    indice: int,
    alpha1: float,
    alpha2: float,
    rangos: dict[str, float],
    tolerancia: float,
) -> dict[str, Any]:
    """Maximiza W = alpha1*N1 + alpha2*N2."""

    modelo, variables_pyomo = _construir_modelo_base(problema)
    expresiones = [
        sum(
            objetivo["coefficients"].get(nombre, 0.0) * variables_pyomo[nombre]
            for nombre in problema["variables"]
        )
        for objetivo in problema["objectives"]
    ]
    normalizadas = []
    for numero, (expresion, objetivo) in enumerate(
        zip(expresiones, problema["objectives"]), start=1
    ):
        minimo = rangos[f"Z{numero}_min"]
        maximo = rangos[f"Z{numero}_max"]
        if objetivo["sense"] == "Maximizar":
            normalizadas.append((expresion - minimo) / (maximo - minimo))
        else:
            normalizadas.append((maximo - expresion) / (maximo - minimo))
    expresion_w = alpha1 * normalizadas[0] + alpha2 * normalizadas[1]
    modelo.weighted_objective = pyo.Objective(expr=expresion_w, sense=pyo.maximize)

    solver = Highs()
    solver.config.load_solution = False
    try:
        resultado = solver.solve(modelo)
    except Exception as exc:
        return {
            "run_index": indice,
            "alpha1": alpha1,
            "alpha2": alpha2,
            "status": "error",
            "error": str(exc),
            "x": None,
            "Z1": None,
            "Z2": None,
            "N1": None,
            "N2": None,
            "W": None,
        }
    if _estado(resultado.termination_condition) != "optimal":
        return {
            "run_index": indice,
            "alpha1": alpha1,
            "alpha2": alpha2,
            "status": str(resultado.termination_condition),
            "x": None,
            "Z1": None,
            "Z2": None,
            "N1": None,
            "N2": None,
            "W": None,
        }

    if resultado.solution_loader:
        resultado.solution_loader.load_vars()
    solucion = {
        nombre: float(pyo.value(variables_pyomo[nombre]))
        for nombre in problema["variables"]
    }

    def evaluar(solucion_actual: dict[str, float]) -> tuple[float, float, float, float, float]:
        z1 = _evaluar_objetivo(problema["objectives"][0], solucion_actual)
        z2 = _evaluar_objetivo(problema["objectives"][1], solucion_actual)
        n1 = normalizar(z1, rangos["Z1_min"], rangos["Z1_max"], problema["objectives"][0]["sense"])
        n2 = normalizar(z2, rangos["Z2_min"], rangos["Z2_max"], problema["objectives"][1]["sense"])
        return z1, z2, n1, n2, alpha1 * n1 + alpha2 * n2

    valores = evaluar(solucion)

    # En un peso extremo se selecciona un representante eficiente de la cara W*.
    ignorado = None
    if alpha1 == 0.0:
        ignorado = 0
    elif alpha2 == 0.0:
        ignorado = 1
    if ignorado is not None:
        modelo.weighted_optimum = pyo.Constraint(expr=expresion_w == valores[4])
        modelo.weighted_objective.deactivate()
        sentido = (
            pyo.maximize
            if problema["objectives"][ignorado]["sense"] == "Maximizar"
            else pyo.minimize
        )
        modelo.representative_objective = pyo.Objective(
            expr=expresiones[ignorado], sense=sentido
        )
        seleccion = Highs().solve(modelo)
        if "optimal" in str(seleccion.termination_condition).lower():
            if seleccion.solution_loader:
                seleccion.solution_loader.load_vars()
            candidata = {
                nombre: float(pyo.value(variables_pyomo[nombre]))
                for nombre in problema["variables"]
            }
            valores_candidatos = evaluar(candidata)
            if abs(valores_candidatos[4] - valores[4]) <= tolerancia:
                solucion = candidata
                valores = valores_candidatos

    return {
        "run_index": indice,
        "alpha1": alpha1,
        "alpha2": alpha2,
        "status": "Optimo",
        "x": solucion,
        "Z1": valores[0],
        "Z2": valores[1],
        "N1": valores[2],
        "N2": valores[3],
        "W": valores[4],
    }


def _clasificar_pareto(
    soluciones: list[dict[str, Any]], sentidos: list[str]
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
                    no_peor.append(candidata[clave] >= solucion[clave] - 1e-4)
                    mejor.append(candidata[clave] > solucion[clave] + 1e-4)
                else:
                    no_peor.append(candidata[clave] <= solucion[clave] + 1e-4)
                    mejor.append(candidata[clave] < solucion[clave] - 1e-4)
            if all(no_peor) and any(mejor):
                solucion["pareto_status"] = f"Dominada (por {candidata['id']})"
                break
    return {
        s["id"]: {
            "x": s["x"],
            "Z1": s["Z1"],
            "Z2": s["Z2"],
            "status": s["pareto_status"],
            "generated_by_weights": s["generated_by_weights"],
        }
        for s in soluciones
    }


def resolver_metodo_ponderaciones(
    problema: dict[str, Any], num_weights: int = 6, tolerancia: float = 1e-6
) -> dict[str, Any]:
    """Aplica la suma ponderada de objetivos normalizados y orientados a MAX."""

    matriz = construir_matriz_pagos(problema, tolerancia)
    rangos = {
        f"Z{k}_{extremo}": funcion(
            matriz["opt_Z1"][f"Z{k}"], matriz["opt_Z2"][f"Z{k}"]
        )
        for k in (1, 2)
        for extremo, funcion in (("min", min), ("max", max))
    }
    rangos["Z1_range"] = rangos["Z1_max"] - rangos["Z1_min"]
    rangos["Z2_range"] = rangos["Z2_max"] - rangos["Z2_min"]
    if rangos["Z1_range"] < TOLERANCIA_RANGO or rangos["Z2_range"] < TOLERANCIA_RANGO:
        raise ValueError("Al menos un objetivo tiene rango de normalizacion nulo.")

    pesos = generar_ponderaciones(num_weights)
    corridas = [
        _resolver_ponderacion(problema, indice, a1, a2, rangos, tolerancia)
        for indice, (a1, a2) in enumerate(pesos, start=1)
    ]

    unicas: list[dict[str, Any]] = []
    for corrida in corridas:
        if corrida["status"] != "Optimo" or corrida["x"] is None:
            continue
        repetida = next(
            (
                u
                for u in unicas
                if all(abs(corrida["x"][v] - u["x"][v]) < 1e-4 for v in problema["variables"])
                and abs(corrida["Z1"] - u["Z1"]) < 1e-4
                and abs(corrida["Z2"] - u["Z2"]) < 1e-4
            ),
            None,
        )
        peso = {"alpha1": corrida["alpha1"], "alpha2": corrida["alpha2"]}
        if repetida:
            repetida["generated_by_weights"].append(peso)
            repetida["count"] += 1
        else:
            unicas.append(
                {
                    "id": chr(ord("A") + len(unicas)),
                    "x": dict(corrida["x"]),
                    "Z1": corrida["Z1"],
                    "Z2": corrida["Z2"],
                    "count": 1,
                    "generated_by_weights": [peso],
                    "pareto_status": "No evaluado",
                }
            )

    clasificacion = _clasificar_pareto(unicas, [o["sense"] for o in problema["objectives"]])
    return {
        "payoff_matrix": matriz,
        "normalization_ranges": rangos,
        "weights": pesos,
        "weighted_runs": corridas,
        "unique_solutions": unicas,
        "pareto_classification": clasificacion,
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
    print("METODO DE PONDERACIONES NORMALIZADAS")
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

    print("\nRangos de normalizacion")
    for objetivo in ("Z1", "Z2"):
        print(
            f"{objetivo}_min={resultado['normalization_ranges'][objetivo + '_min']:.6f}; "
            f"{objetivo}_max={resultado['normalization_ranges'][objetivo + '_max']:.6f}; "
            f"rango={resultado['normalization_ranges'][objetivo + '_range']:.6f}"
        )
    print(f"Pesos: {resultado['weights']}")

    print("\nTabla completa de corridas")
    print("run | alpha1 | alpha2 | estado | variables | Z1 | Z2 | N1 | N2 | W")
    for corrida in resultado["weighted_runs"]:
        vector = "-" if corrida["x"] is None else _formatear_vector(corrida["x"], problema["variables"])
        valores = [corrida[k] for k in ("Z1", "Z2", "N1", "N2", "W")]
        numeros = ["-" if v is None else f"{v:.6f}" for v in valores]
        print(
            f"{corrida['run_index']} | {corrida['alpha1']:.6f} | {corrida['alpha2']:.6f} | "
            f"{corrida['status']} | {vector} | " + " | ".join(numeros)
        )

    print(f"\nSoluciones unicas ({len(resultado['unique_solutions'])})")
    for solucion in resultado["unique_solutions"]:
        pesos = [(p["alpha1"], p["alpha2"]) for p in solucion["generated_by_weights"]]
        print(
            f"{solucion['id']}: pesos={pesos}; Z1={solucion['Z1']:.6f}; "
            f"Z2={solucion['Z2']:.6f}; {solucion['pareto_status']}"
        )
        print(f"  x = {_formatear_vector(solucion['x'], problema['variables'])}")

    print("\nClasificacion Pareto")
    for identificador, datos in resultado["pareto_classification"].items():
        print(f"{identificador}: Z1={datos['Z1']:.6f}; Z2={datos['Z2']:.6f} -> {datos['status']}")


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Metodo portable de ponderaciones normalizadas")
    parser.add_argument("model_file", type=Path, help="Problema biobjetivo en JSON esquema 1.0")
    parser.add_argument("--num-weights", type=int, default=6, help="Numero de ponderaciones (>= 2)")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    argumentos = crear_parser().parse_args(argv)
    try:
        problema = cargar_problema(argumentos.model_file)
        resultado = resolver_metodo_ponderaciones(problema, argumentos.num_weights)
        mostrar_resultados(argumentos.model_file, problema, resultado)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
