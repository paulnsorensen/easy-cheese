"""Typed Mold-to-Cook handoff publication and acceptance."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import unquote, urlsplit

from easy_cheese_schemas import (
    MAX_ARTIFACT_BYTES,
    MAX_CONTRACT_BYTES,
    ArtifactRef,
    ContractValidationError,
    ContractVersion,
    CurdPlan,
    HandoffPointer,
    NormalizationAction,
    NormalizationReceipt,
    NormalizationVersion,
    __version__,
    supported_version_for,
    validate_contract,
    validate_curd_plan,
)
from easy_cheese_schemas.schema_runtime import canonical_bytes as _canonical_bytes

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"
HANDOFF_SCHEMA_URI = "https://schemas.easy-cheese.dev/handoff"
NORMALIZATION_RECEIPT_SCHEMA_URI = (
    "https://schemas.easy-cheese.dev/normalization-receipt"
)
LEGACY_SCHEMA_URI = "https://schemas.easy-cheese.dev/legacy-handoff"
HANDOFF_VERSION = ContractVersion(HANDOFF_SCHEMA_URI, "1", "0")
LEGACY_REMOVE_AFTER = "2.0.0"
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_OPERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class HandoffError(ValueError):
    """The handoff cannot be safely published or accepted."""


@dataclass(frozen=True)
class PublishedArtifact:
    pointer_path: Path
    pointer: HandoffPointer
    canonical: CurdPlan
    normalization_receipt: NormalizationReceipt | None


@dataclass(frozen=True)
class AcceptedArtifact:
    canonical: CurdPlan
    normalization_receipt: NormalizationReceipt | None


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__attrs_attrs__"):
        return {
            attribute.name: _jsonable(getattr(value, attribute.name))
            for attribute in value.__attrs_attrs__
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_bytes(value: object) -> bytes:
    return _canonical_bytes(_jsonable(value))


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HandoffError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strip_comments(text: str) -> tuple[str, list[NormalizationAction]]:
    output: list[str] = []
    actions: list[NormalizationAction] = []
    quote: str | None = None
    escaped = False
    index = 0
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
        elif text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            actions.append(NormalizationAction("comment", "$"))
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise HandoffError("unterminated block comment")
            index = end + 2
            actions.append(NormalizationAction("comment", "$"))
        else:
            output.append(char)
            index += 1
    if quote is not None:
        raise HandoffError("unterminated string")
    return "".join(output), actions


def _single_quotes(text: str) -> tuple[str, list[NormalizationAction]]:
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
        if end == len(text):
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


def _outside_strings(text: str) -> list[bool]:
    outside = [True] * len(text)
    quoted = escaped = False
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
    if quoted:
        raise HandoffError("unterminated string")
    return outside


def _unquoted_keys(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_strings(text)
    actions: list[NormalizationAction] = []
    pattern = re.compile(r"(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_-]*)(?=\s*:)")
    def replace(match: re.Match[str]) -> str:
        if not outside[match.start("key")]:
            return match.group(0)
        key = match.group("key")
        actions.append(NormalizationAction("unquoted_key", key))
        return match.group("prefix") + json.dumps(key)
    return pattern.sub(replace, text), actions


def _trailing_commas(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_strings(text)
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


def _closing_delimiter(text: str) -> tuple[str, list[NormalizationAction]]:
    outside = _outside_strings(text)
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
    if len(stack) != 1:
        raise HandoffError("more than one closing delimiter is missing")
    return text + stack[0], [NormalizationAction("closing_delimiter", "$")]


def normalize_writer_text(
    text: str,
) -> tuple[CurdPlan, tuple[NormalizationAction, ...]]:
    if not isinstance(text, str) or not text.strip():
        raise HandoffError("writer view must be non-empty UTF-8 text")
    if len(text.encode()) > MAX_CONTRACT_BYTES:
        raise HandoffError("writer view exceeds MAX_CONTRACT_BYTES")
    repaired = text.strip()
    actions: list[NormalizationAction] = []
    for repair in (
        _strip_comments,
        _single_quotes,
        _unquoted_keys,
        _trailing_commas,
        _closing_delimiter,
    ):
        repaired, found = repair(repaired)
        actions.extend(found)
    try:
        raw = json.loads(repaired, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, HandoffError, RecursionError) as exc:
        raise HandoffError("writer view is not uniquely repairable") from exc
    if isinstance(raw, Mapping) and set(raw) == {"curd_plan"}:
        raw = raw["curd_plan"]
        actions.append(NormalizationAction("writer_shorthand", "curd_plan"))
    return _validated_plan(raw, "invalid writer CurdPlan"), tuple(actions)


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _open_directory(path: Path, *, create: bool = False) -> tuple[Path, int]:
    absolute = _absolute(path)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.sep, flags)
    try:
        for component in absolute.parts[1:]:
            if create:
                try:
                    os.mkdir(component, dir_fd=descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return absolute, descriptor
    except OSError as exc:
        os.close(descriptor)
        raise HandoffError(f"unsafe directory path: {absolute}") from exc


def _read_file(directory_fd: int, name: str, limit: int) -> bytes:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise HandoffError(f"artifact must be a regular file: {name}")
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise HandoffError(f"artifact exceeds {limit} bytes: {name}")
        return data
    except OSError as exc:
        raise HandoffError(f"unable to read artifact safely: {name}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_file_once(directory_fd: int, name: str, data: bytes) -> bool:
    temporary = f".{name}.{os.getpid()}.{uuid.uuid4().hex}"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(
                temporary,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            return False
        return True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class _OperationStore:
    root: Path
    root_fd: int
    directories: Mapping[str, int]

    def path(self, directory: str, operation_id: str) -> Path:
        return self.root / directory / f"{operation_id}.json"

    def exists(self, directory: str, name: str) -> bool:
        try:
            metadata = os.stat(name, dir_fd=self.directories[directory], follow_symlinks=False)
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(metadata.st_mode):
            raise HandoffError(f"operation artifact must be a regular file: {name}")
        return True

    def read(self, directory: str, name: str, limit: int = MAX_CONTRACT_BYTES) -> bytes:
        return _read_file(self.directories[directory], name, limit)

    def write_once(self, directory: str, name: str, data: bytes) -> bool:
        return _write_file_once(self.directories[directory], name, data)

    def assert_attached(self) -> None:
        _, current_root = _open_directory(self.root)
        try:
            if _identity(self.root_fd) != _identity(current_root):
                raise HandoffError("operation root changed during publication")
            flags = (
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            for name, expected_fd in self.directories.items():
                current = os.open(name, flags, dir_fd=current_root)
                try:
                    if _identity(expected_fd) != _identity(current):
                        raise HandoffError(
                            f"operation {name} directory changed during publication"
                        )
                finally:
                    os.close(current)
        except OSError as exc:
            raise HandoffError("operation directories changed during publication") from exc
        finally:
            os.close(current_root)


def _identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


@contextmanager
def _operation_store(root: Path, *, create: bool) -> Iterator[_OperationStore]:
    absolute, root_fd = _open_directory(root, create=create)
    with ExitStack() as stack:
        stack.callback(os.close, root_fd)
        directories: dict[str, int] = {}
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        for name in ("payloads", "receipts", "pointers"):
            if create:
                try:
                    os.mkdir(name, dir_fd=root_fd)
                except FileExistsError:
                    pass
            try:
                descriptor = os.open(name, flags, dir_fd=root_fd)
            except OSError as exc:
                raise HandoffError(f"unsafe operation directory: {name}") from exc
            stack.callback(os.close, descriptor)
            directories[name] = descriptor
        yield _OperationStore(absolute, root_fd, directories)


def read_nofollow(path: Path, limit: int = MAX_ARTIFACT_BYTES) -> bytes:
    _, directory_fd = _open_directory(path.parent)
    try:
        return _read_file(directory_fd, path.name, limit)
    finally:
        os.close(directory_fd)


def read_text_nofollow(path: Path, limit: int = MAX_CONTRACT_BYTES) -> str:
    try:
        return read_nofollow(path, limit).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HandoffError(f"artifact is not UTF-8: {path}") from exc


def _reference(path: Path, role: str, data: bytes, schema_uri: str) -> ArtifactRef:
    return ArtifactRef(
        path.stem,
        role,
        path.as_uri(),
        digest(data),
        len(data),
        "application/json",
        schema_uri,
    )


def _file_path(uri: str) -> Path:
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise HandoffError("handoff artifacts must use local file URIs")
    if parsed.query or parsed.fragment:
        raise HandoffError("artifact URI must not contain query or fragment")
    return _absolute(Path(unquote(parsed.path)))


def _validated_plan(raw: object, message: str) -> CurdPlan:
    supported = supported_version_for(CurdPlan)
    if supported is None:
        raise HandoffError("CurdPlan has no supported contract version")
    try:
        artifact = validate_contract(raw, CurdPlan, supported)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise HandoffError(f"{message}: {exc}") from exc
    assert isinstance(artifact.value, CurdPlan)
    return artifact.value


def _load_pointer(store: _OperationStore, name: str) -> HandoffPointer:
    data = store.read("pointers", name)
    try:
        artifact = validate_contract(data, HandoffPointer, HANDOFF_VERSION)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise HandoffError("invalid handoff pointer") from exc
    if not isinstance(artifact.value, HandoffPointer) or artifact.canonical_bytes != data:
        raise HandoffError("pointer must be canonical")
    return artifact.value


def _verify_reference(
    reference: ArtifactRef,
    store: _OperationStore,
    operation_id: str,
    directory: str,
    role: str,
    schema_uri: str,
) -> bytes:
    expected = store.path(directory, operation_id)
    if _file_path(reference.uri) != expected:
        raise HandoffError(f"{role} reference escapes its operation root")
    if (
        reference.artifact_id != operation_id
        or reference.role != role
        or reference.schema_uri != schema_uri
        or reference.media_type != "application/json"
    ):
        raise HandoffError(f"{role} reference metadata mismatch")
    data = store.read(directory, expected.name)
    if digest(data) != reference.digest or len(data) != reference.size_bytes:
        raise HandoffError(f"corrupt referenced artifact: {expected}")
    return data


def _validate_receipt(
    receipt: NormalizationReceipt,
    pointer: HandoffPointer,
    payload: bytes,
) -> None:
    if receipt.source_digest != pointer.request_digest:
        raise HandoffError("normalization receipt source digest mismatch")
    if receipt.canonical_digest != digest(payload):
        raise HandoffError("normalization receipt canonical digest mismatch")
    if receipt.ingress_kind == "writer_view":
        valid = (
            receipt.source_schema_uri == CURD_PLAN_SCHEMA_URI
            and receipt.source_version is None
            and receipt.normalizer_id == "writer-json-repair-v1"
            and receipt.remove_after is None
            and bool(receipt.actions)
            and all(action.kind != "legacy_adapter" for action in receipt.actions)
        )
    else:
        valid = (
            receipt.source_schema_uri == LEGACY_SCHEMA_URI
            and receipt.source_version == NormalizationVersion("1", "0")
            and receipt.normalizer_id == "legacy-curd-plan-v1"
            and receipt.actions == (NormalizationAction("legacy_adapter", "$"),)
            and receipt.remove_after == LEGACY_REMOVE_AFTER
        )
    if not valid:
        raise HandoffError("unsupported normalization receipt provenance")


def _accept(store: _OperationStore, pointer_name: str) -> AcceptedArtifact:
    pointer = _load_pointer(store, pointer_name)
    if pointer.contract_version != HANDOFF_VERSION:
        raise HandoffError("handoff schema version mismatch")
    if (pointer.source_phase, pointer.destination_phase) != ("mold", "cook"):
        raise HandoffError("handoff route must be mold to cook")
    if pointer_name != f"{pointer.operation_id}.json":
        raise HandoffError("pointer path does not match its operation id")
    payload = _verify_reference(
        pointer.payload,
        store,
        pointer.operation_id,
        "payloads",
        "canonical-payload",
        CURD_PLAN_SCHEMA_URI,
    )
    plan = _validated_plan(payload, "payload is not a canonical CurdPlan")
    if canonical_bytes(plan) != payload:
        raise HandoffError("payload is not a canonical CurdPlan")
    receipt = None
    if pointer.normalization_receipt is not None:
        receipt_bytes = _verify_reference(
            pointer.normalization_receipt,
            store,
            pointer.operation_id,
            "receipts",
            "normalization-receipt",
            NORMALIZATION_RECEIPT_SCHEMA_URI,
        )
        try:
            receipt_artifact = validate_contract(
                receipt_bytes, NormalizationReceipt
            )
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise HandoffError("invalid normalization receipt") from exc
        if (
            not isinstance(receipt_artifact.value, NormalizationReceipt)
            or receipt_artifact.canonical_bytes != receipt_bytes
        ):
            raise HandoffError("normalization receipt must be canonical")
        receipt = receipt_artifact.value
        _validate_receipt(receipt, pointer, payload)
    return AcceptedArtifact(plan, receipt)


def accept(pointer_path: Path) -> AcceptedArtifact:
    absolute = _absolute(pointer_path)
    if absolute.parent.name != "pointers":
        raise HandoffError("pointer must be inside the operation pointers directory")
    with _operation_store(absolute.parent.parent, create=False) as store:
        return _accept(store, absolute.name)


def _publish(
    plan: CurdPlan,
    source: bytes,
    actions: tuple[NormalizationAction, ...],
    destination: str,
    operation_id: str,
    out_dir: Path,
    *,
    ingress_kind: str = "writer_view",
    source_schema_uri: str = CURD_PLAN_SCHEMA_URI,
    source_version: Mapping[str, str] | None = None,
    remove_after: str | None = None,
) -> PublishedArtifact:
    if destination != "cook":
        raise HandoffError("unsupported Mold handoff route")
    if _OPERATION_RE.fullmatch(operation_id) is None:
        raise HandoffError("invalid operation id")
    try:
        plan = validate_curd_plan(plan)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise HandoffError(f"invalid canonical CurdPlan: {exc}") from exc
    payload = canonical_bytes(plan)
    request_digest = digest(source)
    with _operation_store(out_dir, create=True) as store:
        payload_path = store.path("payloads", operation_id)
        receipt_path = store.path("receipts", operation_id)
        pointer_path = store.path("pointers", operation_id)
        receipt = (
            NormalizationReceipt(
                ingress_kind,
                source_schema_uri,
                source_version,
                (
                    "legacy-curd-plan-v1"
                    if ingress_kind == "legacy_artifact"
                    else "writer-json-repair-v1"
                ),
                actions,
                request_digest,
                digest(payload),
                remove_after,
            )
            if actions
            else None
        )
        receipt_bytes = canonical_bytes(receipt) if receipt is not None else None
        pointer = HandoffPointer(
            HANDOFF_VERSION,
            operation_id,
            request_digest,
            "mold",
            destination,
            _reference(payload_path, "canonical-payload", payload, CURD_PLAN_SCHEMA_URI),
            (
                _reference(
                    receipt_path,
                    "normalization-receipt",
                    receipt_bytes,
                    NORMALIZATION_RECEIPT_SCHEMA_URI,
                )
                if receipt_bytes is not None
                else None
            ),
        )
        pointer_bytes = canonical_bytes(pointer)
        if store.exists("pointers", pointer_path.name):
            existing = _load_pointer(store, pointer_path.name)
            if existing != pointer:
                raise HandoffError("operation id conflicts with an existing request")
            accepted = _accept(store, pointer_path.name)
            return PublishedArtifact(
                pointer_path,
                existing,
                accepted.canonical,
                accepted.normalization_receipt,
            )
        for directory, path, data in (
            ("payloads", payload_path, payload),
            ("receipts", receipt_path, receipt_bytes),
        ):
            if data is None:
                continue
            if store.exists(directory, path.name):
                if store.read(directory, path.name) != data:
                    raise HandoffError("prepared artifact conflicts with operation id")
            else:
                store.write_once(directory, path.name, data)
            store.assert_attached()
            if store.read(directory, path.name) != data:
                raise HandoffError("prepared artifact was corrupted")
        _verify_reference(
            pointer.payload,
            store,
            operation_id,
            "payloads",
            "canonical-payload",
            CURD_PLAN_SCHEMA_URI,
        )
        if pointer.normalization_receipt is not None:
            _verify_reference(
                pointer.normalization_receipt,
                store,
                operation_id,
                "receipts",
                "normalization-receipt",
                NORMALIZATION_RECEIPT_SCHEMA_URI,
            )
        store.assert_attached()
        created_pointer = store.write_once("pointers", pointer_path.name, pointer_bytes)
        if not created_pointer:
            winner = _load_pointer(store, pointer_path.name)
            if winner != pointer:
                raise HandoffError("operation id conflicts with the winning request")
        try:
            store.assert_attached()
        except HandoffError:
            if created_pointer:
                try:
                    os.unlink(pointer_path.name, dir_fd=store.directories["pointers"])
                except FileNotFoundError:
                    pass
            raise
        accepted = _accept(store, pointer_path.name)
        return PublishedArtifact(
            pointer_path, pointer, accepted.canonical, accepted.normalization_receipt
        )


def publish_writer_text(
    text: str, destination: str, operation_id: str, out_dir: Path
) -> PublishedArtifact:
    plan, actions = normalize_writer_text(text)
    return _publish(plan, text.encode(), actions, destination, operation_id, out_dir)


def migrate_legacy_text(
    text: str, operation_id: str, out_dir: Path
) -> PublishedArtifact:
    if tuple(map(int, __version__.split("."))) >= tuple(
        map(int, LEGACY_REMOVE_AFTER.split("."))
    ):
        raise HandoffError("legacy adapter sunset has passed")
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise HandoffError("legacy handoff must be strict JSON") from exc
    required = {"schema_uri", "version", "source_phase", "destination_phase", "payload"}
    if not isinstance(raw, Mapping) or set(raw) != required:
        raise HandoffError("legacy handoff has unknown or missing fields")
    if (
        raw["schema_uri"] != LEGACY_SCHEMA_URI
        or raw["version"] != {"major": "1", "minor": "0"}
        or raw["source_phase"] != "mold"
        or raw["destination_phase"] != "cook"
    ):
        raise HandoffError("unsupported legacy handoff schema, version, or route")
    plan = _validated_plan(raw["payload"], "legacy payload is not a CurdPlan")
    return _publish(
        plan,
        text.encode(),
        (NormalizationAction("legacy_adapter", "$"),),
        "cook",
        operation_id,
        out_dir,
        ingress_kind="legacy_artifact",
        source_schema_uri=LEGACY_SCHEMA_URI,
        source_version={"major": "1", "minor": "0"},
        remove_after=LEGACY_REMOVE_AFTER,
    )


__all__ = [
    "AcceptedArtifact",
    "HandoffError",
    "PublishedArtifact",
    "accept",
    "canonical_bytes",
    "migrate_legacy_text",
    "normalize_writer_text",
    "publish_writer_text",
    "read_text_nofollow",
]
