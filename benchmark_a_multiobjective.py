"""
Benchmark A — Evaluación multiobjetivo exacta con AMPL + HiGHS.

Este script ejecuta el flujo completo de optimización biobjetivo lineal:
1. Optimización independiente de Z1 y Z2 con HiGHS.
2. Construcción programática de la matriz de pagos y cálculo de rangos de normalización.
3. Barrido de 6 combinaciones de ponderaciones normalizadas.
4. Detección programática de soluciones repetidas y clasificación de dominancia de Pareto.
5. Generación de gráficos (espacio de objetivos y región factible) y exportación JSON.
6. Aserciones y validaciones matemáticas estrictas frente a la referencia académica.
"""

import os
import sys
import json
import time
from typing import List, Dict, Any, Tuple
import matplotlib
matplotlib.use("Agg")  # Backend sin interfaz gráfica
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


def run_benchmark_a() -> Dict[str, Any]:
    print("=" * 75)
    print("BENCHMARK A: EVALUACIÓN MULTIOBJETIVO EXACTA (AMPL + HiGHS)")
    print("=" * 75)

    # 1. Carga de amplpy y módulos
    try:
        import amplpy
        from amplpy import AMPL, modules
    except ImportError as exc:
        print(f"[ERROR] No se pudo importar amplpy: {exc}")
        sys.exit(1)

    modules.load()
    ampl = AMPL()
    ampl.option["solver"] = "highs"

    print(f"Intérprete Python: {sys.executable}")
    print(f"Versión amplpy   : {amplpy.__version__}")
    print(f"AMPL Engine      : {ampl.get_value('_version')}")
    print(f"Solver           : HiGHS (ampl-module-highs)")
    print("-" * 75)

    tol = 1e-4
    t_total_start = time.perf_counter()
    # 2. Formulación del modelo base en AMPL
    model_decl = """
    reset;
    var x1 >= 0;
    var x2 >= 0;

    s.t. c1: x1 + x2 <= 130;
    s.t. c2: 2.5*x1 + x2 <= 250;

    maximize Obj1: 10*x1 + 3*x2;
    maximize Obj2: 0.8*x1 + 1.3*x2;
    """
    ampl.eval(model_decl)

    # 3. Optimización individual de Z1
    print("[1/4] Resolviendo Z1 individualmente (MAX 10*x1 + 3*x2)...")
    t_z1_start = time.perf_counter()
    ampl.eval("objective Obj1; solve;")
    t_z1_end = time.perf_counter()
    z1_opt_solve_res = str(ampl.get_value("solve_result"))
    x1_at_z1 = float(ampl.get_variable("x1").value())
    x2_at_z1 = float(ampl.get_variable("x2").value())
    z1_val_at_z1 = 10.0 * x1_at_z1 + 3.0 * x2_at_z1
    z2_val_at_z1 = 0.8 * x1_at_z1 + 1.3 * x2_at_z1

    print(f"  -> Solucion Z1*: x1 = {x1_at_z1:.4f}, x2 = {x2_at_z1:.4f}")
    print(f"  -> Z1 = {z1_val_at_z1:.4f}, Z2 = {z2_val_at_z1:.4f} (estado: {z1_opt_solve_res})")

    # 4. Optimización individual de Z2
    print("\n[2/4] Resolviendo Z2 individualmente (MAX 0.8*x1 + 1.3*x2)...")
    t_z2_start = time.perf_counter()
    ampl.eval("objective Obj2; solve;")
    t_z2_end = time.perf_counter()
    z2_opt_solve_res = str(ampl.get_value("solve_result"))
    x1_at_z2 = float(ampl.get_variable("x1").value())
    x2_at_z2 = float(ampl.get_variable("x2").value())
    z1_val_at_z2 = 10.0 * x1_at_z2 + 3.0 * x2_at_z2
    z2_val_at_z2 = 0.8 * x1_at_z2 + 1.3 * x2_at_z2

    print(f"  -> Solucion Z2*: x1 = {x1_at_z2:.4f}, x2 = {x2_at_z2:.4f}")
    print(f"  -> Z1 = {z1_val_at_z2:.4f}, Z2 = {z2_val_at_z2:.4f} (estado: {z2_opt_solve_res})")

    t_individual = (t_z1_end - t_z1_start) + (t_z2_end - t_z2_start)

    # Validaciones obligatorias de óptimos individuales
    assert abs(x1_at_z1 - 100.0) < tol and abs(x2_at_z1 - 0.0) < tol, "Fallo en optimo individual Z1 (x)"
    assert abs(z1_val_at_z1 - 1000.0) < tol and abs(z2_val_at_z1 - 80.0) < tol, "Fallo en valores Z1, Z2 en optimo Z1"
    assert abs(x1_at_z2 - 0.0) < tol and abs(x2_at_z2 - 130.0) < tol, "Fallo en optimo individual Z2 (x)"
    assert abs(z1_val_at_z2 - 390.0) < tol and abs(z2_val_at_z2 - 169.0) < tol, "Fallo en valores Z1, Z2 en optimo Z2"

    # 5. Construcción de la matriz de pagos y rangos de normalización
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
    print(f"  Óptimo Z1 -> Z1 = {z1_val_at_z1:7.2f}, Z2 = {z2_val_at_z1:7.2f}")
    print(f"  Óptimo Z2 -> Z1 = {z1_val_at_z2:7.2f}, Z2 = {z2_val_at_z2:7.2f}")
    print(f"\nRANGOS DE NORMALIZACIÓN CALCULADOS:")
    print(f"  Z1_range = {z1_max:.2f} - {z1_min:.2f} = {z1_range:.2f}")
    print(f"  Z2_range = {z2_max:.2f} - {z2_min:.2f} = {z2_range:.2f}")

    assert abs(z1_range - 610.0) < tol, f"Z1_range esperado 610.0, obtenido {z1_range}"
    assert abs(z2_range - 89.0) < tol, f"Z2_range esperado 89.0, obtenido {z2_range}"

    # 6. Método de Suma Ponderada Normalizada (6 combinaciones)
    print("\n[3/4] Ejecutando barrido de ponderaciones normalizadas...")
    weights_list = [
        (0.0, 1.0),
        (0.2, 0.8),
        (0.4, 0.6),
        (0.6, 0.4),
        (0.8, 0.2),
        (1.0, 0.0)
    ]

    expected_results = [
        {"alpha1": 0.0, "alpha2": 1.0, "x1": 0.0, "x2": 130.0, "Z1": 390.0, "Z2": 169.0},
        {"alpha1": 0.2, "alpha2": 0.8, "x1": 0.0, "x2": 130.0, "Z1": 390.0, "Z2": 169.0},
        {"alpha1": 0.4, "alpha2": 0.6, "x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"alpha1": 0.6, "alpha2": 0.4, "x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"alpha1": 0.8, "alpha2": 0.2, "x1": 80.0, "x2": 50.0, "Z1": 950.0, "Z2": 129.0},
        {"alpha1": 1.0, "alpha2": 0.0, "x1": 100.0, "x2": 0.0, "Z1": 1000.0, "Z2": 80.0}
    ]

    # Declarar parámetros y objetivo ponderado en AMPL
    ampl.eval(f"""
    param a1;
    param a2;
    param r1 default {z1_range};
    param r2 default {z2_range};
    maximize W: a1 * (10*x1 + 3*x2) / r1 + a2 * (0.8*x1 + 1.3*x2) / r2;
    objective W;
    """)

    weighted_runs: List[Dict[str, Any]] = []

    print("-" * 75)
    print(f"{'a1':>4} | {'a2':>4} | {'x1':>6} | {'x2':>6} | {'Z1':>7} | {'Z2':>7} | {'W':>8} | {'Estado':<8}")
    print("-" * 75)

    t_sweep_start = time.perf_counter()

    for i, (a1, a2) in enumerate(weights_list):
        ampl.param["a1"] = a1
        ampl.param["a2"] = a2
        ampl.solve()

        res_state = str(ampl.get_value("solve_result"))
        x1_val = float(ampl.get_variable("x1").value())
        x2_val = float(ampl.get_variable("x2").value())
        z1_val = 10.0 * x1_val + 3.0 * x2_val
        z2_val = 0.8 * x1_val + 1.3 * x2_val
        w_val = float(ampl.get_objective("W").value())

        run_data = {
            "run_index": i + 1,
            "alpha1": a1,
            "alpha2": a2,
            "x1": round(x1_val, 4),
            "x2": round(x2_val, 4),
            "Z1": round(z1_val, 4),
            "Z2": round(z2_val, 4),
            "W": round(w_val, 6),
            "solve_result": res_state
        }
        weighted_runs.append(run_data)

        print(f"{a1:4.1f} | {a2:4.1f} | {x1_val:6.1f} | {x2_val:6.1f} | {z1_val:7.1f} | {z2_val:7.1f} | {w_val:8.4f} | {res_state:<8}")

        # Comparación estricta con la referencia académica
        exp = expected_results[i]
        assert abs(x1_val - exp["x1"]) < tol, f"Fallo en x1 para alpha=({a1},{a2})"
        assert abs(x2_val - exp["x2"]) < tol, f"Fallo en x2 para alpha=({a1},{a2})"
        assert abs(z1_val - exp["Z1"]) < tol, f"Fallo en Z1 para alpha=({a1},{a2})"
        assert abs(z2_val - exp["Z2"]) < tol, f"Fallo en Z2 para alpha=({a1},{a2})"

    t_sweep_end = time.perf_counter()
    t_sweep = t_sweep_end - t_sweep_start

    ampl.close()

    # 7. Detección programática de soluciones repetidas y agrupación de soluciones únicas
    print("\n[4/4] Analizando soluciones únicas y dominancia de Pareto...")
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
                "x1": run["x1"],
                "x2": run["x2"],
                "Z1": run["Z1"],
                "Z2": run["Z2"],
                "count": 1,
                "generated_by_weights": [{"alpha1": run["alpha1"], "alpha2": run["alpha2"]}],
                "pareto_status": "No evaluado"
            })

    print("-" * 75)
    print(f"Soluciones unicas detectadas ({len(unique_solutions)}):")
    for u in unique_solutions:
        weights_str = ", ".join([f"({w['alpha1']:.1f}, {w['alpha2']:.1f})" for w in u["generated_by_weights"]])
        print(f"  Solucion {u['id']}: (x1={u['x1']:.1f}, x2={u['x2']:.1f}) -> Z1={u['Z1']:.1f}, Z2={u['Z2']:.1f} | Ponderaciones: {weights_str}")

    assert len(unique_solutions) == 3, f"Se esperaban 3 soluciones unicas, obtenidas {len(unique_solutions)}"

    # 8. Evaluacion Algoritmica de Dominancia de Pareto
    # Para MAX Z1 y MAX Z2: A domina a B si Z1(A) >= Z1(B) y Z2(A) >= Z2(B) y al menos una desigualdad estricta.
    for i, sol_a in enumerate(unique_solutions):
        is_dominated = False
        dominator_id = None
        for j, sol_b in enumerate(unique_solutions):
            if i == j:
                continue
            z1_b_ge_a = sol_b["Z1"] >= sol_a["Z1"] - tol
            z2_b_ge_a = sol_b["Z2"] >= sol_a["Z2"] - tol
            strict_b = (sol_b["Z1"] > sol_a["Z1"] + tol) or (sol_b["Z2"] > sol_a["Z2"] + tol)
            if z1_b_ge_a and z2_b_ge_a and strict_b:
                is_dominated = True
                dominator_id = sol_b["id"]
                break

        if is_dominated:
            sol_a["pareto_status"] = f"Dominada (por {dominator_id})"
        else:
            sol_a["pareto_status"] = "No dominada"

    print("\nClasificacion de Pareto:")
    for u in unique_solutions:
        print(f"  Solucion {u['id']}: Z = ({u['Z1']:.1f}, {u['Z2']:.1f}) -> {u['pareto_status']}")
        assert u["pareto_status"] == "No dominada", f"La solucion {u['id']} deberia ser no dominada"

    # 9. Generacion de Graficos con Matplotlib
    os.makedirs("results", exist_ok=True)

    # --- Grafico 1: Espacio de Objetivos (Z1 vs Z2) ---
    fig_obj, ax_obj = plt.subplots(figsize=(9, 6), dpi=300)

    # Ordenar soluciones no dominadas por Z1 para trazar la linea de aproximacion discreta
    non_dominated_sorted = sorted(unique_solutions, key=lambda s: s["Z1"])
    z1_line = [s["Z1"] for s in non_dominated_sorted]
    z2_line = [s["Z2"] for s in non_dominated_sorted]

    # Linea de ayuda visual
    ax_obj.plot(z1_line, z2_line, color="#1f77b4", linestyle="--", linewidth=1.5,
                label="Aproximacion discreta (soluciones no dominadas)", zorder=2)

    # Puntos unicos no dominados
    for u in unique_solutions:
        ax_obj.scatter(u["Z1"], u["Z2"], color="#d62728", s=100, zorder=4, edgecolor="black")
        weights_text = "\n".join([f"a=({w['alpha1']:.1f}, {w['alpha2']:.1f})" for w in u["generated_by_weights"]])
        offset = (12, -8) if u['id'] == 'A' else ((12, 12) if u['id'] == 'B' else (12, -25))
        ax_obj.annotate(
            f"Solucion {u['id']}\nZ=({u['Z1']:.0f}, {u['Z2']:.0f})\n{weights_text}",
            (u["Z1"], u["Z2"]),
            textcoords="offset points",
            xytext=offset,
            fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="#f8f9fa", ec="#cccccc", alpha=0.9),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#666666")
        )

    ax_obj.set_title("Benchmark A — Soluciones obtenidas por método de ponderaciones", fontsize=12, fontweight="bold", pad=15)
    ax_obj.set_xlabel("Objetivo Z1 (10*x1 + 3*x2) [MAX]", fontsize=10, fontweight="bold")
    ax_obj.set_ylabel("Objetivo Z2 (0.8*x1 + 1.3*x2) [MAX]", fontsize=10, fontweight="bold")
    ax_obj.set_xlim(300, 1100)
    ax_obj.set_ylim(60, 190)
    ax_obj.grid(True, linestyle=":", alpha=0.6)
    ax_obj.legend(loc="upper right", frameon=True)
    fig_obj.tight_layout()

    obj_space_path = os.path.join("results", "benchmark_a_objective_space.png")
    fig_obj.savefig(obj_space_path)
    plt.close(fig_obj)
    print(f"\n[Gráfico guardado] Espacio de Objetivos: {obj_space_path}")

    # --- Gráfico 2: Región Factible (x1 vs x2) ---
    fig_feas, ax_feas = plt.subplots(figsize=(9, 6), dpi=300)

    # Dibujar lineas de restriccion
    # c1: x1 + x2 <= 130 -> x2 = 130 - x1
    # c2: 2.5*x1 + x2 <= 250 -> x2 = 250 - 2.5*x1
    ax_feas.plot([0, 130], [130, 0], label=r"$x_1 + x_2 \leq 130$", color="#2ca02c", linewidth=1.5, linestyle="-")
    ax_feas.plot([0, 100], [250, 0], label=r"$2.5x_1 + x_2 \leq 250$", color="#ff7f0e", linewidth=1.5, linestyle="-")

    # Polígono de región factible: (0,0) -> (100,0) -> (80,50) -> (0,130)
    feasible_polygon = Polygon([(0, 0), (100, 0), (80, 50), (0, 130)],
                               closed=True, facecolor="#e8f4f8", edgecolor="#1f77b4", linewidth=1.5,
                               label="Región Factible", alpha=0.7, zorder=1)
    ax_feas.add_patch(feasible_polygon)

    # Vertices optimos encontrados
    for u in unique_solutions:
        ax_feas.scatter(u["x1"], u["x2"], color="#d62728", s=90, zorder=4, edgecolor="black")
        label_text = f"Solucion {u['id']}\n({u['x1']:.0f}, {u['x2']:.0f})"
        offset = (-55, 10) if u['id'] == 'C' else (10, 10)
        ax_feas.annotate(
            label_text,
            (u["x1"], u["x2"]),
            textcoords="offset points",
            xytext=offset,
            fontsize=8.5,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#333333", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="#333333")
        )

    ax_feas.set_title("Benchmark A — Región Factible y Soluciones Óptimas", fontsize=12, fontweight="bold", pad=15)
    ax_feas.set_xlabel("Variable de Decisión $x_1$", fontsize=10, fontweight="bold")
    ax_feas.set_ylabel("Variable de Decisión $x_2$", fontsize=10, fontweight="bold")
    ax_feas.set_xlim(-5, 140)
    ax_feas.set_ylim(-5, 160)
    ax_feas.grid(True, linestyle=":", alpha=0.6)
    ax_feas.legend(loc="upper right", frameon=True)
    fig_feas.tight_layout()

    feas_reg_path = os.path.join("results", "benchmark_a_feasible_region.png")
    fig_feas.savefig(feas_reg_path)
    plt.close(fig_feas)
    print(f"[Gráfico guardado] Región Factible: {feas_reg_path}")

    # 10. Exportación de Resultados Estructurados en JSON
    benchmark_data = {
        "metadata": {
            "benchmark_name": "Benchmark A — Multiobjective Normalized Weighted Sum",
            "date": "2026-08-23",
            "python_version": sys.version,
            "amplpy_version": amplpy.__version__,
            "solver": "HiGHS (1.15.1)",
            "problem_type": "Biobjective Continuous LP"
        },
        "individual_optima": {
            "Z1_max": {"x1": x1_at_z1, "x2": x2_at_z1, "Z1": z1_val_at_z1, "Z2": z2_val_at_z1, "solve_result": z1_opt_solve_res},
            "Z2_max": {"x1": x1_at_z2, "x2": x2_at_z2, "Z1": z1_val_at_z2, "Z2": z2_val_at_z2, "solve_result": z2_opt_solve_res}
        },
        "payoff_matrix": payoff_matrix,
        "normalization_ranges": {
            "Z1_max": z1_max,
            "Z1_min": z1_min,
            "Z1_range": z1_range,
            "Z2_max": z2_max,
            "Z2_min": z2_min,
            "Z2_range": z2_range
        },
        "weighted_runs": weighted_runs,
        "unique_solutions": unique_solutions,
        "pareto_classification": {
            sol["id"]: {
                "x": [sol["x1"], sol["x2"]],
                "Z": [sol["Z1"], sol["Z2"]],
                "status": sol["pareto_status"],
                "generated_by_weights": sol["generated_by_weights"]
            }
            for sol in unique_solutions
        }
    }

    t_total_end = time.perf_counter()
    t_total = t_total_end - t_total_start

    # Add timing to benchmark_data before saving JSON
    benchmark_data["timing"] = {
        "individual_optima_sec": round(t_individual, 4),
        "weighted_sweep_sec": round(t_sweep, 4),
        "total_sec": round(t_total, 4),
    }

    json_path = os.path.join("results", "benchmark_a_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
    print(f"[Resultados guardados] JSON estructurado: {json_path}")

    print("-" * 75)
    print("TIEMPOS DE EJECUCION (AMPL + HiGHS):")
    print(f"  Optimizacion individual : {t_individual*1000:.1f} ms")
    print(f"  Barrido 6 ponderaciones : {t_sweep*1000:.1f} ms")
    print(f"  Total benchmark         : {t_total*1000:.1f} ms")

    print("=" * 75)
    print("[EXITO TOTAL] Benchmark A completado y validado al 100% contra referencia.")
    print("=" * 75)

    return benchmark_data


if __name__ == "__main__":
    run_benchmark_a()
