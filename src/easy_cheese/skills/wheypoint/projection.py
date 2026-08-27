"""The generated Markdown view of a record: render, parse, and pin.

The document opens with a fixed keyed preamble -- the same shape the handoff
slug uses, so a cold reader already knows how to read the first lines -- and
closes with the gating entries and the decision dossier.

Two rules make the file safe to hand back to a human:

* **`status:` is written, never read.** Parsing derives the status from the
  gating entry list, exactly as the schema types do. Editing the word `gated`
  to `ok` changes nothing except the digest.
* **The digest covers the document.** `projection_digest` is a hash of the
  rendered text with its own value blanked, so every other byte -- preamble,
  orientation, gates, dossier -- is pinned, and the digest line is the only
  thing that cannot hash itself.
"""

from __future__ import annotations

import json
import re

from attrs import evolve
from easy_cheese_schemas import (
    DecisionFork,
    Durability,
    NextAction,
    NextMove,
    WheypointProjection,
    WheypointRecord,
)

from . import canonical, records

_PREAMBLE_KEYS = (
    "status",
    "next",
    "artifact",
    "work_id",
    "revision_id",
    "record_digest",
    "projection_digest",
    "durability",
    "schema_version",
)
_ORIENTATION_LINE = len(_PREAMBLE_KEYS)
_GATES_HEADING = "## Gating entries"
_DOSSIER_HEADING = "## Decision dossier"
_FENCE = "```json"
_NO_GATES = "none"
_UNPINNED_DIGEST = f"{canonical.DIGEST_PREFIX}{'0' * 64}"
_DIGEST_LINE_RE = re.compile(r"^projection_digest:.*$", re.MULTILINE)


class ProjectionParseError(ValueError):
    """Raised when a projection document cannot be read as one."""


def projection_digest_of_text(text: str) -> str:
    """The digest the document's own `projection_digest:` line should carry."""
    blanked = _DIGEST_LINE_RE.sub("projection_digest:", text, count=1)
    return canonical.digest_text(blanked)


def render(projection: WheypointProjection) -> str:
    action = projection.next_action
    lines = [
        f"status: {projection.status.value}",
        f"next: {action.move.value}",
        f"artifact: {action.artifact or ''}",
        f"work_id: {projection.work_id}",
        f"revision_id: {projection.revision_id}",
        f"record_digest: {projection.record_digest}",
        f"projection_digest: {projection.projection_digest}",
        f"durability: {projection.durability.value}",
        f"schema_version: {projection.schema_version}",
        action.orientation,
        "",
        f"# Wheypoint {projection.work_id} @ {projection.revision_id}",
        "",
        _GATES_HEADING,
        "",
    ]
    if projection.gating_entry_ids:
        lines.extend(f"- {entry_id}" for entry_id in projection.gating_entry_ids)
    else:
        lines.append(_NO_GATES)
    dossier = canonical.canonical_bytes(
        [records.unstructure(fork) for fork in projection.decision_dossier]
    ).decode("utf-8")
    lines.extend(["", _DOSSIER_HEADING, "", _FENCE, dossier, "```", ""])
    return "\n".join(lines)


def build_projection(
    record: WheypointRecord, *, durability: Durability
) -> tuple[WheypointProjection, str]:
    """Derive the projection for `record` and render it, in one step.

    Returning both is the point: the digest inside the document is a hash of
    the document, so a caller that could build one without the other could hold
    a projection whose digest belongs to text nobody has.
    """
    draft = WheypointProjection(
        schema_version=record.schema_version,
        work_id=record.work_id,
        revision_id=record.revision_id,
        record_digest=records.record_digest(record),
        projection_digest=_UNPINNED_DIGEST,
        next_action=record.next_action,
        gating_entry_ids=list(record.gating_entry_ids),
        decision_dossier=list(record.decision_dossier),
        durability=durability,
    )
    pinned = evolve(draft, projection_digest=projection_digest_of_text(render(draft)))
    return pinned, render(pinned)


def _preamble(lines: list[str]) -> dict[str, str]:
    if len(lines) <= _ORIENTATION_LINE:
        raise ProjectionParseError(
            f"projection needs {_ORIENTATION_LINE + 1} preamble lines, "
            f"got {len(lines)}"
        )
    values: dict[str, str] = {}
    for index, key in enumerate(_PREAMBLE_KEYS):
        prefix = f"{key}: "
        line = lines[index]
        if not line.startswith(prefix):
            raise ProjectionParseError(f"expected {key!r} line, got {line!r}")
        values[key] = line[len(key) + 1 :].strip()
    orientation = lines[_ORIENTATION_LINE].strip()
    if not orientation:
        raise ProjectionParseError("orientation line must be non-empty")
    values["orientation"] = orientation
    return values


def _section(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(heading) + 1
    except ValueError:
        raise ProjectionParseError(f"missing {heading!r} section") from None
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return [line for line in lines[start:end] if line.strip()]


def _gating_entry_ids(lines: list[str]) -> list[str]:
    body = _section(lines, _GATES_HEADING)
    if body == [_NO_GATES]:
        return []
    if not body or any(not line.startswith("- ") for line in body):
        raise ProjectionParseError(
            f"{_GATES_HEADING!r} must list '- <entry-id>' lines or {_NO_GATES!r}"
        )
    return [line[2:].strip() for line in body]


def _dossier(lines: list[str]) -> list[DecisionFork]:
    body = _section(lines, _DOSSIER_HEADING)
    if len(body) < 3 or body[0] != _FENCE or body[-1] != "```":
        raise ProjectionParseError(f"{_DOSSIER_HEADING!r} must hold one json block")
    try:
        payload = json.loads("\n".join(body[1:-1]))
    except ValueError as exc:
        raise ProjectionParseError(f"decision dossier is not JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ProjectionParseError("decision dossier must be a JSON array")
    try:
        return [records.structure(fork, DecisionFork) for fork in payload]
    except records.RecordError as exc:
        raise ProjectionParseError(str(exc)) from exc


def parse(text: str) -> WheypointProjection:
    """Read a projection document back. The written `status:` is ignored."""
    lines = text.splitlines()
    values = _preamble(lines)
    try:
        move = NextMove(values["next"])
    except ValueError as exc:
        raise ProjectionParseError(f"unknown next move {values['next']!r}") from exc
    try:
        durability = Durability(values["durability"])
    except ValueError as exc:
        raise ProjectionParseError(
            f"unknown durability {values['durability']!r}"
        ) from exc
    if not values["schema_version"].isdigit():
        raise ProjectionParseError(
            f"schema_version must be an integer, got {values['schema_version']!r}"
        )
    try:
        return WheypointProjection(
            schema_version=int(values["schema_version"]),
            work_id=values["work_id"],
            revision_id=values["revision_id"],
            record_digest=values["record_digest"],
            projection_digest=values["projection_digest"],
            next_action=NextAction(
                move=move,
                orientation=values["orientation"],
                artifact=values["artifact"] or None,
            ),
            gating_entry_ids=_gating_entry_ids(lines),
            decision_dossier=_dossier(lines),
            durability=durability,
        )
    except ValueError as exc:
        if isinstance(exc, ProjectionParseError):
            raise
        raise ProjectionParseError(str(exc)) from exc
