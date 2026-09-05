"""Shared publication gateway: the canonical Mold-to-Cook handoff boundary.

Agent writer output passes through a syntax-generous, semantics-strict
pipeline: :func:`syntax_normalize` repairs only the closed set of JSON syntax
slips (stray whitespace, curly quotes, trailing commas), rejecting anything
ambiguous or unrecoverable; the existing semantics-strict normalizer
(``normalize_agent_output``) then structures the payload with no heuristic
coercion. :func:`publish` validates the resulting canonical payload and its
route, writes the payload (and, if any syntax repair happened, its receipt)
as immutable content-addressed files, and only then atomically reveals one
idempotent ``HandoffPointer`` -- the boundary a consumer is allowed to act on.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from easy_cheese_schemas import (
    COMPILED_TRANSITION_REGISTRY,
    MAX_CONTRACT_BYTES,
    NORMALIZATION_RECEIPT_SCHEMA_URI,
    AcceptedArtifact,
    ArtifactRef,
    CanonicalArtifact,
    ContractValidationError,
    HandoffPointer,
    IngressKind,
    NormalizationAction,
    NormalizationActionKind,
    NormalizationReceipt,
    PublishedArtifact,
    canonical_bytes,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
    validate_transition,
)
from easy_cheese_schemas.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
)


__all__ = [
    "AmbiguousSyntaxRepairError",
    "CorruptLeftoverError",
    "IdempotencyConflictError",
    "PayloadDigestMismatchError",
    "PointerNotFoundError",
    "PublicationError",
    "UnrecoverableSyntaxError",
    "accept",
    "publish",
    "publish_canonical",
    "request_digest",
    "syntax_normalize",
]


class PublicationError(ValueError):
    """Base for every error the publication gateway itself raises.

    A caller across the Mold-to-Cook boundary can catch this one type to
    reject any publication-gateway failure as a diagnosed error, instead of
    letting an unlisted member of the family escape as a raw traceback.
    """


class UnrecoverableSyntaxError(PublicationError):
    """No closed syntax-repair subset makes the agent writer text parse."""


class AmbiguousSyntaxRepairError(PublicationError):
    """More than one distinct syntax-repair candidate parses the text."""


class IdempotencyConflictError(PublicationError):
    """``operation_id`` replayed with a request that does not match."""


class CorruptLeftoverError(PublicationError):
    """A prepared payload or receipt file does not match its content digest.

    Raised on retry after an interrupted publication when a leftover file was
    tampered with between the crash and the retry. Repair quarantines the
    file first. It removes a file that stays corrupt, and it retains a valid
    replacement that a racing writer put in place. The message names the
    outcome, and a further retry starts from a clean or valid file.
    """


class PointerNotFoundError(PublicationError):
    """``pointer_path`` does not reference an existing pointer file."""


class PayloadDigestMismatchError(PublicationError):
    """A previously revealed pointer's payload no longer matches its digest."""


@dataclass(frozen=True)
class _PublicationRequest:
    operation_id: str
    request_digest: str
    source_phase: str
    destination_phase: str
    payload_schema_uri: str


def _trim_whitespace(text: str) -> str:
    return text.strip()


_CURLY_QUOTE_MAP = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}


def _string_content_mask(text: str) -> list[bool]:
    """Mark which indices of ``text`` fall strictly inside a JSON string.

    Only straight double quotes toggle string state (with backslash-escape
    tracking); curly quotes never delimit a string for this scan. That makes
    the mask fully deterministic ahead of repair: content between straight
    quotes -- including any curly quotes or commas an agent wrote as prose --
    is never mistaken for structure. Text with no straight quotes remains
    unchanged because its curly quotes can be either structure or payload data.
    """
    mask = [False] * len(text)
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
                mask[index] = True
            elif char == "\\":
                escaped = True
                mask[index] = True
            elif char == '"':
                in_string = False
            else:
                mask[index] = True
        elif char == '"':
            in_string = True
    return mask


def _normalize_quotes(text: str) -> str:
    if '"' not in text:
        return text
    mask = _string_content_mask(text)
    return "".join(
        char if mask[index] else _CURLY_QUOTE_MAP.get(char, char)
        for index, char in enumerate(text)
    )


_TRAILING_COMMA_RE = re.compile(r",(\s*)([}\]])")


def _remove_trailing_comma(text: str) -> str:
    mask = _string_content_mask(text)

    def _repair(match: re.Match[str]) -> str:
        if mask[match.start()]:
            return match.group(0)
        return match.group(1) + match.group(2)

    return _TRAILING_COMMA_RE.sub(_repair, text)


