from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from enum import Enum
from collections.abc import Iterable
from typing import ClassVar, Protocol, TypeVar, cast

import attrs
from attrs import define, field, validators

_attrs_field = field

MAX_CONTRACT_BYTES = 8 * 1024 * 1024
MAX_CONTRACT_DEPTH = 64
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_COLLECTION_ITEMS = 256
MAX_CONTEXT_ITEMS = 32
MAX_SCOPE_PATHS = 64
MAX_TEXT_LENGTH = 4096
MAX_CONTEXT_TEXT_LENGTH = 8192

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERSION_RE = re.compile(r"(?:0|[1-9][0-9]*)")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_MEDIA_TYPE_RE = re.compile(
    r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+(?:;[^\r\n]+)?"
)
_URI_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:.+")

class _NamedAttribute(Protocol):
    name: str


class _HasUncertaintyScope(Protocol):
    @property
    def scope(self) -> UncertaintyScope: ...


_ItemT = TypeVar("_ItemT")
_C = TypeVar("_C")
_ClsT = TypeVar("_ClsT", bound=type)

Validator = Callable[[object, _NamedAttribute, object], None]

_CONTRACT_MARKER = "__contract_slug__"


def _validate_contract_slug(slug: object) -> str:
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("contract slug must be a non-empty string")
    return slug


def contract(slug: str) -> Callable[[_ClsT], _ClsT]:
    """Mark a contract class with its canonical schema slug."""
    validated_slug = _validate_contract_slug(slug)

    def decorate(cls: _ClsT) -> _ClsT:
        setattr(cls, _CONTRACT_MARKER, validated_slug)
        return cls

    return decorate


def _registered_contracts() -> tuple[tuple[str, type], ...]:
    """Return marked contract classes in deterministic slug order."""
    pairs: list[tuple[str, type]] = []
    for value in cast(Iterable[object], globals().values()):
        if not isinstance(value, type):
            continue
        slug = cast(object, getattr(value, _CONTRACT_MARKER, None))
        if slug is None:
            continue
        pairs.append((_validate_contract_slug(slug), value))
    pairs.sort(key=lambda pair: pair[0])
    for previous, current in zip(pairs, pairs[1:]):
        if previous[0] == current[0]:
            raise ValueError(f"duplicate contract marker {current[0]!r}")
    return tuple(pairs)


def registered_contracts() -> tuple[tuple[str, type], ...]:
    """Public accessor for marked contract classes in deterministic slug order."""
    return _registered_contracts()


def _unstructure(value: object) -> object:
    """Project attrs models, enums, and containers onto JSON-serializable data."""
    if attrs.has(type(value)):
        return {
            attribute.name: _unstructure(cast(object, getattr(value, attribute.name)))
            for attribute in cast(
                "tuple[attrs.Attribute[object], ...]", attrs.fields(type(value))
            )
        }
    if isinstance(value, Enum):
        return cast(object, value.value)
    if isinstance(value, (tuple, list)):
        sequence_value = cast("tuple[object, ...] | list[object]", value)
        return [_unstructure(item) for item in sequence_value]
    if isinstance(value, Mapping):
        mapping_value = cast("Mapping[object, object]", value)
        return {str(key): _unstructure(item) for key, item in mapping_value.items()}
    return value


