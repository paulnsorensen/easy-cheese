"""The generated Markdown view of a record: render, parse, and pin.

The document opens with the shared handoff preamble -- `status:`, `next:`,
`artifact:`, then the orientation -- so `parse_handoff_slug()` reads a
projection like any other handoff. The gating entries and the body follow,
and the work and revision identifiers close the file.

`status:` is written, never read. Parsing derives the status from the gating
entry list, exactly as the schema types do. Editing the word `gated` to `ok`
changes nothing.

Projections written at schema 4 or older opened with a pins block that held a
`projection_digest`; `parse` still reads them and ignores that digest.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
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
from easy_cheese_schemas.contracts import DirectiveScope
from easy_cheese_schemas.handback_status import (
    MAX_REASON_LENGTH,
    render_status_field,
)

from easy_cheese.shared import git_utils

from . import canonical, records
from .ref_grammar import Scheme, locator_path

# The shared handoff preamble: three keyed lines, then the orientation.
_HEAD_KEYS = ("status", "next", "artifact")
_ORIENTATION_LINE = len(_HEAD_KEYS)
# The identifier block that closes a projection.
_META_KEYS = (
    "work_id",
    "revision_id",
    "record_digest",
    "durability",
    "schema_version",
)
# Schema 4 and older opened with the pins and carried a projection digest.
_LEGACY_META_KEYS = (
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
_TITLE = "# Wheypoint handoff"
_IDENTIFIERS_HEADING = "## Identifiers"
_GATES_HEADING = "## Gates"
_LEGACY_GATES_HEADING = "## Gating entries"
_OPEN_HEADING = "## Open entries"
_DECISIONS_HEADING = "## Decisions"
_DIRECTIVES_HEADING = "## Directives"
_OPERATOR_HEADING = "## Operator preferences"
_NOTES_HEADING = "## Notes"
_SUPERSEDED_HEADING = "## Superseded"
_LOCAL_HEADING = "## Local references"
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_TOKEN_OPEN = "`'\"([<"
_TOKEN_CLOSE = "`'\")]>,;.:"
_CONTEXT_HEADING = "## Context"
_ARTIFACTS_HEADING = "## Artifacts"
_LINKS_HEADING = "## Links"
_TASKS_HEADING = "## Tasks"
_NONE = "none"
_DIGEST_LINE_RE = re.compile(r"^projection_digest:.*$", re.MULTILINE)


class ProjectionParseError(ValueError):
    """Raised when a projection document cannot be read as one."""


def projection_digest_of_text(text: str) -> str:
    """The digest a schema-4-or-older projection's `projection_digest:` line carried."""
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


_ESCAPES = {
    "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\v": "\\v", "\f": "\\f",
    "\x1c": "\\u001c", "\x1d": "\\u001d", "\x1e": "\\u001e",
    "\u0085": "\\u0085", "\u2028": "\\u2028", "\u2029": "\\u2029",
}
_UNESCAPES = {escaped[1:]: char for char, escaped in _ESCAPES.items()} | {"t": "\t"}


def escape(text: str, *, tab: bool = False) -> str:
    """Escape every line separator so each field stays on one physical line."""
    for char, escaped in _ESCAPES.items():
        text = text.replace(char, escaped)
    return text.replace("\t", "\\t") if tab else text


def unescape(text: str) -> str:
    return re.sub(r"\\(u[0-9a-f]{4}|.)", lambda match: _UNESCAPES.get(match[1], match[1]), text)


# One table each drives both the render order in `_tasks` and the
# required-field check in `_parse_tasks`, so a new `HandoffTask`/`ParallelPlan`
# field needs one edit here instead of two hand-maintained lists.
_PLAN_FIELDS: tuple[tuple[str, bool], ...] = (
    ("isolation", True),
    ("worktree_strategy", True),
    ("worktree_root", False),
)
_TASK_FIELDS: tuple[tuple[str, bool], ...] = (
    ("intent", True),
    ("repo", True),
    ("worktree", False),
    ("branch", True),
    ("branch_from", True),
    ("command", True),
)


def _field_text(value: str | WorktreeStrategy) -> str:
    """Render one table-driven field value as its escaped line text."""
    return escape(value.value if isinstance(value, WorktreeStrategy) else value)


def _entry_line(entry: ProtectedEntry) -> str:
    line = f"- {entry.entry_id} ({entry.kind.value}) — {escape(entry.summary)}"
    return f"{line} (when: {escape(entry.when)})" if entry.when else line


