from __future__ import annotations

import json
import types
from collections.abc import Mapping
from enum import Enum
from functools import cache
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints  # pyright: ignore[reportDeprecated]

import attrs
from attrs import Attribute
from easy_cheese_schemas._schema_catalog import (
    REGISTERED_CONTRACT_SCHEMA_URIS,
    SCHEMA_ROOT,
)
import easy_cheese_schemas.contracts as contract_models

from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    BoundedContext,
    ContractVersion,
    Criterion,
    CriterionResult,
    CurdPlan,
    CurdPlanWriterView,
    CurdResult,
    CurdResultWriterView,
    DiagnosisCause,
    DiagnosisCauseWriterView,
    DiagnosisHypothesis,
    DiagnosisHypothesisWriterView,
    DiagnosisResult,
    DiagnosisResultWriterView,
    EvidenceRef,
    HandoffPointer,
    IdentityAction,
    IdentityLineage,
    MAX_CONTRACT_BYTES,
    MAX_CONTRACT_DEPTH,
    PlannerResult,
    PlannerResultWriterView,
    PlannerUncertainty,
    Reproduction,
    ReproductionWriterView,
    ReviewCoverage,
    ReviewFinding,
    ReviewFindingWriterView,
    ReviewResult,
    ReviewResultWriterView,
    SemanticCurd,
    SourceCurdRef,
    SourceLocation,
    SourceLocationWriterView,
    SourcePlanRef,
    WriterViewKind,
    canonical_bytes,
    canonical_digest,
    curd_plan_digest,
    derive_curd_disposition,
)
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


@attrs.define(frozen=True, slots=True)
class _RegisteredContract:
    schema_uri: str
    contract: type
    supported_version: ContractVersion | None


_MARKED_CONTRACTS = contract_models.registered_contracts()
_REGISTERED_CONTRACTS = tuple(
    _RegisteredContract(
        schema_uri := f"{SCHEMA_ROOT}/{slug}",
        contract,
        (
            ContractVersion(schema_uri=schema_uri, major="1", minor="0")
            if "contract_version" in attrs.fields_dict(contract)
            else None
        ),
    )
    for slug, contract in _MARKED_CONTRACTS
)
if frozenset(entry.schema_uri for entry in _REGISTERED_CONTRACTS) != (
    REGISTERED_CONTRACT_SCHEMA_URIS
):
    raise RuntimeError("generated schema catalog is stale")
_CANONICAL_SCHEMA_BY_WRITER_KIND = {
    WriterViewKind.CURD_PLAN: f"{SCHEMA_ROOT}/curd-plan",
    WriterViewKind.PLANNER_RESULT: f"{SCHEMA_ROOT}/planner-result",
    WriterViewKind.REVIEW_RESULT: f"{SCHEMA_ROOT}/review-result",
    WriterViewKind.DIAGNOSIS_RESULT: f"{SCHEMA_ROOT}/diagnosis-result",
    WriterViewKind.CURD_RESULT: f"{SCHEMA_ROOT}/curd-result",
}

_HOST_OWNED_FIELDS = {
    "artifact_id",
    "contract_version",
    "coverage",
    "curd_id",
    "criterion_id",
    "digest",
    "diagnosis_id",
    "evidence",
    "expected_criterion_ids",
    "finding_id",
    "hypothesis_id",
    "identity_action",
    "lineage",
    "plan_id",
    "request_id",
    "result_id",
    "review_id",
    "revision",
    "runtime_refs",
    "schema_uri",
    "size_bytes",
    "source_curd_ref",
    "source_plan_ref",
    "uri",
}

_MISSING = object()


class ContractValidationError(ValueError):
    pass


@attrs.define(frozen=True)
class CanonicalArtifact:
    value: object
    canonical_bytes: bytes
    source_version: ContractVersion | None


@attrs.define(frozen=True)
class AcceptedArtifact:
    canonical: CanonicalArtifact
    normalization_receipt: ArtifactRef | None = None


@attrs.define(frozen=True)
class PublishedArtifact:
    pointer: HandoffPointer
    canonical: CanonicalArtifact
    normalization_receipt: ArtifactRef | None = None


def _enum_schema(enum: type[Enum]) -> dict[str, object]:
    values = [cast(object, member.value) for member in enum]
    value_type = type(values[0])
    json_types: dict[type, str] = {str: "string", int: "integer"}
    json_type = json_types.get(value_type)
    if json_type is None:
        raise TypeError(f"unsupported enum value type {value_type.__name__}")
    return {"enum": values, "type": json_type}


def _validator_constraints(validator: object) -> dict[str, object]:
    if validator is None:
        return {}
    constraints = cast(
        "Mapping[str, object]", getattr(validator, "__schema_constraints__", {})
    )
    result = dict(constraints)
    nested = cast(object, getattr(validator, "validator", None))
    if nested is not None and nested is not validator:
        result.update(_validator_constraints(nested))
    nested_many = cast("tuple[object, ...]", getattr(validator, "validators", ()))
    for child in nested_many:
        result.update(_validator_constraints(child))
    return result


