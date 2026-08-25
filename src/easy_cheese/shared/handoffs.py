"""Canonical Mold-to-Cook publication, migration, and acceptance gateway."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

from easy_cheese_schemas.artifacts import ArtifactResolutionError, resolve_artifact
from easy_cheese_schemas.compat import load
from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    ContractVersion,
    CurdPlan,
    HandoffPointer,
    NormalizationAction,
    NormalizationReceipt,
)
from easy_cheese_schemas.handoff import (
    CURD_PLAN_SCHEMA_URI,
    HANDOFF_SCHEMA_URI,
    LEGACY_SCHEMA_URI,
    NORMALIZATION_RECEIPT_SCHEMA_URI,
    WRITER_VIEW_SCHEMA_URI,
)
from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    TransitionError,
    validate_transition,
)
from easy_cheese_schemas.schema_runtime import (
    canonical_bytes as _schema_canonical_bytes,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
    validate_curd_plan,
)

HANDOFF_VERSION = ContractVersion(HANDOFF_SCHEMA_URI, "1", "0")
LEGACY_SOURCE_VERSION = ContractVersion(LEGACY_SCHEMA_URI, "1", "0")
LEGACY_REMOVE_AFTER = (2, 0, 0)
PACKAGE_VERSION = (1, 1, 0)
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_FENCED_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


class HandoffError(ValueError):
    """Raised when a canonical boundary cannot be established or accepted."""


@dataclass(frozen=True)
class InvocationContext:
    root: Path
    contract_version: ContractVersion
    plan_id: str
    revision: int
    request_digest: str
    artifacts: Mapping[str, ArtifactRef] = field(default_factory=dict)
    lineages: Mapping[str, object] = field(default_factory=dict)
    parent_plan_ref: object | None = None
    source_phase: str = "mold"

    def __post_init__(self) -> None:
        if self.contract_version.schema_uri != CURD_PLAN_SCHEMA_URI:
            raise ValueError("invocation contract_version must target CurdPlan")
        if not self.plan_id or self.revision < 1:
            raise ValueError("invocation plan_id and positive revision are required")
        _require_digest(self.request_digest)
        if self.source_phase != "mold":
            raise ValueError("invocation source_phase must be mold")
        for key, artifact in self.artifacts.items():
            if not isinstance(key, str) or not isinstance(artifact, ArtifactRef):
                raise TypeError("invocation artifacts must map strings to ArtifactRef")

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "plan_id": self.plan_id,
            "revision": self.revision,
            "artifacts": dict(self.artifacts),
            "lineages": dict(self.lineages),
            "parent_plan_ref": self.parent_plan_ref,
        }

    def to_mapping(self) -> dict[str, object]:
        mapping = self.as_mapping()
        return {
            "root": str(self.root),
            **mapping,
            "request_digest": self.request_digest,
            "source_phase": self.source_phase,
        }


@dataclass(frozen=True)
class AcceptedArtifact:
    canonical: CurdPlan
    normalization_receipt: NormalizationReceipt | None = None


@dataclass(frozen=True)
class PublishedArtifact:
    pointer: HandoffPointer
    canonical: CurdPlan
    normalization_receipt: NormalizationReceipt | None = None


@dataclass(frozen=True)
class LegacyHandoff:
    payload: Mapping[str, object]
    source_schema_uri: str
    source_version: ContractVersion
    invocation: InvocationContext


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__attrs_attrs__"):
        return {
            attribute.name: _jsonable(getattr(value, attribute.name))
            for attribute in value.__attrs_attrs__
        }
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _jsonable(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_bytes(value: object) -> bytes:
    if hasattr(value, "__dataclass_fields__"):
        return json.dumps(
            _jsonable(value), sort_keys=True, separators=(",", ":")
        ).encode()
    return _schema_canonical_bytes(value)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError("digest must be sha256:<64 lowercase hex characters>")
    return value


def _operation_paths(root: Path, operation_id: str) -> tuple[Path, Path, Path]:
    if not isinstance(operation_id, str) or _OPERATION_ID_RE.fullmatch(operation_id) is None:
        raise ValueError(
            "operation_id must be 1-64 alphanumeric, '_' or '-' characters"
        )
    base = root.resolve()
    paths = tuple(
        base / directory / f"{operation_id}.json"
        for directory in ("payloads", "receipts", "pointers")
    )
    return paths  # type: ignore[return-value]


def _ref(path: Path, role: str, data: bytes, schema_uri: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=path.stem,
        role=role,
        uri=path.resolve().as_uri(),
        digest=_digest(data),
        size_bytes=len(data),
        media_type="application/json",
        schema_uri=schema_uri,
    )


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _file_path(uri: str) -> Path:
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise HandoffError("handoff artifacts must use local file URIs")
    if parsed.query or parsed.fragment:
        raise HandoffError("handoff artifact URI must not contain query or fragment")
    return Path(unquote(parsed.path)).resolve()


def _operation_root(pointer: HandoffPointer) -> Path:
    payload = _file_path(pointer.payload.uri)
    if payload.parent.name != "payloads" or payload.name != f"{pointer.operation_id}.json":
        raise HandoffError("payload reference escapes its operation root")
    return payload.parent.parent


def _verify_ref(
    reference: ArtifactRef,
    *,
    root: Path,
    directory: str,
    operation_id: str,
    role: str,
    schema_uri: str,
) -> bytes:
    expected_path = (root / directory / f"{operation_id}.json").resolve()
    if _file_path(reference.uri) != expected_path:
        raise HandoffError(f"{role} reference escapes its operation root")
    if (
        reference.artifact_id != operation_id
        or reference.role != role
        or reference.schema_uri != schema_uri
        or reference.media_type != "application/json"
    ):
        raise HandoffError(f"{role} reference metadata mismatch")
    try:
        data = expected_path.read_bytes()
    except OSError as exc:
        raise HandoffError(f"missing referenced artifact: {expected_path}") from exc
    if _digest(data) != reference.digest or len(data) != reference.size_bytes:
        raise HandoffError(f"corrupt referenced artifact: {expected_path}")
    return data


def pointer_from_mapping(value: Mapping[str, object]) -> HandoffPointer:
    try:
        artifact = validate_contract(value, HandoffPointer, HANDOFF_VERSION)
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffError("invalid handoff pointer") from exc
    assert isinstance(artifact.value, HandoffPointer)
    return artifact.value


def _load_pointer(path: Path) -> HandoffPointer:
    try:
        data = path.read_bytes()
        raw = json.loads(data)
        if not isinstance(raw, Mapping):
            raise TypeError("pointer must be an object")
        pointer = pointer_from_mapping(raw)
        if canonical_bytes(pointer) != data:
            raise ValueError("pointer must use canonical JSON")
        return pointer
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HandoffError("invalid existing handoff pointer") from exc


def _strip_comments(text: str) -> tuple[str, list[NormalizationAction]]:
    output: list[str] = []
    actions: list[NormalizationAction] = []
    index = 0
    quote: str | None = None
    escaped = False
    while index < len(text):
        char = text[index]
        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            actions.append(NormalizationAction("comment", "$"))
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise HandoffError("unterminated block comment")
            index = end + 2
            actions.append(NormalizationAction("comment", "$"))
            continue
        output.append(char)
        index += 1
    return "".join(output), actions


def _repair_single_quotes(text: str) -> tuple[str, list[NormalizationAction]]:
    output: list[str] = []
    actions: list[NormalizationAction] = []
    index = 0
    in_double = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_double:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_double = False
            index += 1
            continue
        if char == '"':
            in_double = True
            output.append(char)
            index += 1
            continue
        if char != "'":
            output.append(char)
            index += 1
            continue
        end = index + 1
        escaped = False
        while end < len(text):
            if escaped:
                escaped = False
            elif text[end] == "\\":
                escaped = True
            elif text[end] == "'":
                break
            end += 1
        if end >= len(text):
            raise HandoffError("unterminated single-quoted string")
        try:
            value = ast.literal_eval(text[index : end + 1])
        except (SyntaxError, ValueError) as exc:
            raise HandoffError("invalid single-quoted string") from exc
        if not isinstance(value, str):
            raise HandoffError("single-quoted values must be strings")
        output.append(json.dumps(value))
        actions.append(NormalizationAction("single_quote", "$"))
        index = end + 1
    return "".join(output), actions


def _outside_string_positions(text: str) -> list[bool]:
    outside = [True] * len(text)
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        outside[index] = not quoted
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            outside[index] = True
    if quoted:
        raise HandoffError("unterminated string")
    return outside


def _repair_unquoted_keys(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_string_positions(text)
    pattern = re.compile(r"(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_-]*)(?=\s*:)")
    actions: list[NormalizationAction] = []

    def replace(match: re.Match[str]) -> str:
        if not outside[match.start("key")]:
            return match.group(0)
        key = match.group("key")
        actions.append(NormalizationAction("unquoted_key", key))
        return match.group("prefix") + json.dumps(key)

    return pattern.sub(replace, text), actions


def _repair_trailing_commas(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_string_positions(text)
    output: list[str] = []
    actions: list[NormalizationAction] = []
    index = 0
    while index < len(text):
        if text[index] == "," and outside[index]:
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                actions.append(NormalizationAction("trailing_comma", "$"))
                index += 1
                continue
        output.append(text[index])
        index += 1
    return "".join(output), actions


def _repair_closing_delimiters(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_string_positions(text)
    stack: list[str] = []
    pairs = {"{": "}", "[": "]"}
    for index, char in enumerate(text):
        if not outside[index]:
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif char in "}]":
            if not stack or stack.pop() != char:
                raise HandoffError("mismatched closing delimiter")
    if not stack:
        return text, []
    return text + "".join(reversed(stack)), [NormalizationAction("closing_delimiter", "$")]


def _writer_from_mapping(value: object) -> AgentWriterView:
    if isinstance(value, Mapping) and set(value) == {"curd_plan"}:
        value = {"kind": "curd_plan", "payload": value["curd_plan"]}
    loaded = load(value, AgentWriterView, strict=True)
    if loaded.value is None:
        raise HandoffError("; ".join(loaded.problems))
    return loaded.value


def normalize_writer_text(
    text: str,
) -> tuple[AgentWriterView, tuple[NormalizationAction, ...]]:
    if not isinstance(text, str) or not text.strip():
        raise HandoffError("writer output must be non-empty text")
    fenced = _FENCED_BLOCK_RE.findall(text)
    candidates = fenced or [text.strip()]
    successes: list[tuple[AgentWriterView, tuple[NormalizationAction, ...]]] = []
    for candidate in candidates:
        actions: list[NormalizationAction] = []
        try:
            repaired, found = _strip_comments(candidate)
            actions.extend(found)
            repaired, found = _repair_single_quotes(repaired)
            actions.extend(found)
            repaired, found = _repair_unquoted_keys(repaired)
            actions.extend(found)
            repaired, found = _repair_trailing_commas(repaired)
            actions.extend(found)
            repaired, found = _repair_closing_delimiters(repaired)
            actions.extend(found)
            value = json.loads(repaired)
            if isinstance(value, Mapping) and set(value) == {"curd_plan"}:
                actions.append(NormalizationAction("writer_shorthand", "curd_plan"))
            successes.append((_writer_from_mapping(value), tuple(actions)))
        except (HandoffError, json.JSONDecodeError, TypeError, ValueError):
            continue
    if len(successes) != 1:
        raise HandoffError("writer output must contain exactly one valid candidate")
    return successes[0]


def _plan_artifact_refs(plan: CurdPlan) -> tuple[ArtifactRef, ...]:
    refs = [reference for curd in plan.curds for reference in curd.inputs]
    if plan.context is not None:
        refs.extend(plan.context.shared_inputs)
    return tuple(refs)


def _resolve_plan_artifacts(plan: CurdPlan, root: Path) -> None:
    for reference in _plan_artifact_refs(plan):
        try:
            resolve_artifact(
                reference,
                repository_root=root,
                artifact_directory=root / "resolved-artifacts",
            )
        except ArtifactResolutionError as exc:
            raise HandoffError(
                f"unresolved plan artifact {reference.artifact_id!r}: {exc}"
            ) from exc


def _normalize_writer(
    writer_view: AgentWriterView, invocation: InvocationContext
) -> tuple[CurdPlan, bytes]:
    if not isinstance(writer_view, AgentWriterView):
        raise HandoffError("publish requires an AgentWriterView")
    try:
        artifact = normalize_agent_output(writer_view, invocation.as_mapping())
        plan = artifact.value
        validate_curd_plan(plan)
    except (TypeError, ValueError, KeyError) as exc:
        raise HandoffError("writer view cannot be normalized to CurdPlan") from exc
    _resolve_plan_artifacts(plan, invocation.root)
    return plan, canonical_bytes(plan)


def _validate_receipt(receipt: NormalizationReceipt, payload: bytes) -> None:
    expected = {
        "writer_view": (WRITER_VIEW_SCHEMA_URI, None, "writer-json-repair-v1"),
        "legacy_artifact": (
            LEGACY_SCHEMA_URI,
            LEGACY_SOURCE_VERSION,
            "legacy-curd-plan-v1",
        ),
    }
    if (
        receipt.ingress_kind not in expected
        or (
            receipt.source_schema_uri,
            receipt.source_version,
            receipt.normalizer_id,
        )
        != expected[receipt.ingress_kind]
    ):
        raise HandoffError("normalization receipt source metadata mismatch")
    if receipt.canonical_digest != _digest(payload):
        raise HandoffError("normalization receipt digest mismatch")
    if not receipt.actions:
        raise HandoffError("normalization receipt requires recorded actions")


def _publish_canonical(
    plan: CurdPlan,
    payload: bytes,
    invocation: InvocationContext,
    destination: str,
    operation_id: str,
    receipt: NormalizationReceipt | None,
) -> PublishedArtifact:
    try:
        route = validate_transition(
            COMPILED_TRANSITION_REGISTRY,
            "mold",
            destination,
            CURD_PLAN_SCHEMA_URI,
        )
    except TransitionError as exc:
        raise HandoffError(f"unsupported Mold handoff route: {exc}") from exc
    if route is None:
        raise HandoffError("unsupported Mold handoff route")
    _require_digest(invocation.request_digest)
    payload_path, receipt_path, pointer_path = _operation_paths(
        invocation.root, operation_id
    )
    canonical_digest = _digest(payload)
    if receipt is not None:
        _validate_receipt(receipt, payload)
    receipt_bytes = canonical_bytes(receipt) if receipt is not None else None

    if pointer_path.exists():
        pointer = _load_pointer(pointer_path)
        if pointer.request_digest != invocation.request_digest:
            raise HandoffError("operation id conflicts with request digest")
        if pointer.payload.digest != canonical_digest:
            raise HandoffError("operation id conflicts with canonical digest")
        expected_receipt_digest = (
            _digest(receipt_bytes) if receipt_bytes is not None else None
        )
        actual_receipt_digest = (
            pointer.normalization_receipt.digest
            if pointer.normalization_receipt is not None
            else None
        )
        if actual_receipt_digest != expected_receipt_digest:
            raise HandoffError("operation id conflicts with normalization receipt")
        accepted = accept(pointer)
        return PublishedArtifact(pointer, accepted.canonical, accepted.normalization_receipt)

    if payload_path.exists() and _digest(payload_path.read_bytes()) != canonical_digest:
        raise HandoffError("prepared payload conflicts with operation id")
    if receipt_path.exists():
        if receipt_bytes is None or _digest(receipt_path.read_bytes()) != _digest(
            receipt_bytes
        ):
            raise HandoffError("prepared receipt conflicts with operation id")

    if not payload_path.exists():
        _write_atomic(payload_path, payload)
    if receipt_bytes is not None and not receipt_path.exists():
        _write_atomic(receipt_path, receipt_bytes)
    payload_ref = _ref(
        payload_path, "canonical-payload", payload, CURD_PLAN_SCHEMA_URI
    )
    receipt_ref = (
        _ref(
            receipt_path,
            "normalization-receipt",
            receipt_bytes,
            NORMALIZATION_RECEIPT_SCHEMA_URI,
        )
        if receipt_bytes is not None
        else None
    )
    pointer = HandoffPointer(
        HANDOFF_VERSION,
        operation_id,
        invocation.request_digest,
        "mold",
        destination,
        payload_ref,
        receipt_ref,
    )
    _write_atomic(pointer_path, canonical_bytes(pointer))
    return PublishedArtifact(pointer, plan, receipt)


def publish(
    writer_view: AgentWriterView,
    invocation: InvocationContext,
    destination: str,
    operation_id: str,
) -> PublishedArtifact:
    plan, payload = _normalize_writer(writer_view, invocation)
    return _publish_canonical(
        plan, payload, invocation, destination, operation_id, None
    )


def publish_writer_text(
    text: str,
    invocation: InvocationContext,
    destination: str,
    operation_id: str,
) -> PublishedArtifact:
    writer, actions = normalize_writer_text(text)
    plan, payload = _normalize_writer(writer, invocation)
    if not actions:
        return _publish_canonical(
            plan, payload, invocation, destination, operation_id, None
        )
    receipt = NormalizationReceipt(
        "writer_view",
        WRITER_VIEW_SCHEMA_URI,
        None,
        "writer-json-repair-v1",
        actions,
        _digest(text.encode()),
        _digest(payload),
    )
    return _publish_canonical(
        plan, payload, invocation, destination, operation_id, receipt
    )


def _accept_receipt(
    reference: ArtifactRef, payload: bytes, root: Path, operation_id: str
) -> NormalizationReceipt:
    receipt_bytes = _verify_ref(
        reference,
        root=root,
        directory="receipts",
        operation_id=operation_id,
        role="normalization-receipt",
        schema_uri=NORMALIZATION_RECEIPT_SCHEMA_URI,
    )
    try:
        artifact = validate_contract(receipt_bytes, NormalizationReceipt)
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffError("invalid normalization receipt") from exc
    assert isinstance(artifact.value, NormalizationReceipt)
    _validate_receipt(artifact.value, payload)
    return artifact.value


def accept(pointer: HandoffPointer) -> AcceptedArtifact:
    if not isinstance(pointer, HandoffPointer):
        raise HandoffError("accept requires a HandoffPointer")
    if pointer.contract_version != HANDOFF_VERSION:
        raise HandoffError("handoff schema version mismatch")
    try:
        validated = validate_contract(
            canonical_bytes(pointer), HandoffPointer, HANDOFF_VERSION
        ).value
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffError("invalid handoff pointer") from exc
    assert isinstance(validated, HandoffPointer)
    try:
        route = validate_transition(
            COMPILED_TRANSITION_REGISTRY,
            pointer.source_phase,
            pointer.destination_phase,
            CURD_PLAN_SCHEMA_URI,
        )
    except TransitionError as exc:
        raise HandoffError(f"handoff route is not declared: {exc}") from exc
    if route is None:
        raise HandoffError("handoff route is not declared")
    operation_root = _operation_root(pointer)
    payload = _verify_ref(
        pointer.payload,
        root=operation_root,
        directory="payloads",
        operation_id=pointer.operation_id,
        role="canonical-payload",
        schema_uri=CURD_PLAN_SCHEMA_URI,
    )
    try:
        supported = supported_version_for(CurdPlan)
        artifact = validate_contract(payload, CurdPlan, supported)
        plan = artifact.value
        validate_curd_plan(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffError("payload is not a canonical CurdPlan") from exc
    if canonical_bytes(plan) != payload:
        raise HandoffError("payload is not canonical JSON")
    _resolve_plan_artifacts(plan, operation_root)
    receipt = (
        _accept_receipt(
            pointer.normalization_receipt,
            payload,
            operation_root,
            pointer.operation_id,
        )
        if pointer.normalization_receipt is not None
        else None
    )
    return AcceptedArtifact(plan, receipt)


def migrate(legacy_handoff: LegacyHandoff, operation_id: str) -> PublishedArtifact:
    if not isinstance(legacy_handoff, LegacyHandoff):
        raise TypeError("migrate requires a LegacyHandoff")
    if PACKAGE_VERSION >= LEGACY_REMOVE_AFTER:
        raise HandoffError("legacy adapter sunset has passed")
    if legacy_handoff.source_schema_uri != LEGACY_SCHEMA_URI:
        raise HandoffError("legacy source schema URI mismatch")
    if legacy_handoff.source_version != LEGACY_SOURCE_VERSION:
        raise HandoffError("unsupported legacy source version")
    try:
        supported = supported_version_for(CurdPlan)
        artifact = validate_contract(legacy_handoff.payload, CurdPlan, supported)
        plan = artifact.value
        validate_curd_plan(plan)
        _resolve_plan_artifacts(plan, legacy_handoff.invocation.root)
        payload = canonical_bytes(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffError("legacy payload is not a CurdPlan") from exc
    receipt = NormalizationReceipt(
        "legacy_artifact",
        LEGACY_SCHEMA_URI,
        legacy_handoff.source_version,
        "legacy-curd-plan-v1",
        (NormalizationAction("legacy_adapter", "$"),),
        _digest(canonical_bytes(legacy_handoff.payload)),
        _digest(payload),
    )
    return _publish_canonical(
        plan,
        payload,
        legacy_handoff.invocation,
        "cook",
        operation_id,
        receipt,
    )


__all__ = [
    "AcceptedArtifact",
    "HANDOFF_VERSION",
    "LEGACY_REMOVE_AFTER",
    "LEGACY_SOURCE_VERSION",
    "HandoffError",
    "HandoffPointer",
    "InvocationContext",
    "LegacyHandoff",
    "NormalizationAction",
    "NormalizationReceipt",
    "PublishedArtifact",
    "accept",
    "canonical_bytes",
    "migrate",
    "normalize_writer_text",
    "pointer_from_mapping",
    "publish",
    "publish_writer_text",
]