def canonical_bytes(value: object) -> bytes:
    """Serialize ``value`` to the canonical, digest-stable JSON encoding."""
    return (
        json.dumps(_unstructure(value), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def canonical_digest(value: object) -> str:
    """Return the ``sha256:``-prefixed digest of ``value``'s canonical bytes."""
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def schema_constraints(
    *rules: Mapping[str, object], **simple: object
) -> Callable[[_C], _C]:
    """Attach JSON Schema constraints to a validator or attrs model."""
    declarations = (*map(dict, rules), *([simple] if simple else []))

    def decorate(target: _C) -> _C:
        if isinstance(target, type):
            setattr(target, "__schema_constraints__", declarations)
        else:
            merged = {
                key: value
                for declaration in declarations
                for key, value in declaration.items()
            }
            setattr(target, "__schema_constraints__", merged)
        return target

    return decorate


def _constraints_of(target: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], getattr(target, "__schema_constraints__"))


def _if_equals(
    field_name: str, value: str, then: Mapping[str, object]
) -> dict[str, object]:
    return {
        "if": {
            "properties": {field_name: {"const": value}},
            "required": [field_name],
        },
        "then": dict(then),
    }


def _without(*field_names: str) -> dict[str, object]:
    return {"not": {"required": list(field_names)}}


class IdentityAction(str, Enum):
    NEW = "new"
    RETAIN = "retain"
    DERIVE = "derive"


class EvidenceKind(str, Enum):
    SOURCE = "source"
    REVIEW = "review"
    DIAGNOSIS = "diagnosis"
    VERIFICATION = "verification"
    RUNTIME = "runtime"


class PlannerRequestKind(str, Enum):
    DECOMPOSE = "decompose"
    REMEDIATE = "remediate"
    REPLAN = "replan"


class PlannerDisposition(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NO_WORK = "no_work"
    BLOCKED = "blocked"
    INVALID = "invalid"
    EXECUTOR_FAILURE = "executor_failure"


class UncertaintyScope(str, Enum):
    OMITTED_WORK = "omitted_work"
    EMITTED_WORK = "emitted_work"
    DEPENDENCY = "dependency"
    SHARED_CONSTRAINT = "shared_constraint"


class ReviewKind(str, Enum):
    TASTE_TEST = "taste_test"
    AGE = "age"


class ReviewDisposition(str, Enum):
    CLEAN = "clean"
    FINDINGS = "findings"
    BLOCKED = "blocked"
    INVALID = "invalid"
    EXECUTOR_FAILURE = "executor_failure"


class ReviewSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoverageDisposition(str, Enum):
    COVERED = "covered"
    NOT_COVERED = "not_covered"


class DiagnosisDisposition(str, Enum):
    CONFIRMED = "confirmed"
    INCONCLUSIVE = "inconclusive"
    NOT_REPRODUCED = "not_reproduced"
    BLOCKED = "blocked"
    INVALID = "invalid"
    EXECUTOR_FAILURE = "executor_failure"


class ReproductionDisposition(str, Enum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    BLOCKED = "blocked"


class HypothesisDisposition(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class CriterionDisposition(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class CurdDisposition(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class WriterViewKind(str, Enum):
    CURD_PLAN = "curd_plan"
    PLANNER_RESULT = "planner_result"
    REVIEW_RESULT = "review_result"
    DIAGNOSIS_RESULT = "diagnosis_result"
    CURD_RESULT = "curd_result"


@schema_constraints(minLength=1, maxLength=MAX_TEXT_LENGTH)
def _bounded_string(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")
    if len(value) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"{attribute.name} must be at most {MAX_TEXT_LENGTH} characters"
        )


@schema_constraints(minLength=1, maxLength=MAX_CONTEXT_TEXT_LENGTH)
def _context_string(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")
    if len(value) > MAX_CONTEXT_TEXT_LENGTH:
        raise ValueError(
            f"{attribute.name} must be at most {MAX_CONTEXT_TEXT_LENGTH} characters"
        )


@schema_constraints(_constraints_of(_bounded_string))
def _optional_string(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if value is not None:
        _bounded_string(instance, attribute, value)


@schema_constraints(pattern=_ID_RE.pattern, minLength=1, maxLength=128)
def _identifier(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be an opaque identifier matching {_ID_RE.pattern}"
        )


@schema_constraints(_constraints_of(_identifier))
def _optional_identifier(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if value is not None:
        _identifier(instance, attribute, value)


@schema_constraints(pattern=_DIGEST_RE.pattern)
def _digest(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be sha256: followed by 64 lowercase hexadecimal characters"
        )


@schema_constraints(minimum=1)
def _positive_integer(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{attribute.name} must be a positive integer")


@schema_constraints(minimum=0, maximum=MAX_ARTIFACT_BYTES)
def _artifact_size(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    _non_negative_integer(instance, attribute, value)
    assert isinstance(value, int)
    if value > MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"{attribute.name} must be at most {MAX_ARTIFACT_BYTES} bytes"
        )


@schema_constraints(minimum=0)
def _non_negative_integer(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{attribute.name} must be a non-negative integer")


 
@schema_constraints(pattern=_VERSION_RE.pattern, minLength=1)
def _version_component(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} version component must be a canonical decimal string"
        )


def _tuple_sequence(value: list[_ItemT] | tuple[_ItemT, ...]) -> tuple[_ItemT, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):  # pyright: ignore[reportUnnecessaryIsInstance]
        return tuple(value)
    raise TypeError(  # pyright: ignore[reportUnreachable]
        "collection fields must be provided as a list or tuple"
    )


@schema_constraints(pattern=_URI_RE.pattern, minLength=1)
def _uri(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _URI_RE.fullmatch(value) is None:
        raise ValueError(f"{attribute.name} must be an absolute URI")




@schema_constraints(_constraints_of(_uri))
def _optional_uri(instance: object, attribute: _NamedAttribute, value: object) -> None:
    if value is not None:
        _uri(instance, attribute, value)




@schema_constraints(pattern=_MEDIA_TYPE_RE.pattern, minLength=3)
def _media_type(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _MEDIA_TYPE_RE.fullmatch(value) is None:
        raise ValueError(f"{attribute.name} must be a valid media type")




@schema_constraints(_constraints_of(_bounded_string))
def _scope_path(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    _bounded_string(_instance, attribute, value)
    assert isinstance(value, str)
    if value.startswith("/") or value in {".", ".."} or ".." in value.split("/"):
        raise ValueError(f"{attribute.name} must be a repository-relative path")


def _list_of(
    expected: type[_ItemT],
    *,
    non_empty: bool = False,
    limit: int = MAX_COLLECTION_ITEMS,
) -> Validator:
    def validate(_instance: object, attribute: _NamedAttribute, value: object) -> None:
        if not isinstance(value, tuple):
            raise ValueError(f"{attribute.name} must be a list")
        items = cast(tuple[object, ...], value)
        if non_empty and not items:
            raise ValueError(f"{attribute.name} must be a non-empty list")
        if len(items) > limit:
            raise ValueError(f"{attribute.name} must be at most {limit} items")
        for index, item in enumerate(items, start=1):
            if not isinstance(item, expected):
                raise ValueError(
                    f"{attribute.name}[{index}] must be {expected.__name__}"
                )

    setattr(
        validate,
        "__schema_constraints__",
        {"maxItems": limit, **({"minItems": 1} if non_empty else {})},
    )
    return validate


def _string_list(
    *,
    non_empty: bool = False,
    limit: int = MAX_COLLECTION_ITEMS,
    path: bool = False,
    item_validator: Validator | None = None,
) -> Validator:
    if item_validator is not None and path:
        raise ValueError("path and item_validator cannot be combined")
    element_validator = item_validator or (_scope_path if path else _bounded_string)

    def validate(instance: object, attribute: _NamedAttribute, value: object) -> None:
        if not isinstance(value, tuple):
            raise ValueError(f"{attribute.name} must be a list")
        items = cast(tuple[object, ...], value)
        if non_empty and not items:
            raise ValueError(f"{attribute.name} must be a non-empty list")
        if len(items) > limit:
            raise ValueError(f"{attribute.name} must be at most {limit} items")
        seen: set[str] = set()
        for index, item in enumerate(items, start=1):
            item_attribute = _ListItemAttribute(f"{attribute.name}[{index}]")
            _ = element_validator(instance, item_attribute, item)
            assert isinstance(item, str)
            if item in seen:
                raise ValueError(
                    f"{attribute.name} must not contain duplicate {item!r}"
                )
            seen.add(item)

    setattr(
        validate,
        "__schema_constraints__",
        {
            "maxItems": limit,
            "uniqueItems": True,
            **({"minItems": 1} if non_empty else {}),
        },
    )
    setattr(
        validate,
        "__schema_item_constraints__",
        getattr(element_validator, "__schema_constraints__", {}),
    )
    return validate


def _identifier_list(
    *,
    non_empty: bool = False,
    limit: int = MAX_COLLECTION_ITEMS,
) -> Validator:
    return _string_list(
        non_empty=non_empty,
        limit=limit,
        item_validator=_identifier,
    )


def _uri_list(
    *,
    non_empty: bool = False,
    limit: int = MAX_COLLECTION_ITEMS,
) -> Validator:
    return _string_list(
        non_empty=non_empty,
        limit=limit,
        item_validator=_uri,
    )


def _context_string_list(
    *,
    non_empty: bool = False,
    limit: int = MAX_COLLECTION_ITEMS,
) -> Validator:
    return _string_list(
        non_empty=non_empty,
        limit=limit,
        item_validator=_context_string,
    )


class _ListItemAttribute:
    def __init__(self, name: str) -> None:
        self.name: str = name


def _unique_by(attribute_name: str, values: tuple[object, ...]) -> str | None:
    seen: set[object] = set()
    for value in values:
        item = cast(object, getattr(value, attribute_name))
        if item in seen:
            return str(item)
        seen.add(item)
    return None


@define(frozen=True)
class ContractVersion:
    schema_uri: str = field(validator=_uri)
    major: str = field(validator=_version_component)
    minor: str = field(validator=_version_component)


_SOURCE_LOCATION_SCHEMA_CONSTRAINTS = (
    {
        "if": {"required": ["end_column"]},
        "then": {"required": ["start_column"]},
    },
)


@schema_constraints(*_SOURCE_LOCATION_SCHEMA_CONSTRAINTS)
@define(frozen=True)
class SourceLocation:
    artifact_id: str = field(validator=_identifier)
    path: str = field(validator=_scope_path)
    start_line: int = field(validator=_positive_integer)
    end_line: int = field(validator=_positive_integer)
    start_column: int | None = field(
        default=None, validator=validators.optional(_positive_integer)
    )
    end_column: int | None = field(
        default=None, validator=validators.optional(_positive_integer)
    )

    @end_column.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportOptionalMemberAccess]
    def _validate_bounds(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.end_line < self.start_line:
            raise ValueError("end_line must not precede start_line")
        if self.end_column is not None and self.start_column is None:
            raise ValueError("end_column requires start_column")
        if (
            self.start_line == self.end_line
            and self.start_column is not None
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError("end_column must not precede start_column")


@define(frozen=True)
class ArtifactRef:
    artifact_id: str = field(validator=_identifier)
    role: str = field(validator=_identifier)
    uri: str = field(validator=_uri)
    digest: str = field(validator=_digest)
    size_bytes: int = field(validator=_artifact_size)
    media_type: str = field(validator=_media_type)
    schema_uri: str | None = field(default=None, validator=_optional_uri)


@define(frozen=True)
class EvidenceRef:
    evidence_id: str = field(validator=_identifier)
    kind: EvidenceKind = field(validator=validators.instance_of(EvidenceKind))
    artifact: ArtifactRef = field(validator=validators.instance_of(ArtifactRef))
    location: SourceLocation | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocation)),
    )
    summary: str | None = field(default=None, validator=_optional_string)

    @summary.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_location(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.location is not None
            and self.location.artifact_id != self.artifact.artifact_id
        ):
            raise ValueError("location.artifact_id must match artifact.artifact_id")


@define(frozen=True)
class SourcePlanRef:
    plan_id: str = field(validator=_identifier)
    revision: int = field(validator=_positive_integer)
    digest: str = field(validator=_digest)


@define(frozen=True)
class SourceCurdRef:
    curd_id: str = field(validator=_identifier)
    digest: str = field(validator=_digest)


class IngressKind(str, Enum):
    WRITER_VIEW = "writer_view"
    LEGACY_ARTIFACT = "legacy_artifact"


class NormalizationActionKind(str, Enum):
    TRIM_WHITESPACE = "trim_whitespace"
    NORMALIZE_QUOTES = "normalize_quotes"
    REMOVE_TRAILING_COMMA = "remove_trailing_comma"


@define(frozen=True)
class NormalizationAction:
    field_path: str = field(validator=_bounded_string)
    action: NormalizationActionKind = field(
        validator=validators.instance_of(NormalizationActionKind)
    )


def _normalization_receipt_schema_constraints() -> tuple[dict[str, object], ...]:
    return (
        _if_equals(
            "ingress_kind",
            IngressKind.LEGACY_ARTIFACT.value,
            {
                "required": ["source_schema_uri", "source_version"],
                # Both fields stay nullable for writer-view ingress, so the
                # conditional must also reject an explicit null here. Without
                # it a JSON Schema consumer accepts a receipt that the runtime
                # model refuses.
                "properties": {
                    "source_schema_uri": {"type": "string"},
                    "source_version": {"type": "object"},
                },
            },
        ),
    )


@schema_constraints(*_normalization_receipt_schema_constraints())
@contract("normalization-receipt")
@define(frozen=True)
class NormalizationReceipt:
    ingress_kind: IngressKind = field(validator=validators.instance_of(IngressKind))
    normalizer_id: str = field(validator=_identifier)
    source_digest: str = field(validator=_digest)
    canonical_digest: str = field(validator=_digest)
    actions: tuple[NormalizationAction, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(NormalizationAction),
    )
    source_schema_uri: str | None = field(default=None, validator=_optional_uri)
    source_version: ContractVersion | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(ContractVersion)),
    )

    @source_version.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportOptionalMemberAccess]
    def _validate_legacy_requires_source(
        self, _attribute: _NamedAttribute, _value: object
    ) -> None:  # noqa: V103
        if self.ingress_kind is not IngressKind.LEGACY_ARTIFACT:
            return
        if self.source_schema_uri is None or self.source_version is None:
            raise ValueError(
                "legacy_artifact ingress requires source_schema_uri and source_version"
            )
        # One receipt names one source. The flat URI and the nested version
        # URI are two views of the same identity, so a disagreement is a
        # forged provenance claim, not a redundant field.
        if self.source_schema_uri != self.source_version.schema_uri:
            raise ValueError(
                "legacy_artifact ingress requires source_schema_uri to equal source_version.schema_uri"
            )


@contract("handoff-pointer")
@define(frozen=True)
class HandoffPointer:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    operation_id: str = field(validator=_identifier)
    request_digest: str = field(validator=_digest)
    source_phase: str = field(validator=_identifier)
    destination_phase: str = field(validator=_identifier)
    payload: ArtifactRef = field(validator=validators.instance_of(ArtifactRef))
    normalization_receipt: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(ArtifactRef)),
    )

@schema_constraints(
    _if_equals(
        "identity_action",
        "new",
        {"properties": {"source_curd_ids": {"maxItems": 0}}},
    ),
    _if_equals(
        "identity_action",
        "retain",
        {
            "properties": {
                "source_curd_ids": {"minItems": 1, "maxItems": 1}
            }
        },
    ),
    _if_equals(
        "identity_action",
        "derive",
        {"properties": {"source_curd_ids": {"minItems": 1}}},
    ),
)
@define(frozen=True)
class IdentityLineage:
    identity_action: IdentityAction = field(
        validator=validators.instance_of(IdentityAction)
    )
    source_curd_ids: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_identifier_list(limit=MAX_CONTEXT_ITEMS),
    )

    @source_curd_ids.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_action(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        count = len(self.source_curd_ids)
        if self.identity_action is IdentityAction.NEW and count:
            raise ValueError("new lineage must not name source curds")
        if self.identity_action is IdentityAction.RETAIN and count != 1:
            raise ValueError("retain lineage must name exactly one source curd")
        if self.identity_action is IdentityAction.DERIVE and not count:
            raise ValueError("derive lineage must name at least one source curd")


@define(frozen=True)
class BoundedScope:
    paths: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_string_list(non_empty=True, limit=MAX_SCOPE_PATHS, path=True),
    )
    excluded_paths: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_string_list(limit=MAX_SCOPE_PATHS, path=True),
    )

    @excluded_paths.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_exclusions(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if set(self.paths) & set(self.excluded_paths):
            raise ValueError("paths and excluded_paths must not overlap")
        if len(self.paths) + len(self.excluded_paths) > MAX_SCOPE_PATHS:
            raise ValueError(
                f"scope must contain at most {MAX_SCOPE_PATHS} included and excluded paths"
            )


_BOUNDED_CONTEXT_SCHEMA_CONSTRAINTS = (
    {
        "anyOf": [
            {
                "properties": {"shared_inputs": {"minItems": 1}},
                "required": ["shared_inputs"],
            },
            {
                "properties": {"shared_input_keys": {"minItems": 1}},
                "required": ["shared_input_keys"],
            },
            {
                "properties": {"constraints": {"minItems": 1}},
                "required": ["constraints"],
            },
            {
                "properties": {"invariants": {"minItems": 1}},
                "required": ["invariants"],
            },
        ]
    },
)


@schema_constraints(*_BOUNDED_CONTEXT_SCHEMA_CONSTRAINTS)
@define(frozen=True)
class BoundedContext:
    shared_inputs: tuple[ArtifactRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef, limit=MAX_CONTEXT_ITEMS),
    )
    constraints: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_context_string_list(limit=MAX_CONTEXT_ITEMS),
    )
    invariants: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_context_string_list(limit=MAX_CONTEXT_ITEMS),
    )

    @invariants.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_context(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if not (self.shared_inputs or self.constraints or self.invariants):
            raise ValueError("bounded context must not be empty")
        duplicate = _unique_by("artifact_id", self.shared_inputs)
        if duplicate is not None:
            raise ValueError(f"shared_inputs artifact_id {duplicate!r} must be unique")


@define(frozen=True)
class Criterion:
    criterion_id: str = field(validator=_identifier)
    description: str = field(validator=_bounded_string)
    check: str = field(validator=_bounded_string)


@define(frozen=True)
class SemanticCurd:
    curd_id: str = field(validator=_identifier)
    outcome: str = field(validator=_bounded_string)
    scope: BoundedScope = field(validator=validators.instance_of(BoundedScope))
    inputs: tuple[ArtifactRef, ...] = field(
        converter=_tuple_sequence, validator=_list_of(ArtifactRef)
    )
    outputs: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_string_list(non_empty=True)
    )
    dependencies: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_identifier_list()
    )
    criteria: tuple[Criterion, ...] = field(
        converter=_tuple_sequence, validator=_list_of(Criterion, non_empty=True)
    )
    lineage: IdentityLineage = field(validator=validators.instance_of(IdentityLineage))

    @lineage.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_curd(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.curd_id in self.dependencies:
            raise ValueError("dependencies must not contain the curd's own curd_id")
        duplicate_input = _unique_by("artifact_id", self.inputs)
        if duplicate_input is not None:
            raise ValueError(f"inputs artifact_id {duplicate_input!r} must be unique")
        duplicate_criterion = _unique_by("criterion_id", self.criteria)
        if duplicate_criterion is not None:
            raise ValueError(
                f"criterion_id {duplicate_criterion!r} must be unique within a curd"
            )
        if (
            self.lineage.identity_action is IdentityAction.RETAIN
            and self.lineage.source_curd_ids != (self.curd_id,)
        ):
            raise ValueError(f"retain lineage must preserve curd_id {self.curd_id!r}")


@schema_constraints(
    maxItems=MAX_COLLECTION_ITEMS,
    minItems=1,
    uniqueItems=True,
)
def _validate_plan_curds(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    _list_of(SemanticCurd, non_empty=True)(_instance, attribute, value)
    assert isinstance(value, tuple)
    curds = cast(tuple[SemanticCurd, ...], value)
    duplicate_curd = _unique_by("curd_id", curds)
    if duplicate_curd is not None:
        raise ValueError(f"curd_id {duplicate_curd!r} must be unique")

    curd_ids = {curd.curd_id for curd in curds}
    criterion_ids: set[str] = set()
    for index, curd in enumerate(curds, start=1):
        for dependency in curd.dependencies:
            if dependency not in curd_ids:
                raise ValueError(
                    f"curds[{index}].dependencies references undeclared curd {dependency!r}"
                )
        for item in curd.criteria:
            if item.criterion_id in criterion_ids:
                raise ValueError(
                    f"criterion_id {item.criterion_id!r} must be unique across the plan"
                )
            criterion_ids.add(item.criterion_id)

    dependencies = {curd.curd_id: curd.dependencies for curd in curds}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(curd_id: str) -> None:
        if curd_id in visiting:
            raise ValueError("curd dependencies must be acyclic")
        if curd_id in visited:
            return
        visiting.add(curd_id)
        for dependency in dependencies[curd_id]:
            visit(dependency)
        visiting.remove(curd_id)
        visited.add(curd_id)

    for curd_id in dependencies:
        visit(curd_id)


@contract("curd-plan")
@define(frozen=True)
class CurdPlan:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    plan_id: str = field(validator=_identifier)
    revision: int = field(validator=_positive_integer)
    digest: str = field(validator=_digest)
    objective: str = field(validator=_context_string)
    curds: tuple[SemanticCurd, ...] = field(
        converter=_tuple_sequence, validator=_validate_plan_curds
    )
    context: BoundedContext | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(BoundedContext)),
    )
    parent_plan_ref: SourcePlanRef | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourcePlanRef)),
    )

    @parent_plan_ref.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportOptionalMemberAccess]
    def _validate_parent(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.parent_plan_ref is not None
            and self.parent_plan_ref.plan_id == self.plan_id
        ):
            raise ValueError("parent_plan_ref must identify a different plan")

    def __attrs_post_init__(self) -> None:
        """Reject a plan whose digest does not cover its own content."""
        expected = _curd_plan_digest(self)
        if self.digest != expected:
            raise ValueError(
                f"CurdPlan digest mismatch: expected {expected}, got {self.digest}"
            )

    @classmethod
    def signed(
        cls,
        *,
        contract_version: ContractVersion,
        plan_id: str,
        revision: int,
        objective: str,
        curds: tuple[SemanticCurd, ...],
        context: BoundedContext | None = None,
        parent_plan_ref: SourcePlanRef | None = None,
    ) -> CurdPlan:
        """Build a plan whose digest is derived from the content it signs."""
        digest = canonical_digest(
            _curd_plan_unsigned(
                contract_version=contract_version,
                plan_id=plan_id,
                revision=revision,
                objective=objective,
                curds=curds,
                context=context,
                parent_plan_ref=parent_plan_ref,
            )
        )
        return cls(
            contract_version=contract_version,
            plan_id=plan_id,
            revision=revision,
            digest=digest,
            objective=objective,
            curds=curds,
            context=context,
            parent_plan_ref=parent_plan_ref,
        )