_UNASSIGNED = "unassigned"


def _open_lines(open_entries: list[ProtectedEntry]) -> list[str]:
    """Open questions, one subheading per owner once any question has one.

    Owners match case-insensitively and show as first spelled; unowned
    questions go last under `unassigned`. With no owner anywhere the list stays
    flat, so a record written before owners existed renders as it did.
    """
    if not any(e.owner for e in open_entries):
        return [_entry_line(e) for e in open_entries] or [_NONE]
    groups: dict[str, tuple[str, list[ProtectedEntry]]] = {}
    for entry in open_entries:
        key = (entry.owner or _UNASSIGNED).lower()
        groups.setdefault(key, (entry.owner or _UNASSIGNED, []))[1].append(entry)
    ordered = sorted(groups, key=lambda key: (key == _UNASSIGNED, key))
    lines: list[str] = []
    for key in ordered:
        name, members = groups[key]
        lines += [f"### {escape(name)}", "", *(_entry_line(e) for e in members), ""]
    return lines[:-1]


def _quoted(entries: list[ProtectedEntry]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        lines.append(_entry_line(entry))
        if entry.quote:
            lines.extend(f"  > {part}" for part in entry.quote.splitlines() or [""])
    return lines


def _drift_marker(record: WheypointRecord) -> list[str]:
    """One line saying the notes predate the latest decision change, else nothing.

    A record without stamps renders no marker: it cannot say which is newer.
    """
    decided = record.decisions_revision_number
    written = record.notes_revision_number
    if not record.notes or decided is None or (written is not None and decided <= written):
        return []
    notes_at = "unstamped" if written is None else f"revision {written}"
    return [
        f"> notes may be stale: decisions changed at revision {decided}, "
        + f"notes written at {notes_at}"
    ]


def _superseded(record: WheypointRecord) -> list[str]:
    """The `## Superseded` section, or nothing when no entry was superseded."""
    moved = [
        e for e in records.entries(record)
        if e.state is EntryState.SUPERSEDED and e.superseded_by
    ]
    if not moved:
        return []
    return ["", _SUPERSEDED_HEADING, "", *(f"- {e.entry_id} -> {e.superseded_by}" for e in moved)]


def _checkout() -> Path | None:
    """The Git worktree root of the working directory, or None outside one."""
    try:
        top = git_utils.run_git(["rev-parse", "--show-toplevel"], timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(top.stdout.strip()) if top.returncode == 0 and top.stdout.strip() else None


def _local_references(record: WheypointRecord) -> list[str]:
    """The `## Local references` section, or nothing when no reference is local.

    A reference is local when it needs the author's machine: an `xdg:` ref, an
    absolute path outside the checkout, or a repository path Git ignores.
    Outside a checkout only the first two classify.
    """
    candidates: list[tuple[str, bool]] = []
    for link in record.artifact_links:
        ref = link.ref
        candidates.append((link.path if ref is None or ref.startswith("repo:") else ref, False))
    candidates += [(edge.to, False) for edge in record.edges]
    for item in record.working_context:
        for word in item.split():
            token = word.strip(_TOKEN_OPEN).rstrip(_TOKEN_CLOSE)
            if "/" in token or "." in token:
                candidates.append((token, True))
    checkout = _checkout() if candidates else None
    found: list[str] = []
    for text, must_exist in candidates:
        if text not in found and _is_local(text, checkout, must_exist=must_exist):
            found.append(text)
    if not found:
        return []
    return ["", _LOCAL_HEADING, "", *(f"- {escape(text)}" for text in found)]


def _is_local(text: str, checkout: Path | None, *, must_exist: bool) -> bool:
    if text.lower().startswith(f"{Scheme.XDG.value}:"):
        return True
    path = locator_path(text)
    path = path.removeprefix(f"{Scheme.REPO.value}:")
    try:
        if path.startswith("/"):
            if checkout is None:
                return True
            absolute = Path(path).resolve()
            root = checkout.resolve()
            if not absolute.is_relative_to(root):
                return True
            path = absolute.relative_to(root).as_posix()
        if checkout is None or _SCHEME_RE.match(path) or path in {"", "."}:
            return False
        if must_exist and not (checkout / path).exists():
            return False
        ignored = git_utils.run_git(
            ["check-ignore", "-q", "--", path], cwd=checkout, timeout=5
        )
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False
    return ignored.returncode == 0


def _body(record: WheypointRecord) -> list[str]:
    """The human sections: everything the record holds that the pins do not."""
    lines: list[str] = []
    active = [e for e in records.entries(record) if e.state is EntryState.ACTIVE]
    open_entries = [
        e for e in active
        if e.kind is EntryKind.QUESTION and not e.blocks_continuation
    ]
    lines += [_OPEN_HEADING, ""]
    lines += _open_lines(open_entries)
    lines += ["", _DECISIONS_HEADING, ""]
    decisions = [e for e in active if e.kind is EntryKind.DECISION]
    for entry in decisions:
        lines.append(_entry_line(entry))
        if entry.rationale:
            lines.append(f"  rationale: {escape(entry.rationale)}")
    if not decisions:
        lines.append(_NONE)
    lines += ["", _DIRECTIVES_HEADING, ""]
    directives = [
        e for e in active
        if e.kind is EntryKind.DIRECTIVE and e.scope is DirectiveScope.WORK
    ]
    lines += _quoted(directives) or [_NONE]
    operator = [
        e for e in active
        if e.kind is EntryKind.DIRECTIVE and e.scope is DirectiveScope.OPERATOR
    ]
    if operator:
        lines += ["", _OPERATOR_HEADING, "", *_quoted(operator)]
    lines += ["", _NOTES_HEADING, "", *_drift_marker(record)]
    # A notes line that looks like a heading would split the parsed sections.
    lines += (
        [("\\" + line) if line.startswith("#") else line for line in record.notes.splitlines()]
        or [""]
    ) if record.notes else [_NONE]
    lines += ["", _CONTEXT_HEADING, ""]
    lines += [f"- {escape(item)}" for item in record.working_context] or [_NONE]
    lines += ["", _ARTIFACTS_HEADING, ""]
    for link in record.artifact_links:
        detail = [
            f"digest: {link.digest}" if link.digest else "",
            f"revision: {link.revision_id}" if link.revision_id else "",
            f"covers: {', '.join(link.covers_entry_ids)}" if link.covers_entry_ids else "",
        ]
        detail_text = ", ".join(part for part in detail if part)
        ref = records.effective_ref(link)
        shown = link.path if ref.partition(":")[0] == Scheme.REPO.value else ref
        lines.append(f"- {escape(shown)}" + (f" ({detail_text})" if detail_text else ""))
    if not record.artifact_links:
        lines.append(_NONE)
    lines += ["", _LINKS_HEADING, ""]
    for edge in record.edges:
        pin = f" @{edge.revision_id}" if edge.revision_id else ""
        lines.append(f"- {edge.kind.value} {escape(edge.to)}{pin}")
        if edge.rationale:
            lines.append(f"  rationale: {escape(edge.rationale)}")
    if not record.edges:
        lines.append(_NONE)
    return lines + _superseded(record) + _local_references(record)


def _tasks(action: NextAction) -> list[str]:
    """The `parallel:` and `tasks:` blocks in the shape `parallel-handoffs.md` documents."""
    if not action.tasks:
        return []
    lines = ["", _TASKS_HEADING, ""]
    if action.parallel is not None:
        lines.append("parallel:")
        for key, _required in _PLAN_FIELDS:
            plan_value = cast("str | WorktreeStrategy | None", getattr(action.parallel, key))
            if plan_value is not None:
                lines.append(f"  {key}: {_field_text(plan_value)}")
    lines.append("tasks:")
    for task in action.tasks:
        lines.append(f"  - slug: {escape(task.slug)}")
        for key, _required in _TASK_FIELDS:
            task_value = cast("str | None", getattr(task, key))
            if task_value is not None:
                lines.append(f"    {key}: {_field_text(task_value)}")
    return lines


def render(projection: WheypointProjection, record: WheypointRecord) -> str:
    """Render the projection with the human body sections from `record`.

    The gates, the tasks and the identifiers come from the
    projection and are parsed back; the body is derived from the record and is
    never parsed back. The identifiers close the file so the content leads.
    """
    action = projection.next_action
    lines = [
        f"status: {status_field(projection)}",
        f"next: {action.move.value}",
    ]
    if action.tasks:
        lines.append(f"{_MODE_PREFIX}{_MODE_PARALLEL}")
    lines += [f"artifact: {action.artifact or ''}", action.orientation]
    lines += [
        "",
        _TITLE,
        "",
        _GATES_HEADING,
        "",
    ]
    summaries = {e.entry_id: e.summary for e in records.entries(record)}
    if projection.gating_entry_ids:
        for entry_id in projection.gating_entry_ids:
            summary = summaries.get(entry_id)
            lines.append(f"- {entry_id}" + (f" — {escape(summary)}" if summary else ""))
    else:
        lines.append(_NONE)
    lines += ["", *_body(record)]
    lines += _tasks(action)
    lines += [
        "",
        _IDENTIFIERS_HEADING,
        "",
        f"work_id: {projection.work_id}",
        f"revision_id: {projection.revision_id}",
        f"record_digest: {projection.record_digest}",
        f"durability: {projection.durability.value}",
        f"schema_version: {projection.schema_version}",
        "",
    ]
    return "\n".join(lines)


def build_projection(
    record: WheypointRecord, *, durability: Durability
) -> tuple[WheypointProjection, str]:
    """Derive the projection for `record` and render it, in one step."""
    projection = WheypointProjection(
        schema_version=record.schema_version,
        work_id=record.work_id,
        revision_id=record.revision_id,
        record_digest=records.record_digest(record),
        next_action=record.next_action,
        gating_entry_ids=list(record.gating_entry_ids),
        durability=durability,
    )
    return projection, render(projection, record)


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


def _meta_start(lines: list[str], body_start: int) -> int:
    """The index of the first metadata line, after the orientation block.

    The orientation may hold more than one physical line, so the block ends at
    the blank line that separates it from the pins rather than at a fixed
    offset.
    """
    # The pins are the keyed block directly above the `# Wheypoint` title: a
    # look-alike block inside the orientation text is text, not pins.
    title = body_start - 1
    start = title - 1 - len(_LEGACY_META_KEYS)
    if start < _META_LINE or lines[title - 1].strip():
        raise ProjectionParseError("the pins must sit directly above the title, ending in a blank line")
    if not lines[start].startswith(f"{_LEGACY_META_KEYS[0]}: "):
        raise ProjectionParseError(f"missing {_LEGACY_META_KEYS[0]!r} line")
    if lines[start - 1].strip():
        raise ProjectionParseError("the orientation must end with a blank line")
    return start


def _identifiers_start(lines: list[str], body_start: int) -> int | None:
    """The index of the closing identifiers heading, or None in a legacy layout."""
    for index in range(len(lines) - 1, body_start - 1, -1):
        if lines[index] == _IDENTIFIERS_HEADING:
            return index
    return None


def _preamble(lines: list[str], body_start: int) -> dict[str, str]:
    if len(lines) < _MIN_LINES:
        raise ProjectionParseError(
            f"projection needs {_MIN_LINES} preamble lines, got {len(lines)}"
        )
    values = _keyed(lines, _HEAD_KEYS[:2], 0)
    artifact_line = 2
    if lines[artifact_line].startswith(_MODE_PREFIX):
        mode = lines[artifact_line][len(_MODE_PREFIX) :].strip()
        if mode != _MODE_PARALLEL:
            raise ProjectionParseError(f"unknown mode {mode!r}: a projection renders only {_MODE_PARALLEL!r}")
        values["mode"] = mode
        artifact_line += 1
    values.update(_keyed(lines, ("artifact",), artifact_line))
    orientation_line = artifact_line + 1
    identifiers = _identifiers_start(lines, body_start)
    orientation_start = orientation_line
    if identifiers is None:
        # Schema 4 and older: the pins sit above the title.
        keys = _LEGACY_META_KEYS
        try:
            start = _meta_start(lines, body_start)
            orientation_end = start - 1
        except ProjectionParseError:
            # Schema 1 stored the pins right after the artifact line, with the
            # orientation below them.
            if not lines[orientation_line].startswith(f"{keys[0]}: "):
                raise
            start = orientation_line
            orientation_start = start + len(keys)
            orientation_end = body_start - 2
            if orientation_end < orientation_start or lines[orientation_end].strip():
                raise ProjectionParseError("the orientation must end with a blank line") from None
    else:
        start = identifiers + 2
        orientation_end = body_start - 2
        keys = _META_KEYS
        if orientation_end < orientation_line or lines[orientation_end].strip():
            raise ProjectionParseError("the orientation must end with a blank line")
        if lines[identifiers + 1].strip():
            raise ProjectionParseError(f"{_IDENTIFIERS_HEADING!r} must be followed by a blank line")
    orientation = "\n".join(lines[orientation_start:orientation_end]).strip()
    if not orientation:
        raise ProjectionParseError("orientation line must be non-empty")
    values["orientation"] = orientation
    values.update(_keyed(lines, keys, start))
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


def _section(lines: list[str], body_start: int, heading: str, *legacy: str) -> list[str]:
    start = -1
    for candidate in (heading, *legacy):
        try:
            start = lines.index(candidate, body_start) + 1
            break
        except ValueError:
            continue
    if start < 0:
        raise ProjectionParseError(f"missing {heading!r} section")
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return [line for line in lines[start:end] if line.strip()]


def _gating_entry_ids(lines: list[str], body_start: int) -> list[str]:
    body = _section(lines, body_start, _GATES_HEADING, _LEGACY_GATES_HEADING)
    if body == [_NONE]:
        return []
    if not body or any(not line.startswith("- ") for line in body):
        raise ProjectionParseError(
            f"{_GATES_HEADING!r} must list '- <entry-id>' lines or {_NONE!r}"
        )
    # `- <id>` (legacy) or `- <id> — <summary>`: the id is the first token.
    return [line[2:].strip().split(" ", 1)[0] for line in body]


def _require_fields(fields: dict[str, str], table: tuple[tuple[str, bool], ...]) -> None:
    """Raise if a required key from a `_PLAN_FIELDS`/`_TASK_FIELDS` table is missing."""
    for key, required in table:
        if required and key not in fields:
            raise KeyError(key)


def _parse_tasks(
    lines: list[str], body_start: int
) -> tuple[list[HandoffTask] | None, ParallelPlan | None]:
    """Read the `## Tasks` block back; absent means a single move."""
    if _TASKS_HEADING not in lines[body_start:]:
        return None, None
    body = _section(lines, body_start, _TASKS_HEADING)
    plan_fields: dict[str, str] = {}
    tasks: list[dict[str, str]] = []
    target: dict[str, str] | None = None
    for line in body:
        if line == "parallel:":
            target = plan_fields
        elif line == "tasks:":
            target = None
        elif line.startswith("  - slug: "):
            tasks.append({"slug": unescape(line[len("  - slug: ") :])})
            target = tasks[-1]
        elif target is not None and line.startswith("  " if target is plan_fields else "    "):
            indent = 2 if target is plan_fields else 4
            key, _, value = line[indent:].partition(": ")
            target[key] = unescape(value)
        else:
            raise ProjectionParseError(f"unreadable tasks line {line!r}")
    try:
        parallel = None
        if plan_fields:
            _require_fields(plan_fields, _PLAN_FIELDS)
            parallel = ParallelPlan(
                isolation=plan_fields["isolation"],
                worktree_strategy=WorktreeStrategy(plan_fields["worktree_strategy"]),
                worktree_root=plan_fields.get("worktree_root"),
            )
        handoff_tasks: list[HandoffTask] = []
        for task in tasks:
            _require_fields(task, _TASK_FIELDS)
            handoff_tasks.append(
                HandoffTask(
                    slug=task["slug"],
                    intent=task["intent"],
                    repo=task["repo"],
                    worktree=task.get("worktree"),
                    branch=task["branch"],
                    branch_from=task["branch_from"],
                    command=task["command"],
                )
            )
    except (KeyError, ValueError) as exc:
        raise ProjectionParseError(f"tasks block is incomplete: {exc}") from exc
    return handoff_tasks, parallel


def parse(text: str) -> WheypointProjection:
    """Read a projection document back. The written `status:` is ignored."""
    lines = text.splitlines()
    body_start = _body_start(lines)
    values = _preamble(lines, body_start)
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
    tasks, parallel = _parse_tasks(lines, body_start)
    try:
        return WheypointProjection(
            schema_version=int(values["schema_version"]),
            work_id=values["work_id"],
            revision_id=values["revision_id"],
            record_digest=values["record_digest"],
            next_action=NextAction(
                move=move,
                orientation=values["orientation"],
                artifact=values["artifact"] or None,
                tasks=tasks,
                parallel=parallel,
            ),
            gating_entry_ids=_gating_entry_ids(lines, body_start),
            durability=durability,
        )
    except ValueError as exc:
        if isinstance(exc, ProjectionParseError):
            raise
        raise ProjectionParseError(str(exc)) from exc
