"""Verifica la expansion estructural de familias indexadas a escala."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from solver_optimizador.indexed_compiler import compile_indexed_model
from solver_optimizador.indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    VariableFamilySpec,
)


def main() -> None:
    size = 1000
    spec = IndexedModelSpec(
        name="Contrato de escala indexado",
        sets=(IndexSetSpec("T", 1, size),),
        indexed_parameters=(
            IndexedParameterSpec("cap", "T", {index: 100.0 for index in range(1, size + 1)}),
        ),
        variable_families=tuple(VariableFamilySpec(name, "T") for name in ("X", "Y", "Z")),
        objectives=(
            IndexedObjectiveSpec("Objetivo", "Minimizar", (ObjectiveTermSpec("X", "T"),)),
        ),
        constraint_families=(
            ConstraintFamilySpec("LimiteX", "T", "t", "X[t] <= cap[t]"),
            ConstraintFamilySpec("LimiteY", "T", "t", "Y[t] <= cap[t]"),
            ConstraintFamilySpec("LimiteZ", "T", "t", "Z[t] <= cap[t]"),
            ConstraintFamilySpec("MezclaXY", "T", "t", "X[t] + Y[t] <= cap[t]"),
            ConstraintFamilySpec("MezclaYZ", "T", "t", "Y[t] + Z[t] <= cap[t]"),
        ),
    )
    expanded = compile_indexed_model(spec)
    stats = expanded.statistics
    assert stats["generated_variables"] == 3000
    assert stats["generated_constraints"] == 5000
    assert stats["nonzero_coefficients"] == 7000
    assert max(len(row["coefficients"]) for row in expanded.constraints) == 2
    print(f"set_size={size}")
    print(f"variable_families={stats['variable_families']}")
    print(f"generated_variables={stats['generated_variables']}")
    print(f"constraint_families={stats['constraint_families']}")
    print(f"generated_constraints={stats['generated_constraints']}")
    print(f"nonzeros={stats['nonzero_coefficients']}")
    print(f"density={stats['density']:.8f}")
    print("RESULT: PASS (indexed model scaling contract satisfied)")


if __name__ == "__main__":
    main()