def _curd_plan_unsigned(
    *,
    contract_version: ContractVersion,
    plan_id: str,
    revision: int,
    objective: str,
    curds: tuple[SemanticCurd, ...],
    context: BoundedContext | None,
    parent_plan_ref: SourcePlanRef | None,
) -> dict[str, object]:
    """Return the digest-covered projection of a plan: every field but ``digest``."""
    return {
        "contract_version": contract_version,
        "plan_id": plan_id,
        "revision": revision,
        "objective": objective,
        "curds": curds,
        "context": context,
        "parent_plan_ref": parent_plan_ref,
    }


def _curd_plan_digest(plan: CurdPlan) -> str:
    return canonical_digest(
        _curd_plan_unsigned(
            contract_version=plan.contract_version,
            plan_id=plan.plan_id,
            revision=plan.revision,
            objective=plan.objective,
            curds=plan.curds,
            context=plan.context,
            parent_plan_ref=plan.parent_plan_ref,
        )
    )


def curd_plan_digest(plan: object) -> str:
    """Return the digest a ``CurdPlan``'s content signs."""
    if not isinstance(plan, CurdPlan):
        raise TypeError(f"curd_plan_digest expects CurdPlan, not {type(plan).__name__}")
    return _curd_plan_digest(plan)


@define(frozen=True)
class PlannerUncertainty:
    description: str = field(validator=_bounded_string)
    scope: UncertaintyScope = field(validator=validators.instance_of(UncertaintyScope))
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )


