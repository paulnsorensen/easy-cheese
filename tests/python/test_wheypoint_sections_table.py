
"""Doc-lint guard for wheypoint's state→required-body-sections table (question-transport-policy, curd 3).

Supply-side fix: `/wheypoint` used to compress a `status: gated:` note down to
a one-line decision, discarding the design-fork weighing built up earlier in
the session — so a resumed session had nothing to discuss from. The fix adds
a state→required-Document-sections table beside `## Suggested skills` whose
`status: gated:` row mandates a decision dossier per open fork (options /
evidence `file:line` / what-each-breaks / prior leanings), and states that this
mandate overrides the "just enough state" compression rule for gated notes.

Each assertion pins the *semantic relationship* within a bounded span, not a
vacuous co-occurrence of isolated substrings anywhere in the file — the same
discipline `test_culture_convergence.py` and `test_when_to_structure_policy.py`
use.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WHEYPOINT_SKILL = REPO_ROOT / "skills" / "wheypoint" / "SKILL.md"


def _read() -> str:
    return WHEYPOINT_SKILL.read_text(encoding="utf-8")

# --- Table existence + gated→dossier row --------------------------------
# The table maps a `state` column to a `required Document sections` column,
# and its gated row points at a `## Decision dossier` section.
STATE_TO_SECTIONS_TABLE = re.compile(
    r"\bstate\b[^|\n]{0,20}\|[^|\n]{0,10}\brequired\b[^|\n]{0,10}\bDocument\b[^|\n]{0,10}\bsections\b",
    re.I,
)
GATED_ROW_POINTS_AT_DOSSIER = re.compile(
    r"`?status:\s*gated:`?[^|\n]{0,20}\|[^\n]{0,40}##\s*Decision dossier",
    re.I,
)

# --- Dossier row requires all four elements ----------------------------------
DOSSIER_HAS_OPTIONS = re.compile(r"##\s*Decision dossier\b[^\n]{0,200}\boptions\b", re.I)
DOSSIER_HAS_EVIDENCE_FILE_LINE = re.compile(
    r"##\s*Decision dossier\b[^\n]{0,200}\bevidence\b[^\n]{0,40}`file:line`", re.I
)
DOSSIER_HAS_WHAT_BREAKS = re.compile(
    r"##\s*Decision dossier\b[^\n]{0,200}\bwhat[- ]each[- ]breaks\b", re.I
)
DOSSIER_HAS_PRIOR_LEANINGS = re.compile(
    r"##\s*Decision dossier\b[^\n]{0,200}\bprior leanings\b", re.I
)

# --- Per-open-fork framing ----------------------------------------------------
DOSSIER_PER_OPEN_FORK = re.compile(
    r"##\s*Decision dossier\b[^\n]{0,60}\bper open fork\b", re.I
)

# --- Remaining state rows -----------------------------------------------------
CULTURE_ROW = re.compile(
    r"`?next:\s*culture`?[^|\n]{0,20}\|[^\n]{0,80}\bagenda\b[^\n]{0,40}\bopen[- ]thread\b[^\n]{0,20}\bstate\b",
    re.I,
)
CURE_ROW = re.compile(
    r"`?next:\s*cure`?[^|\n]{0,20}\|[^\n]{0,80}\bfindings\b[^\n]{0,20}\bartifact\b",
    re.I,
)
COOK_PRESS_AGE_ROW = re.compile(
    r"`?next:\s*cook`?[^|\n]{0,80}`?press`?[^|\n]{0,80}`?age`?[^|\n]{0,20}\|[^\n]{0,80}\bspec\b[^\n]{0,10}/[^\n]{0,10}\bslug\b[^\n]{0,20}\bpointers\b",
    re.I,
)
HOLD_DONE_ROW = re.compile(
    r"`?next:\s*hold`?[^|\n]{0,80}`?done`?[^|\n]{0,20}\|[^\n]{0,40}\borientation only\b",
    re.I,
)

# --- Override of the "just enough state" compression rule -------------------
# The compression rule lives in the skill's own opening line ("captures just
# enough state for a cold reader to resume"); the new table must say the
# dossier mandate overrides it for gated notes.
OVERRIDES_COMPRESSION_RULE = re.compile(
    r"\boverrides?\b[^.\n]{0,60}\bjust enough state\b[^.\n]{0,60}\bcompression\b[^.\n]{0,20}\bgated\b",
    re.I,
)

# --- Adjacency to § Suggested skills ---------------------------------------
# The table's placement is part of the contract: it must sit immediately
# after "## Suggested skills" with no other heading wedged between them.
HEADING_LINE = re.compile(r"^## .*$", re.M)


def _headings_between(body: str, start_name: str, end_name: str) -> list[str]:
    start = re.search(r"^## " + re.escape(start_name) + r"\s*$", body, re.M)
    end = re.search(r"^## " + re.escape(end_name) + r"\s*$", body, re.M)
    assert start and end, f"heading not found: {start_name!r} or {end_name!r}"
    return HEADING_LINE.findall(body[start.start():end.start()])


def test_wheypoint_skill_exists() -> None:
    assert WHEYPOINT_SKILL.exists(), f"wheypoint SKILL.md moved or renamed: {WHEYPOINT_SKILL}"


def test_state_to_sections_table_present_with_gated_dossier_row() -> None:
    body = _read()
    missing = []
    if not STATE_TO_SECTIONS_TABLE.search(body):
        missing.append("a state -> required Document sections table")
    if not GATED_ROW_POINTS_AT_DOSSIER.search(body):
        missing.append("the `status: gated:` row pointing at a `## Decision dossier` section")
    assert not missing, (
        "question-transport-policy curd 3 table absent:\n  - " + "\n  - ".join(missing)
    )


def test_decision_dossier_requires_all_four_elements() -> None:
    body = _read()
    missing = []
    if not DOSSIER_PER_OPEN_FORK.search(body):
        missing.append("dossier is scoped per open fork")
    if not DOSSIER_HAS_OPTIONS.search(body):
        missing.append("options")
    if not DOSSIER_HAS_EVIDENCE_FILE_LINE.search(body):
        missing.append("evidence `file:line`")
    if not DOSSIER_HAS_WHAT_BREAKS.search(body):
        missing.append("what-each-breaks")
    if not DOSSIER_HAS_PRIOR_LEANINGS.search(body):
        missing.append("prior leanings")
    assert not missing, (
        "## Decision dossier must spell out all four elements per open fork:\n  - "
        + "\n  - ".join(missing)
    )


def test_remaining_state_rows_present() -> None:
    body = _read()
    missing = []
    if not CULTURE_ROW.search(body):
        missing.append("`next: culture` -> agenda + open-thread state")
    if not CURE_ROW.search(body):
        missing.append("`next: cure` -> findings artifact ref")
    if not COOK_PRESS_AGE_ROW.search(body):
        missing.append("`next: cook`/`press`/`age` -> spec/slug pointers")
    if not HOLD_DONE_ROW.search(body):
        missing.append("`next: hold`/`done` -> orientation only")
    assert not missing, (
        "state->sections table missing rows:\n  - " + "\n  - ".join(missing)
    )


def test_dossier_mandate_overrides_compression_rule() -> None:
    body = _read()
    assert OVERRIDES_COMPRESSION_RULE.search(body), (
        "the table must state explicitly that the gated dossier requirement "
        "overrides the \"just enough state\" compression rule for gated notes"
    )


def test_table_stays_adjacent_to_suggested_skills() -> None:
    body = _read()
    headings = _headings_between(body, "Suggested skills", "Do not duplicate")
    assert headings == ["## Suggested skills", "## Required body sections by state"], (
        "the state->sections table must sit immediately after `## Suggested skills` "
        f"with no heading wedged in between; found: {headings}"
    )