def _apply_schema_constraints(
    schema: dict[str, object], constraints: Mapping[str, object]
) -> dict[str, object]:
    if not constraints:
        return schema
    constrained = dict(schema)
    constrained.update(constraints)
    return constrained
_REPOSITORY_RELATIVE_PATH_PATTERN = (
    r"^(?!/)(?!\.{1,2}$)(?!.*(?:^|/)\.\.(?:/|$))[\s\S]+$"
)




def _contract_version_definition(
    owner: type | None, definitions: dict[str, object]
) -> dict[str, object]:
    if owner is not None:
        try:
            registered = _registered(owner)
        except KeyError:
            registered = None
    else:
        registered = None
    name = "ContractVersion"
    if name in definitions:
        if registered is not None and owner is not None:
            name = f"{owner.__name__}ContractVersion"
        else:
            return {"$ref": "#/$defs/ContractVersion"}
    if name not in definitions:
        properties: dict[str, object] = {
            "schema_uri": {
                "minLength": 1,
                "pattern": r"[A-Za-z][A-Za-z0-9+.-]*:.+",
                "type": "string",
            },
            "major": {
                "minLength": 1,
                "pattern": r"(?:0|[1-9][0-9]*)",
                "type": "string",
            },
            "minor": {
                "minLength": 1,
                "pattern": r"(?:0|[1-9][0-9]*)",
                "type": "string",
            },
        }
        schema: dict[str, object] = {
            "additionalProperties": False,
            "properties": properties,
            "required": ["schema_uri", "major", "minor"],
            "type": "object",
        }
        if registered is not None and registered.supported_version is not None:
            version = registered.supported_version
            properties["schema_uri"] = {
                "const": registered.schema_uri,
                "type": "string",
            }
            properties["major"] = {
                "const": version.major,
                "type": "string",
            }
            properties["minor"] = {
                "const": version.minor,
                "type": "string",
            }
        definitions[name] = schema
    return {"$ref": f"#/$defs/{name}"}

_UNIQUE_COLLECTION_FIELDS = {
    "BoundedContext": {"shared_inputs"},
    "CurdPlan": {"curds"},
    "CurdResult": {"criterion_results", "deliverables"},
    "DiagnosisResult": {"hypotheses"},
    "PhaseContract": {"outputs"},
    "ReviewResult": {"coverage", "findings"},
    "SemanticCurd": {"criteria", "inputs"},
}


def _definition(type_: type, definitions: dict[str, object]) -> dict[str, object]:
    name = type_.__name__
    reference: dict[str, object] = {"$ref": f"#/$defs/{name}"}
    if name in definitions:
        return reference

    definitions[name] = {}
    hints = cast("dict[str, object]", get_type_hints(type_))
    fields = cast("tuple[Attribute[object], ...]", attrs.fields(type_))
    properties: dict[str, object] = {}
    required: list[str] = []
    for attribute in fields:
        property_schema = _type_schema(
            hints[attribute.name],
            definitions,
            attribute.validator,
            field_name=attribute.name,
            owner=type_,
        )
        if (
            attribute.name in _UNIQUE_COLLECTION_FIELDS.get(name, set())
            and property_schema.get("type") == "array"
        ):
            property_schema = {**property_schema, "uniqueItems": True}
        properties[attribute.name] = property_schema
        if attribute.default is attrs.NOTHING:
            required.append(attribute.name)

    schema: dict[str, object] = {
        "additionalProperties": False,
        "properties": properties,
        "type": "object",
    }
    if required:
        schema["required"] = required
    model_constraints = cast(
        "tuple[object, ...]", getattr(type_, "__schema_constraints__", ())
    )
    if model_constraints:
        schema["allOf"] = list(model_constraints)
    definitions[name] = schema
    return reference


