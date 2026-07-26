"""Pinned tokenizer identity and invocation load-event measurement."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Protocol

from .contracts import LoadEvent, TokenMetricProfile, TokenizerIdentity


class Encoder(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool) -> object: ...


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_tokenizer_identity(
    tokenizer_artifact: str,
    tokenizer_revision: str,
    tokenizer_hash: str,
    runtime: str,
) -> TokenizerIdentity:
    fields = {
        "tokenizer_artifact": tokenizer_artifact,
        "tokenizer_revision": tokenizer_revision,
        "tokenizer_hash": tokenizer_hash,
        "runtime": runtime,
        "text_encoding": "utf-8",
        "event_mode": "independent",
        "chat_template": "none",
        "add_special_tokens": False,
    }
    if not all((tokenizer_artifact, tokenizer_revision, tokenizer_hash, runtime)):
        raise ValueError("tokenizer artifact, revision, hash, and runtime are required")
    return TokenizerIdentity(**fields, identity_digest=_digest(fields))


def measure_load_events(
    identity: TokenizerIdentity,
    loads: Iterable[tuple[str, str, str | bytes]],
    encoder: Encoder,
) -> TokenMetricProfile:
    """Encode every exact UTF-8 load independently, preserving duplicates and order."""
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