@contract("planner-request")
@schema_constraints(
    _if_equals("kind", "decompose", _without("source_plan_ref")),
    _if_equals(
        "kind",
        "remediate",
        {
            "required": ["source_plan_ref", "evidence"],
            "properties": {"evidence": {"minItems": 1}},
        },
    ),
    _if_equals("kind", "replan", {"required": ["source_plan_ref"]}),
)
@define(frozen=True)
class PlannerRequest:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    request_id: str = field(validator=_identifier)
    kind: PlannerRequestKind = field(
        validator=validators.instance_of(PlannerRequestKind)
    )
    objective: str = field(validator=_context_string)
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )
    source_plan_ref: SourcePlanRef | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourcePlanRef)),
    )

    @source_plan_ref.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportOptionalMemberAccess]
    def _validate_kind(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.kind is PlannerRequestKind.DECOMPOSE
            and self.source_plan_ref is not None
        ):
            raise ValueError("decompose request must not name a source plan")
        if (
            self.kind is not PlannerRequestKind.DECOMPOSE
            and self.source_plan_ref is None
        ):
            raise ValueError(f"{self.kind.value} request must name a source plan")
        if self.kind is PlannerRequestKind.REMEDIATE and not self.evidence:
            raise ValueError("remediate request must carry evidence")


def _validate_planner_disposition(
    disposition: PlannerDisposition,
    plan: object | None,
    unresolved_work: tuple[_HasUncertaintyScope, ...],
    reason: str | None,
    *,
    label: str,
) -> None:
    if disposition is PlannerDisposition.COMPLETE:
        if plan is None:
            raise ValueError(f"complete {label} must carry a plan")
        if unresolved_work:
            raise ValueError(f"complete {label} must not carry unresolved work")
        if reason:
            raise ValueError(f"complete {label} must not include a reason")
        return
    if disposition is PlannerDisposition.PARTIAL:
        if plan is None:
            raise ValueError(f"partial {label} must carry a plan")
        if not unresolved_work:
            raise ValueError(f"partial {label} must describe omitted work")
        if any(
            item.scope is not UncertaintyScope.OMITTED_WORK
            for item in unresolved_work
        ):
            raise ValueError(
                f"partial {label} uncertainty must concern omitted work only"
            )
        if reason:
            raise ValueError(f"partial {label} must not include a reason")
        return
    if plan is not None:
        raise ValueError(f"{disposition.value} {label} must not carry a plan")
    if disposition is PlannerDisposition.BLOCKED and not unresolved_work:
        raise ValueError(f"blocked {label} must describe unresolved work")
    if (
        disposition
        in {
            PlannerDisposition.NO_WORK,
            PlannerDisposition.INVALID,
            PlannerDisposition.EXECUTOR_FAILURE,
        }
        and unresolved_work
    ):
        raise ValueError(
            f"{disposition.value} {label} must not carry unresolved work"
        )
    if not reason:
        raise ValueError(f"{disposition.value} {label} must include a reason")


_PLANNER_RESULT_SCHEMA_CONSTRAINTS = (
    _if_equals(
        "disposition",
        "complete",
        {
            "required": ["plan"],
            "properties": {"unresolved_work": {"maxItems": 0}},
            **_without("reason"),
        },
    ),
    _if_equals(
        "disposition",
        "partial",
        {
            "required": ["plan"],
            "properties": {
                "unresolved_work": {
                    "minItems": 1,
                    "items": {
                        "properties": {"scope": {"const": "omitted_work"}}
                    },
                }
            },
            **_without("reason"),
        },
    ),
    _if_equals(
        "disposition",
        "blocked",
        {
            "properties": {"unresolved_work": {"minItems": 1}},
            "required": ["reason"],
            **_without("plan"),
        },
    ),
    _if_equals(
        "disposition",
        "no_work",
        {
            "properties": {"unresolved_work": {"maxItems": 0}},
            "required": ["reason"],
            **_without("plan"),
        },
    ),
    _if_equals(
        "disposition",
        "invalid",
        {
            "properties": {"unresolved_work": {"maxItems": 0}},
            "required": ["reason"],
            **_without("plan"),
        },
    ),
    _if_equals(
        "disposition",
        "executor_failure",
        {
            "properties": {"unresolved_work": {"maxItems": 0}},
            "required": ["reason"],
            **_without("plan"),
        },
    ),
)


@schema_constraints(*_PLANNER_RESULT_SCHEMA_CONSTRAINTS)
@contract("planner-result")
@define(frozen=True)
class PlannerResult:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    request_id: str = field(validator=_identifier)
    disposition: PlannerDisposition = field(
        validator=validators.instance_of(PlannerDisposition)
    )
    plan: CurdPlan | None = field(
        default=None, validator=validators.optional(validators.instance_of(CurdPlan))
    )
    unresolved_work: tuple[PlannerUncertainty, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(PlannerUncertainty),
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        _validate_planner_disposition(
            self.disposition,
            self.plan,
            self.unresolved_work,
            self.reason,
            label="planner result",
        )


@contract("review-request")
@define(frozen=True)
class ReviewRequest:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    review_id: str = field(validator=_identifier)
    subject: ArtifactRef = field(validator=validators.instance_of(ArtifactRef))
    coverage_targets: tuple[str, ...] = field(
        converter=_tuple_sequence,
        validator=_identifier_list(non_empty=True),
    )
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )
    review_kind: ReviewKind | None = field(
        default=None, validator=validators.optional(validators.instance_of(ReviewKind))
    )


@schema_constraints(
    _if_equals("disposition", "covered", _without("reason")),
    _if_equals("disposition", "not_covered", {"required": ["reason"]}),
)
@define(frozen=True)
class ReviewCoverage:
    target: str = field(validator=_identifier)
    disposition: CoverageDisposition = field(
        validator=validators.instance_of(CoverageDisposition)
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.disposition is CoverageDisposition.NOT_COVERED and not self.reason:
            raise ValueError("not_covered review coverage must include a reason")
        if self.disposition is CoverageDisposition.COVERED and self.reason is not None:
            raise ValueError("covered review coverage must not include a reason")


@define(frozen=True)
class ReviewFinding:
    finding_id: str = field(validator=_identifier)
    severity: ReviewSeverity = field(validator=validators.instance_of(ReviewSeverity))
    summary: str = field(validator=_bounded_string)
    evidence: tuple[EvidenceRef, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef, non_empty=True),
    )
    location: SourceLocation | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocation)),
    )


_REVIEW_RESULT_TERMINAL_SCHEMA_CONSTRAINTS = tuple(
    _if_equals(
        "disposition",
        disposition,
        {
            "properties": {"findings": {"maxItems": 0}},
            "required": ["reason"],
        },
    )
    for disposition in ("blocked", "invalid", "executor_failure")
)


@schema_constraints(
    _if_equals(
        "disposition",
        "clean",
        {
            "required": ["coverage"],
            "properties": {
                "findings": {"maxItems": 0},
                "coverage": {
                    "minItems": 1,
                    "items": {
                        "properties": {"disposition": {"const": "covered"}}
                    },
                },
            },
        },
    ),
    _if_equals(
        "disposition",
        "findings",
        {
            "required": ["coverage"],
            "properties": {
                "findings": {"minItems": 1},
                "coverage": {"minItems": 1},
            },
        },
    ),
    *_REVIEW_RESULT_TERMINAL_SCHEMA_CONSTRAINTS,
)
@contract("review-result")
@define(frozen=True)
class ReviewResult:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    review_id: str = field(validator=_identifier)
    disposition: ReviewDisposition = field(
        validator=validators.instance_of(ReviewDisposition)
    )
    findings: tuple[ReviewFinding, ...] = field(
        converter=_tuple_sequence, validator=_list_of(ReviewFinding)
    )
    coverage: tuple[ReviewCoverage, ...] = field(
        converter=_tuple_sequence, validator=_list_of(ReviewCoverage)
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        duplicate_target = _unique_by("target", self.coverage)
        if duplicate_target is not None:
            raise ValueError(f"coverage target {duplicate_target!r} must be unique")
        duplicate_finding = _unique_by("finding_id", self.findings)
        if duplicate_finding is not None:
            raise ValueError(f"finding_id {duplicate_finding!r} must be unique")

        if self.disposition is ReviewDisposition.CLEAN:
            if self.findings:
                raise ValueError("clean review result must not include findings")
            if not self.coverage or any(
                row.disposition is not CoverageDisposition.COVERED
                for row in self.coverage
            ):
                raise ValueError("clean review result requires complete coverage")
            return
        if self.disposition is ReviewDisposition.FINDINGS:
            if not self.findings:
                raise ValueError(
                    "findings review result must include at least one finding"
                )
            if not self.coverage:
                raise ValueError("findings review result requires a coverage ledger")
            return
        if (
            self.disposition
            in {
                ReviewDisposition.BLOCKED,
                ReviewDisposition.INVALID,
                ReviewDisposition.EXECUTOR_FAILURE,
            }
            and self.findings
        ):
            raise ValueError(
                f"{self.disposition.value} review result must not include findings"
            )
        if not self.reason:
            raise ValueError(
                f"{self.disposition.value} review result must include a reason"
            )


@contract("diagnosis-request")
@define(frozen=True)
class DiagnosisRequest:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    diagnosis_id: str = field(validator=_identifier)
    symptom: str = field(validator=_context_string)
    subject: ArtifactRef = field(validator=validators.instance_of(ArtifactRef))
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )


