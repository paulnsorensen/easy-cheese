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


class StatusError(ValueError):
    """Raised when a handback `status:` field is outside the declared vocabulary."""


@dataclass(frozen=True, order=True, slots=True)
class HandbackStatus:
    """One `status:` value a phase may hand back.

    `requires_reason` decides the wire grammar: `ok` stands alone, every other
    status is `"<name>: <one-line reason>"`. `disposition` is what the
    orchestrator does with it, and is the only field a consumer should branch
    on -- adding a status must not require editing every consumer.
    """

    name: str
    requires_reason: bool
    disposition: str


PROCEED = "proceed"
RETRY = "retry"
STOP = "stop"
DISPOSITIONS = (PROCEED, RETRY, STOP)

HANDBACK_STATUSES: Mapping[str, HandbackStatus] = MappingProxyType(
    {
        status.name: status
        for status in (
            HandbackStatus("ok", requires_reason=False, disposition=PROCEED),
            HandbackStatus(
                "ok-with-concerns", requires_reason=True, disposition=PROCEED
            ),
            HandbackStatus("needs-context", requires_reason=True, disposition=RETRY),
            HandbackStatus("gated", requires_reason=True, disposition=STOP),
            HandbackStatus("halt", requires_reason=True, disposition=STOP),
        )
    }
)
REGISTERED_STATUSES = tuple(HANDBACK_STATUSES)


def _status_vocabulary() -> str:
    return " | ".join(
        status.name if not status.requires_reason else f"{status.name}: <reason>"
        for status in HANDBACK_STATUSES.values()
    )


_LINE_SEPARATORS = ("\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")


def _require_single_line(field: str, value: str) -> None:
    if any(separator in value for separator in _LINE_SEPARATORS):
        raise StatusError(f"{field} must fit on one physical line")


def parse_status_field(
    value: str, *, require_reason: bool = True
) -> tuple[str, str | None]:
    """Split a `status:` field value into `(status name, reason or None)`.

    This is the single grammar for every producer and consumer of the handback
    preamble; callers translate `StatusError` into their own error type. The
    name is matched case-insensitively after stripping, because the field is
    read back out of agent-authored prose.

    `require_reason=False` is for readers of an already-emitted field -- the
    phase router and the legacy note reader. A reason-carrying status that
    arrived bare (`halt` with no colon) must still route by its declared
    disposition rather than be rejected into some caller's fallback; the
    vocabulary itself is never forked.
    """
    _require_single_line("status field", value)
    text = value.strip()
    name, separator, reason_text = text.partition(":")
    name = name.strip().lower()
    status = HANDBACK_STATUSES.get(name)
    if status is None:
        raise StatusError(
            f"status must be one of {_status_vocabulary()}, got {value!r}"
        )
    reason = reason_text.strip()
    if not status.requires_reason:
        if separator or reason:
            raise StatusError(f"{name} status takes no reason")
        return name, None
    if not reason:
        if require_reason:
            raise StatusError(f"{name} status requires a reason after '{name}:'")
        return name, None
    return name, reason


def render_status_field(name: str, reason: str | None) -> str:
    """Render `(status name, reason)` back to its canonical field value."""
    _require_single_line("status name", name)
    if reason is not None:
        _require_single_line("status reason", reason)
    status = HANDBACK_STATUSES.get(name)
    if status is None:
        raise StatusError(
            f"status must be one of {_status_vocabulary()}, got {name!r}"
        )
    if not status.requires_reason:
        if reason:
            raise StatusError(f"{name} status takes no reason")
        return name
    if not reason:
        raise StatusError(f"{name} status requires a reason")
    return f"{name}: {reason}"


def status_disposition(name: str) -> str:
    """Return what an orchestrator must do with `name`: proceed, retry, or stop."""
    status = HANDBACK_STATUSES.get(name)
    if status is None:
        raise StatusError(
            f"status must be one of {_status_vocabulary()}, got {name!r}"
        )
    return status.disposition


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
    "DISPOSITIONS",
    "HANDBACK_STATUSES",
    "PHASE_CONTRACT_SCHEMA_URI",
    "PLANNER_REQUEST_SCHEMA_URI",
    "PROCEED",
    "REGISTERED_PHASES",
    "REGISTERED_SCHEMA_URIS",
    "REGISTERED_STATUSES",
    "RETRY",
    "STOP",
    "CompiledPhase",
    "CompiledTransition",
    "HandbackStatus",
    "StatusError",
    "TransitionError",
    "TransitionRegistry",
    "is_registered_phase",
    "parse_status_field",
    "render_status_field",
    "resolve_compiled_transition",
    "resolve_transition",
    "status_disposition",
    "validate_transition",
]