_ACTIONS: tuple[tuple[NormalizationActionKind, Callable[[str], str]], ...] = (
    (NormalizationActionKind.TRIM_WHITESPACE, _trim_whitespace),
    (NormalizationActionKind.NORMALIZE_QUOTES, _normalize_quotes),
    (NormalizationActionKind.REMOVE_TRAILING_COMMA, _remove_trailing_comma),
)

# The 7 non-empty subsets of the 3 closed syntax-repair actions, in fixed
# order: singletons first, then pairs, then the full set -- each group listed
# by ascending action index. Applying a subset always runs its actions in
# this same ascending order, so a subset's output text is deterministic.
_SUBSETS: tuple[tuple[int, ...], ...] = (
    (0,),
    (1,),
    (2,),
    (0, 1),
    (0, 2),
    (1, 2),
    (0, 1, 2),
)


def _apply_subset(text: str, subset: tuple[int, ...]) -> str:
    for index in subset:
        _, action_fn = _ACTIONS[index]
        text = action_fn(text)
    return text


def _select_repair(text: str) -> tuple[str, tuple[int, ...]]:
    """Return the unique parsing candidate and the subset that produced it.

    Enumerates ``_SUBSETS`` in fixed order, applying each subset's actions and
    attempting a plain JSON parse. Candidates are deduped by output text, so
    the first (smallest) subset to produce a given text is the one recorded
    for it. Zero distinct parsing candidates is unrecoverable; more than one
    is ambiguous; exactly one is accepted.
    """
    seen: dict[str, tuple[int, ...]] = {}
    for subset in _SUBSETS:
        candidate = _apply_subset(text, subset)
        try:
            json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if candidate not in seen:
            seen[candidate] = subset
    if not seen:
        raise UnrecoverableSyntaxError(
            "no syntax-repair subset makes the agent writer text parse"
        )
    if len(seen) > 1:
        raise AmbiguousSyntaxRepairError(
            f"{len(seen)} distinct syntax-repair candidates parse the agent writer text"
        )
    ((candidate, subset),) = seen.items()
    return candidate, subset


def syntax_normalize(raw_text: str) -> tuple[str, tuple[NormalizationAction, ...]]:
    """Repair ``raw_text`` using only the closed syntax-recovery action set.

    A direct parse is tried first (zero actions, zero drift). Otherwise the 7
    non-empty action subsets are enumerated in fixed order; a unique
    resulting candidate is accepted with its actions recorded at ``\"$\"``,
    none is rejected as :class:`UnrecoverableSyntaxError`, and more than one
    distinct candidate is rejected as :class:`AmbiguousSyntaxRepairError`.
    """
    try:
        json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    else:
        return raw_text, ()
    candidate, subset = _select_repair(raw_text)
    actions = tuple(
        NormalizationAction(field_path="$", action=_ACTIONS[index][0])
        for index in subset
    )
    return candidate, actions