def _reproduction_schema_constraints(
    evidence_field: str,
) -> tuple[dict[str, object], ...]:
    return (
        _if_equals(
            "status",
            "reproduced",
            {
                "required": ["observed", evidence_field],
                "properties": {evidence_field: {"minItems": 1}},
            },
        ),
        _if_equals("status", "blocked", {"required": ["observed"]}),
    )


@schema_constraints(*_reproduction_schema_constraints("evidence"))
@define(frozen=True)
class Reproduction:
    status: ReproductionDisposition = field(
        validator=validators.instance_of(ReproductionDisposition)
    )
    steps: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_string_list(non_empty=True)
    )
    observed: str | None = field(default=None, validator=_optional_string)
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )

    @evidence.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_status(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.status is ReproductionDisposition.REPRODUCED:
            if self.observed is None:
                raise ValueError("reproduced result must describe what was observed")
            if not self.evidence:
                raise ValueError("reproduced result must include evidence")
        if self.status is ReproductionDisposition.BLOCKED and self.observed is None:
            raise ValueError("blocked reproduction must explain the blocker")


def _diagnosis_hypothesis_schema_constraints(
    evidence_field: str,
) -> tuple[dict[str, object], ...]:
    return tuple(
        _if_equals(
            "disposition",
            disposition,
            {
                "required": [evidence_field],
                "properties": {evidence_field: {"minItems": 1}},
            },
        )
        for disposition in ("confirmed", "rejected")
    )


@schema_constraints(*_diagnosis_hypothesis_schema_constraints("evidence"))
@define(frozen=True)
class DiagnosisHypothesis:
    hypothesis_id: str = field(validator=_identifier)
    statement: str = field(validator=_bounded_string)
    disposition: HypothesisDisposition = field(
        validator=validators.instance_of(HypothesisDisposition)
    )
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )

    @evidence.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.disposition is not HypothesisDisposition.UNRESOLVED
            and not self.evidence
        ):
            raise ValueError(
                f"{self.disposition.value} hypothesis must include evidence"
            )


@define(frozen=True)
class DiagnosisCause:
    summary: str = field(validator=_bounded_string)
    evidence: tuple[EvidenceRef, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef, non_empty=True),
    )
    location: SourceLocation | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocation)),
    )


def _diagnosis_result_schema_constraints(
    unresolved_field: str,
) -> tuple[dict[str, object], ...]:
    without_result = _without("confirmed_cause", "regression_seam")
    return (
        _if_equals(
            "disposition",
            "confirmed",
            {
                "required": ["confirmed_cause", "regression_seam"],
                "properties": {
                    "reproduction": {
                        "properties": {"status": {"const": "reproduced"}},
                        "required": ["status"],
                    }
                },
            },
        ),
        _if_equals(
            "disposition",
            "inconclusive",
            {
                **without_result,
                "required": [unresolved_field],
                "properties": {unresolved_field: {"minItems": 1}},
            },
        ),
        _if_equals(
            "disposition",
            "not_reproduced",
            {
                **without_result,
                "properties": {
                    "reproduction": {
                        "properties": {"status": {"const": "not_reproduced"}},
                        "required": ["status"],
                    }
                },
            },
        ),
        *(
            _if_equals(
                "disposition",
                disposition,
                {**without_result, "required": ["reason"]},
            )
            for disposition in ("blocked", "invalid", "executor_failure")
        ),
    )


@schema_constraints(*_diagnosis_result_schema_constraints("unresolved_evidence"))
@contract("diagnosis-result")
@define(frozen=True)
class DiagnosisResult:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    diagnosis_id: str = field(validator=_identifier)
    disposition: DiagnosisDisposition = field(
        validator=validators.instance_of(DiagnosisDisposition)
    )
    symptom: str = field(validator=_context_string)
    reproduction: Reproduction = field(validator=validators.instance_of(Reproduction))
    hypotheses: tuple[DiagnosisHypothesis, ...] = field(
        converter=_tuple_sequence, validator=_list_of(DiagnosisHypothesis)
    )
    confirmed_cause: DiagnosisCause | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(DiagnosisCause)),
    )
    regression_seam: SourceLocation | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocation)),
    )
    unresolved_evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        duplicate = _unique_by("hypothesis_id", self.hypotheses)
        if duplicate is not None:
            raise ValueError(f"hypothesis_id {duplicate!r} must be unique")

        if self.disposition is DiagnosisDisposition.CONFIRMED:
            if self.reproduction.status is not ReproductionDisposition.REPRODUCED:
                raise ValueError("confirmed diagnosis requires a reproduced symptom")
            if self.confirmed_cause is None:
                raise ValueError("confirmed diagnosis must include a confirmed cause")
            if self.regression_seam is None:
                raise ValueError("confirmed diagnosis must identify a regression seam")
            return
        if self.confirmed_cause is not None:
            raise ValueError(
                f"{self.disposition.value} diagnosis must not include a confirmed cause"
            )
        if self.regression_seam is not None:
            raise ValueError(
                f"{self.disposition.value} diagnosis must not identify a regression seam"
            )
        if self.disposition is DiagnosisDisposition.INCONCLUSIVE:
            if not self.unresolved_evidence:
                raise ValueError(
                    "inconclusive diagnosis must include unresolved evidence"
                )
            return
        if self.disposition is DiagnosisDisposition.NOT_REPRODUCED:
            if self.reproduction.status is not ReproductionDisposition.NOT_REPRODUCED:
                raise ValueError(
                    "not_reproduced diagnosis requires a not_reproduced result"
                )
            return
        if not self.reason:
            raise ValueError(
                f"{self.disposition.value} diagnosis must include a reason"
            )


def _criterion_result_schema_constraints(
    evidence_field: str,
) -> tuple[dict[str, object], ...]:
    return (
        *(
            _if_equals(
                "disposition",
                disposition,
                {
                    "required": [evidence_field],
                    "properties": {evidence_field: {"minItems": 1}},
                },
            )
            for disposition in ("passed", "failed")
        ),
        *(
            _if_equals(
                "disposition", disposition, {"required": ["reason"]}
            )
            for disposition in ("blocked", "skipped")
        ),
    )


@schema_constraints(*_criterion_result_schema_constraints("evidence"))
@define(frozen=True)
class CriterionResult:
    criterion_id: str = field(validator=_identifier)
    disposition: CriterionDisposition = field(
        validator=validators.instance_of(CriterionDisposition)
    )
    evidence: tuple[EvidenceRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(EvidenceRef),
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.disposition
            in {
                CriterionDisposition.PASSED,
                CriterionDisposition.FAILED,
            }
            and not self.evidence
        ):
            raise ValueError(
                f"{self.disposition.value} criterion result must include evidence"
            )
        if (
            self.disposition
            in {
                CriterionDisposition.BLOCKED,
                CriterionDisposition.SKIPPED,
            }
            and not self.reason
        ):
            raise ValueError(
                f"{self.disposition.value} criterion result must include a reason"
            )


def derive_curd_disposition(rows: tuple[CriterionResult, ...]) -> CurdDisposition:
    dispositions = {row.disposition for row in rows}
    if CriterionDisposition.FAILED in dispositions:
        return CurdDisposition.FAILED
    if CriterionDisposition.BLOCKED in dispositions:
        return CurdDisposition.BLOCKED
    if dispositions == {CriterionDisposition.SKIPPED}:
        return CurdDisposition.SKIPPED
    if CriterionDisposition.SKIPPED in dispositions:
        return CurdDisposition.BLOCKED
    return CurdDisposition.PASSED


