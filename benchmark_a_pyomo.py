"""
Benchmark A — Evaluacion multiobjetivo exacta con Pyomo + HiGHS.

Reproduce exactamente el mismo Benchmark A biobjetivo lineal previamente validado
con AMPL + HiGHS, para comparar backends de modelado matematico.

Flujo:
1. Optimizacion independiente de Z1 y Z2 con Pyomo + HiGHS (APPSI).
2. Construccion programatica de la matriz de pagos y rangos de normalizacion.
3. Barrido de 6 combinaciones de ponderaciones normalizadas.
4. Deteccion de soluciones repetidas y clasificacion de dominancia de Pareto.
5. Generacion de graficos (espacio de objetivos y region factible) y exportacion JSON.
6. Aserciones y validaciones estrictas frente a la referencia academica.
7. Medicion de tiempos de ejecucion para comparacion con AMPL.
"""

import os
import sys
import json
import time
from typing import List, Dict, Any

import pyomo
import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


# ---------------------------------------------------------------------------
# Helper: build the base model (variables + constraints, no objective yet)
# ---------------------------------------------------------------------------
def _build_base_model() -> pyo.ConcreteModel:
    """Create a Pyomo ConcreteModel with x1, x2 and the two constraints."""
    m = pyo.ConcreteModel("BenchmarkA")
    m.x1 = pyo.Var(within=pyo.NonNegativeReals)
    m.x2 = pyo.Var(within=pyo.NonNegativeReals)
    m.c1 = pyo.Constraint(expr=m.x1 + m.x2 <= 130)
    m.c2 = pyo.Constraint(expr=2.5 * m.x1 + m.x2 <= 250)
    return m


