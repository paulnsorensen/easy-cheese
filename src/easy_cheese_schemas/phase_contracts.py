from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypedDict, cast

from ._compiled_phase_registry import PHASE_REGISTRY_DATA
from ._schema_catalog import (
    CURD_PLAN_SCHEMA_URI,
    CURD_RESULT_SCHEMA_URI,
    PHASE_CONTRACT_SCHEMA_URI,
    PLANNER_REQUEST_SCHEMA_URI,
    REGISTERED_CONTRACT_SCHEMA_URIS,
)

REGISTERED_SCHEMA_URIS = REGISTERED_CONTRACT_SCHEMA_URIS


class TransitionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class CompiledTransition:
    source: str
    destination: str
    payload_schema_uri: str


@dataclass(frozen=True, order=True, slots=True)
class CompiledPhase:
    source: str
    contract_schema_uri: str
    contract_major: str
    contract_minor: str
    input_schema_uris: tuple[str, ...]
    outputs: tuple[CompiledTransition, ...]


@dataclass(frozen=True, slots=True)
class TransitionRegistry:
    phases: tuple[CompiledPhase, ...]

    def phase(self, source: str) -> CompiledPhase | None:
        return next((phase for phase in self.phases if phase.source == source), None)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(phase.source for phase in self.phases)

    def to_data(self) -> list[dict[str, object]]:
        return [
            {
                "contract_version": {
                    "major": phase.contract_major,
                    "minor": phase.contract_minor,
                    "schema_uri": phase.contract_schema_uri,
                },
                "input_schema_uris": list(phase.input_schema_uris),
                "outputs": [
                    {
                        "destination": route.destination,
                        "payload_schema_uri": route.payload_schema_uri,
                    }
                    for route in phase.outputs
                ],
                "source": phase.source,
            }
            for phase in self.phases
        ]

    def to_json(self) -> str:
        return json.dumps(
            {"phases": self.to_data()}, sort_keys=True, separators=(",", ":")
        )


class _TransitionData(TypedDict):
    destination: str
    payload_schema_uri: str


class _ContractVersionData(TypedDict):
    major: str
    minor: str
    schema_uri: str


# referenced only inside quoted cast("_PhaseData", ...) below
class _PhaseData(TypedDict):  # noqa: V102
    contract_version: _ContractVersionData
    input_schema_uris: list[str]
    outputs: list[_TransitionData]
    source: str


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        mapping = cast("Mapping[object, object]", value)
        return MappingProxyType({key: _freeze(item) for key, item in mapping.items()})
    if isinstance(value, list):
        items = cast("list[object]", value)
        return tuple(_freeze(item) for item in items)
    return value


_PHASE_DATA = cast(
    "tuple[_PhaseData, ...]", tuple(_freeze(phase) for phase in PHASE_REGISTRY_DATA)
)
_PHASES_BY_SOURCE = MappingProxyType(
    {phase["source"]: phase for phase in _PHASE_DATA}
)
REGISTERED_PHASES = tuple(sorted(_PHASES_BY_SOURCE))


def is_registered_phase(source: str) -> bool:
    return source in _PHASES_BY_SOURCE


def _registry_from_data() -> TransitionRegistry:
    phases = tuple(
        CompiledPhase(
            source=phase["source"],
            contract_schema_uri=phase["contract_version"]["schema_uri"],
            contract_major=phase["contract_version"]["major"],
            contract_minor=phase["contract_version"]["minor"],
            input_schema_uris=tuple(phase["input_schema_uris"]),
            outputs=tuple(
                CompiledTransition(
                    source=phase["source"],
                    destination=route["destination"],
                    payload_schema_uri=route["payload_schema_uri"],
                )
                for route in phase["outputs"]
            ),
        )
        for phase in _PHASE_DATA
    )
    return TransitionRegistry(phases=phases)


COMPILED_TRANSITION_REGISTRY = _registry_from_data()


def _require_compiled_registry(registry: TransitionRegistry) -> None:
    if registry is not COMPILED_TRANSITION_REGISTRY:
        raise TransitionError("runtime transition registry is generated and immutable")


def _resolve_transition(
    source: str,
    destination: str,
    payload_schema_uri: str | None = None,
) -> CompiledTransition | None:
    if source not in _PHASES_BY_SOURCE:
        raise TransitionError(f"unknown source phase {source!r}")
    if destination == "done":
        if payload_schema_uri is not None:
            raise TransitionError("terminal transition cannot carry a payload schema")
        return None

    phase = COMPILED_TRANSITION_REGISTRY.phase(source)
    if phase is None:
        raise TransitionError(f"unknown source phase {source!r}")
    routes = tuple(
        route for route in phase.outputs if route.destination == destination
    )
    if not routes:
        raise TransitionError(f"transition {source} -> {destination} is not declared")
    if payload_schema_uri is not None:
        route = next(
            (
                route
                for route in routes
                if route.payload_schema_uri == payload_schema_uri
            ),
            None,
        )
        if route is None:
            raise TransitionError(
                f"payload schema {payload_schema_uri!r} is not declared for "
                + f"{source} -> {destination}"
            )
    elif len(routes) != 1:
        raise TransitionError(
            "payload schema is required for ambiguous transition "
            + f"{source} -> {destination}"
        )
    else:
        route = routes[0]
    return route


def resolve_transition(
    registry: TransitionRegistry,
    source: str,
    destination: str,
    payload_schema_uri: str | None = None,
) -> CompiledTransition | None:
    _require_compiled_registry(registry)
    return _resolve_transition(source, destination, payload_schema_uri)


def validate_transition(
    registry: TransitionRegistry,
    source: str,
    destination: str,
    payload_schema_uri: str | None = None,
) -> CompiledTransition | None:
    return resolve_transition(registry, source, destination, payload_schema_uri)


def resolve_compiled_transition(
    source: str,
    destination: str,
    payload_schema_uri: str | None = None,
) -> dict[str, str] | None:
    route = _resolve_transition(source, destination, payload_schema_uri)
    return (
        None
        if route is None
        else {
            "source": route.source,
            "destination": route.destination,
            "payload_schema_uri": route.payload_schema_uri,
        }
    )


__all__ = [
    "COMPILED_TRANSITION_REGISTRY",
    "CURD_PLAN_SCHEMA_URI",
    "CURD_RESULT_SCHEMA_URI",
    "PHASE_CONTRACT_SCHEMA_URI",
    "PLANNER_REQUEST_SCHEMA_URI",
    "REGISTERED_PHASES",
    "REGISTERED_SCHEMA_URIS",
    "CompiledPhase",
    "CompiledTransition",
    "TransitionError",
    "TransitionRegistry",
    "is_registered_phase",
    "resolve_compiled_transition",
    "resolve_transition",
    "validate_transition",
]
