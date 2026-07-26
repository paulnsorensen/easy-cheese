#!/usr/bin/env python3
"""Lint a /wheypoint handoff note for contract violations.

A wheypoint note is the only thing standing between a session about to lose its
context and a fresh agent that must resume cold, yet nothing verifies the note.
The documented misfire is a `status: ok` note whose body actually holds a
blocker (skills/wheypoint/SKILL.md § status values). This is the deterministic
backstop: it runs a finished note through mechanical contract checks so the
misfire class, and the other structural breakages a cold reader would trip on,
cannot ship silently.

Checks (each emits one finding line, all accumulate — a run names every
problem, not just the first):

  - header parses: line 1 is `status:`, line 2 is `next:`, and a non-empty
    orientation line follows the keyed preamble.
  - status grammar: `ok`, `gated: <reason>`, or `halt: <reason>`.
  - next enum / list rules: a single value from the documented set, or an inline
    `next: [...]` list that carries `order:` (parallel|sequential) and names only
    read-only skills (briesearch|culture).
  - parallel requires tasks: `mode: parallel` needs a `tasks:` block and
    `next: tasks` (and the converse), and each task carries `command:` plus the
    isolation fields its `worktree_strategy` requires.
  - artifact paths exist: the `artifact:` value and every `.cheese/` path the
    body references resolve on disk, relative to the note's own repo root.
  - ok-vs-blockers contradiction: `status: ok` while the body's open-questions /
    blockers section carries un-negated blocker language (the documented misfire).

This wraps the note contract in skills/wheypoint/SKILL.md. It parses the note
directly rather than through shared/scripts/handoff.py:parse_handoff_slug: that
parser is the cook-family slug (status / next / artifact on lines 1-3), whereas a
wheypoint note is a superset — `status: gated:` is legal, `mode:` sits before
`artifact:`, and provenance / `parents:` lines follow — so the shared parser
rejects a valid wheypoint note outright. The line-oriented discipline here mirrors
it: the preamble is read from strict physical lines so a missing orientation can
never silently consume a body line.

Exit: 0 clean, 1 on any finding, 2 on a bad argument or an unreadable note.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from schema import non_empty_string

# The preamble keys a wheypoint note may carry, in any order after status/next.
# A line whose key is not one of these ends the preamble: it is the orientation.
PREAMBLE_KEYS = frozenset(
    {"status", "next", "mode", "artifact", "order", "session", "git", "created", "parents"}
)
# Single-value `next:` targets (skills/wheypoint/SKILL.md § next: values).
NEXT_SINGLE = frozenset(
    {"mold", "cook", "press", "age", "cure", "affinage", "briesearch", "culture", "hold", "tasks", "done"}
)
# The only skills an inline `next: [...]` list may name (§ next: list form).
READONLY_SKILLS = frozenset({"briesearch", "culture"})
ORDER_VALUES = frozenset({"parallel", "sequential"})
MODE_VALUES = frozenset({"single", "parallel"})
WORKTREE_STRATEGIES = frozenset({"existing", "create", "harness"})

_KEYED_LINE = re.compile(r"^([A-Za-z_]+):\s?(.*)$")
_TASKS_BLOCK = re.compile(r"(?m)^tasks:\s*$")
_HEADING = re.compile(r"^#{1,6}\s")
# A `.cheese/...` path token; stops at whitespace or a brace (brace-expansion
# shorthand like `.cheese/specs/{a,b}.md` is not a single real path).
_CHEESE_PATH = re.compile(r"\.cheese/[A-Za-z0-9._/-]+")
# A PR reference or URL in the artifact slot is not a filesystem path.
_ARTIFACT_NON_PATH = re.compile(r"^(none|PR#\d+|https?://)", re.IGNORECASE)

# Blocker language, stemmed so "block", "blocked", "blocker(s)", "blocking" all
# match. Kept short on purpose (spec § Risks): a wide net turns the misfire
# heuristic into noise. One source, shared by the plain and negated forms.
_BLOCKER_WORD = r"(?:block(?:s|ed|er|ers|ing)?|waiting[ -]on|unresolved|stuck)"
_BLOCKER = re.compile(rf"\b{_BLOCKER_WORD}\b", re.IGNORECASE)
# A negation shortly before a blocker word flips its meaning: "None blocking",
# "no blockers", "no known blockers", "no longer blocked". Up to two words may
# sit between the negation and the blocker word; a wider window would start
# swallowing genuine blockers ("no auth yet, still blocked on the call").
_NEGATED_BLOCKER = re.compile(
    rf"\b(?:no|none|not|never|nothing|zero|without)\b(?:\W+\w+){{0,2}}?\W+{_BLOCKER_WORD}\b",
    re.IGNORECASE,
)
# The lead of the open-questions / blockers section, anchored to the start of a
# line: an optional heading (`## `) or bold lead-in (`**`) marker, the label
# phrase, then a label terminator (`.`, `:`, `**`, or end of line). Line-anchored
# so a "blocker" mentioned mid-prose in an earlier section (e.g. State: "cleared
# the parser blocker") is never mistaken for the section itself — the
# false-negative that would otherwise ship the documented misfire.
_BLOCKERS_LEAD = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]+|\*\*[ \t]*)?"
    r"(?:open questions(?:[ \t]+and[ \t]+blockers?)?|blockers?)"
    r"[ \t]*(?=[.:*]|$)",
    re.IGNORECASE,
)
# Any /wheypoint § Document section lead, used to bound a blockers section's body
# at the next section (headings, bold lead-ins, or the documented plain labels).
_SECTION_LEAD = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]+|\*\*[ \t]*)?"
    r"(?:goal|state|key decisions|open questions|blockers?|artifacts|environment|suggested skills)"
    r"\b",
    re.IGNORECASE,
)


class Preamble:
    """The parsed top of a wheypoint note: keyed fields, orientation, and the
    two body slices the checks read (the YAML region that holds any tasks block,
    and the full post-orientation text)."""

    __slots__ = ("fields", "orientation", "yaml_region", "post", "errors")

    def __init__(
        self,
        fields: dict[str, str],
        orientation: str | None,
        yaml_region: str,
        post: str,
        errors: list[str],
    ) -> None:
        self.fields = fields
        self.orientation = orientation
        self.yaml_region = yaml_region
        self.post = post
        self.errors = errors


def parse_preamble(text: str) -> Preamble:
    """Read the keyed preamble from strict physical lines.

    Line 1 must be `status:` and line 2 `next:`; both are recorded as findings
    when misplaced rather than raising, so the rest of the note is still linted.
    After them, consecutive lines whose key is in ``PREAMBLE_KEYS`` are collected
    in any order; the first non-key, non-empty line is the orientation.
    """
    lines = text.splitlines()
    errors: list[str] = []
    if not lines or not lines[0].startswith("status:"):
        errors.append("header must start with a 'status:' line")
    if len(lines) < 2 or not lines[1].startswith("next:"):
        errors.append("second line must be a 'next:' line")

    fields: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = _KEYED_LINE.match(lines[index])
        if not match or match.group(1) not in PREAMBLE_KEYS:
            break
        key = match.group(1)
        fields.setdefault(key, match.group(2).strip())
        index += 1

    orientation: str | None = None
    if index < len(lines) and lines[index].strip() and not _HEADING.match(lines[index]):
        orientation = lines[index].strip()
        index += 1
    if orientation is None:
        errors.append("missing orientation line after the keyed preamble")

    post_lines = lines[index:]
    region: list[str] = []
    for line in post_lines:
        if _HEADING.match(line):
            break
        region.append(line)
    return Preamble(fields, orientation, "\n".join(region), "\n".join(post_lines), errors)


def _check_status(fields: dict[str, str]) -> list[str]:
    value = fields.get("status")
    if value is None:
        return []
    if value == "ok":
        return []
    for prefix in ("gated:", "halt:"):
        if value.startswith(prefix):
            if value[len(prefix):].strip():
                return []
            return [f"status: '{prefix}' requires a reason after it"]
    return [f"status must be 'ok', 'gated: <reason>', or 'halt: <reason>', got {value!r}"]


def _parse_next_list(value: str) -> list[str]:
    """Skill names from an inline `next: [briesearch "a", culture "b"]` value.
    Each item is `<skill> "<arg>"`; quoted arguments are stripped first so a comma
    inside an arg cannot be mis-read as an item separator."""
    inner = value.strip()[1:-1]
    without_args = re.sub(r'"[^"]*"', "", inner)
    return [item.split()[0].strip("/") for item in without_args.split(",") if item.strip()]


def _check_next(fields: dict[str, str]) -> list[str]:
    value = fields.get("next")
    if value is None:
        return []
    if value.startswith("["):
        findings: list[str] = []
        if not value.endswith("]"):
            return ["next: list is not closed with ']'"]
        skills = _parse_next_list(value)
        if not skills:
            findings.append("next: list is empty")
        for skill in skills:
            if skill not in READONLY_SKILLS:
                findings.append(
                    f"next: list may only name read-only skills (briesearch|culture), got {skill!r}"
                )
        order = fields.get("order")
        if order is None:
            findings.append("next: list form requires an 'order:' line (parallel|sequential)")
        elif order not in ORDER_VALUES:
            findings.append(f"order: must be parallel|sequential, got {order!r}")
        return findings
    if value not in NEXT_SINGLE:
        return [f"next: must be one of {'|'.join(sorted(NEXT_SINGLE))} or a list, got {value!r}"]
    return []


def _check_mode(fields: dict[str, str]) -> list[str]:
    value = fields.get("mode")
    if value is not None and value not in MODE_VALUES:
        return [f"mode: must be single|parallel, got {value!r}"]
    return []


def _check_task_fields(yaml_region: str) -> tuple[list[str], list[str]]:
    """Structurally validate the parallel/tasks block, returning
    ``(findings, advisories)``. Needs PyYAML; when it is absent the check
    degrades to one loud advisory rather than failing (the tasks-block
    *presence* check in ``_check_parallel`` is PyYAML-free and still runs)."""
    try:
        import yaml
    except ImportError:
        return [], [
            "PyYAML unavailable: per-task fields (command/branch/branch_from) not "
            "structurally validated"
        ]
    try:
        data = yaml.safe_load(yaml_region)
    except yaml.YAMLError as exc:
        return [f"tasks block is not valid YAML: {exc}"], []
    if not isinstance(data, dict):
        return ["tasks block did not parse as a mapping"], []

    findings: list[str] = []
    parallel = data.get("parallel")
    strategy = parallel.get("worktree_strategy") if isinstance(parallel, dict) else None
    if strategy is not None and strategy not in WORKTREE_STRATEGIES:
        findings.append(
            f"parallel.worktree_strategy must be existing|create|harness, got {strategy!r}"
        )
    if strategy == "create" and not (isinstance(parallel, dict) and parallel.get("worktree_root")):
        findings.append("parallel.worktree_strategy 'create' requires parallel.worktree_root")

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        findings.append("tasks: must be a non-empty list")
        return findings, []
    required = ["command", "branch", "branch_from"]
    if strategy == "existing":
        required.append("worktree")
    for offset, task in enumerate(tasks, start=1):
        where = f"tasks[{offset}]"
        if not isinstance(task, dict):
            findings.append(f"{where} must be a mapping")
            continue
        for key in required:
            findings.extend(non_empty_string(task, key, where))
    return findings, []


def _check_parallel(fields: dict[str, str], preamble: Preamble) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    advisories: list[str] = []
    mode = fields.get("mode")
    next_value = fields.get("next", "")
    has_tasks = _TASKS_BLOCK.search(preamble.post) is not None
    if mode == "parallel":
        if not has_tasks:
            findings.append("mode: parallel requires a 'tasks:' block")
        if next_value != "tasks":
            findings.append("mode: parallel requires 'next: tasks'")
    if next_value == "tasks" and mode != "parallel":
        findings.append("next: tasks requires 'mode: parallel'")
    if mode == "parallel" and has_tasks:
        task_findings, task_advisories = _check_task_fields(preamble.yaml_region)
        findings.extend(task_findings)
        advisories.extend(task_advisories)
    return findings, advisories


def _repo_root_for_note(note_path: Path) -> Path:
    """The repo root a note's relative paths resolve against: the parent of the
    `.cheese/` dir the note lives under, else the note's own directory."""
    resolved = note_path.resolve()
    for parent in resolved.parents:
        if parent.name == ".cheese":
            return parent.parent
    return resolved.parent


