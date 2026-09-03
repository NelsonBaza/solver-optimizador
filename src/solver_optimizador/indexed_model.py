"""Especificacion serializable de modelos lineales indexados unidimensionales."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


INDEXED_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class IndexSetSpec:
    name: str
    start: int
    end: int

    @property
    def values(self) -> list[int]:
        return list(range(self.start, self.end + 1))


@dataclass(frozen=True)
class ScalarParameterSpec:
    name: str
    value: float


@dataclass(frozen=True)
class IndexedParameterSpec:
    name: str
    index_set: str
    values: Mapping[int, float]


@dataclass(frozen=True)
class VariableFamilySpec:
    name: str
    index_set: str


@dataclass(frozen=True)
class ObjectiveTermSpec:
    variable_family: str
    index_set: str
    coefficient: str = "1"
    start_index: int | None = None
    end_index: int | None = None


@dataclass(frozen=True)
class IndexedObjectiveSpec:
    name: str
    sense: str
    terms: tuple[ObjectiveTermSpec, ...]


@dataclass(frozen=True)
class ConstraintFamilySpec:
    name: str
    index_set: str
    index_symbol: str
    expression: str
    start_index: int | None = None
    end_index: int | None = None


@dataclass(frozen=True)
class IndexedModelSpec:
    name: str
    sets: tuple[IndexSetSpec, ...]
    scalar_parameters: tuple[ScalarParameterSpec, ...] = ()
    indexed_parameters: tuple[IndexedParameterSpec, ...] = ()
    variable_families: tuple[VariableFamilySpec, ...] = ()
    objectives: tuple[IndexedObjectiveSpec, ...] = ()
    constraint_families: tuple[ConstraintFamilySpec, ...] = ()
    description: str = ""
    indexed_schema_version: str = INDEXED_SCHEMA_VERSION


@dataclass(frozen=True)
class ExpandedIndexedModel:
    name: str
    description: str
    problem_type: str
    variables: tuple[str, ...]
    constraints: tuple[dict[str, Any], ...]
    mono_objective: dict[str, Any] | None
    bio_objectives: dict[str, dict[str, Any]] | None
    variable_provenance: Mapping[str, dict[str, Any]]
    generated_constraint_provenance: Mapping[str, dict[str, Any]]
    statistics: Mapping[str, int | float]
    source_spec: IndexedModelSpec = field(repr=False)

    def to_builder_state(self) -> dict[str, Any]:
        """Devuelve exactamente la representacion que consumen los builders vigentes."""

        state: dict[str, Any] = {
            "problem_type": self.problem_type,
            "var_names": list(self.variables),
            "num_vars": len(self.variables),
            "constraints_data": [dict(row) for row in self.constraints],
        }
        if self.problem_type == "Monoobjetivo":
            assert self.mono_objective is not None
            state["obj_sense"] = self.mono_objective["sense"]
            state["obj_coeffs"] = dict(self.mono_objective["coefficients"])
        else:
            assert self.bio_objectives is not None
            state["obj1_sense"] = self.bio_objectives["obj1"]["sense"]
            state["obj1_coeffs"] = dict(self.bio_objectives["obj1"]["coefficients"])
            state["obj2_sense"] = self.bio_objectives["obj2"]["sense"]
            state["obj2_coeffs"] = dict(self.bio_objectives["obj2"]["coefficients"])
        return state


def indexed_model_spec_to_dict(spec: IndexedModelSpec) -> dict[str, Any]:
    data = asdict(spec)
    data["indexed_parameters"] = [
        {
            **parameter,
            "values": {str(index): value for index, value in parameter["values"].items()},
        }
        for parameter in data["indexed_parameters"]
    ]
    return data


def indexed_model_spec_from_dict(data: Mapping[str, Any]) -> IndexedModelSpec:
    if not isinstance(data, Mapping):
        raise ValueError("La especificacion indexada debe ser un objeto JSON.")
    version = str(data.get("indexed_schema_version", ""))
    if version != INDEXED_SCHEMA_VERSION:
        raise ValueError(
            f"Version indexada no soportada: '{version}'. Se esperaba '{INDEXED_SCHEMA_VERSION}'."
        )
    try:
        return IndexedModelSpec(
            name=str(data.get("name", "Modelo indexado")),
            description=str(data.get("description", "")),
            indexed_schema_version=version,
            sets=tuple(IndexSetSpec(**item) for item in data.get("sets", [])),
            scalar_parameters=tuple(
                ScalarParameterSpec(**item) for item in data.get("scalar_parameters", [])
            ),
            indexed_parameters=tuple(
                IndexedParameterSpec(
                    name=item["name"],
                    index_set=item["index_set"],
                    values={int(index): value for index, value in item["values"].items()},
                )
                for item in data.get("indexed_parameters", [])
            ),
            variable_families=tuple(
                VariableFamilySpec(**item) for item in data.get("variable_families", [])
            ),
            objectives=tuple(
                IndexedObjectiveSpec(
                    name=item["name"],
                    sense=item["sense"],
                    terms=tuple(ObjectiveTermSpec(**term) for term in item.get("terms", [])),
                )
                for item in data.get("objectives", [])
            ),
            constraint_families=tuple(
                ConstraintFamilySpec(**item) for item in data.get("constraint_families", [])
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Estructura de especificacion indexada invalida: {exc}") from exc


def serialize_indexed_model_spec(spec: IndexedModelSpec) -> str:
    """Serializa la fuente indexada; no mezcla este esquema con el JSON explicito."""

    return json.dumps(indexed_model_spec_to_dict(spec), indent=2, ensure_ascii=False)


def build_indexed_spec_signature(spec: IndexedModelSpec) -> str:
    """Firma SHA-256 determinista de toda la fuente indexada relevante."""

    canonical_payload = json.dumps(
        indexed_model_spec_to_dict(spec),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


def is_indexed_preview_current(
    current_spec: IndexedModelSpec,
    preview_signature: str | None,
) -> bool:
    """Indica si la fuente visible coincide con la fotografia compilada."""

    return bool(preview_signature) and (
        build_indexed_spec_signature(current_spec) == preview_signature
    )


def deserialize_indexed_model_spec(payload: str) -> IndexedModelSpec:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON indexado malformado: {exc}") from exc
    return indexed_model_spec_from_dict(data)
