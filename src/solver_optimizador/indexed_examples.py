"""Especificaciones indexadas reproducibles usadas por UI, tests y auditoria."""

from __future__ import annotations

from .indexed_model import (
    ConstraintFamilySpec,
    IndexedModelSpec,
    IndexedObjectiveSpec,
    IndexedParameterSpec,
    IndexSetSpec,
    ObjectiveTermSpec,
    ScalarParameterSpec,
    VariableFamilySpec,
)


def production_planning_example_spec(periods: int = 6) -> IndexedModelSpec:
    """Ejemplo academico pequeño de produccion e inventario multiperiodo."""

    demand = {index: float(4 + index) for index in range(1, periods + 1)}
    capacity = {index: 10.0 for index in range(1, periods + 1)}
    return IndexedModelSpec(
        name=f"Planificacion de produccion ({periods} periodos)",
        description="Ejemplo academico indexado; datos ilustrativos.",
        sets=(IndexSetSpec("T", 1, periods),),
        scalar_parameters=(ScalarParameterSpec("I0", 2.0),),
        indexed_parameters=(
            IndexedParameterSpec("demanda", "T", demand),
            IndexedParameterSpec("capacidad", "T", capacity),
            IndexedParameterSpec("costo", "T", {index: 1.0 + index / 10 for index in demand}),
        ),
        variable_families=(VariableFamilySpec("x", "T"), VariableFamilySpec("inventario", "T")),
        objectives=(
            IndexedObjectiveSpec(
                "Z",
                "Minimizar",
                (
                    ObjectiveTermSpec("x", "T", "costo[t]"),
                    ObjectiveTermSpec("inventario", "T", "0.05"),
                ),
            ),
        ),
        constraint_families=(
            ConstraintFamilySpec(
                "BalanceInicial", "T", "t",
                "x[t] - inventario[t] = demanda[t] - I0", 1, 1,
            ),
            ConstraintFamilySpec(
                "Balance", "T", "t",
                "inventario[t-1] + x[t] - inventario[t] = demanda[t]", 2, periods,
            ),
            ConstraintFamilySpec(
                "Capacidad", "T", "t", "x[t] <= capacidad[t]", 1, periods,
            ),
        ),
    )


def hydroelectric_fixture_indexed_spec() -> IndexedModelSpec:
    """Equivalencia algebraica indexada con el fixture hidro vigente de cuatro periodos."""

    periods = (1, 2, 3, 4)
    return IndexedModelSpec(
        name="Generacion Hidroelectrica Indexada 4 Periodos",
        description=(
            "Equivalencia algebraica con el fixture vigente; no certifica fidelidad fisica "
            "al enunciado fuente."
        ),
        sets=(IndexSetSpec("TSET", 1, 4),),
        scalar_parameters=(
            ScalarParameterSpec("V0", 80.0),
            ScalarParameterSpec("Vmax", 100.0),
            ScalarParameterSpec("Vmin", 40.0),
            ScalarParameterSpec("Tmax", 70.0),
        ),
        indexed_parameters=(
            IndexedParameterSpec("aporte", "TSET", dict(zip(periods, (10.0, 20.0, 15.0, 10.0)))),
            IndexedParameterSpec("demanda", "TSET", dict(zip(periods, (60.0, 80.0, 70.0, 90.0)))),
        ),
        variable_families=tuple(
            VariableFamilySpec(name, "TSET") for name in ("T", "V", "S", "PH", "GH", "GT")
        ),
        objectives=(
            IndexedObjectiveSpec(
                "Z", "Minimizar", (ObjectiveTermSpec("GT", "TSET", "100"),)
            ),
        ),
        constraint_families=(
            ConstraintFamilySpec(
                "Balance_H_Inicial", "TSET", "t", "T[t] + V[t] + S[t] = V0 + aporte[t]", 1, 1
            ),
            ConstraintFamilySpec(
                "Balance_H", "TSET", "t", "T[t] - V[t-1] + V[t] + S[t] = aporte[t]", 2, 4
            ),
            ConstraintFamilySpec("Turb_Pot", "TSET", "t", "PH[t] - 2.4525*T[t] = 0"),
            ConstraintFamilySpec("Pot_Ene", "TSET", "t", "GH[t] - PH[t] = 0"),
            ConstraintFamilySpec("Demanda_P", "TSET", "t", "GH[t] + GT[t] = demanda[t]"),
            ConstraintFamilySpec("V_Max", "TSET", "t", "V[t] <= Vmax"),
            ConstraintFamilySpec("V_Min", "TSET", "t", "V[t] >= Vmin"),
            ConstraintFamilySpec("T_Max", "TSET", "t", "T[t] <= Tmax"),
        ),
    )


def biobjective_indexed_example_spec() -> IndexedModelSpec:
    """Caso MAX/MIN indexado pequeño para probar el adaptador biobjetivo existente."""

    return IndexedModelSpec(
        name="Asignacion indexada biobjetivo",
        sets=(IndexSetSpec("T", 1, 4),),
        indexed_parameters=(
            IndexedParameterSpec("costo", "T", {1: 4.0, 2: 3.0, 3: 2.0, 4: 1.0}),
            IndexedParameterSpec("cap", "T", {1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0}),
        ),
        variable_families=(VariableFamilySpec("x", "T"),),
        objectives=(
            IndexedObjectiveSpec("Z1", "Maximizar", (ObjectiveTermSpec("x", "T", "1"),)),
            IndexedObjectiveSpec("Z2", "Minimizar", (ObjectiveTermSpec("x", "T", "costo[t]"),)),
        ),
        constraint_families=(
            ConstraintFamilySpec("Capacidad", "T", "t", "x[t] <= cap[t]"),
            ConstraintFamilySpec("Servicio", "T", "t", "x[t] >= 0.5"),
        ),
    )