def _path_exists(reference: str, repo_root: Path) -> bool:
    candidate = Path(reference)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.exists()


def _check_artifact_paths(fields: dict[str, str], preamble: Preamble, repo_root: Path) -> list[str]:
    findings: list[str] = []
    artifact = fields.get("artifact", "").strip()
    if artifact and not _ARTIFACT_NON_PATH.match(artifact):
        if not _path_exists(artifact, repo_root):
            findings.append(f"artifact path does not exist: {artifact}")

    seen: set[str] = set()
    for match in _CHEESE_PATH.finditer(preamble.post):
        reference = match.group(0).rstrip("./,);:`")
        if reference in seen:
            continue
        seen.add(reference)
        if not _path_exists(reference, repo_root):
            findings.append(f"referenced path does not exist: {reference}")
    return findings


def _blockers_sections(post: str) -> list[str]:
    """Every open-questions / blockers section body in the note.

    Each section is located by its line-anchored lead and bounded by the next
    section lead (or end of text); the lead line's label is excluded so its own
    word 'blockers' never trips the scan. Every candidate section is returned,
    not just the first — a decoy 'blocker' word earlier in the body must not
    shadow the real section further down."""
    sections: list[str] = []
    for lead in _BLOCKERS_LEAD.finditer(post):
        rest = post[lead.end():]
        nxt = _SECTION_LEAD.search(rest)
        sections.append(rest[: nxt.start()] if nxt else rest)
    return sections