@contract("curd-result")
@schema_constraints(
    _if_equals(
        "disposition",
        "passed",
        {"properties": {"unresolved_work": {"maxItems": 0}}},
    )
)
@define(frozen=True)
class CurdResult:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    result_id: str = field(validator=_identifier)
    source_plan_ref: SourcePlanRef = field(
        validator=validators.instance_of(SourcePlanRef)
    )
    source_curd_ref: SourceCurdRef = field(
        validator=validators.instance_of(SourceCurdRef)
    )
    disposition: CurdDisposition = field(
        validator=validators.instance_of(CurdDisposition)
    )
    expected_criterion_ids: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_identifier_list(non_empty=True)
    )
    criterion_results: tuple[CriterionResult, ...] = field(
        converter=_tuple_sequence, validator=_list_of(CriterionResult, non_empty=True)
    )
    deliverables: tuple[ArtifactRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef),
    )
    unresolved_work: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )
    runtime_refs: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )

    @runtime_refs.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_result(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        result_ids = [row.criterion_id for row in self.criterion_results]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("criterion_results must contain one row per criterion_id")
        if set(result_ids) != set(self.expected_criterion_ids):
            raise ValueError(
                "criterion_results must cover expected_criterion_ids exactly"
            )
        derived = derive_curd_disposition(self.criterion_results)
        if self.disposition is not derived:
            raise ValueError(
                f"disposition must be {derived.value} for the supplied criterion_results"
            )
        duplicate = _unique_by("artifact_id", self.deliverables)
        if duplicate is not None:
            raise ValueError(f"deliverables artifact_id {duplicate!r} must be unique")
        if self.disposition is CurdDisposition.PASSED and self.unresolved_work:
            raise ValueError("passed curd result must not include unresolved work")


@define(frozen=True)
class PhaseDestination:
    destination: str = field(validator=_identifier)
    payload_schema_uri: str = field(validator=_uri)


@contract("phase-contract")
@define(frozen=True)
class PhaseContract:
    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    source: str = field(validator=_identifier)
    input_schema_uris: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_uri_list(non_empty=True)
    )
    outputs: tuple[PhaseDestination, ...] = field(
        converter=_tuple_sequence, validator=_list_of(PhaseDestination, non_empty=True)
    )

    @outputs.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_routes(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        routes = {
            (route.destination, route.payload_schema_uri) for route in self.outputs
        }
        if len(routes) != len(self.outputs):
            raise ValueError("outputs must not contain duplicate routes")


@define(frozen=True)
class UnsupportedProjection:
    target: str = field(validator=_identifier)
    curd_id: str | None = field(validator=_optional_identifier)
    field: str = field(validator=_identifier)
    reason: str = _attrs_field(validator=_bounded_string)


@define(frozen=True)
class CriterionWriterView:
    description: str = field(validator=_bounded_string)
    check: str = field(validator=_bounded_string)


@schema_constraints(*_SOURCE_LOCATION_SCHEMA_CONSTRAINTS)
@define(frozen=True)
class SourceLocationWriterView:
    path: str = field(validator=_scope_path)
    start_line: int = field(validator=_positive_integer)
    end_line: int = field(validator=_positive_integer)
    start_column: int | None = field(
        default=None, validator=validators.optional(_positive_integer)
    )
    end_column: int | None = field(
        default=None, validator=validators.optional(_positive_integer)
    )

    @end_column.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportOptionalMemberAccess]
    def _validate_bounds(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.end_line < self.start_line:
            raise ValueError("end_line must not precede start_line")
        if self.end_column is not None and self.start_column is None:
            raise ValueError("end_column requires start_column")
        if (
            self.start_line == self.end_line
            and self.start_column is not None
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError("end_column must not precede start_column")


@schema_constraints(*_BOUNDED_CONTEXT_SCHEMA_CONSTRAINTS)
@define(frozen=True)
class BoundedContextWriterView:
    shared_input_keys: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_identifier_list(limit=MAX_CONTEXT_ITEMS),
    )
    constraints: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_context_string_list(limit=MAX_CONTEXT_ITEMS),
    )
    invariants: tuple[str, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_context_string_list(limit=MAX_CONTEXT_ITEMS),
    )

    @invariants.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_context(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if not (self.shared_input_keys or self.constraints or self.invariants):
            raise ValueError("bounded context must not be empty")


@define(frozen=True)
class SemanticCurdWriterView:
    key: str = field(validator=_identifier)
    outcome: str = field(validator=_bounded_string)
    scope: BoundedScope = field(validator=validators.instance_of(BoundedScope))
    outputs: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_string_list(non_empty=True)
    )
    criteria: tuple[CriterionWriterView, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(CriterionWriterView, non_empty=True),
    )
    input_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )
    dependencies: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )


@define(frozen=True)
class CurdPlanWriterView:
    objective: str = field(validator=_context_string)
    curds: tuple[SemanticCurdWriterView, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(SemanticCurdWriterView, non_empty=True),
    )
    context: BoundedContextWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(BoundedContextWriterView)),
    )


@define(frozen=True)
class PlannerUncertaintyWriterView:
    description: str = field(validator=_bounded_string)
    scope: UncertaintyScope = field(validator=validators.instance_of(UncertaintyScope))
    evidence_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )


@schema_constraints(*_PLANNER_RESULT_SCHEMA_CONSTRAINTS)
@define(frozen=True)
class PlannerResultWriterView:
    disposition: PlannerDisposition = field(
        validator=validators.instance_of(PlannerDisposition)
    )
    plan: CurdPlanWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(CurdPlanWriterView)),
    )
    unresolved_work: tuple[PlannerUncertaintyWriterView, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(PlannerUncertaintyWriterView),
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        _validate_planner_disposition(
            self.disposition,
            self.plan,
            self.unresolved_work,
            self.reason,
            label="planner writer view",
        )


@define(frozen=True)
class ReviewFindingWriterView:
    severity: ReviewSeverity = field(validator=validators.instance_of(ReviewSeverity))
    summary: str = field(validator=_bounded_string)
    evidence_keys: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_identifier_list(non_empty=True)
    )
    location: SourceLocationWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocationWriterView)),
    )


@schema_constraints(
    _if_equals(
        "disposition",
        "clean",
        {"properties": {"findings": {"maxItems": 0}}},
    ),
    _if_equals(
        "disposition",
        "findings",
        {"properties": {"findings": {"minItems": 1}}},
    ),
    *_REVIEW_RESULT_TERMINAL_SCHEMA_CONSTRAINTS,
)
@define(frozen=True)
class ReviewResultWriterView:
    disposition: ReviewDisposition = field(
        validator=validators.instance_of(ReviewDisposition)
    )
    findings: tuple[ReviewFindingWriterView, ...] = field(
        converter=_tuple_sequence, validator=_list_of(ReviewFindingWriterView)
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.disposition is ReviewDisposition.CLEAN and self.findings:
            raise ValueError("clean review writer view must not include findings")
        if self.disposition is ReviewDisposition.FINDINGS and not self.findings:
            raise ValueError(
                "findings review writer view must include at least one finding"
            )
        if (
            self.disposition
            in {
                ReviewDisposition.BLOCKED,
                ReviewDisposition.INVALID,
                ReviewDisposition.EXECUTOR_FAILURE,
            }
            and self.findings
        ):
            raise ValueError(
                f"{self.disposition.value} review writer view must not include findings"
            )
        if (
            self.disposition
            in {
                ReviewDisposition.BLOCKED,
                ReviewDisposition.INVALID,
                ReviewDisposition.EXECUTOR_FAILURE,
            }
            and not self.reason
        ):
            raise ValueError(
                f"{self.disposition.value} review writer view must include a reason"
            )


@schema_constraints(*_reproduction_schema_constraints("evidence_keys"))
@define(frozen=True)
class ReproductionWriterView:
    status: ReproductionDisposition = field(
        validator=validators.instance_of(ReproductionDisposition)
    )
    steps: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_string_list(non_empty=True)
    )
    observed: str | None = field(default=None, validator=_optional_string)
    evidence_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )

    @evidence_keys.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_status(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.status is ReproductionDisposition.REPRODUCED:
            if self.observed is None:
                raise ValueError(
                    "reproduced writer result must describe what was observed"
                )
            if not self.evidence_keys:
                raise ValueError("reproduced writer result must include evidence")
        if self.status is ReproductionDisposition.BLOCKED and self.observed is None:
            raise ValueError("blocked writer reproduction must explain the blocker")


@schema_constraints(
    *_diagnosis_hypothesis_schema_constraints("evidence_keys")
)
@define(frozen=True)
class DiagnosisHypothesisWriterView:
    statement: str = field(validator=_bounded_string)
    disposition: HypothesisDisposition = field(
        validator=validators.instance_of(HypothesisDisposition)
    )
    evidence_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )

    @evidence_keys.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.disposition is not HypothesisDisposition.UNRESOLVED
            and not self.evidence_keys
        ):
            raise ValueError(
                f"{self.disposition.value} hypothesis must include evidence"
            )


@define(frozen=True)
class DiagnosisCauseWriterView:
    summary: str = field(validator=_bounded_string)
    evidence_keys: tuple[str, ...] = field(
        converter=_tuple_sequence, validator=_identifier_list(non_empty=True)
    )
    location: SourceLocationWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocationWriterView)),
    )


@schema_constraints(
    *_diagnosis_result_schema_constraints("unresolved_evidence_keys")
)
@define(frozen=True)
class DiagnosisResultWriterView:
    disposition: DiagnosisDisposition = field(
        validator=validators.instance_of(DiagnosisDisposition)
    )
    reproduction: ReproductionWriterView = field(
        validator=validators.instance_of(ReproductionWriterView)
    )
    hypotheses: tuple[DiagnosisHypothesisWriterView, ...] = field(
        converter=_tuple_sequence, validator=_list_of(DiagnosisHypothesisWriterView)
    )
    confirmed_cause: DiagnosisCauseWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(DiagnosisCauseWriterView)),
    )
    regression_seam: SourceLocationWriterView | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(SourceLocationWriterView)),
    )
    unresolved_evidence_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if self.disposition is DiagnosisDisposition.CONFIRMED:
            if self.reproduction.status is not ReproductionDisposition.REPRODUCED:
                raise ValueError(
                    "confirmed diagnosis writer view requires a reproduced symptom"
                )
            if self.confirmed_cause is None:
                raise ValueError(
                    "confirmed diagnosis writer view must include a confirmed cause"
                )
            if self.regression_seam is None:
                raise ValueError(
                    "confirmed diagnosis writer view must identify a regression seam"
                )
            return
        if self.confirmed_cause is not None:
            raise ValueError(
                f"{self.disposition.value} diagnosis writer view must not include a confirmed cause"
            )
        if self.regression_seam is not None:
            raise ValueError(
                f"{self.disposition.value} diagnosis writer view must not identify a regression seam"
            )
        if self.disposition is DiagnosisDisposition.INCONCLUSIVE:
            if not self.unresolved_evidence_keys:
                raise ValueError(
                    "inconclusive diagnosis writer view must include unresolved evidence"
                )
            return
        if self.disposition is DiagnosisDisposition.NOT_REPRODUCED:
            if self.reproduction.status is not ReproductionDisposition.NOT_REPRODUCED:
                raise ValueError(
                    "not_reproduced diagnosis writer view requires a not_reproduced result"
                )
            return
        if not self.reason:
            raise ValueError(
                f"{self.disposition.value} diagnosis writer view must include a reason"
            )