def _digest_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _digest_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def request_digest(
    raw_text: str,
    invocation: Mapping[str, object],
    *,
    source_phase: str,
    destination_phase: str,
    payload_schema_uri: str,
) -> str:
    """Digest the request text, invocation, route, and payload schema."""
    envelope = json.dumps(
        {
            "destination_phase": destination_phase,
            "invocation": invocation,
            "payload_schema_uri": payload_schema_uri,
            "raw_text": raw_text,
            "source_phase": source_phase,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _digest_text(envelope)


def _fsync_dir(directory: Path) -> None:
    """Flush ``directory`` metadata where the platform supports it.

    Windows and some network filesystems refuse a directory handle or a
    directory ``fsync``. Durability is best effort there; the caller has
    already flushed the file itself, so the publication still proceeds.
    """
    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        return
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _fsync_dir(path.parent)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _exclusive_reveal(temp_name: str, path: Path, content: bytes) -> None:
    """Link ``temp_name`` to ``path``, falling back to an exclusive create.

    A hard link is the primitive that fails loudly on a racing reveal. A
    filesystem without hard links (for example FAT or an SMB share) raises
    ``OSError``; the fallback writes the same content under ``O_EXCL``,
    which keeps the same ``FileExistsError`` contract for that race.
    """
    try:
        os.link(temp_name, path)
        return
    except FileExistsError:
        raise
    except OSError:
        pass
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        _ = handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_reveal(path: Path, content: bytes) -> None:
    """Create ``path`` exclusively, raising ``FileExistsError`` if it is
    already there -- a racing reveal for the same ``operation_id`` can never
    overwrite a pointer another caller already published."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _exclusive_reveal(temp_name, path, content)
        _fsync_dir(path.parent)
    finally:
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def _content_path(directory: Path, digest: str) -> Path:
    return directory / f"{digest.replace(':', '-')}.json"


@contextmanager
def _digest_lock(directory: Path, digest: str) -> Generator[None, None, None]:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = directory / f".{digest.replace(':', '-')}.lock"
    descriptor = os.open(
        str(lock_path),
        os.O_CREAT | os.O_RDWR,
        0o600,
    )
    locked = False
    try:
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if fcntl is not None and locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _retain_content(directory: Path, digest: str, content: bytes) -> Path:
    """Write ``content`` at its digest-addressed path, revalidating a leftover.

    The lock serializes cooperating writers. Atomic quarantine also prevents a
    lockless writer from losing a valid replacement during corrupt-file repair.
    """
    path = _content_path(directory, digest)
    with _digest_lock(directory, digest):
        if path.exists():
            try:
                existing = path.read_bytes()
            except FileNotFoundError as exc:
                raise CorruptLeftoverError(
                    f"prepared content at {path} changed during repair"
                ) from exc
            if _digest_bytes(existing) == digest:
                return path

            descriptor, quarantine_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".corrupt", dir=str(directory)
            )
            os.close(descriptor)
            quarantine = Path(quarantine_name)
            try:
                try:
                    os.replace(path, quarantine)
                except FileNotFoundError as exc:
                    raise CorruptLeftoverError(
                        f"prepared content at {path} changed during repair"
                    ) from exc
                quarantined = quarantine.read_bytes()
                if _digest_bytes(quarantined) == digest:
                    _atomic_write(path, quarantined)
                    raise CorruptLeftoverError(
                        f"prepared content at {path} changed during repair; retained"
                    )
            finally:
                quarantine.unlink(missing_ok=True)
            raise CorruptLeftoverError(
                f"prepared content at {path} does not match digest {digest}; removed"
            )
        _atomic_write(path, content)
    return path


def _read_bounded(path: Path) -> bytes:
    """Read at most one contract-sized file, rejecting a larger one unread.

    A pointer path is caller-supplied, so the gateway never allocates more
    than ``MAX_CONTRACT_BYTES`` for it before schema validation runs.
    """
    with path.open("rb") as handle:
        raw = handle.read(MAX_CONTRACT_BYTES + 1)
    if len(raw) > MAX_CONTRACT_BYTES:
        raise ContractValidationError(
            f"pointer at {path} exceeds MAX_CONTRACT_BYTES ({MAX_CONTRACT_BYTES} bytes)"
        )
    return raw


def _read_pointer(path: Path) -> HandoffPointer:
    raw = _read_bounded(path)
    artifact = validate_contract(
        raw, HandoffPointer, supported_version_for(HandoffPointer)
    )
    value = artifact.value
    assert isinstance(value, HandoffPointer)
    return value


def _resolve_pointer_artifact(
    ref: ArtifactRef,
    artifact_root: Path,
    *,
    digest_error: Callable[[str], Exception] | None = None,
) -> bytes:
    try:
        scheme = urlsplit(ref.uri).scheme
    except ValueError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} has an invalid uri"
        ) from exc
    if scheme != "file":
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is not a file:// uri"
        )
    try:
        resolved = resolve_artifact(
            ref,
            repository_root=artifact_root,
            artifact_directory=artifact_root,
            allowed_local_root=artifact_root,
        )
    except ArtifactDigestMismatchError as exc:
        error = (
            digest_error(str(exc))
            if digest_error is not None
            else ContractValidationError(str(exc))
        )
        raise error from exc
    except ArtifactResolutionError as exc:
        raise ContractValidationError(str(exc)) from exc
    return resolved.content


def _resolve_pointer(
    pointer: HandoffPointer,
    request: _PublicationRequest,
    artifact_root: Path,
) -> tuple[CanonicalArtifact, ArtifactRef | None]:
    if pointer.destination_phase != request.destination_phase:
        raise ContractValidationError(
            f"pointer destination {pointer.destination_phase!r} does not match "
            + f"consumer {request.destination_phase!r}"
        )
    _ = validate_transition(
        COMPILED_TRANSITION_REGISTRY,
        pointer.source_phase,
        pointer.destination_phase,
        request.payload_schema_uri,
    )
    payload_bytes = _resolve_pointer_artifact(
        pointer.payload,
        artifact_root,
        digest_error=PayloadDigestMismatchError,
    )
    canonical = validate_contract(
        payload_bytes,
        request.payload_schema_uri,
        supported_version_for(request.payload_schema_uri),
    )

    receipt_ref = pointer.normalization_receipt
    if receipt_ref is not None:
        receipt_bytes = _resolve_pointer_artifact(receipt_ref, artifact_root)
        receipt_artifact = validate_contract(receipt_bytes, NormalizationReceipt, None)
        receipt = receipt_artifact.value
        assert isinstance(receipt, NormalizationReceipt)
        source_version = receipt.source_version
        if (
            source_version is not None
            and receipt.source_schema_uri != source_version.schema_uri
        ):
            raise ContractValidationError(
                "normalization_receipt declares two legacy source identities: "
                + f"{receipt.source_schema_uri!r} and {source_version.schema_uri!r}"
            )
        if receipt.canonical_digest != _digest_bytes(canonical.canonical_bytes):
            raise ContractValidationError(
                "normalization_receipt.canonical_digest does not match the canonical payload"
            )
    return canonical, receipt_ref


def _rehydrate(
    pointer: HandoffPointer, request: _PublicationRequest, artifact_root: Path
) -> PublishedArtifact:
    canonical, receipt_ref = _resolve_pointer(pointer, request, artifact_root)
    return PublishedArtifact(
        pointer=pointer,
        canonical=canonical,
        normalization_receipt=receipt_ref,
    )


def _pointer_path(root: Path, operation_id: str) -> Path:
    if (
        not isinstance(operation_id, str)  # pyright: ignore[reportUnnecessaryIsInstance]
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", operation_id) is None
    ):
        raise PublicationError("invalid operation_id")
    pointer_dir = (root / "pointers").resolve()
    pointer_path = pointer_dir / f"{operation_id}.json"
    if pointer_path.parent != pointer_dir:
        raise PublicationError("invalid operation_id")
    return pointer_path


def _validate_replay(pointer: HandoffPointer, request: _PublicationRequest) -> None:
    if (
        pointer.operation_id != request.operation_id
        or
        pointer.request_digest != request.request_digest
        or pointer.source_phase != request.source_phase
        or pointer.destination_phase != request.destination_phase
        or pointer.payload.schema_uri != request.payload_schema_uri
    ):
        raise IdempotencyConflictError(
            f"operation {pointer.operation_id!r} was already published with a different request"
        )


def publish_canonical(
    *,
    request_digest: str,
    source_phase: str,
    destination_phase: str,
    payload_schema_uri: str,
    operation_id: str,
    artifact_root: str | Path,
    prepare: Callable[[], tuple[CanonicalArtifact, NormalizationReceipt | None]],
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Validate, persist, and reveal one canonical publication."""
    request = _PublicationRequest(
        operation_id=operation_id,
        request_digest=request_digest,
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
    )
    return _publish_canonical(
        request=request,
        artifact_root=artifact_root,
        prepare=prepare,
        _before_reveal=_before_reveal,
    )


def _publish_canonical(
    *,
    request: _PublicationRequest,
    artifact_root: str | Path,
    prepare: Callable[[], tuple[CanonicalArtifact, NormalizationReceipt | None]],
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Persist a prepared canonical payload and reveal its pointer."""
    root = Path(artifact_root)
    pointer_path = _pointer_path(root, request.operation_id)
    _ = validate_transition(
        COMPILED_TRANSITION_REGISTRY,
        request.source_phase,
        request.destination_phase,
        request.payload_schema_uri,
    )
    if pointer_path.exists():
        existing = _read_pointer(pointer_path)
        _validate_replay(existing, request)
        return _rehydrate(existing, request, root)

    validated, receipt = prepare()

    payload_bytes = validated.canonical_bytes
    payload_digest = _digest_bytes(payload_bytes)
    payload_path = _retain_content(root / "payloads", payload_digest, payload_bytes)
    payload_ref = ArtifactRef(
        artifact_id=f"payload-{request.operation_id}",
        role="payload",
        uri=payload_path.resolve().as_uri(),
        digest=payload_digest,
        size_bytes=len(payload_bytes),
        media_type="application/json",
        schema_uri=request.payload_schema_uri,
    )

    receipt_ref: ArtifactRef | None = None
    if receipt is not None:
        receipt_bytes = canonical_bytes(receipt)
        receipt_digest = _digest_bytes(receipt_bytes)
        receipt_path = _retain_content(root / "receipts", receipt_digest, receipt_bytes)
        receipt_ref = ArtifactRef(
            artifact_id=f"receipt-{request.operation_id}",
            role="normalization_receipt",
            uri=receipt_path.resolve().as_uri(),
            digest=receipt_digest,
            size_bytes=len(receipt_bytes),
            media_type="application/json",
            schema_uri=NORMALIZATION_RECEIPT_SCHEMA_URI,
        )
    handoff_version = supported_version_for(HandoffPointer)
    assert handoff_version is not None
    pointer = HandoffPointer(
        contract_version=handoff_version,
        operation_id=request.operation_id,
        request_digest=request.request_digest,
        source_phase=request.source_phase,
        destination_phase=request.destination_phase,
        payload=payload_ref,
        normalization_receipt=receipt_ref,
    )
    pointer_bytes = canonical_bytes(pointer)
    if _before_reveal is not None:
        _before_reveal()
    _ = _resolve_pointer(pointer, request, root)
    try:
        _atomic_reveal(pointer_path, pointer_bytes)
    except FileExistsError:
        existing = _read_pointer(pointer_path)
        _validate_replay(existing, request)
        return _rehydrate(existing, request, root)
    return PublishedArtifact(
        pointer=pointer, canonical=validated, normalization_receipt=receipt_ref
    )


def publish(
    raw_text: str,
    invocation: Mapping[str, object],
    *,
    source_phase: str,
    destination_phase: str,
    payload_schema_uri: str,
    operation_id: str,
    artifact_root: str | Path,
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Validate, persist, and reveal one canonical Mold-to-Cook handoff.

    Runs ``raw_text`` through :func:`syntax_normalize` then the existing
    semantics-strict ``normalize_agent_output``, then hands the canonical
    result to :func:`publish_canonical` for route validation, immutable
    persistence, and pointer-last reveal. A replayed ``operation_id`` with the
    same request returns the same :class:`PublishedArtifact`; a replay with a
    different request raises :class:`IdempotencyConflictError`.
    """
    request = _PublicationRequest(
        operation_id=operation_id,
        request_digest=request_digest(
            raw_text,
            invocation,
            source_phase=source_phase,
            destination_phase=destination_phase,
            payload_schema_uri=payload_schema_uri,
        ),
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
    )

    def _prepare() -> tuple[CanonicalArtifact, NormalizationReceipt | None]:
        normalized_text, actions = syntax_normalize(raw_text)
        canonical = normalize_agent_output(normalized_text, invocation)
        validated = validate_contract(
            canonical.canonical_bytes,
            request.payload_schema_uri,
            supported_version_for(request.payload_schema_uri),
        )
        receipt = None
        if actions:
            receipt = NormalizationReceipt(
                ingress_kind=IngressKind.WRITER_VIEW,
                normalizer_id="easy_cheese.shared.publication:syntax_normalize",
                source_digest=_digest_text(raw_text),
                canonical_digest=_digest_bytes(validated.canonical_bytes),
                actions=actions,
            )
        return validated, receipt

    return _publish_canonical(
        request=request,
        artifact_root=artifact_root,
        prepare=_prepare,
        _before_reveal=_before_reveal,
    )


def accept(
    pointer_path: str | Path,
    *,
    destination_phase: str,
    payload_schema_uri: str,
    artifact_root: str | Path | None = None,
) -> AcceptedArtifact:
    """Validate a canonical ``HandoffPointer`` and return its AcceptedArtifact.

    ``pointer_path`` is a filesystem path to a pointer JSON file; a bare
    canonical payload handed to this function is rejected because it will
    not conform to the handoff-pointer schema, and a missing path raises
    :class:`PointerNotFoundError` rather than a misdiagnosed JSON error.
    ``artifact_root`` is the caller-declared artifact root; when omitted, it
    is derived from ``pointer_path``'s resolved (not merely relative) parent
    directory, so accepting a pointer via a relative path from inside its
    own ``pointers/`` directory still resolves the correct root. Execution
    may proceed only once this function returns: the pointer's contract
    version is checked for strict equality, its ``source_phase ->
    destination_phase`` route is validated against the compiled phase
    registry, every referenced artifact (payload and, when present,
    normalization receipt) is checked for file existence and digest match, a
    present receipt is bound to the canonical payload's digest, and the
    canonical payload itself is validated against ``payload_schema_uri``.
    """
    path = Path(pointer_path)
    if not path.is_file():
        raise PointerNotFoundError(f"pointer not found at {path}")
    root = (
        Path(artifact_root)
        if artifact_root is not None
        else path.resolve().parent.parent
    )
    pointer = _read_pointer(path)
    request = _PublicationRequest(
        operation_id=pointer.operation_id,
        request_digest=pointer.request_digest,
        source_phase=pointer.source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
    )
    canonical, receipt_ref = _resolve_pointer(pointer, request, root)
    return AcceptedArtifact(canonical=canonical, normalization_receipt=receipt_ref)
