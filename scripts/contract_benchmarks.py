from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, cast

import attrs

from easy_cheese_schemas.schema_runtime import (
    CanonicalArtifact,
    ContractValidationError,
    normalize_agent_output,
)


@dataclass(frozen=True, slots=True)
class ContractBenchmarkInput:
    """One host-owned, representative writer input for offline measurement."""

    name: str
    writer_view: object
    invocation: Mapping[str, object]
    repair_view: object | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("benchmark name must not be empty")
        if not isinstance(self.invocation, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("benchmark invocation must be a mapping")


@dataclass(frozen=True, slots=True)
class BenchmarkRecord:
    """Deterministic facts derived from one normalization attempt."""

    name: str
    first_pass_valid: bool
    repair_attempted: bool
    repair_succeeded: bool
    writer_bytes: int
    canonical_bytes: int | None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("benchmark name must not be empty")
        if self.writer_bytes <= 0:
            raise ValueError("writer_bytes must be positive")
        if self.canonical_bytes is not None and self.canonical_bytes <= 0:
            raise ValueError("canonical_bytes must be positive when present")
        if self.first_pass_valid and self.repair_attempted:
            raise ValueError("repair cannot be attempted after a valid first pass")
        if self.repair_succeeded and not self.repair_attempted:
            raise ValueError("repair cannot succeed unless it was attempted")
        if self.repair_succeeded and self.canonical_bytes is None:
            raise ValueError("a successful repair must have canonical bytes")


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Deterministic aggregate evidence for a representative input set."""

    records: tuple[BenchmarkRecord, ...]
    first_pass_validity: float
    repair_rate: float


class _NamedAttribute(Protocol):
    name: str


def _json_value(value: object) -> object:
    if isinstance(value, CanonicalArtifact):
        return value.canonical_bytes.decode()
    if attrs.has(type(value)):
        attributes = cast("tuple[_NamedAttribute, ...]", attrs.fields(type(value)))
        return {
            attribute.name: _json_value(cast(object, getattr(value, attribute.name)))
            for attribute in attributes
        }
    if isinstance(value, Enum):
        return cast(object, value.value)
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return {str(key): _json_value(item) for key, item in mapping.items()}
    if isinstance(value, (tuple, list)):
        items = cast("tuple[object, ...] | list[object]", value)
        return [_json_value(item) for item in items]
    return value


def _serialized_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            _json_value(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise TypeError("benchmark writer data must be JSON serializable") from error
    return (payload + "\n").encode()


def _normalized_size(
    view: object, invocation: Mapping[str, object]
) -> tuple[bool, CanonicalArtifact | None]:
    try:
        return True, normalize_agent_output(view, invocation)
    except ContractValidationError:
        return False, None


def _record(input_: ContractBenchmarkInput) -> BenchmarkRecord:
    writer_bytes = len(_serialized_bytes(input_.writer_view))
    first_pass_valid, canonical = _normalized_size(
        input_.writer_view, input_.invocation
    )

    repair_attempted = False
    repair_succeeded = False
    if not first_pass_valid and input_.repair_view is not None:
        repair_attempted = True
        repair_succeeded, repaired = _normalized_size(
            input_.repair_view, input_.invocation
        )
        if repair_succeeded:
            canonical = repaired

    return BenchmarkRecord(
        name=input_.name,
        first_pass_valid=first_pass_valid,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        writer_bytes=writer_bytes,
        canonical_bytes=None if canonical is None else len(canonical.canonical_bytes),
    )


def benchmark_contracts(
    inputs: Iterable[ContractBenchmarkInput],
) -> BenchmarkReport:
    representative_inputs = tuple(inputs)
    if not representative_inputs:
        raise ValueError("at least one benchmark input is required")
    if not all(
        isinstance(input_, ContractBenchmarkInput)  # pyright: ignore[reportUnnecessaryIsInstance]
        for input_ in representative_inputs
    ):
        raise TypeError("benchmark_contracts requires ContractBenchmarkInput values")

    records = tuple(_record(input_) for input_ in representative_inputs)
    repair_attempts = sum(record.repair_attempted for record in records)
    return BenchmarkReport(
        records=records,
        first_pass_validity=sum(
            record.first_pass_valid for record in records
        )
        / len(records),
        repair_rate=(
            sum(record.repair_succeeded for record in records) / repair_attempts
            if repair_attempts
            else 0.0
        ),
    )


__all__ = [
    "BenchmarkRecord",
    "BenchmarkReport",
    "ContractBenchmarkInput",
    "benchmark_contracts",
]
