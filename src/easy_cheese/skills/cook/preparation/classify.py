"""Cook ingress classification: choose the contract before reading contents."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from easy_cheese_schemas.mold_cook import MoldCookInputKind
from easy_cheese.shared.paths import validate_slug
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import ClassifiedCookInput, CookInputError
from .evidence import as_path, is_regular_path, read_path

_POINTER_MARKERS = frozenset(
    {"operation_id", "request_digest", "source_phase", "destination_phase", "payload"}
)
_PROJECTION_MARKERS = frozenset(
    {
        "schema_version",
        "work_id",
        "revision_id",
        "record_digest",
        "projection_digest",
        "next_action",
        "gating_entry_ids",
        "decision_dossier",
        "durability",
        "status",
    }
)
_HANDOFF_MARKERS = frozenset(
    {"request_id", "input_kind", "mode", "spec_ref", "approval_ref", "coverage"}
)


def _declared_kind(raw: bytes) -> MoldCookInputKind | None:
    try:
        value = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    mapping = cast("Mapping[str, object]", value)
    keys = set(mapping)
    if keys & _POINTER_MARKERS:
        return MoldCookInputKind.CANONICAL_POINTER
    if keys & _PROJECTION_MARKERS:
        return MoldCookInputKind.CONTINUATION
    if _HANDOFF_MARKERS <= keys:
        return MoldCookInputKind.CANONICAL_POINTER
    return None


def coerce_kind(value: MoldCookInputKind | str | None) -> MoldCookInputKind | None:
    if value is None:
        return None
    if isinstance(value, MoldCookInputKind):
        return value
    normalized = value.strip().casefold().replace("-", "_")
    values = {
        "spec": MoldCookInputKind.DIRECT_SPEC,
        "direct_spec": MoldCookInputKind.DIRECT_SPEC,
        "pointer": MoldCookInputKind.CANONICAL_POINTER,
        "canonical_pointer": MoldCookInputKind.CANONICAL_POINTER,
        "continue": MoldCookInputKind.CONTINUATION,
        "continuation": MoldCookInputKind.CONTINUATION,
        "task": MoldCookInputKind.TASK,
        "slug": MoldCookInputKind.SLUG,
    }
    try:
        return values[normalized]
    except KeyError:
        try:
            return MoldCookInputKind(normalized)
        except ValueError as exc:
            raise CookInputError(f"unsupported explicit input mode {value!r}") from exc


def classify_input(
    source: str | Path,
    *,
    explicit_kind: MoldCookInputKind | str | None = None,
) -> ClassifiedCookInput:
    """Choose the ingress contract before resolving its contents.

    Explicit mode always wins. Existing regular files are inspected before
    slug/task inference, including cwd-relative names without path markers.
    """

    expected = coerce_kind(explicit_kind)
    source_text = str(source)
    path = as_path(source)
    regular = path is not None and is_regular_path(path)
    snapshot: bytes | None = None
    declared: MoldCookInputKind | None = None
    if regular:
        assert path is not None
        snapshot = read_path(path)
        declared = _declared_kind(snapshot)
    if expected is not None:
        if declared is not None and declared is not expected:
            raise CookInputError(
                f"input declares {declared.value}, not the explicit {expected.value} mode"
            )
        return ClassifiedCookInput(
            expected, source_text, path, True, declared, snapshot
        )
    if declared is not None:
        return ClassifiedCookInput(
            declared, source_text, path, False, declared, snapshot
        )
    if regular:
        assert path is not None
        if path.suffix.casefold() in {".md", ".markdown"}:
            return ClassifiedCookInput(
                MoldCookInputKind.DIRECT_SPEC,
                source_text,
                path,
                False,
                None,
                snapshot,
            )
        raise CookInputError(
            f"unrecognised artifact {str(path)!r}; use an explicit Cook input mode"
        )
    if validate_slug(source_text) is None:
        return ClassifiedCookInput(MoldCookInputKind.SLUG, source_text)
    if not source_text.strip():
        raise CookInputError("Cook input must not be empty")
    return ClassifiedCookInput(MoldCookInputKind.TASK, source_text)


def derive_request_id(source: ClassifiedCookInput, explicit: str | None) -> str:
    if explicit:
        return explicit
    # The parts are JSON-encoded, never newline-joined: free text in the
    # objective would otherwise reproduce another input's token.
    token = json.dumps(
        [
            source.kind.value,
            source.source,
            "" if source.path is None else str(source.path.resolve()),
            "" if source.snapshot is None else digest_bytes(source.snapshot),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"cook-{hashlib.sha256(token.encode()).hexdigest()[:20]}"
