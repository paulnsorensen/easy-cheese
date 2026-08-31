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
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import unquote, urlsplit

from easy_cheese_schemas import (
    COMPILED_TRANSITION_REGISTRY,
    ArtifactRef,
    CanonicalArtifact,
    HandoffPointer,
    IngressKind,
    NormalizationAction,
    NormalizationActionKind,
    NormalizationReceipt,
    PublishedArtifact,
    canonical_bytes,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
    validate_transition,
)

__all__ = [
    "AmbiguousSyntaxRepairError",
    "CorruptLeftoverError",
    "IdempotencyConflictError",
    "UnrecoverableSyntaxError",
    "publish",
    "publish_canonical",
    "request_digest",
    "syntax_normalize",
]


class UnrecoverableSyntaxError(ValueError):
    """No closed syntax-repair subset makes the agent writer text parse."""


class AmbiguousSyntaxRepairError(ValueError):
    """More than one distinct syntax-repair candidate parses the text."""


class IdempotencyConflictError(ValueError):
    """``operation_id`` replayed with a request that does not match."""


class CorruptLeftoverError(ValueError):
    """A prepared payload or receipt file does not match its content digest.

    Raised on retry after an interrupted publication when a leftover file was
    tampered with between the crash and the retry; the corrupt file is
    removed before this is raised, so a further retry starts clean.
    """


def _trim_whitespace(text: str) -> str:
    return text.strip()


_CURLY_QUOTES = str.maketrans({
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
})


def _normalize_quotes(text: str) -> str:
    return text.translate(_CURLY_QUOTES)


_TRAILING_COMMA_RE = re.compile(r",(\s*)([}\]])")


def _remove_trailing_comma(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1\2", text)


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


def request_digest(raw_text: str, invocation: Mapping[str, object]) -> str:
    """Digest binding a request to its exact raw text and invocation context.

    Two publications sharing an ``operation_id`` are the same request only if
    this digest matches; both :func:`publish` and
    ``easy_cheese.shared.migrate.migrate`` bind idempotency to it.
    """
    envelope = json.dumps(
        {"invocation": invocation, "raw_text": raw_text},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _digest_text(envelope)


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
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _content_path(directory: Path, digest: str) -> Path:
    return directory / f"{digest.replace(':', '-')}.json"


def _retain_content(directory: Path, digest: str, content: bytes) -> Path:
    """Write ``content`` at its digest-addressed path, revalidating a leftover.

    A file already at this path was fully written by a prior attempt (writes
    are atomic), so it must match ``digest`` exactly. If it does not --
    tampered after the fact -- the leftover is removed and rejected rather
    than silently overwritten, so a caller learns of the corruption instead of
    a retry quietly proceeding on it.
    """
    path = _content_path(directory, digest)
    if path.exists():
        existing = path.read_bytes()
        if _digest_bytes(existing) == digest:
            return path
        path.unlink()
        raise CorruptLeftoverError(
            f"prepared content at {path} does not match digest {digest}; removed"
        )
    _atomic_write(path, content)
    return path


def _uri_to_path(uri: str) -> Path:
    return Path(unquote(urlsplit(uri).path))


def _read_pointer(path: Path) -> HandoffPointer:
    raw = path.read_bytes()
    artifact = validate_contract(
        raw, HandoffPointer, supported_version_for(HandoffPointer)
    )
    value = artifact.value
    assert isinstance(value, HandoffPointer)
    return value


def _rehydrate(pointer: HandoffPointer, payload_schema_uri: str) -> PublishedArtifact:
    payload_path = _uri_to_path(pointer.payload.uri)
    payload_bytes = payload_path.read_bytes()
    canonical = validate_contract(
        payload_bytes, payload_schema_uri, supported_version_for(payload_schema_uri)
    )
    return PublishedArtifact(
        pointer=pointer,
        canonical=canonical,
        normalization_receipt=pointer.normalization_receipt,
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
    """Validate a route, persist canonical content, and reveal one pointer.

    The shared second half of every Mold-to-Cook publication: an idempotency
    check against ``operation_id``, then -- only for a genuinely new request
    -- ``prepare()`` supplies the already-canonical payload and its optional
    receipt, the route is validated against the compiled phase registry, both
    are written as immutable content-addressed files, and the
    ``HandoffPointer`` is atomically revealed last. :func:`publish` and
    ``easy_cheese.shared.migrate.migrate`` both call this rather than
    duplicating pointer-reveal logic.
    """
    root = Path(artifact_root)
    pointer_path = root / "pointers" / f"{operation_id}.json"
    if pointer_path.exists():
        existing = _read_pointer(pointer_path)
        if existing.request_digest != request_digest:
            raise IdempotencyConflictError(
                f"operation {operation_id!r} was already published with a different request"
            )
        return _rehydrate(existing, payload_schema_uri)

    validated, receipt = prepare()
    _ = validate_transition(
        COMPILED_TRANSITION_REGISTRY, source_phase, destination_phase, payload_schema_uri
    )

    payload_digest = canonical_digest(validated.value)
    payload_path = _retain_content(
        root / "payloads", payload_digest, validated.canonical_bytes
    )
    payload_ref = ArtifactRef(
        artifact_id=f"payload-{operation_id}",
        role="payload",
        uri=payload_path.resolve().as_uri(),
        digest=payload_digest,
        size_bytes=len(validated.canonical_bytes),
        media_type="application/json",
        schema_uri=payload_schema_uri,
    )

    receipt_ref: ArtifactRef | None = None
    if receipt is not None:
        receipt_bytes = canonical_bytes(receipt)
        receipt_digest = canonical_digest(receipt)
        receipt_path = _retain_content(root / "receipts", receipt_digest, receipt_bytes)
        receipt_ref = ArtifactRef(
            artifact_id=f"receipt-{operation_id}",
            role="normalization_receipt",
            uri=receipt_path.resolve().as_uri(),
            digest=receipt_digest,
            size_bytes=len(receipt_bytes),
            media_type="application/json",
        )

    handoff_version = supported_version_for(HandoffPointer)
    assert handoff_version is not None
    pointer = HandoffPointer(
        contract_version=handoff_version,
        operation_id=operation_id,
        request_digest=request_digest,
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload=payload_ref,
        normalization_receipt=receipt_ref,
    )
    if _before_reveal is not None:
        _before_reveal()
    _atomic_write(pointer_path, canonical_bytes(pointer))
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
    req_digest = request_digest(raw_text, invocation)

    def _prepare() -> tuple[CanonicalArtifact, NormalizationReceipt | None]:
        normalized_text, actions = syntax_normalize(raw_text)
        canonical = normalize_agent_output(normalized_text, invocation)
        validated = validate_contract(
            canonical.canonical_bytes,
            payload_schema_uri,
            supported_version_for(payload_schema_uri),
        )
        receipt = None
        if actions:
            receipt = NormalizationReceipt(
                ingress_kind=IngressKind.WRITER_VIEW,
                normalizer_id="easy_cheese.shared.publication:syntax_normalize",
                source_digest=_digest_text(raw_text),
                canonical_digest=canonical_digest(validated.value),
                actions=actions,
            )
        return validated, receipt

    return publish_canonical(
        request_digest=req_digest,
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
        operation_id=operation_id,
        artifact_root=artifact_root,
        prepare=_prepare,
        _before_reveal=_before_reveal,
    )