@schema_constraints(*_criterion_result_schema_constraints("evidence_keys"))
@define(frozen=True)
class CriterionResultWriterView:
    disposition: CriterionDisposition = field(
        validator=validators.instance_of(CriterionDisposition)
    )
    evidence_keys: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )
    reason: str | None = field(default=None, validator=_optional_string)

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_disposition(self, _attribute: _NamedAttribute, _value: object) -> None:  # noqa: V103
        if (
            self.disposition
            in {
                CriterionDisposition.PASSED,
                CriterionDisposition.FAILED,
            }
            and not self.evidence_keys
        ):
            raise ValueError(
                f"{self.disposition.value} criterion result must include evidence"
            )
        if (
            self.disposition
            in {
                CriterionDisposition.BLOCKED,
                CriterionDisposition.SKIPPED,
            }
            and not self.reason
        ):
            raise ValueError(
                f"{self.disposition.value} criterion result must include a reason"
            )


@define(frozen=True)
class DeliverableWriterView:
    role: str = field(validator=_identifier)
    path: str = field(validator=_scope_path)
    media_type: str = field(validator=_media_type)


@define(frozen=True)
class CurdResultWriterView:
    criterion_results: tuple[CriterionResultWriterView, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(CriterionResultWriterView, non_empty=True),
    )
    deliverables: tuple[DeliverableWriterView, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(DeliverableWriterView),
    )
    unresolved_work: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )


WriterPayload = (
    CurdPlanWriterView
    | PlannerResultWriterView
    | ReviewResultWriterView
    | DiagnosisResultWriterView
    | CurdResultWriterView
)

_WRITER_PAYLOAD_TYPES: dict[WriterViewKind, type] = {
    WriterViewKind.CURD_PLAN: CurdPlanWriterView,
    WriterViewKind.PLANNER_RESULT: PlannerResultWriterView,
    WriterViewKind.REVIEW_RESULT: ReviewResultWriterView,
    WriterViewKind.DIAGNOSIS_RESULT: DiagnosisResultWriterView,
    WriterViewKind.CURD_RESULT: CurdResultWriterView,
}


def writer_payload_types() -> dict[WriterViewKind, type]:
    """Public accessor for the writer-view-kind to payload-type mapping."""
    return dict(_WRITER_PAYLOAD_TYPES)


@schema_constraints(
    {
        "oneOf": [
            {
                "properties": {
                    "kind": {"const": "curd_plan"},
                    "payload": {"$ref": "#/$defs/CurdPlanWriterView"},
                },
                "required": ["kind", "payload"],
            },
            {
                "properties": {
                    "kind": {"const": "planner_result"},
                    "payload": {"$ref": "#/$defs/PlannerResultWriterView"},
                },
                "required": ["kind", "payload"],
            },
            {
                "properties": {
                    "kind": {"const": "review_result"},
                    "payload": {"$ref": "#/$defs/ReviewResultWriterView"},
                },
                "required": ["kind", "payload"],
            },
            {
                "properties": {
                    "kind": {"const": "diagnosis_result"},
                    "payload": {"$ref": "#/$defs/DiagnosisResultWriterView"},
                },
                "required": ["kind", "payload"],
            },
            {
                "properties": {
                    "kind": {"const": "curd_result"},
                    "payload": {"$ref": "#/$defs/CurdResultWriterView"},
                },
                "required": ["kind", "payload"],
            },
        ]
    }
)
@contract("agent-writer-view")
@define(frozen=True)
class AgentWriterView:
    kind: WriterViewKind = field(validator=validators.instance_of(WriterViewKind))
    payload: WriterPayload = field()

    @payload.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_payload(self, _attribute: _NamedAttribute, value: object) -> None:  # noqa: V103
        expected = _WRITER_PAYLOAD_TYPES[self.kind]
        if not isinstance(value, expected):
            raise ValueError(
                f"{self.kind.value} writer view payload must be {expected.__name__}"
            )


# --- mold-spec document format (skills-only-spec-format-enforcement) ---
#
# Declares the mold spec-template shape as decorated models beside the
# existing @contract markers.  A build-only compiler in the
# _schema_catalog_compiler family (_document_rules_compiler.py) projects
# this declaration into the dependency-free
# src/easy_cheese/shared/document_rules.py, consumed by the hand-rolled
# src/easy_cheese/skills/mold/validate_spec.py CLI.


@define(frozen=True)
class TableRule:
    """Column shape and per-row rule descriptions for a section's table."""

    columns: tuple[str, ...] = field(converter=_tuple_sequence)
    per_row: tuple[str, ...] = field(converter=_tuple_sequence, factory=tuple)


@define(frozen=True)
class Section:
    """One declared spec-template section."""

    name: str
    optional: bool = False
    table: TableRule | None = None


@define(frozen=True)
class CrossFieldRule:
    """A named cross-field semantic rule enforced on MoldSpecDocument."""

    rule_id: str
    description: str


class GateApplicabilityDisposition(str, Enum):
    RED_REQUIRED = "red-required"
    NOT_APPLICABLE = "not-applicable"


class WorkClass(str, Enum):
    BEHAVIOR = "behavior"
    DOCS_ONLY = "docs-only"
    REFACTOR_ONLY = "refactor-only"
    TEST_ONLY = "test-only"
    APPEARANCE_ONLY = "appearance-only"


class UiSurface(str, Enum):
    BROWSER = "browser"
    NON_BROWSER = "non-browser"
    NOT_APPLICABLE = "not-applicable"


class SpecConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TestContractMode(str, Enum):
    TRACER = "tracer"
    CONTRACT_MATRIX = "contract-matrix"
    GUARD = "guard"


class GroundingProbe(str, Enum):
    """The preconditions a spec may not be curdled without having probed.

    ``wiki`` is the durable-knowledge probe; ``explorer`` is the delegated
    code-evidence probe.  Both are steps mold's prose already mandated and
    that runs skipped, so they are recorded as spec rows instead.
    """

    WIKI = "wiki"
    EXPLORER = "explorer"


class GroundingOutcome(str, Enum):
    """What the probe returned.  ``unavailable`` keeps the degrade path open
    while forcing it to leave evidence rather than be assumed."""

    HIT = "hit"
    MISS = "miss"
    UNAVAILABLE = "unavailable"


@define(frozen=True)
class GateApplicability:
    disposition: GateApplicabilityDisposition = field(
        validator=validators.instance_of(GateApplicabilityDisposition)
    )
    work_class: WorkClass = field(validator=validators.instance_of(WorkClass))
    ui_surface: UiSurface = field(validator=validators.instance_of(UiSurface))
    reason: str | None = field(default=None, validator=_optional_string)

    @ui_surface.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_combination(
        self, _attribute: _NamedAttribute, value: object
    ) -> None:  # noqa: V103
        if self.disposition is GateApplicabilityDisposition.RED_REQUIRED:
            if self.work_class is not WorkClass.BEHAVIOR:
                raise ValueError("red-required-work-class-must-be-behavior")
            if value is UiSurface.NOT_APPLICABLE:
                raise ValueError(
                    "red-required-ui-surface-must-be-browser-or-non-browser"
                )
        else:
            if self.work_class is WorkClass.BEHAVIOR:
                raise ValueError(
                    "not-applicable-work-class-must-be-closed-non-behavior"
                )
            if value is not UiSurface.NOT_APPLICABLE:
                raise ValueError(
                    "not-applicable-ui-surface-must-be-not-applicable"
                )

    @reason.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_not_applicable_reason(
        self, _attribute: _NamedAttribute, value: object
    ) -> None:  # noqa: V103
        if self.disposition is GateApplicabilityDisposition.NOT_APPLICABLE and not value:
            raise ValueError(
                "gate_applicability.reason is required when disposition is not-applicable"
            )


@define(frozen=True)
class MoldSpecFrontmatter:
    slug: str = field(validator=_identifier)
    status: str = field(validator=_bounded_string)
    source: str = field(validator=_bounded_string)
    created: str = field(validator=_bounded_string)
    confidence: SpecConfidence = field(validator=validators.instance_of(SpecConfidence))
    gate_applicability: GateApplicability = field(
        validator=validators.instance_of(GateApplicability)
    )
    gates_overridden: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )
    agent_introduced_scope: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )
    entity_referent_bindings: tuple[Mapping[str, object], ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_list_of(Mapping)
    )


@define(frozen=True)
class TestContractRow:
    acceptance_id: str = field(validator=_identifier)
    interface_referent: str = field(validator=_bounded_string)
    outermost_stable_seam: str = field(validator=_bounded_string)
    expected_failure: str = field(validator=_bounded_string)
    mode: TestContractMode = field(validator=validators.instance_of(TestContractMode))
    interface_version: str = field(default="", validator=validators.instance_of(str))
    matrix_rows: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )

    @matrix_rows.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_mode_cells(self, _attribute: _NamedAttribute, value: object) -> None:  # noqa: V103
        if self.mode in (TestContractMode.TRACER, TestContractMode.GUARD):
            if self.interface_version or value:
                raise ValueError(
                    f"Test Contracts row {self.acceptance_id} is {self.mode.value} mode and must leave Interface version and Matrix rows blank"
                )
        elif not self.interface_version or not value:
            raise ValueError(
                f"Test Contracts row {self.acceptance_id} is contract-matrix mode and requires both Interface version and Matrix rows"
            )
        elif len(set(cast(tuple[str, ...], value))) != len(cast(tuple[str, ...], value)):
            raise ValueError(
                f"contract-matrix-rows-not-unique:{self.acceptance_id}"
            )