def _check_ok_vs_blockers(fields: dict[str, str], preamble: Preamble) -> list[str]:
    if fields.get("status") != "ok":
        return []
    for section in _blockers_sections(preamble.post):
        negated_spans = [m.span() for m in _NEGATED_BLOCKER.finditer(section)]
        for match in _BLOCKER.finditer(section):
            if any(start <= match.start() < end for start, end in negated_spans):
                continue
            return [
                "status: ok but the open-questions/blockers section contains blocker "
                "language; use 'gated:' or resolve the blocker"
            ]
    return []


def lint_note(text: str, repo_root: Path) -> tuple[list[str], list[str]]:
    """Return ``(findings, advisories)`` for a wheypoint note's text. Findings
    are contract violations that drive a non-zero exit; advisories are loud
    degrade notes (e.g. PyYAML missing) that print but do not fail the note."""
    preamble = parse_preamble(text)
    findings = list(preamble.errors)
    findings.extend(_check_status(preamble.fields))
    findings.extend(_check_next(preamble.fields))
    findings.extend(_check_mode(preamble.fields))
    parallel_findings, advisories = _check_parallel(preamble.fields, preamble)
    findings.extend(parallel_findings)
    findings.extend(_check_artifact_paths(preamble.fields, preamble, repo_root))
    findings.extend(_check_ok_vs_blockers(preamble.fields, preamble))
    return findings, advisories


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("note", help="Path to the wheypoint note (.cheese/notes/<slug>.md).")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON to stdout.")
    args = parser.parse_args(argv)

    note_path = Path(args.note)
    try:
        text = note_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.note}: {exc}", file=sys.stderr)
        return 2

    findings, advisories = lint_note(text, _repo_root_for_note(note_path))

    if args.json:
        print(
            json.dumps(
                {"note": args.note, "ok": not findings, "findings": findings, "advisories": advisories},
                indent=2,
            )
        )
        return 1 if findings else 0

    for advisory in advisories:
        print(f"{args.note}: advisory: {advisory}", file=sys.stderr)
    for finding in findings:
        print(f"{args.note}: {finding}", file=sys.stderr)
    if findings:
        print(f"\n{len(findings)} finding(s) in {args.note}", file=sys.stderr)
        return 1
    print(f"lint ok: {args.note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
