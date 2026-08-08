"""Press readiness and outer-TDD gate receipt schemas.

Readiness remains the Press scoreboard verdict.  Gate receipts are the
phase-neutral evidence exchanged by Mold, Cut, Cook, and Press; their fields
are deliberately data-only so a consumer can validate before acting on them.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal

import attrs
from attrs import Attribute, define, field

__all__ = [
    "BaselineCheck",
    "EvidenceOrigin",
    "GateDisposition",
    "GateMode",
    "GateProducer",
    "GateReceipt",
    "ProtectedFile",
    "Readiness",
    "RedCase",
    "RedKind",
    "TestContract",
    "classify_readiness",
]


class Readiness(str, Enum):
    READY = "ready for /age"
    FOLLOW_UP = "follow-up recommended"
    BLOCKED = "blocked"


class GateDisposition(str, Enum):
    RED = "red"
    NOT_APPLICABLE = "not-applicable"


class GateMode(str, Enum):
    TRACER = "tracer"
    CONTRACT_MATRIX = "contract-matrix"


class RedKind(str, Enum):
    BEHAVIOR = "behavior"
    CONTRACT = "contract"


class GateProducer(str, Enum):
    CUT = "cut"
    PRESS = "press"


class EvidenceOrigin(str, Enum):
    GENERATED = "generated"
    ADOPTED = "adopted"


def _non_empty_string(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")


def _optional_non_empty_string(
    instance: object, attribute: Attribute[Any], value: object
) -> None:
    if value is not None:
        _non_empty_string(instance, attribute, value)


def _optional_project_relative_path(
    instance: object, attribute: Attribute[Any], value: object
) -> None:
    if value is not None:
        _project_relative_path(instance, attribute, value)


def _string_list(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{attribute.name}[{index}] must be a non-empty string")


def _non_empty_string_list(
    instance: object, attribute: Attribute[Any], value: object
) -> None:
    _string_list(instance, attribute, value)
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


_SHELL_TOKENS = frozenset({"&&", "||", ";", "|", "&"})


def _argv(_instance: object, attribute: Attribute[Any], value: object) -> None:
    _non_empty_string_list(_instance, attribute, value)
    assert isinstance(value, list)
    if any(token in _SHELL_TOKENS for token in value):
        raise ValueError(f"{attribute.name} must contain argv data, not shell syntax")
    if any("\x00" in token or "\n" in token or "\r" in token for token in value):
        raise ValueError(f"{attribute.name} must contain argv data, not shell syntax")


def _project_relative_path(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    _non_empty_string(_instance, attribute, value)
    assert isinstance(value, str)
    first = value.split("/", 1)[0]
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value.startswith("\\")
        or "\\" in value
        or ":" in first
        or ".." in path.parts
        or "\x00" in value
    ):
        raise ValueError(f"{attribute.name} must be a project-relative path")


_DIGEST_RE = re.compile(r"(?:sha256:)?[0-9A-Fa-f]{64}")


def _optional_digest(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if value is not None and (
        not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None
    ):
        raise ValueError(f"{attribute.name} must be a 64-character hexadecimal digest")


def _digest(_instance: object, attribute: Attribute[Any], value: object) -> None:
    _optional_digest(_instance, attribute, value)
    if value is None:
        raise ValueError(f"{attribute.name} must be a 64-character hexadecimal digest")


def _enum(enum_type: type[Enum]):
    def validate(_instance: object, attribute: Attribute[Any], value: object) -> None:
        if not isinstance(value, enum_type):
            raise ValueError(
                f"{attribute.name} must be a {enum_type.__name__}, "
                f"not {type(value).__name__}"
            )

    return validate


def _schema_version(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{attribute.name} must be an integer")


def _zero_exit_code(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if isinstance(value, bool) or value != 0:
        raise ValueError(f"{attribute.name} must be exactly 0")


def _observed_exit_code(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{attribute.name} must be an integer")


def _contract_source(
    _instance: object, attribute: Attribute[Any], value: object
) -> None:
    if value not in ("approved", "inferred"):
        raise ValueError(f"{attribute.name} must be one of: approved, inferred")


def _receipt_list_shape(
    instance: object,
    attribute: Attribute[Any],
    value: object,
) -> None:
    """Apply RED/N/A closure rules to one receipt evidence collection."""
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    disposition = getattr(instance, "disposition", None)
    if disposition is GateDisposition.RED and not value:
        raise ValueError(f"{attribute.name} must be a non-empty list for RED")
    if disposition is GateDisposition.NOT_APPLICABLE and value:
        raise ValueError(f"{attribute.name} must be empty for not-applicable receipts")


def _receipt_guards(instance: object, attribute: Attribute[Any], value: object) -> None:
    _string_list(instance, attribute, value)
    if (
        getattr(instance, "disposition", None) is GateDisposition.NOT_APPLICABLE
        and value
    ):
        raise ValueError(f"{attribute.name} must be empty for not-applicable receipts")


def _receipt_reason(instance: object, attribute: Attribute[Any], value: object) -> None:
    disposition = getattr(instance, "disposition", None)
    if disposition is GateDisposition.NOT_APPLICABLE:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{attribute.name} must be a non-empty string for "
                "not-applicable receipts"
            )
    elif disposition is GateDisposition.RED and value is not None:
        raise ValueError(f"{attribute.name} must be absent for RED receipts")


def _serialize(_instance: object, _attribute: object, value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


class _GateRecord:
    def to_dict(self) -> dict[str, Any]:
        return attrs.asdict(self, recurse=True, value_serializer=_serialize)


@define(frozen=True)
class TestContract(_GateRecord):
    acceptance_id: str = field(validator=_non_empty_string)
    interface: str = field(validator=_non_empty_string)
    seam: str = field(validator=_non_empty_string)
    expected_failure: str = field(validator=_non_empty_string)
    mode: GateMode = field(validator=_enum(GateMode))
    contract_source: Literal["approved", "inferred"] = field(validator=_contract_source)
    interface_version: str | None = field(
        default=None,
        validator=_optional_non_empty_string,
    )
    matrix_rows: list[str] = field(factory=list, validator=_string_list)


@define(frozen=True)
class BaselineCheck(_GateRecord):
    id: str = field(validator=_non_empty_string)
    argv: list[str] = field(validator=_argv)
    cwd: str = field(validator=_project_relative_path)
    observed_exit_code: Literal[0] = field(validator=_zero_exit_code)


@define(frozen=True)
class RedCase(_GateRecord):
    id: str = field(validator=_non_empty_string)
    acceptance_ids: list[str] = field(validator=_non_empty_string_list)
    curd: str | None = field(validator=_optional_non_empty_string)
    seam: str = field(validator=_non_empty_string)
    argv: list[str] = field(validator=_argv)
    cwd: str = field(validator=_project_relative_path)
    kind: RedKind = field(validator=_enum(RedKind))
    origin: EvidenceOrigin = field(validator=_enum(EvidenceOrigin))
    expected_witness: list[str] = field(validator=_non_empty_string_list)
    observed_exit_code: int = field(validator=_observed_exit_code)
    observed_witness: str = field(validator=_non_empty_string)
    matrix_row: str | None = field(
        default=None,
        validator=_optional_non_empty_string,
    )


@define(frozen=True)
class ProtectedFile(_GateRecord):
    path: str = field(validator=_project_relative_path)
    sha256: str = field(validator=_digest)


def _phase_token_pair(
    instance: GateReceipt,
    attribute: Attribute[Any],
    value: str | None,
) -> None:
    if bool(instance.phase_token_ref) != bool(value):
        raise ValueError(
            f"{attribute.name} and phase_token_ref must be provided together"
        )


@define(frozen=True)
class GateReceipt(_GateRecord):
    __schema_forbidden_fields__ = frozenset({"mode"})
    schema_version: int = field(validator=_schema_version)
    work_id: str = field(validator=_non_empty_string)
    project_key: str = field(validator=_non_empty_string)
    producer: GateProducer = field(validator=_enum(GateProducer))
    disposition: GateDisposition = field(validator=_enum(GateDisposition))
    spec_ref: str | None = field(validator=_optional_non_empty_string)
    spec_sha256: str | None = field(validator=_optional_digest)
    guard_receipt_refs: list[str] = field(validator=_receipt_guards)
    contracts: list[TestContract] = field(validator=_receipt_list_shape)
    baseline_checks: list[BaselineCheck] = field(validator=_receipt_list_shape)
    cases: list[RedCase] = field(validator=_receipt_list_shape)
    protected_files: list[ProtectedFile] = field(validator=_receipt_list_shape)
    not_applicable_reason: str | None = field(
        validator=[_optional_non_empty_string, _receipt_reason]
    )
    phase_token_ref: str | None = field(
        default=None, validator=_optional_project_relative_path
    )
    phase_token_sha256: str | None = field(
        default=None, validator=[_optional_digest, _phase_token_pair]
    )

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        for contract in payload["contracts"]:
            if contract["interface_version"] is None:
                contract.pop("interface_version")
            if not contract["matrix_rows"]:
                contract.pop("matrix_rows")
        for case in payload["cases"]:
            if case["matrix_row"] is None:
                case.pop("matrix_row")
        return payload


def classify_readiness(
    *,
    hard_floor_met: bool,
    has_open_level_1_or_2: bool,
    has_open_level_3: bool,
    has_open_level_4_or_5: bool,
    any_spinning: bool,
) -> Readiness:
    # hard_floor_met is a precondition: without it, the press scoreboard is
    # incomplete (failing gates, missing tests, etc.) and the verdict is
    # BLOCKED regardless of which gap levels are still open.
    if any_spinning or not hard_floor_met or has_open_level_1_or_2:
        return Readiness.BLOCKED
    if has_open_level_3:
        return Readiness.READY  # level-3 gaps are encouraged to close in /age
    if has_open_level_4_or_5:
        return Readiness.FOLLOW_UP
    return Readiness.READY
