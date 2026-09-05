"""The generated Markdown view of a record: render, parse, and pin.

The document opens with the shared handoff preamble -- `status:`, `next:`,
`artifact:`, then the orientation -- so `parse_handoff_slug()` reads a
projection like any other handoff. The Wheypoint pins follow the orientation
as a keyed metadata block, and the gating entries and the decision dossier
close the file.

Two rules make the file safe to hand back to a human:

* **`status:` is written, never read.** Parsing derives the status from the
  gating entry list, exactly as the schema types do. Editing the word `gated`
  to `ok` changes nothing except the digest. `declared_status` hands the
  written word back separately so lint can report the disagreement instead of
  quietly discarding it.
* **The digest covers the document.** `projection_digest` is a hash of the
  rendered text with its own value blanked, so every other byte -- preamble,
  orientation, gates, dossier -- is pinned, and the digest line is the only
  thing that cannot hash itself.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import cast

from attrs import evolve
from easy_cheese_schemas import (
    DecisionFork,
    DossierOption,
    Durability,
    EntryKind,
    EntryState,
    HandoffTask,
    NextAction,
    NextMove,
    ParallelPlan,
    ProtectedEntry,
    WheypointProjection,
    WheypointRecord,
    WheypointStatus,
    WorktreeStrategy,
)
from easy_cheese_schemas.handback_status import (
    MAX_REASON_LENGTH,
    StatusError,
    parse_status_field,
    render_status_field,
)

from . import canonical, records

# The shared handoff preamble: three keyed lines, then the orientation.
_HEAD_KEYS = ("status", "next", "artifact")
_ORIENTATION_LINE = len(_HEAD_KEYS)
# The Wheypoint pins, in the keyed block that follows the orientation.
_META_KEYS = (
    "work_id",
    "revision_id",
    "record_digest",
    "projection_digest",
    "durability",
    "schema_version",
)
_META_LINE = _ORIENTATION_LINE + 2
_MODE_PREFIX = "mode: "
_MODE_PARALLEL = "parallel"
_TITLE_PREFIX = "# Wheypoint "
_GATES_HEADING = "## Gates"
_LEGACY_GATES_HEADING = "## Gating entries"
_OPEN_HEADING = "## Open entries"
_DECISIONS_HEADING = "## Decisions"
_DIRECTIVES_HEADING = "## Directives"
_NOTES_HEADING = "## Notes"
_CONTEXT_HEADING = "## Context"
_ARTIFACTS_HEADING = "## Artifacts"
_DOSSIER_HEADING = "## Decision dossier"
_TASKS_HEADING = "## Tasks"
_FENCE = "```json"
_NO_GATES = "none"
_NONE = "none"
_FORK_PREFIX = "### Fork: "
_LEANING_PREFIX = "Prior leaning: "
_OPTION_PREFIX = "- Option: "
_EVIDENCE_PREFIX = "  Evidence: "
_BREAKS_PREFIX = "  Breaks: "
_UNPINNED_DIGEST = f"{canonical.DIGEST_PREFIX}{'0' * 64}"
_DIGEST_LINE_RE = re.compile(r"^projection_digest:.*$", re.MULTILINE)


class ProjectionParseError(ValueError):
    """Raised when a projection document cannot be read as one."""


def projection_digest_of_text(text: str) -> str:
    """The digest the document's own `projection_digest:` line should carry."""
    blanked = _DIGEST_LINE_RE.sub("projection_digest:", text, count=1)
    return canonical.digest_text(blanked)


def gated_reason(gating_entry_ids: Sequence[str]) -> str:
    """The one-line reason a `gated` projection carries in its status field.

    The shared grammar requires a reason on every non-`ok` status. The reason
    is derived from the same list the status itself derives from, so a
    re-render of the same record reproduces it byte for byte.
    """
    count = len(gating_entry_ids)
    noun = "entry" if count == 1 else "entries"
    reason = f"{count} open gating {noun}: {', '.join(gating_entry_ids)}"
    if len(reason) > MAX_REASON_LENGTH:
        reason = reason[: MAX_REASON_LENGTH - 1].rstrip(", ") + "\u2026"
    return reason