def run_benchmark_a_pyomo() -> Dict[str, Any]:
    print("=" * 75)
    print("BENCHMARK A (PYOMO): EVALUACION MULTIOBJETIVO EXACTA (Pyomo + HiGHS)")
    print("=" * 75)

    print(f"Interprete Python : {sys.executable}")
    print(f"Version Pyomo     : {pyomo.__version__}")

    solver = Highs()
    print(f"HiGHS disponible  : {solver.available()}")
    import importlib.metadata
    highspy_version = importlib.metadata.version("highspy")
    print(f"Version highspy   : {highspy_version}")
    print("-" * 75)

    tol = 1e-4
    t_total_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Optimizacion individual de Z1
    # ------------------------------------------------------------------
    print("[1/4] Resolviendo Z1 individualmente (MAX 10*x1 + 3*x2)...")
    t_z1_start = time.perf_counter()

    m1 = _build_base_model()
    m1.obj = pyo.Objective(expr=10 * m1.x1 + 3 * m1.x2, sense=pyo.maximize)
    res1 = solver.solve(m1)
    t_z1_end = time.perf_counter()

    x1_at_z1 = float(pyo.value(m1.x1))
    x2_at_z1 = float(pyo.value(m1.x2))
    z1_val_at_z1 = 10.0 * x1_at_z1 + 3.0 * x2_at_z1
    z2_val_at_z1 = 0.8 * x1_at_z1 + 1.3 * x2_at_z1
    z1_term = str(res1.termination_condition)

    print(f"  -> Solucion Z1*: x1 = {x1_at_z1:.4f}, x2 = {x2_at_z1:.4f}")
    print(f"  -> Z1 = {z1_val_at_z1:.4f}, Z2 = {z2_val_at_z1:.4f}")
    print(f"  -> Terminacion: {z1_term}  ({(t_z1_end - t_z1_start)*1000:.1f} ms)")

    assert abs(x1_at_z1 - 100.0) < tol, f"Fallo Z1 opt: x1={x1_at_z1}"
    assert abs(x2_at_z1 - 0.0) < tol, f"Fallo Z1 opt: x2={x2_at_z1}"
    assert abs(z1_val_at_z1 - 1000.0) < tol, f"Fallo Z1 val={z1_val_at_z1}"
    assert abs(z2_val_at_z1 - 80.0) < tol, f"Fallo Z2 cruzado={z2_val_at_z1}"

    # ------------------------------------------------------------------
    # 2. Optimizacion individual de Z2
    # ------------------------------------------------------------------
    print("\n[2/4] Resolviendo Z2 individualmente (MAX 0.8*x1 + 1.3*x2)...")
    t_z2_start = time.perf_counter()

    m2 = _build_base_model()
    m2.obj = pyo.Objective(expr=0.8 * m2.x1 + 1.3 * m2.x2, sense=pyo.maximize)
    res2 = solver.solve(m2)
    t_z2_end = time.perf_counter()

    x1_at_z2 = float(pyo.value(m2.x1))
    x2_at_z2 = float(pyo.value(m2.x2))
    z1_val_at_z2 = 10.0 * x1_at_z2 + 3.0 * x2_at_z2
    z2_val_at_z2 = 0.8 * x1_at_z2 + 1.3 * x2_at_z2
    z2_term = str(res2.termination_condition)

    print(f"  -> Solucion Z2*: x1 = {x1_at_z2:.4f}, x2 = {x2_at_z2:.4f}")
    print(f"  -> Z1 = {z1_val_at_z2:.4f}, Z2 = {z2_val_at_z2:.4f}")
    print(f"  -> Terminacion: {z2_term}  ({(t_z2_end - t_z2_start)*1000:.1f} ms)")

    assert abs(x1_at_z2 - 0.0) < tol, f"Fallo Z2 opt: x1={x1_at_z2}"
    assert abs(x2_at_z2 - 130.0) < tol, f"Fallo Z2 opt: x2={x2_at_z2}"
    assert abs(z1_val_at_z2 - 390.0) < tol, f"Fallo Z1 cruzado={z1_val_at_z2}"
    assert abs(z2_val_at_z2 - 169.0) < tol, f"Fallo Z2 val={z2_val_at_z2}"

    t_individual = (t_z1_end - t_z1_start) + (t_z2_end - t_z2_start)

    # ------------------------------------------------------------------
    # 3. Matriz de pagos y rangos de normalizacion
    # ------------------------------------------------------------------
    payoff_matrix = {
        "opt_Z1": {"x1": x1_at_z1, "x2": x2_at_z1, "Z1": z1_val_at_z1, "Z2": z2_val_at_z1},
        "opt_Z2": {"x1": x1_at_z2, "x2": x2_at_z2, "Z1": z1_val_at_z2, "Z2": z2_val_at_z2},
    }

    z1_max = max(z1_val_at_z1, z1_val_at_z2)
    z1_min = min(z1_val_at_z1, z1_val_at_z2)
    z1_range = z1_max - z1_min

    z2_max = max(z2_val_at_z1, z2_val_at_z2)
    z2_min = min(z2_val_at_z1, z2_val_at_z2)
    z2_range = z2_max - z2_min

    print("-" * 75)
    print("MATRIZ DE PAGOS (PAYOFF MATRIX):")
    print(f"  Optimo Z1 -> Z1 = {z1_val_at_z1:7.2f}, Z2 = {z2_val_at_z1:7.2f}")
    print(f"  Optimo Z2 -> Z1 = {z1_val_at_z2:7.2f}, Z2 = {z2_val_at_z2:7.2f}")
    print(f"\nRANGOS DE NORMALIZACION CALCULADOS:")
    print(f"  Z1_range = {z1_max:.2f} - {z1_min:.2f} = {z1_range:.2f}")
    print(f"  Z2_range = {z2_max:.2f} - {z2_min:.2f} = {z2_range:.2f}")

    assert abs(z1_range - 610.0) < tol, f"Z1_range esperado 610, obtenido {z1_range}"
    assert abs(z2_range - 89.0) < tol, f"Z2_range esperado 89, obtenido {z2_range}"

    # ------------------------------------------------------------------
    # 4. Barrido de ponderaciones normalizadas
    # ------------------------------------------------------------------
    print("\n[3/4] Ejecutando barrido de ponderaciones normalizadas...")
    weights_list = [
        (0.0, 1.0), (0.2, 0.8), (0.4, 0.6),
        (0.6, 0.4), (0.8, 0.2), (1.0, 0.0),
    ]

    expected_results = [
        {"a1": 0.0, "a2": 1.0, "x1": 0.0,   "x2": 130.0, "Z1": 390.0,  "Z2": 169.0},
        {"a1": 0.2, "a2": 0.8, "x1": 0.0,   "x2": 130.0, "Z1": 390.0,  "Z2": 169.0},
        {"a1": 0.4, "a2": 0.6, "x1": 80.0,  "x2": 50.0,  "Z1": 950.0,  "Z2": 129.0},
        {"a1": 0.6, "a2": 0.4, "x1": 80.0,  "x2": 50.0,  "Z1": 950.0,  "Z2": 129.0},
        {"a1": 0.8, "a2": 0.2, "x1": 80.0,  "x2": 50.0,  "Z1": 950.0,  "Z2": 129.0},
        {"a1": 1.0, "a2": 0.0, "x1": 100.0, "x2": 0.0,   "Z1": 1000.0, "Z2": 80.0},
    ]

    weighted_runs: List[Dict[str, Any]] = []

    print("-" * 75)
    print(f"{'a1':>4} | {'a2':>4} | {'x1':>6} | {'x2':>6} | {'Z1':>7} | {'Z2':>7} | {'W':>8} | {'Estado':<12}")
    print("-" * 75)

    t_sweep_start = time.perf_counter()

    for i, (a1, a2) in enumerate(weights_list):
        mw = _build_base_model()
        # W = a1*N1 + a2*N2, con Nk=(Zk-Zk_min)/Zk_range para MAX.
        mw.obj = pyo.Objective(
            expr=a1 * ((10 * mw.x1 + 3 * mw.x2) - z1_min) / z1_range
               + a2 * ((0.8 * mw.x1 + 1.3 * mw.x2) - z2_min) / z2_range,
            sense=pyo.maximize,
        )
        res_w = solver.solve(mw)

        x1_val = float(pyo.value(mw.x1))
        x2_val = float(pyo.value(mw.x2))
        z1_val = 10.0 * x1_val + 3.0 * x2_val
        z2_val = 0.8 * x1_val + 1.3 * x2_val
        n1_val = (z1_val - z1_min) / z1_range
        n2_val = (z2_val - z2_min) / z2_range
        w_val = float(pyo.value(mw.obj.expr))
        term_str = str(res_w.termination_condition)

        run_data = {
            "run_index": i + 1,
            "alpha1": a1,
            "alpha2": a2,
            "x1": x1_val,
            "x2": x2_val,
            "Z1": z1_val,
            "Z2": z2_val,
            "N1": n1_val,
            "N2": n2_val,
            "W": w_val,
            "solve_result": term_str,
        }
        weighted_runs.append(run_data)

        print(f"{a1:4.1f} | {a2:4.1f} | {x1_val:6.1f} | {x2_val:6.1f} | "
              f"{z1_val:7.1f} | {z2_val:7.1f} | {w_val:8.4f} | {term_str:<12}")

        # Strict validation
        exp = expected_results[i]
        assert abs(x1_val - exp["x1"]) < tol, f"x1 fallo para a=({a1},{a2})"
        assert abs(x2_val - exp["x2"]) < tol, f"x2 fallo para a=({a1},{a2})"
        assert abs(z1_val - exp["Z1"]) < tol, f"Z1 fallo para a=({a1},{a2})"
        assert abs(z2_val - exp["Z2"]) < tol, f"Z2 fallo para a=({a1},{a2})"

    t_sweep_end = time.perf_counter()
    t_sweep = t_sweep_end - t_sweep_start

    # ------------------------------------------------------------------
    # 5. Soluciones unicas y dominancia de Pareto
    # ------------------------------------------------------------------
    print("\n[4/4] Analizando soluciones unicas y dominancia de Pareto...")
    unique_solutions: List[Dict[str, Any]] = []

    for run in weighted_runs:
        matched = False
        for u in unique_solutions:
            if (abs(run["x1"] - u["x1"]) < tol and
                abs(run["x2"] - u["x2"]) < tol and
                abs(run["Z1"] - u["Z1"]) < tol and
                abs(run["Z2"] - u["Z2"]) < tol):
                u["generated_by_weights"].append({"alpha1": run["alpha1"], "alpha2": run["alpha2"]})
                u["count"] += 1
                matched = True
                break
        if not matched:
            unique_solutions.append({
                "id": chr(ord('A') + len(unique_solutions)),
                "x1": run["x1"], "x2": run["x2"],
                "Z1": run["Z1"], "Z2": run["Z2"],
                "count": 1,
                "generated_by_weights": [{"alpha1": run["alpha1"], "alpha2": run["alpha2"]}],
                "pareto_status": "No evaluado",
            })

    print("-" * 75)
    print(f"Soluciones unicas detectadas ({len(unique_solutions)}):")
    for u in unique_solutions:
        ws = ", ".join(f"({w['alpha1']:.1f}, {w['alpha2']:.1f})" for w in u["generated_by_weights"])
        print(f"  Solucion {u['id']}: (x1={u['x1']:.1f}, x2={u['x2']:.1f}) "
              f"-> Z1={u['Z1']:.1f}, Z2={u['Z2']:.1f} | Ponderaciones: {ws}")

    assert len(unique_solutions) == 3, f"Esperadas 3 unicas, obtenidas {len(unique_solutions)}"

    # Pareto dominance (both MAX)
    for i, sa in enumerate(unique_solutions):
        dominated = False
        for j, sb in enumerate(unique_solutions):
            if i == j:
                continue
            ge1 = sb["Z1"] >= sa["Z1"] - tol
            ge2 = sb["Z2"] >= sa["Z2"] - tol
            strict = (sb["Z1"] > sa["Z1"] + tol) or (sb["Z2"] > sa["Z2"] + tol)
            if ge1 and ge2 and strict:
                dominated = True
                sa["pareto_status"] = f"Dominada (por {sb['id']})"
                break
        if not dominated:
            sa["pareto_status"] = "No dominada"

    print("\nClasificacion de Pareto:")
    for u in unique_solutions:
        print(f"  Solucion {u['id']}: Z = ({u['Z1']:.1f}, {u['Z2']:.1f}) -> {u['pareto_status']}")
        assert u["pareto_status"] == "No dominada", f"Solucion {u['id']} deberia ser no dominada"

    t_total_end = time.perf_counter()
    t_total = t_total_end - t_total_start

    # ------------------------------------------------------------------
    # 6. Graficos
    # ------------------------------------------------------------------
    os.makedirs("results", exist_ok=True)

    # --- Grafico 1: Espacio de Objetivos ---
    fig_obj, ax_obj = plt.subplots(figsize=(9, 6), dpi=300)
    nd_sorted = sorted(unique_solutions, key=lambda s: s["Z1"])
    ax_obj.plot([s["Z1"] for s in nd_sorted], [s["Z2"] for s in nd_sorted],
                color="#1f77b4", linestyle="--", linewidth=1.5,
                label="Aproximacion discreta (soluciones no dominadas)", zorder=2)

    for u in unique_solutions:
        ax_obj.scatter(u["Z1"], u["Z2"], color="#d62728", s=100, zorder=4, edgecolor="black")
        wt = "\n".join(f"a=({w['alpha1']:.1f}, {w['alpha2']:.1f})" for w in u["generated_by_weights"])
        offset = (12, -8) if u['id'] == 'A' else ((12, 12) if u['id'] == 'B' else (12, -25))
        ax_obj.annotate(
            f"Solucion {u['id']}\nZ=({u['Z1']:.0f}, {u['Z2']:.0f})\n{wt}",
            (u["Z1"], u["Z2"]), textcoords="offset points", xytext=offset,
            fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="#f8f9fa", ec="#cccccc", alpha=0.9),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#666666"))

    ax_obj.set_title("Benchmark A (Pyomo) -- Soluciones por metodo de ponderaciones",
                     fontsize=12, fontweight="bold", pad=15)
    ax_obj.set_xlabel("Objetivo Z1 (10*x1 + 3*x2) [MAX]", fontsize=10, fontweight="bold")
    ax_obj.set_ylabel("Objetivo Z2 (0.8*x1 + 1.3*x2) [MAX]", fontsize=10, fontweight="bold")
    ax_obj.set_xlim(300, 1100); ax_obj.set_ylim(60, 190)
    ax_obj.grid(True, linestyle=":", alpha=0.6); ax_obj.legend(loc="upper right")
    fig_obj.tight_layout()
    fig_obj.savefig(os.path.join("results", "benchmark_a_pyomo_objective_space.png"))
    plt.close(fig_obj)
    print(f"\n[Grafico guardado] results/benchmark_a_pyomo_objective_space.png")

    # --- Grafico 2: Region Factible ---
    fig_f, ax_f = plt.subplots(figsize=(9, 6), dpi=300)
    ax_f.plot([0, 130], [130, 0], label=r"$x_1 + x_2 \leq 130$",
              color="#2ca02c", linewidth=1.5)
    ax_f.plot([0, 100], [250, 0], label=r"$2.5x_1 + x_2 \leq 250$",
              color="#ff7f0e", linewidth=1.5)
    poly = Polygon([(0, 0), (100, 0), (80, 50), (0, 130)], closed=True,
                   facecolor="#e8f4f8", edgecolor="#1f77b4", linewidth=1.5,
                   label="Region Factible", alpha=0.7, zorder=1)
    ax_f.add_patch(poly)
    for u in unique_solutions:
        ax_f.scatter(u["x1"], u["x2"], color="#d62728", s=90, zorder=4, edgecolor="black")
        offset = (-55, 10) if u['id'] == 'C' else (10, 10)
        ax_f.annotate(f"Solucion {u['id']}\n({u['x1']:.0f}, {u['x2']:.0f})",
                      (u["x1"], u["x2"]), textcoords="offset points", xytext=offset,
                      fontsize=8.5, fontweight="bold",
                      bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#333333", alpha=0.9),
                      arrowprops=dict(arrowstyle="->", color="#333333"))
    ax_f.set_title("Benchmark A (Pyomo) -- Region Factible y Soluciones Optimas",
                   fontsize=12, fontweight="bold", pad=15)
    ax_f.set_xlabel("Variable $x_1$", fontsize=10, fontweight="bold")
    ax_f.set_ylabel("Variable $x_2$", fontsize=10, fontweight="bold")
    ax_f.set_xlim(-5, 140); ax_f.set_ylim(-5, 160)
    ax_f.grid(True, linestyle=":", alpha=0.6); ax_f.legend(loc="upper right")
    fig_f.tight_layout()
    fig_f.savefig(os.path.join("results", "benchmark_a_pyomo_feasible_region.png"))
    plt.close(fig_f)
    print(f"[Grafico guardado] results/benchmark_a_pyomo_feasible_region.png")

    # ------------------------------------------------------------------
    # 7. Exportacion JSON
    # ------------------------------------------------------------------
    benchmark_data = {
        "metadata": {
            "benchmark_name": "Benchmark A -- Pyomo + HiGHS Weighted Sum",
            "date": "2026-08-23",
            "python_version": sys.version,
            "pyomo_version": pyomo.__version__,
            "highspy_version": highspy_version,
            "solver": f"HiGHS ({highspy_version})",
            "problem_type": "Biobjective Continuous LP",
        },
        "individual_optima": {
            "Z1_max": {"x1": x1_at_z1, "x2": x2_at_z1,
                       "Z1": z1_val_at_z1, "Z2": z2_val_at_z1,
                       "termination": z1_term},
            "Z2_max": {"x1": x1_at_z2, "x2": x2_at_z2,
                       "Z1": z1_val_at_z2, "Z2": z2_val_at_z2,
                       "termination": z2_term},
        },
        "payoff_matrix": payoff_matrix,
        "normalization_ranges": {
            "Z1_max": z1_max, "Z1_min": z1_min, "Z1_range": z1_range,
            "Z2_max": z2_max, "Z2_min": z2_min, "Z2_range": z2_range,
        },
        "weighted_runs": weighted_runs,
        "unique_solutions": unique_solutions,
        "pareto_classification": {
            s["id"]: {"x": [s["x1"], s["x2"]], "Z": [s["Z1"], s["Z2"]],
                      "status": s["pareto_status"],
                      "generated_by_weights": s["generated_by_weights"]}
            for s in unique_solutions
        },
        "timing": {
            "individual_optima_sec": round(t_individual, 4),
            "weighted_sweep_sec": round(t_sweep, 4),
            "total_sec": round(t_total, 4),
        },
    }

    json_path = os.path.join("results", "benchmark_a_pyomo_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
    print(f"[Resultados guardados] {json_path}")

    print("-" * 75)
    print("TIEMPOS DE EJECUCION (Pyomo + HiGHS):")
    print(f"  Optimizacion individual : {t_individual*1000:.1f} ms")
    print(f"  Barrido 6 ponderaciones : {t_sweep*1000:.1f} ms")
    print(f"  Total benchmark         : {t_total*1000:.1f} ms")

    print("=" * 75)
    print("[EXITO TOTAL] Benchmark A (Pyomo) validado al 100% contra referencia.")
    print("=" * 75)

    return benchmark_data


if __name__ == "__main__":
    run_benchmark_a_pyomo()
