"""Structural checks for Mold-to-Cook agent transcripts.

The checker deliberately ignores model prose. It accepts only bounded,
machine-readable action events and enforces the authority ordering shared by
Mold and Cook.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

MAX_EVENTS = 64
MAX_EVENT_KEYS = 16
MAX_TEXT = 4096


class TranscriptCheckError(ValueError):
    """A trace cannot prove the required workflow ordering."""


@dataclass(frozen=True)
class TranscriptReport:
    scenario: str
    input_kind: str
    mode: str
    artifact_refs: tuple[str, ...]
    event_types: tuple[str, ...]


_EVENT_TYPES = frozenset(
    {
        "input_classified",
        "prepare",
        "approval_requested",
        "approval_recorded",
        "plan_materialized",
        "setup_authorized",
        "setup_evidence",
        "handoff_published",
        "consumer_accept",
        "feature_write",
        "remainder_preserved",
    }
)
_INPUT_KINDS = frozenset(
    {"direct_spec", "slug", "task", "canonical_pointer", "continuation"}
)
_MODES = frozenset({"full", "light"})
_APPROVAL_KINDS = frozenset({"scope", "plan", "partial_plan", "runner"})


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TranscriptCheckError(f"{label} must be an object")
    mapping = cast(Mapping[str, object], value)
    result = dict(mapping)
    if len(result) > MAX_EVENT_KEYS:
        raise TranscriptCheckError(f"{label} has too many fields")
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT:
        raise TranscriptCheckError(f"{label} must be a bounded non-empty string")
    return value


def _artifact_refs(events: Sequence[dict[str, object]]) -> tuple[str, ...]:
    refs: list[str] = []
    for event in events:
        if event["type"] not in {"handoff_published", "consumer_accept"}:
            continue
        value = _text(event.get("artifact_ref"), "artifact_ref")
        if value.startswith(("/", "~")) or ".." in Path(value).parts:
            raise TranscriptCheckError("artifact_ref must be repository-relative")
        refs.append(value)
    return tuple(refs)


def check_transcript(
    trace: Mapping[str, object],
    *,
    expected_input_kind: str | None = None,
    expected_mode: str | None = None,
) -> TranscriptReport:
    """Validate action ordering and authority without inspecting prose."""
    document = _mapping(trace, "trace")
    scenario = _text(document.get("scenario"), "scenario")
    raw_events = document.get("events")
    if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
        raise TranscriptCheckError("events must be a list")
    if not raw_events or len(raw_events) > MAX_EVENTS:
        raise TranscriptCheckError("events must contain between one and 64 items")
    events = [_mapping(item, f"events[{index}]") for index, item in enumerate(raw_events)]
    types = tuple(_text(event.get("type"), f"events[{index}].type") for index, event in enumerate(events))
    if any(event_type not in _EVENT_TYPES for event_type in types):
        unknown = next(event_type for event_type in types if event_type not in _EVENT_TYPES)
        raise TranscriptCheckError(f"unknown event type {unknown!r}")
    if types[0] != "input_classified":
        raise TranscriptCheckError("trace must classify input before any action")

    classified = events[0]
    input_kind = _text(classified.get("input_kind"), "input_kind")
    if input_kind not in _INPUT_KINDS:
        raise TranscriptCheckError(f"unsupported input kind {input_kind!r}")
    if expected_input_kind is not None and input_kind != expected_input_kind:
        raise TranscriptCheckError("trace routed the input to the wrong ingress")

    preparations = [event for event in events if event["type"] == "prepare"]
    if not preparations:
        raise TranscriptCheckError("trace has no preparation action")
    mode = _text(preparations[-1].get("mode"), "prepare.mode")
    if mode not in _MODES:
        raise TranscriptCheckError(f"unsupported preparation mode {mode!r}")
    if expected_mode is not None and mode != expected_mode:
        raise TranscriptCheckError("trace used the wrong preparation mode")

    approvals = [event for event in events if event["type"] == "approval_recorded"]
    if not approvals:
        raise TranscriptCheckError("trace has no harness approval evidence")
    for approval in approvals:
        if approval.get("source") != "harness":
            raise TranscriptCheckError("approval evidence must originate in the fixture harness")
        kind = _text(approval.get("kind"), "approval.kind")
        if kind not in _APPROVAL_KINDS:
            raise TranscriptCheckError(f"unsupported approval kind {kind!r}")
        if approval.get("decision") != "approved":
            raise TranscriptCheckError("recorded approval does not authorize execution")

    first_write = next((index for index, event in enumerate(events) if event["type"] == "feature_write"), None)
    accepted_index = next((index for index, event in enumerate(events) if event["type"] == "consumer_accept"), None)
    if first_write is not None and (accepted_index is None or first_write < accepted_index):
        raise TranscriptCheckError("feature write occurred before consumer acceptance")

    setup_authorized = next((index for index, event in enumerate(events) if event["type"] == "setup_authorized"), None)
    setup_evidence = next((index for index, event in enumerate(events) if event["type"] == "setup_evidence"), None)
    if setup_authorized is not None and setup_evidence is None:
        raise TranscriptCheckError("setup authorization has no evidence")
    if setup_evidence is not None:
        if setup_authorized is None or setup_evidence < setup_authorized:
            raise TranscriptCheckError("setup evidence arrived before authorization")
        evidence = events[setup_evidence]
        if evidence.get("status") != "valid" or evidence.get("exit_code") != 0:
            raise TranscriptCheckError("setup evidence is stale or failed")

    partial = any(event.get("kind") == "partial_plan" for event in approvals) or any(
        event.get("outcome") == "partial"
        for event in events
        if event["type"] == "plan_materialized"
    )
    if partial:
        preserved = [event for event in events if event["type"] == "remainder_preserved"]
        if len(preserved) != 1 or not preserved[0].get("unresolved_work"):
            raise TranscriptCheckError("partial workflow lost its unresolved remainder")

    published_indices = [index for index, event in enumerate(events) if event["type"] == "handoff_published"]
    if not published_indices:
        raise TranscriptCheckError("trace has no published handoff")
    final_published = events[published_indices[-1]]
    if final_published.get("ready") is not True:
        raise TranscriptCheckError("final handoff is not ready")
    if accepted_index is None or accepted_index <= published_indices[-1]:
        raise TranscriptCheckError("ready handoff was not accepted by the consumer")
    if events[accepted_index].get("ready") is not True:
        raise TranscriptCheckError("consumer reported a false ready result")

    return TranscriptReport(
        scenario=scenario,
        input_kind=input_kind,
        mode=mode,
        artifact_refs=_artifact_refs(events),
        event_types=types,
    )


def load_transcript(path: str | Path) -> dict[str, object]:
    """Load one bounded JSON transcript fixture."""
    source = Path(path)
    raw = source.read_bytes()
    if len(raw) > MAX_TEXT * MAX_EVENTS:
        raise TranscriptCheckError("transcript exceeds the bounded input size")
    try:
        value = cast(object, json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TranscriptCheckError(f"invalid transcript JSON: {exc}") from exc
    return _mapping(value, "trace")


__all__ = ["TranscriptCheckError", "TranscriptReport", "check_transcript", "load_transcript"]