def _type_schema(
    annotation: object,
    definitions: dict[str, object],
    validator: object = None,
    *,
    field_name: str | None = None,
    owner: type | None = None,
) -> dict[str, object]:
    constraints = _validator_constraints(validator)
    item_constraints = dict(
        cast(
            "Mapping[str, object]",
            getattr(validator, "__schema_item_constraints__", {}),
        )
    )
    if field_name in {"path", "paths", "excluded_paths"}:
        if field_name == "path":
            constraints = {
                **constraints,
                "pattern": _REPOSITORY_RELATIVE_PATH_PATTERN,
            }
        else:
            item_constraints = {
                **item_constraints,
                "pattern": _REPOSITORY_RELATIVE_PATH_PATTERN,
            }
    origin = get_origin(annotation)
    if origin in {types.UnionType, Union}:  # pyright: ignore[reportDeprecated]
        members = cast("tuple[object, ...]", get_args(annotation))
        schema: dict[str, object] = {
            "anyOf": [
                _type_schema(
                    member,
                    definitions,
                    field_name=field_name,
                    owner=owner,
                )
                for member in members
            ]
        }
    elif origin in {list, tuple}:
        item_type, *remainder = cast("tuple[object, ...]", get_args(annotation))
        if origin is tuple and remainder != [Ellipsis]:
            prefix_items = [
                _type_schema(member, definitions, owner=owner)
                for member in (item_type, *remainder)
            ]
            if item_constraints:
                prefix_items = [
                    _apply_schema_constraints(item, item_constraints)
                    for item in prefix_items
                ]
            schema = {"prefixItems": prefix_items, "type": "array"}
        else:
            item_schema = _type_schema(item_type, definitions, owner=owner)
            if item_constraints:
                item_schema = _apply_schema_constraints(item_schema, item_constraints)
            schema = {"items": item_schema, "type": "array"}
    elif annotation is type(None):
        schema = {"type": "null"}
    elif annotation is Any:
        schema = {}
    elif annotation is ContractVersion:
        schema = _contract_version_definition(owner, definitions)
    elif annotation is str:
        schema = {"type": "string"}
    elif annotation is bool:
        schema = {"type": "boolean"}
    elif annotation is int:
        schema = {"type": "integer"}
    elif annotation is float:
        schema = {"type": "number"}
    elif isinstance(annotation, type) and issubclass(annotation, Enum):
        schema = _enum_schema(annotation)
    elif isinstance(annotation, type) and attrs.has(annotation):
        schema = _definition(annotation, definitions)
    else:
        raise TypeError(f"unsupported schema annotation {annotation!r}")
    return _apply_schema_constraints(schema, constraints)


def _registered(schema: str | type) -> _RegisteredContract:
    if isinstance(schema, str):
        for entry in _REGISTERED_CONTRACTS:
            if entry.schema_uri == schema:
                return entry
        raise KeyError(f"unregistered contract schema {schema!r}")
    for entry in _REGISTERED_CONTRACTS:
        if entry.contract is schema:
            return entry
    name = getattr(schema, "__name__", repr(schema))
    raise KeyError(f"unregistered contract type {name}") from None


def supported_version_for(schema: str | type) -> ContractVersion | None:
    return _registered(schema).supported_version


def schema_bytes(schema: str | type) -> bytes:
    registered = _registered(schema)
    definitions: dict[str, object] = {}
    reference = _definition(registered.contract, definitions)
    document = {
        "$defs": definitions,
        "$id": registered.schema_uri,
        "$ref": reference["$ref"],
        "$schema": DRAFT_2020_12,
        "title": registered.contract.__name__,
        "x-maxContractBytes": MAX_CONTRACT_BYTES,
        "x-maxContractDepth": MAX_CONTRACT_DEPTH,
    }
    return _json_bytes(document)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(f"duplicate field {key!r}")
        result[key] = value
    return result


def _enforce_tree_depth(value: object) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_CONTRACT_DEPTH:
            raise ContractValidationError(
                f"decoded contract exceeds MAX_CONTRACT_DEPTH ({MAX_CONTRACT_DEPTH})"
            )
        if isinstance(current, Mapping):
            mapping_current = cast("Mapping[object, object]", current)
            pending.extend((item, depth + 1) for item in mapping_current.values())
        elif isinstance(current, list):
            list_current = cast("list[object]", current)
            pending.extend((item, depth + 1) for item in list_current)


def _enforce_raw_depth(raw: str | bytes | bytearray) -> None:
    in_string = False
    escaped = False
    depth = 0
    for item in raw:
        code = ord(item) if isinstance(item, str) else item
        if in_string:
            if escaped:
                escaped = False
            elif code == ord("\\"):
                escaped = True
            elif code == ord('"'):
                in_string = False
            continue
        if code == ord('"'):
            in_string = True
        elif code in {ord("{"), ord("[")}:
            depth += 1
            if depth > MAX_CONTRACT_DEPTH + 1:
                raise ContractValidationError(
                    f"raw contract exceeds MAX_CONTRACT_DEPTH ({MAX_CONTRACT_DEPTH})"
                )
        elif code in {ord("}"), ord("]")}:
            depth = max(0, depth - 1)


