"""Verifica que una preview indexada obsoleta nunca pueda aplicarse."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from solver_optimizador.indexed_application import (
    IndexedPreviewSynchronizationError,
    apply_indexed_preview_if_current,
)
from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_model import build_indexed_spec_signature
from solver_optimizador.indexed_text_io import parse_indexed_tables


def spec_from_csv(value: float, *, reverse_values: bool = False):
    values = [(1, 10), (2, value), (3, 30)]
    if reverse_values:
        values.reverse()
    parameters = ["parameter,index_set,index,value"]
    parameters.extend(f"cap,T,{index},{number}" for index, number in values)
    return parse_indexed_tables(
        name="Sincronizacion reproducible",
        description="Firma de la fuente efectiva",
        sets_text="name,start,end\nT,1,3",
        scalar_parameters_text="name,value",
        indexed_parameters_text="\n".join(parameters),
        variable_families_text="family,index_set\nX,T",
        objectives_text=(
            "objective,sense,variable_family,index_set,start_index,end_index,coefficient\n"
            "Z,Maximizar,X,T,1,3,1"
        ),
        constraint_families_text=(
            "name,index_set,index_symbol,start_index,end_index,expression\n"
            "Cap,T,t,1,3,X[t] <= cap[t]"
        ),
    )


def main() -> None:
    spec_a = spec_from_csv(20)
    preview_a = compile_indexed_model(spec_a)
    signature_a = build_indexed_spec_signature(spec_a)

    spec_b = spec_from_csv(999)
    signature_b = build_indexed_spec_signature(spec_b)
    assert signature_a != signature_b
    print(f"CASE A PASS: parameter change produces distinct signatures ({signature_a[:12]} != {signature_b[:12]})")

    sentinel = object()
    state = {
        "var_names": ["old"],
        "constraints_data": [{"name": "old", "coefficients": {}, "operator": "<=", "rhs": 1}],
        "last_solution": sentinel,
        "editor_version": 5,
    }
    before = {
        "var_names": list(state["var_names"]),
        "constraints_data": list(state["constraints_data"]),
        "last_solution": state["last_solution"],
        "editor_version": state["editor_version"],
    }
    try:
        apply_indexed_preview_if_current(state, preview_a, spec_b, signature_a)
    except IndexedPreviewSynchronizationError:
        pass
    else:
        raise AssertionError("A stale preview was applied")
    assert state["var_names"] == before["var_names"]
    assert state["constraints_data"] == before["constraints_data"]
    assert state["last_solution"] is before["last_solution"]
    assert state["editor_version"] == before["editor_version"]
    print("CASE B PASS: preview A + effective CSV/spec B blocked with zero state mutation")

    preview_b = compile_indexed_model(spec_b)
    apply_indexed_preview_if_current(state, preview_b, spec_b, signature_b)
    constraints = {row["name"]: row for row in state["constraints_data"]}
    assert constraints["Cap_2"]["rhs"] == 999.0
    assert state["indexed_source_status"] == "synchronized"
    print("CASE C PASS: recompiled B applied; Cap_2 rhs=999; source=synchronized")

    reordered = spec_from_csv(20, reverse_values=True)
    reordered_signature = build_indexed_spec_signature(reordered)
    assert reordered_signature == signature_a
    print("CASE D PASS: parameter value dictionary order does not alter signature")
    print("RESULT: PASS (indexed preview synchronization contract satisfied)")


if __name__ == "__main__":
    main()