@define(frozen=True)
class GroundingRow:
    """One recorded precondition probe standing behind the spec."""

    probe: GroundingProbe = field(validator=validators.instance_of(GroundingProbe))
    outcome: GroundingOutcome = field(validator=validators.instance_of(GroundingOutcome))
    evidence: str = field(validator=_bounded_string)


GROUNDING_COLUMNS: tuple[str, ...] = ("Probe", "Outcome", "Evidence")

GROUNDING_TABLE_RULE = TableRule(
    columns=GROUNDING_COLUMNS,
    per_row=(
        "Probe and Outcome are drawn from their closed sets",
        "Evidence is non-empty, including for unavailable outcomes",
    ),
)


TEST_CONTRACT_COLUMNS: tuple[str, ...] = (
    "Acceptance ID",
    "Interface referent",
    "Outermost stable seam",
    "Expected failure",
    "Mode",
    "Interface version",
    "Matrix rows",
)

TEST_CONTRACT_TABLE_RULE = TableRule(
    columns=TEST_CONTRACT_COLUMNS,
    per_row=(
        "tracer rows leave Interface version and Matrix rows blank",
        "contract-matrix rows require both Interface version and Matrix rows",
    ),
)

MOLD_SPEC_SECTIONS: tuple[Section, ...] = (
    Section("Problem"),
    Section("Goals"),
    Section("Non-goals"),
    Section("Deferred follow-ups", optional=True),
    Section("Grounding", table=GROUNDING_TABLE_RULE),
    Section("Approach"),
    Section("Decisions"),
    Section("Acceptance"),
    Section("Test Contracts", optional=True, table=TEST_CONTRACT_TABLE_RULE),
    Section("Interface sketches"),
    Section("Risks"),
    Section("Open questions"),
    Section("Quality gates"),
    Section("Curds"),
    Section("Reproduction", optional=True),
    Section("References", optional=True),
)

MOLD_SPEC_ENUMS: dict[str, tuple[str, ...]] = {
    "mode": tuple(mode.value for mode in TestContractMode),
    "grounding_probe": tuple(probe.value for probe in GroundingProbe),
    "grounding_outcome": tuple(outcome.value for outcome in GroundingOutcome),
    "gate_applicability_disposition": tuple(
        disposition.value for disposition in GateApplicabilityDisposition
    ),
    "work_class": tuple(work_class.value for work_class in WorkClass),
    "ui_surface": tuple(ui_surface.value for ui_surface in UiSurface),
}

MOLD_SPEC_CROSS_FIELD_RULES: tuple[CrossFieldRule, ...] = (
    CrossFieldRule(
        rule_id="ac-coverage-exactly-once",
        description="Every Acceptance ID must appear exactly once in the Test Contracts table.",
    ),
    CrossFieldRule(
        rule_id="tracer-row-blank-matrix-cells",
        description="Tracer rows must leave Interface version and Matrix rows blank.",
    ),
    CrossFieldRule(
        rule_id="contract-matrix-row-requires-both",
        description="Contract-matrix rows require both Interface version and Matrix rows.",
    ),
    CrossFieldRule(
        rule_id="grounding-probe-recorded",
        description="The Grounding table must record the wiki probe exactly once with non-empty evidence.",
    ),
    CrossFieldRule(
        rule_id="delegation-digest-recorded",
        description="The Grounding table must record the explorer probe exactly once with non-empty evidence.",
    ),
    CrossFieldRule(
        rule_id="not-applicable-closed-class",
        description=(
            "red-required requires Test Contracts; not-applicable forbids them "
            "and requires a reason."
        ),
    ),
)


@define(frozen=True)
class MoldSpecDocument:
    """The mold-spec prose document contract; ``slug`` is its canonical schema slug."""

    frontmatter: MoldSpecFrontmatter = field(
        validator=validators.instance_of(MoldSpecFrontmatter)
    )
    acceptance_ids: tuple[str, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_identifier_list()
    )
    test_contract_rows: tuple[TestContractRow, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_list_of(TestContractRow)
    )
    grounding_rows: tuple[GroundingRow, ...] = field(
        factory=tuple, converter=_tuple_sequence, validator=_list_of(GroundingRow)
    )

    slug: ClassVar[str] = "mold-spec"
    sections: ClassVar[tuple[Section, ...]] = MOLD_SPEC_SECTIONS
    cross_field_rules: ClassVar[tuple[CrossFieldRule, ...]] = MOLD_SPEC_CROSS_FIELD_RULES
    enums: ClassVar[dict[str, tuple[str, ...]]] = MOLD_SPEC_ENUMS

    @acceptance_ids.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_unique_acceptance_ids(
        self, _attribute: _NamedAttribute, value: object
    ) -> None:  # noqa: V103
        assert isinstance(value, tuple)
        ids = cast(tuple[str, ...], value)
        if len(set(ids)) != len(ids):
            raise ValueError("acceptance-ids-not-unique")

    @test_contract_rows.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_ac_coverage(self, _attribute: _NamedAttribute, value: object) -> None:  # noqa: V103
        assert isinstance(value, tuple)
        rows = cast(tuple[TestContractRow, ...], value)
        if (
            self.frontmatter.gate_applicability.disposition
            is GateApplicabilityDisposition.NOT_APPLICABLE
        ):
            if rows:
                raise ValueError(
                    "gate_applicability.disposition=not-applicable requires no Test Contracts rows"
                )
            return

        counts: dict[str, int] = {}
        for row in rows:
            counts[row.acceptance_id] = counts.get(row.acceptance_id, 0) + 1
        missing = [ac for ac in self.acceptance_ids if counts.get(ac, 0) != 1]
        duplicated = sorted(ac for ac, count in counts.items() if count > 1)
        unexpected = sorted(ac for ac in counts if ac not in self.acceptance_ids)
        if missing or duplicated or unexpected:
            raise ValueError(
                f"Test Contracts table must cover every Acceptance ID exactly once: missing={missing} duplicated={duplicated} unexpected={unexpected}"
            )

    @grounding_rows.validator  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue]
    def _validate_grounding_coverage(self, _attribute: _NamedAttribute, value: object) -> None:  # noqa: V103
        assert isinstance(value, tuple)
        rows = cast(tuple[GroundingRow, ...], value)
        counts: dict[GroundingProbe, int] = {}
        for row in rows:
            counts[row.probe] = counts.get(row.probe, 0) + 1
        violations = [
            f"Grounding table must record the {probe.value} probe exactly once, got {counts.get(probe, 0)}"
            for probe in GroundingProbe
            if counts.get(probe, 0) != 1
        ]
        if violations:
            raise ValueError("; ".join(violations))


__all__ = [
    "MAX_ARTIFACT_BYTES",
    "MAX_COLLECTION_ITEMS",
    "MAX_CONTEXT_ITEMS",
    "MAX_CONTEXT_TEXT_LENGTH",
    "MAX_CONTRACT_BYTES",
    "MAX_CONTRACT_DEPTH",
    "MAX_SCOPE_PATHS",
    "MAX_TEXT_LENGTH",
    "canonical_bytes",
    "canonical_digest",
    "curd_plan_digest",
    "derive_curd_disposition",
    "CurdDisposition",
    "AgentWriterView",
    "ArtifactRef",
    "BoundedContext",
    "BoundedContextWriterView",
    "BoundedScope",
    "ContractVersion",
    "CoverageDisposition",
    "Criterion",
    "CriterionDisposition",
    "CriterionResult",
    "CriterionResultWriterView",
    "CriterionWriterView",
    "CurdPlan",
    "CurdPlanWriterView",
    "CrossFieldRule",
    "CurdResult",
    "CurdResultWriterView",
    "DeliverableWriterView",
    "DiagnosisCause",
    "DiagnosisCauseWriterView",
    "DiagnosisDisposition",
    "DiagnosisHypothesis",
    "DiagnosisHypothesisWriterView",
    "DiagnosisRequest",
    "DiagnosisResult",
    "DiagnosisResultWriterView",
    "EvidenceKind",
    "EvidenceRef",
    "GateApplicability",
    "GateApplicabilityDisposition",
    "GroundingOutcome",
    "GroundingProbe",
    "GroundingRow",
    "HypothesisDisposition",
    "IdentityAction",
    "IdentityLineage",
    "MoldSpecDocument",
    "MoldSpecFrontmatter",
    "PhaseContract",
    "PhaseDestination",
    "PlannerDisposition",
    "PlannerRequest",
    "PlannerRequestKind",
    "PlannerResult",
    "PlannerResultWriterView",
    "PlannerUncertainty",
    "PlannerUncertaintyWriterView",
    "Reproduction",
    "ReproductionDisposition",
    "ReproductionWriterView",
    "ReviewCoverage",
    "ReviewDisposition",
    "ReviewFinding",
    "ReviewFindingWriterView",
    "ReviewRequest",
    "ReviewResult",
    "ReviewResultWriterView",
    "ReviewSeverity",
    "Section",
    "SemanticCurd",
    "SemanticCurdWriterView",
    "SourceCurdRef",
    "SourceLocation",
    "SourceLocationWriterView",
    "SourcePlanRef",
    "SpecConfidence",
    "TableRule",
    "TestContractMode",
    "TestContractRow",
    "UiSurface",
    "UncertaintyScope",
    "UnsupportedProjection",
    "WorkClass",
    "WriterPayload",
    "WriterViewKind",
]