def _enforce_text_bytes(raw: str) -> None:
    if len(raw) > MAX_CONTRACT_BYTES:
        raise ContractValidationError(
            f"raw contract exceeds MAX_CONTRACT_BYTES ({MAX_CONTRACT_BYTES} bytes)"
        )
    if raw.isascii():
        return
    size = 0
    for character in raw:
        try:
            size += len(character.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise ContractValidationError(f"invalid UTF-8 text: {error}") from None
        if size > MAX_CONTRACT_BYTES:
            raise ContractValidationError(
                f"raw contract exceeds MAX_CONTRACT_BYTES ({MAX_CONTRACT_BYTES} bytes)"
            )


def _enforce_raw_bytes(raw: bytes | bytearray) -> None:
    if len(raw) > MAX_CONTRACT_BYTES:
        raise ContractValidationError(
            f"raw contract exceeds MAX_CONTRACT_BYTES ({MAX_CONTRACT_BYTES} bytes)"
        )


def _raw_mapping(raw: object) -> Mapping[str, object]:
    if isinstance(raw, str):
        _enforce_text_bytes(raw)
        _enforce_raw_depth(raw)
        payload: object = raw
    elif isinstance(raw, (bytes, bytearray)):
        _enforce_raw_bytes(raw)
        _enforce_raw_depth(raw)
        payload = raw
    else:
        payload = raw
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            raw = cast(object, json.loads(payload, object_pairs_hook=_unique_object))
        except RecursionError:
            raise ContractValidationError(
                f"decoded contract exceeds MAX_CONTRACT_DEPTH ({MAX_CONTRACT_DEPTH})"
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ContractValidationError(f"invalid JSON: {error}") from None
    _enforce_tree_depth(raw)
    if not isinstance(raw, Mapping):
        raise ContractValidationError(
            f"contract must be an object, not {type(raw).__name__}"
        )
    return cast("Mapping[str, object]", raw)



@cache
def _class_hints_and_fields(
    cls: type,
) -> tuple[dict[str, object], dict[str, Attribute[object]]]:
    hints = cast("dict[str, object]", get_type_hints(cls))
    fields = cast("dict[str, Attribute[object]]", attrs.fields_dict(cls))
    return hints, fields


def _structure(value: object, annotation: object, path: str = "$") -> object:
    origin = get_origin(annotation)
    if origin in {types.UnionType, Union}:  # pyright: ignore[reportDeprecated]
        failures: list[str] = []
        for member in cast("tuple[object, ...]", get_args(annotation)):
            try:
                return _structure(value, member, path)
            except ContractValidationError as error:
                failures.append(str(error))
        raise ContractValidationError(
            f"{path} does not match any allowed shape: {'; '.join(failures)}"
        )
    if origin in {list, tuple}:
        if not isinstance(value, list):
            raise ContractValidationError(
                f"{path} must be an array, not {type(value).__name__}"
            )
        items_value = cast("list[object]", value)
        arguments: tuple[object, ...] = get_args(annotation)
        if origin is tuple and len(arguments) > 1 and arguments[-1] is not Ellipsis:
            if len(items_value) != len(arguments):
                raise ContractValidationError(
                    f"{path} must contain exactly {len(arguments)} items"
                )
            return tuple(
                _structure(item, item_type, f"{path}[{index}]")
                for index, (item, item_type) in enumerate(zip(items_value, arguments))
            )
        item_type: object = arguments[0] if arguments else object
        items = tuple(
            _structure(item, item_type, f"{path}[{index}]")
            for index, item in enumerate(items_value)
        )
        return list(items) if origin is list else items
    if annotation is type(None):
        if value is not None:
            raise ContractValidationError(f"{path} must be null")
        return None
    if annotation is Any:
        return value
    if annotation is str:
        if type(value) is not str:
            raise ContractValidationError(
                f"{path} must be a string, not {type(value).__name__}"
            )
        return value
    if annotation is bool:
        if type(value) is not bool:
            raise ContractValidationError(
                f"{path} must be a boolean, not {type(value).__name__}"
            )
        return value
    if annotation is int:
        if type(value) is not int:
            raise ContractValidationError(
                f"{path} must be an integer, not {type(value).__name__}"
            )
        return value
    if annotation is float:
        if type(value) not in {int, float}:
            raise ContractValidationError(
                f"{path} must be a number, not {type(value).__name__}"
            )
        return value
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if type(value) is not type(cast(object, next(iter(annotation)).value)):
            raise ContractValidationError(f"{path} has the wrong enum value type")
        try:
            return annotation(value)
        except ValueError:
            allowed = ", ".join(
                repr(cast(object, member.value)) for member in annotation
            )
            raise ContractValidationError(f"{path} must be one of {allowed}") from None
    if isinstance(annotation, type) and attrs.has(annotation):
        if not isinstance(value, Mapping):
            raise ContractValidationError(
                f"{path} must be an object, not {type(value).__name__}"
            )
        mapping_value = cast("Mapping[str, object]", value)
        hints, fields = _class_hints_and_fields(annotation)
        unknown = sorted(set(mapping_value) - set(fields))
        if unknown:
            raise ContractValidationError(
                f"{path} contains unknown fields: {', '.join(unknown)}"
            )
        values: dict[str, object] = {}
        for name, attribute in fields.items():
            if name in mapping_value:
                values[name] = _structure(
                    mapping_value[name], hints[name], f"{path}.{name}"
                )
            elif attribute.default is attrs.NOTHING:
                raise ContractValidationError(f"{path}.{name} is required")
        try:
            return annotation(**values)
        except (TypeError, ValueError) as error:
            raise ContractValidationError(f"{path} is invalid: {error}") from None
    raise TypeError(f"unsupported structure annotation {annotation!r}")


def _artifact(
    value: object, source_version: ContractVersion | None
) -> CanonicalArtifact:
    return CanonicalArtifact(value, canonical_bytes(value), source_version)


def _validate_curd_plan_against(
    plan: CurdPlan, supported: ContractVersion
) -> CurdPlan:
    registered = _registered(CurdPlan)
    source = plan.contract_version
    if source.schema_uri != registered.schema_uri:
        raise ContractValidationError(
            "contract_version.schema_uri does not match the registered CurdPlan"
        )
    if source != supported:
        raise ContractValidationError(
            f"unsupported contract version {source.major}.{source.minor} "
            + f"for {registered.schema_uri}; expected {supported.major}.{supported.minor}"
        )
    return plan


def validate_curd_plan(plan: object) -> CurdPlan:
    if not isinstance(plan, CurdPlan):
        raise TypeError(f"validate_curd_plan expects CurdPlan, not {type(plan).__name__}")
    supported = supported_version_for(CurdPlan)
    if supported is None:
        raise ContractValidationError("CurdPlan has no host-supported contract version")
    return _validate_curd_plan_against(plan, supported)


def validate_contract(
    raw: object,
    schema: str | type,
    supported_version: ContractVersion | None = None,
) -> CanonicalArtifact:
    registered = _registered(schema)
    schema_uri, contract = registered.schema_uri, registered.contract
    data = _raw_mapping(raw)
    has_version = "contract_version" in attrs.fields_dict(contract)
    source_version = None

    if has_version:
        catalog_version = registered.supported_version
        if supported_version is None:
            raise ContractValidationError("supported_version is required")
        if catalog_version is None:
            raise ContractValidationError(
                f"{contract.__name__} has no host-supported contract version"
            )
        if supported_version.schema_uri != schema_uri:
            raise ContractValidationError(
                "supported_version.schema_uri does not match the registered contract"
            )
        if supported_version != catalog_version:
            raise ContractValidationError(
                "supported_version must equal the catalog's current version"
            )
        if "contract_version" not in data:
            raise ContractValidationError("$.contract_version is required")
        source_version = _structure(
            data["contract_version"], ContractVersion, "$.contract_version"
        )
        assert isinstance(source_version, ContractVersion)
        if source_version.schema_uri != schema_uri:
            raise ContractValidationError(
                "contract_version.schema_uri does not match the registered contract"
            )
        if source_version != supported_version:
            raise ContractValidationError(
                f"unsupported contract version {source_version.major}.{source_version.minor} "
                + f"for {schema_uri}; expected {supported_version.major}.{supported_version.minor}"
            )
    elif supported_version is not None:
        raise ContractValidationError(
            f"{contract.__name__} does not carry a contract version"
        )

    if contract is CurdPlan:
        value = _structure(data, contract)
        assert isinstance(value, CurdPlan)
        assert supported_version is not None
        _ = _validate_curd_plan_against(value, supported_version)
    else:
        value = _structure(data, contract)
    return _artifact(value, source_version)


def _forbidden_field(path: str, value: object) -> tuple[str, str] | None:
    if isinstance(value, Mapping):
        mapping_value = cast("Mapping[str, object]", value)
        for key, item in mapping_value.items():
            child = f"{path}.{key}"
            if key in _HOST_OWNED_FIELDS:
                return child, key
            found = _forbidden_field(child, item)
            if found is not None:
                return found
    elif isinstance(value, list):
        list_value = cast("list[object]", value)
        for index, item in enumerate(list_value):
            found = _forbidden_field(f"{path}[{index}]", item)
            if found is not None:
                return found
    return None


def _invocation_value(
    invocation: Mapping[str, object], name: str, default: object = _MISSING
) -> object:
    if name in invocation:
        return invocation[name]
    if default is not _MISSING:
        return default
    raise ContractValidationError(f"invocation.{name} is required")


_T = TypeVar("_T")


def _typed_host(value: object, type_: type[_T], path: str) -> _T:
    if isinstance(value, type_):
        return value
    return cast(_T, _structure(value, type_, path))


def _host_mapping(
    invocation: Mapping[str, object], name: str
) -> Mapping[str, object]:
    value = _invocation_value(invocation, name, {})
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"invocation.{name} must be an object")
    return cast("Mapping[str, object]", value)


def _version_for(
    invocation: Mapping[str, object], schema_uri: str
) -> ContractVersion:
    versions = invocation.get("versions")
    if versions is not None:
        if not isinstance(versions, Mapping) or schema_uri not in versions:
            raise ContractValidationError(
                f"invocation.versions must contain {schema_uri!r}"
            )
        raw = versions[schema_uri]
    else:
        raw = _invocation_value(invocation, "contract_version")
    version = _typed_host(raw, ContractVersion, "invocation.contract_version")
    if version.schema_uri != schema_uri:
        raise ContractValidationError(
            f"host contract version must identify {schema_uri!r}"
        )
    return version


def _host_refs(
    keys: tuple[str, ...],
    pool: Mapping[str, object],
    type_: type[_T],
    path: str,
) -> tuple[_T, ...]:
    resolved: list[_T] = []
    for key in keys:
        if key not in pool:
            raise ContractValidationError(f"{path} references unknown key {key!r}")
        resolved.append(_typed_host(pool[key], type_, f"{path}[{key!r}]"))
    return tuple(resolved)


def _source_location(
    view: SourceLocationWriterView | None, artifact_id: str
) -> SourceLocation | None:
    if view is None:
        return None
    return SourceLocation(
        artifact_id=artifact_id,
        path=view.path,
        start_line=view.start_line,
        end_line=view.end_line,
        start_column=view.start_column,
        end_column=view.end_column,
    )




def _normalize_plan(
    view: CurdPlanWriterView, invocation: Mapping[str, object]
) -> CurdPlan:
    schema_uri = _CANONICAL_SCHEMA_BY_WRITER_KIND[WriterViewKind.CURD_PLAN]
    version = _version_for(invocation, schema_uri)
    plan_id = cast(str, _invocation_value(invocation, "plan_id"))
    revision = cast(int, _invocation_value(invocation, "revision", 1))
    artifacts = _host_mapping(invocation, "artifacts")
    lineages = _host_mapping(invocation, "lineages")

    keys = [curd.key for curd in view.curds]
    if len(keys) != len(set(keys)):
        raise ContractValidationError("writer curd keys must be unique")
    unknown_lineages = set(lineages) - set(keys)
    if unknown_lineages:
        raise ContractValidationError(
            f"invocation.lineages has unknown curd keys: {sorted(unknown_lineages)!r}"
        )
    curd_ids = {
        key: f"{plan_id}/curd/{index}" for index, key in enumerate(keys, start=1)
    }
    curds: list[SemanticCurd] = []
    for writer_curd in view.curds:
        try:
            dependencies = tuple(
                curd_ids[key] for key in writer_curd.dependencies
            )
        except KeyError as error:
            raise ContractValidationError(
                f"curd {writer_curd.key!r} references unknown dependency "
                + f"{error.args[0]!r}"
            ) from None
        inputs = _host_refs(
            writer_curd.input_keys,
            artifacts,
            ArtifactRef,
            f"curd {writer_curd.key!r} inputs",
        )
        lineage_raw = lineages.get(writer_curd.key)
        lineage = (
            IdentityLineage(IdentityAction.NEW)
            if lineage_raw is None
            else _typed_host(
                lineage_raw,
                IdentityLineage,
                f"invocation.lineages.{writer_curd.key}",
            )
        )
        curd_id = curd_ids[writer_curd.key]
        criteria = tuple(
            Criterion(
                criterion_id=f"{curd_id}/criterion/{index}",
                description=criterion.description,
                check=criterion.check,
            )
            for index, criterion in enumerate(writer_curd.criteria, start=1)
        )
        curds.append(
            SemanticCurd(
                curd_id=curd_id,
                outcome=writer_curd.outcome,
                scope=writer_curd.scope,
                inputs=inputs,
                outputs=writer_curd.outputs,
                dependencies=dependencies,
                criteria=criteria,
                lineage=lineage,
            )
        )

    context = None
    if view.context is not None:
        shared_inputs = _host_refs(
            view.context.shared_input_keys,
            artifacts,
            ArtifactRef,
            "plan context shared inputs",
        )
        context = BoundedContext(
            shared_inputs=shared_inputs,
            constraints=view.context.constraints,
            invariants=view.context.invariants,
        )
    parent_raw = invocation.get("parent_plan_ref")
    parent = (
        None
        if parent_raw is None
        else _typed_host(parent_raw, SourcePlanRef, "invocation.parent_plan_ref")
    )
    return CurdPlan.signed(
        contract_version=version,
        plan_id=plan_id,
        revision=revision,
        objective=view.objective,
        curds=tuple(curds),
        context=context,
        parent_plan_ref=parent,
    )



def _normalize_planner_result(
    view: PlannerResultWriterView, invocation: Mapping[str, object]
) -> PlannerResult:
    schema_uri = _CANONICAL_SCHEMA_BY_WRITER_KIND[WriterViewKind.PLANNER_RESULT]
    evidence = _host_mapping(invocation, "evidence")
    unresolved = tuple(
        PlannerUncertainty(
            description=item.description,
            scope=item.scope,
            evidence=_host_refs(
                item.evidence_keys,
                evidence,
                EvidenceRef,
                "planner unresolved evidence",
            ),
        )
        for item in view.unresolved_work
    )
    plan = None
    if view.plan is not None:
        plan_invocation = _invocation_value(invocation, "plan")
        if not isinstance(plan_invocation, Mapping):
            raise ContractValidationError("invocation.plan must be an object")
        merged = dict(invocation)
        merged.update(cast("Mapping[str, object]", plan_invocation))
        plan = _normalize_plan(view.plan, merged)
    return PlannerResult(
        contract_version=_version_for(invocation, schema_uri),
        request_id=cast(str, _invocation_value(invocation, "request_id")),
        disposition=view.disposition,
        plan=plan,
        unresolved_work=unresolved,
        reason=view.reason,
    )


def _normalize_finding(
    item: ReviewFindingWriterView,
    index: int,
    review_id: str,
    evidence: Mapping[str, object],
) -> ReviewFinding:
    refs = _host_refs(
        item.evidence_keys, evidence, EvidenceRef, f"review finding {index} evidence"
    )
    assert refs
    first = refs[0]
    return ReviewFinding(
        finding_id=f"{review_id}/finding/{index}",
        severity=item.severity,
        summary=item.summary,
        evidence=refs,
        location=_source_location(item.location, first.artifact.artifact_id),
    )


def _normalize_review_result(
    view: ReviewResultWriterView, invocation: Mapping[str, object]
) -> ReviewResult:
    schema_uri = _CANONICAL_SCHEMA_BY_WRITER_KIND[WriterViewKind.REVIEW_RESULT]
    review_id = cast(str, _invocation_value(invocation, "review_id"))
    evidence = _host_mapping(invocation, "evidence")
    coverage_raw = _invocation_value(invocation, "coverage")
    if not isinstance(coverage_raw, list | tuple):
        raise ContractValidationError("invocation.coverage must be an array")
    coverage_raw = cast("list[object] | tuple[object, ...]", coverage_raw)
    coverage = tuple(
        _typed_host(item, ReviewCoverage, f"invocation.coverage[{index}]")
        for index, item in enumerate(coverage_raw)
    )
    return ReviewResult(
        contract_version=_version_for(invocation, schema_uri),
        review_id=review_id,
        disposition=view.disposition,
        findings=tuple(
            _normalize_finding(item, index, review_id, evidence)
            for index, item in enumerate(view.findings, start=1)
        ),
        coverage=coverage,
        reason=view.reason,
    )


def _normalize_reproduction(
    view: ReproductionWriterView, evidence: Mapping[str, object]
) -> Reproduction:
    return Reproduction(
        status=view.status,
        steps=view.steps,
        observed=view.observed,
        evidence=_host_refs(
            view.evidence_keys, evidence, EvidenceRef, "reproduction evidence"
        ),
    )


def _normalize_hypothesis(
    item: DiagnosisHypothesisWriterView,
    index: int,
    diagnosis_id: str,
    evidence: Mapping[str, object],
) -> DiagnosisHypothesis:
    return DiagnosisHypothesis(
        hypothesis_id=f"{diagnosis_id}/hypothesis/{index}",
        statement=item.statement,
        disposition=item.disposition,
        evidence=_host_refs(
            item.evidence_keys,
            evidence,
            EvidenceRef,
            f"diagnosis hypothesis {index} evidence",
        ),
    )


def _normalize_cause(
    item: DiagnosisCauseWriterView | None, evidence: Mapping[str, object]
) -> DiagnosisCause | None:
    if item is None:
        return None
    refs = _host_refs(
        item.evidence_keys, evidence, EvidenceRef, "diagnosis cause evidence"
    )
    assert refs
    first = refs[0]
    return DiagnosisCause(
        summary=item.summary,
        evidence=refs,
        location=_source_location(item.location, first.artifact.artifact_id),
    )


def _normalize_diagnosis_result(
    view: DiagnosisResultWriterView, invocation: Mapping[str, object]
) -> DiagnosisResult:
    schema_uri = _CANONICAL_SCHEMA_BY_WRITER_KIND[WriterViewKind.DIAGNOSIS_RESULT]
    diagnosis_id = cast(str, _invocation_value(invocation, "diagnosis_id"))
    evidence = _host_mapping(invocation, "evidence")
    subject_artifact_id = _invocation_value(invocation, "subject_artifact_id")
    return DiagnosisResult(
        contract_version=_version_for(invocation, schema_uri),
        diagnosis_id=diagnosis_id,
        disposition=view.disposition,
        symptom=cast(str, _invocation_value(invocation, "symptom")),
        reproduction=_normalize_reproduction(view.reproduction, evidence),
        hypotheses=tuple(
            _normalize_hypothesis(item, index, diagnosis_id, evidence)
            for index, item in enumerate(view.hypotheses, start=1)
        ),
        confirmed_cause=_normalize_cause(view.confirmed_cause, evidence),
        regression_seam=_source_location(
            view.regression_seam, str(subject_artifact_id)
        ),
        unresolved_evidence=_host_refs(
            view.unresolved_evidence_keys,
            evidence,
            EvidenceRef,
            "diagnosis unresolved evidence",
        ),
        reason=view.reason,
    )




def _normalize_curd_result(
    view: CurdResultWriterView, invocation: Mapping[str, object]
) -> CurdResult:
    schema_uri = _CANONICAL_SCHEMA_BY_WRITER_KIND[WriterViewKind.CURD_RESULT]
    expected_raw = _invocation_value(invocation, "expected_criterion_ids")
    if not isinstance(expected_raw, list | tuple):
        raise ContractValidationError(
            "invocation.expected_criterion_ids must be an array"
        )
    expected_raw = cast("list[object] | tuple[object, ...]", expected_raw)
    expected = cast("tuple[str, ...]", tuple(expected_raw))
    if len(expected) != len(view.criterion_results):
        raise ContractValidationError(
            "writer criterion results must match expected_criterion_ids"
        )
    evidence = _host_mapping(invocation, "evidence")
    rows = tuple(
        CriterionResult(
            criterion_id=criterion_id,
            disposition=item.disposition,
            evidence=_host_refs(
                item.evidence_keys,
                evidence,
                EvidenceRef,
                f"criterion result {index} evidence",
            ),
            reason=item.reason,
        )
        for index, (criterion_id, item) in enumerate(
            zip(expected, view.criterion_results), start=1
        )
    )
    deliverables = _host_mapping(invocation, "deliverables")
    resolved_deliverables: list[ArtifactRef] = []
    for item in view.deliverables:
        if item.path not in deliverables:
            raise ContractValidationError(
                f"deliverable path {item.path!r} has no host artifact"
            )
        artifact = _typed_host(
            deliverables[item.path],
            ArtifactRef,
            f"invocation.deliverables[{item.path!r}]",
        )
        if artifact.role != item.role or artifact.media_type != item.media_type:
            raise ContractValidationError(
                f"host artifact for {item.path!r} contradicts the writer view"
            )
        resolved_deliverables.append(artifact)
    source_plan = _typed_host(
        _invocation_value(invocation, "source_plan_ref"),
        SourcePlanRef,
        "invocation.source_plan_ref",
    )
    source_curd = _typed_host(
        _invocation_value(invocation, "source_curd_ref"),
        SourceCurdRef,
        "invocation.source_curd_ref",
    )
    runtime_refs = _invocation_value(invocation, "runtime_refs", ())
    if not isinstance(runtime_refs, list | tuple):
        raise ContractValidationError("invocation.runtime_refs must be an array")
    runtime_refs = cast("list[object] | tuple[object, ...]", runtime_refs)
    runtime_refs = cast("tuple[str, ...]", tuple(runtime_refs))
    return CurdResult(
        contract_version=_version_for(invocation, schema_uri),
        result_id=cast(str, _invocation_value(invocation, "result_id")),
        source_plan_ref=source_plan,
        source_curd_ref=source_curd,
        disposition=derive_curd_disposition(rows),
        expected_criterion_ids=expected,
        criterion_results=rows,
        deliverables=tuple(resolved_deliverables),
        unresolved_work=view.unresolved_work,
        runtime_refs=runtime_refs,
    )


def normalize_agent_value(view: object, invocation: object) -> object:
    if not isinstance(invocation, Mapping):
        raise ContractValidationError("invocation must be an object")
    mapping_invocation = cast(Mapping[str, object], invocation)
    if isinstance(view, AgentWriterView):
        writer = view
    else:
        raw = _raw_mapping(view)
        forbidden = _forbidden_field("$", raw)
        if forbidden is not None:
            path, name = forbidden
            raise ContractValidationError(
                f"{path} supplies host-owned field {name!r}"
            )
        writer = _structure(raw, AgentWriterView)
        assert isinstance(writer, AgentWriterView)

    payload = writer.payload
    if isinstance(payload, CurdPlanWriterView):
        return _normalize_plan(payload, mapping_invocation)
    if isinstance(payload, PlannerResultWriterView):
        return _normalize_planner_result(payload, mapping_invocation)
    if isinstance(payload, ReviewResultWriterView):
        return _normalize_review_result(payload, mapping_invocation)
    if isinstance(payload, DiagnosisResultWriterView):
        return _normalize_diagnosis_result(payload, mapping_invocation)
    if isinstance(payload, CurdResultWriterView):  # pyright: ignore[reportUnnecessaryIsInstance]
        return _normalize_curd_result(payload, mapping_invocation)
    raise ContractValidationError(f"unsupported writer view kind {writer.kind!r}")


def normalize_agent_output(
    view: object, invocation: object
) -> CanonicalArtifact:
    value = normalize_agent_value(view, invocation)
    version = cast(ContractVersion, getattr(value, "contract_version"))
    return _artifact(value, version)


__all__ = [
    "AcceptedArtifact",
    "CanonicalArtifact",
    "ContractValidationError",
    "DRAFT_2020_12",
    "MAX_CONTRACT_BYTES",
    "MAX_CONTRACT_DEPTH",
    "PublishedArtifact",
    "REGISTERED_CONTRACT_SCHEMA_URIS",
    "SCHEMA_ROOT",
    "canonical_bytes",
    "canonical_digest",
    "curd_plan_digest",
    "normalize_agent_output",
    "normalize_agent_value",
    "schema_bytes",
    "supported_version_for",
    "validate_contract",
    "validate_curd_plan",
]
