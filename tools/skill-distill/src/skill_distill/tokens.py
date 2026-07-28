"""Pinned tokenizer identity and invocation load-event measurement."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
import re
from typing import Protocol

from .contracts import LoadEvent, TokenMetricProfile, TokenizerIdentity
from .model_lock import snapshot_digest


class Encoder(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool) -> object: ...


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
_EXACT_RUNTIME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[^=\s]+$")


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _identity_fields(
    tokenizer_artifact: str,
    tokenizer_revision: str,
    tokenizer_hash: str,
    runtime: str,
) -> dict[str, object]:
    return {
        "tokenizer_artifact": tokenizer_artifact,
        "tokenizer_revision": tokenizer_revision,
        "tokenizer_hash": tokenizer_hash,
        "runtime": runtime,
        "text_encoding": "utf-8",
        "event_mode": "independent",
        "chat_template": "none",
        "add_special_tokens": False,
    }


def _validate_lock(
    tokenizer_artifact: str,
    tokenizer_revision: str,
    tokenizer_hash: str,
    runtime: str,
) -> None:
    if not tokenizer_artifact:
        raise ValueError("tokenizer_artifact is required")
    if not _FULL_REVISION.fullmatch(tokenizer_revision):
        raise ValueError(
            "tokenizer_revision must be a full 40-character immutable revision"
        )
    if not _SHA256.fullmatch(tokenizer_hash):
        raise ValueError("tokenizer_hash must be a SHA-256")
    if not _EXACT_RUNTIME.fullmatch(runtime):
        raise ValueError("runtime must be an exact name/version identity")


def _validate_identity(identity: TokenizerIdentity) -> None:
    _validate_lock(
        identity.tokenizer_artifact,
        identity.tokenizer_revision,
        identity.tokenizer_hash,
        identity.runtime,
    )
    fields = _identity_fields(
        identity.tokenizer_artifact,
        identity.tokenizer_revision,
        identity.tokenizer_hash,
        identity.runtime,
    )
    if any(getattr(identity, name) != value for name, value in fields.items()):
        raise ValueError("tokenizer encoding options drift")
    if identity.identity_digest != _digest(fields):
        raise ValueError("tokenizer identity digest drift")


def _verify_local_tokenizer(
    identity: TokenizerIdentity, snapshot: Path, runtime: str
) -> None:
    _validate_identity(identity)
    if runtime != identity.runtime:
        raise ValueError("tokenizer runtime identity drift")
    if snapshot.is_symlink():
        raise ValueError(f"symlinked tokenizer snapshot: {snapshot}")
    if snapshot.is_file():
        digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    else:
        digest = snapshot_digest(snapshot)
    if digest != identity.tokenizer_hash:
        raise ValueError("local tokenizer snapshot contains drifted artifacts")


def build_tokenizer_identity(
    tokenizer_artifact: str,
    tokenizer_revision: str,
    tokenizer_hash: str,
    runtime: str,
) -> TokenizerIdentity:
    _validate_lock(
        tokenizer_artifact, tokenizer_revision, tokenizer_hash, runtime
    )
    fields = _identity_fields(
        tokenizer_artifact, tokenizer_revision, tokenizer_hash, runtime
    )
    return TokenizerIdentity(**fields, identity_digest=_digest(fields))


def measure_load_events(
    identity: TokenizerIdentity,
    loads: Iterable[tuple[str, str, str | bytes]],
    encoder: Encoder,
    *,
    snapshot: Path,
    runtime: str,
) -> TokenMetricProfile:
    """Verify the local tokenizer, then encode every exact UTF-8 load."""
    _verify_local_tokenizer(identity, snapshot, runtime)
    events = []
    for role, canonical_path, content in loads:
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        text = raw.decode("utf-8", errors="strict")
        token_ids = encoder.encode(text, add_special_tokens=False)
        events.append(
            LoadEvent(
                role,
                canonical_path,
                hashlib.sha256(raw).hexdigest(),
                identity.identity_digest,
                len(token_ids),
            )
        )
    if not events:
        raise ValueError("token metric profile requires at least one load event")
    return TokenMetricProfile(identity.identity_digest, tuple(events))


def loaded_tokens(profile: TokenMetricProfile) -> int:
    if any(
        event.tokenizer_identity_digest != profile.tokenizer_identity_digest
        for event in profile.load_events
    ):
        raise ValueError("load event tokenizer identity drift")
    return sum(event.token_count for event in profile.load_events)


def token_savings(original: TokenMetricProfile, variant: TokenMetricProfile) -> int:
    if original.tokenizer_identity_digest != variant.tokenizer_identity_digest:
        raise ValueError("tokenizer identity drift")
    return loaded_tokens(original) - loaded_tokens(variant)