def status_field(projection: WheypointProjection) -> str:
    """The rendered `status:` value, with a reason when the record is gated."""
    if projection.status is WheypointStatus.OK:
        return render_status_field(WheypointStatus.OK.value, None)
    return render_status_field(
        WheypointStatus.GATED.value, gated_reason(projection.gating_entry_ids)
    )


def _esc(text: str) -> str:
    """One line per field: backslashes and newlines are escaped."""
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def _unesc(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append("\n" if nxt == "n" else nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _render_dossier(forks: Sequence[DecisionFork]) -> list[str]:
    """The dossier as Markdown a human reads and `parse` reads back."""
    if not forks:
        return [_NONE]
    lines: list[str] = []
    for index, fork in enumerate(forks):
        if index:
            lines.append("")
        lines.append(f"{_FORK_PREFIX}{_esc(fork.fork)}")
        lines.append(
            f"{_LEANING_PREFIX}{_esc(fork.prior_leaning) if fork.prior_leaning else _NONE}"
        )
        for option in fork.options:
            lines.append(f"{_OPTION_PREFIX}{_esc(option.option)}")
            # One line per evidence item: no separator to escape, nothing to split.
            lines.extend(f"{_EVIDENCE_PREFIX}{_esc(item)}" for item in option.evidence)
            lines.append(f"{_BREAKS_PREFIX}{_esc(option.breaks)}")
    return lines


def _entry_line(entry: ProtectedEntry) -> str:
    return f"- {entry.entry_id} ({entry.kind.value}) \u2014 {_esc(entry.summary)}"


def _body(record: WheypointRecord) -> list[str]:
    """The human sections: everything the record holds that the pins do not."""
    lines: list[str] = []
    active = [e for e in records.entries(record) if e.state is EntryState.ACTIVE]
    open_entries = [
        e for e in active
        if e.kind in (EntryKind.QUESTION, EntryKind.BLOCKER) and not e.blocks_continuation
    ]
    lines += [_OPEN_HEADING, ""]
    lines += [_entry_line(e) for e in open_entries] or [_NONE]
    lines += ["", _DECISIONS_HEADING, ""]
    decisions = [e for e in active if e.kind is EntryKind.DECISION]
    for entry in decisions:
        lines.append(_entry_line(entry))
        if entry.rationale:
            lines.append(f"  rationale: {_esc(entry.rationale)}")
    if not decisions:
        lines.append(_NONE)
    lines += ["", _DIRECTIVES_HEADING, ""]
    directives = [e for e in active if e.kind is EntryKind.DIRECTIVE]
    for entry in directives:
        lines.append(_entry_line(entry))
        if entry.quote:
            lines.extend(f"  > {part}" for part in entry.quote.splitlines() or [""])
    if not directives:
        lines.append(_NONE)
    lines += ["", _NOTES_HEADING, ""]
    # A notes line that looks like a heading would split the parsed sections.
    lines += (
        [("\\" + line) if line.startswith("#") else line for line in record.notes.splitlines()]
        or [""]
    ) if record.notes else [_NONE]
    lines += ["", _CONTEXT_HEADING, ""]
    lines += [f"- {_esc(item)}" for item in record.working_context] or [_NONE]
    lines += ["", _ARTIFACTS_HEADING, ""]
    for link in record.artifact_links:
        detail = [
            f"digest: {link.digest}" if link.digest else "",
            f"revision: {link.revision_id}" if link.revision_id else "",
            f"covers: {', '.join(link.covers_entry_ids)}" if link.covers_entry_ids else "",
        ]
        detail_text = ", ".join(part for part in detail if part)
        lines.append(f"- {_esc(link.path)}" + (f" ({detail_text})" if detail_text else ""))
    if not record.artifact_links:
        lines.append(_NONE)
    return lines


def _tasks(action: NextAction) -> list[str]:
    """The `parallel:` and `tasks:` blocks in the shape `parallel-handoffs.md` documents."""
    if not action.tasks:
        return []
    lines = ["", _TASKS_HEADING, ""]
    if action.parallel is not None:
        plan = action.parallel
        lines += ["parallel:", f"  isolation: {_esc(plan.isolation)}"]
        lines.append(f"  worktree_strategy: {plan.worktree_strategy.value}")
        if plan.worktree_root:
            lines.append(f"  worktree_root: {_esc(plan.worktree_root)}")
    lines.append("tasks:")
    for task in action.tasks:
        lines.append(f"  - slug: {_esc(task.slug)}")
        for key, value in (
            ("intent", task.intent),
            ("repo", task.repo),
            ("worktree", task.worktree),
            ("branch", task.branch),
            ("branch_from", task.branch_from),
            ("command", task.command),
        ):
            if value is not None:
                lines.append(f"    {key}: {_esc(value)}")
    return lines


def render(projection: WheypointProjection, record: WheypointRecord) -> str:
    """Render the projection with the human body sections from `record`.

    The pins, the gates, the dossier and the tasks come from the projection and
    are parsed back; the body is derived from the record and is never parsed
    back. The digest covers the whole text, so the pair is what it pins and a
    projection alone cannot reproduce it (ADR wheypoint-continuity-kernel-004).
    """
    action = projection.next_action
    lines = [
        f"status: {status_field(projection)}",
        f"next: {action.move.value}",
        f"artifact: {action.artifact or ''}",
    ]
    if action.tasks:
        lines.append(f"{_MODE_PREFIX}{_MODE_PARALLEL}")
    lines.append(action.orientation)
    lines += [
        "",
        f"work_id: {projection.work_id}",
        f"revision_id: {projection.revision_id}",
        f"record_digest: {projection.record_digest}",
        f"projection_digest: {projection.projection_digest}",
        f"durability: {projection.durability.value}",
        f"schema_version: {projection.schema_version}",
        "",
        f"# Wheypoint {projection.work_id} @ {projection.revision_id}",
        "",
        _GATES_HEADING,
        "",
    ]
    summaries = {e.entry_id: e.summary for e in records.entries(record)}
    if projection.gating_entry_ids:
        for entry_id in projection.gating_entry_ids:
            summary = summaries.get(entry_id)
            lines.append(f"- {entry_id}" + (f" \u2014 {_esc(summary)}" if summary else ""))
    else:
        lines.append(_NO_GATES)
    lines += ["", *_body(record)]
    lines += ["", _DOSSIER_HEADING, "", *_render_dossier(projection.decision_dossier)]
    lines += _tasks(action)
    lines.append("")
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
    pinned = evolve(
        draft, projection_digest=projection_digest_of_text(render(draft, record))
    )
    return pinned, render(pinned, record)


def _keyed(lines: list[str], keys: Sequence[str], start: int) -> dict[str, str]:
    values: dict[str, str] = {}
    for offset, key in enumerate(keys):
        index = start + offset
        if index >= len(lines):
            raise ProjectionParseError(f"projection ends before its {key!r} line")
        prefix = f"{key}: "
        line = lines[index]
        if not line.startswith(prefix):
            raise ProjectionParseError(f"expected {key!r} line, got {line!r}")
        values[key] = line[len(prefix) :].strip()
    return values


_MIN_LINES = _META_LINE + len(_META_KEYS)
_FIRST_META_PREFIX = f"{_META_KEYS[0]}: "


def _meta_start(lines: list[str]) -> int:
    """The index of the first metadata line, after the orientation block.

    The orientation may hold more than one physical line, so the block ends at
    the blank line that separates it from the pins rather than at a fixed
    offset.
    """
    # The pins are the keyed block directly above the `# Wheypoint` title: a
    # look-alike block inside the orientation text is text, not pins.
    title = _body_start(lines) - 1
    start = title - 1 - len(_META_KEYS)
    if start < _META_LINE or lines[title - 1].strip():
        raise ProjectionParseError("the pins must sit directly above the title, ending in a blank line")
    if not lines[start].startswith(_FIRST_META_PREFIX):
        raise ProjectionParseError(f"missing {_META_KEYS[0]!r} line")
    if lines[start - 1].strip():
        raise ProjectionParseError("the orientation must end with a blank line")
    return start


def _preamble(lines: list[str]) -> dict[str, str]:
    if len(lines) < _MIN_LINES:
        raise ProjectionParseError(
            f"projection needs {_MIN_LINES} preamble lines, got {len(lines)}"
        )
    values = _keyed(lines, _HEAD_KEYS, 0)
    orientation_line = _ORIENTATION_LINE
    if lines[orientation_line].startswith(_MODE_PREFIX):
        mode = lines[orientation_line][len(_MODE_PREFIX) :].strip()
        if mode != _MODE_PARALLEL:
            raise ProjectionParseError(f"unknown mode {mode!r}: a projection renders only {_MODE_PARALLEL!r}")
        values["mode"] = mode
        orientation_line += 1
    start = _meta_start(lines)
    orientation = "\n".join(lines[orientation_line : start - 1]).strip()
    if not orientation:
        raise ProjectionParseError("orientation line must be non-empty")
    values["orientation"] = orientation
    values.update(_keyed(lines, _META_KEYS, start))
    return values


def _body_start(lines: list[str]) -> int:
    """Index just past the `# Wheypoint …` title.

    The orientation is the only unescaped multi-line text above the title and
    every body field renders prefixed or escaped, so a title-shaped line can
    come from the orientation only *before* the real one: the last such line
    is the title, and anything above it is text.
    """
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].startswith(_TITLE_PREFIX):
            return index + 1
    raise ProjectionParseError("missing the '# Wheypoint' title line")


def _section(lines: list[str], heading: str, *legacy: str) -> list[str]:
    body_start = _body_start(lines)
    start = -1
    for candidate in (heading, *legacy):
        if candidate in lines[body_start:]:
            start = lines.index(candidate, body_start) + 1
            break
    if start < 0:
        raise ProjectionParseError(f"missing {heading!r} section")
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return [line for line in lines[start:end] if line.strip()]


def _gating_entry_ids(lines: list[str]) -> list[str]:
    body = _section(lines, _GATES_HEADING, _LEGACY_GATES_HEADING)
    if body == [_NO_GATES]:
        return []
    if not body or any(not line.startswith("- ") for line in body):
        raise ProjectionParseError(
            f"{_GATES_HEADING!r} must list '- <entry-id>' lines or {_NO_GATES!r}"
        )
    # `- <id>` (legacy) or `- <id> — <summary>`: the id is the first token.
    return [line[2:].strip().split(" ", 1)[0] for line in body]


def _parse_dossier_markdown(body: list[str]) -> list[DecisionFork]:
    forks: list[dict[str, object]] = []
    options: list[dict[str, object]] = []
    for line in body:
        if line.startswith(_FORK_PREFIX):
            options = []
            forks.append({"fork": _unesc(line[len(_FORK_PREFIX) :]), "options": options, "prior_leaning": None})
        elif line.startswith(_LEANING_PREFIX) and forks:
            value = line[len(_LEANING_PREFIX) :]
            forks[-1]["prior_leaning"] = None if value == _NONE else _unesc(value)
        elif line.startswith(_OPTION_PREFIX) and forks:
            options.append({"option": _unesc(line[len(_OPTION_PREFIX) :]), "evidence": [], "breaks": ""})
        elif line.startswith(_EVIDENCE_PREFIX) and options:
            cast(list[str], options[-1]["evidence"]).append(_unesc(line[len(_EVIDENCE_PREFIX) :]))
        elif line.startswith(_BREAKS_PREFIX) and options:
            options[-1]["breaks"] = _unesc(line[len(_BREAKS_PREFIX) :])
        else:
            raise ProjectionParseError(f"unreadable dossier line {line!r}")
    try:
        return [
            DecisionFork(
                fork=cast(str, fork["fork"]),
                options=[
                    DossierOption(
                        option=cast(str, o["option"]),
                        evidence=cast(list[str], o["evidence"]),
                        breaks=cast(str, o["breaks"]),
                    )
                    for o in cast(list[dict[str, object]], fork["options"])
                ],
                prior_leaning=cast("str | None", fork["prior_leaning"]),
            )
            for fork in forks
        ]
    except ValueError as exc:
        raise ProjectionParseError(str(exc)) from exc


def _dossier(lines: list[str]) -> list[DecisionFork]:
    body = _section(lines, _DOSSIER_HEADING)
    if body == [_NONE]:
        return []
    if not body or body[0] != _FENCE:
        return _parse_dossier_markdown(body)
    if len(body) < 3 or body[-1] != "```":
        raise ProjectionParseError(f"{_DOSSIER_HEADING!r} must hold one json block")
    try:
        payload = cast(object, json.loads("\n".join(body[1:-1])))
    except ValueError as exc:
        raise ProjectionParseError(f"decision dossier is not JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ProjectionParseError("decision dossier must be a JSON array")
    forks = cast("list[object]", payload)
    try:
        return [records.structure(fork, DecisionFork) for fork in forks]
    except records.RecordError as exc:
        raise ProjectionParseError(str(exc)) from exc


def _parse_tasks(lines: list[str]) -> tuple[list[HandoffTask] | None, ParallelPlan | None]:
    """Read the `## Tasks` block back; absent means a single move."""
    if _TASKS_HEADING not in lines[_body_start(lines) :]:
        return None, None
    body = _section(lines, _TASKS_HEADING)
    plan_fields: dict[str, str] = {}
    tasks: list[dict[str, str]] = []
    target: dict[str, str] | None = None
    for line in body:
        if line == "parallel:":
            target = plan_fields
        elif line == "tasks:":
            target = None
        elif line.startswith("  - slug: "):
            tasks.append({"slug": _unesc(line[len("  - slug: ") :])})
            target = tasks[-1]
        elif line.startswith("    ") and target is not None and target is not plan_fields:
            key, _, value = line.strip().partition(": ")
            target[key] = _unesc(value)
        elif line.startswith("  ") and target is plan_fields:
            key, _, value = line.strip().partition(": ")
            plan_fields[key] = _unesc(value)
        else:
            raise ProjectionParseError(f"unreadable tasks line {line!r}")
    try:
        parallel = (
            ParallelPlan(
                isolation=plan_fields["isolation"],
                worktree_strategy=WorktreeStrategy(plan_fields["worktree_strategy"]),
                worktree_root=plan_fields.get("worktree_root"),
            )
            if plan_fields
            else None
        )
        handoff_tasks = [
            HandoffTask(
                slug=task["slug"],
                intent=task["intent"],
                repo=task["repo"],
                branch=task["branch"],
                branch_from=task["branch_from"],
                command=task["command"],
                worktree=task.get("worktree"),
            )
            for task in tasks
        ]
    except (KeyError, ValueError) as exc:
        raise ProjectionParseError(f"tasks block is incomplete: {exc}") from exc
    return handoff_tasks, parallel


def declared_status(text: str) -> str:
    """The word the document's own `status:` line claims.

    `parse` derives the status instead of reading it, which is what keeps an
    edited header harmless. Handing the written word back separately lets a
    caller hold the two against each other and report the lie rather than
    silently discard it.
    """
    field_value = _preamble(text.splitlines())["status"]
    # Only the name is read back. A forged `ok` that still carries the gated
    # reason must be reported as the lie it is, not rejected as unreadable.
    written_name, _, _ = field_value.partition(":")
    try:
        name, _ = parse_status_field(written_name, require_reason=False)
    except StatusError as exc:
        raise ProjectionParseError(str(exc)) from exc
    return name


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
    tasks, parallel = _parse_tasks(lines)
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
                tasks=tasks,
                parallel=parallel,
            ),
            gating_entry_ids=_gating_entry_ids(lines),
            decision_dossier=_dossier(lines),
            durability=durability,
        )
    except ValueError as exc:
        if isinstance(exc, ProjectionParseError):
            raise
        raise ProjectionParseError(str(exc)) from exc
