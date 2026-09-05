"""Contract guard: `/culture` records ideas, decisions, and info.

Culture used to write only the end-of-session wheypoint, so every idea and
settled decision from a thinking session lived in transient `.cheese/notes`
or in nobody's memory. The record ledger sends decisions to ADRs, ideas and
info to the wiki (or a loud tracked fallback), returns the ledger from
internal mode instead of writing, and keeps code, specs, commits, and PRs
off limits. These tests pin that contract in `SKILL.md` and the README row.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CULTURE = REPO_ROOT / "skills" / "culture" / "SKILL.md"
README = REPO_ROOT / "README.md"


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert match, f"section {heading!r} missing"
    level = len(match.group(1))
    rest = text[match.end() :]
    stop = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: stop.start()] if stop else rest


def _table_rows(text: str, first_header: str) -> list[list[str]]:
    lines = text.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith(f"| {first_header} |")
    )
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
    return rows


def _body() -> str:
    return CULTURE.read_text(encoding="utf-8")


def test_record_ledger_names_three_kinds_with_targets_and_fallbacks() -> None:
    rows = _table_rows(_section(_body(), "Record ledger"), "Kind")
    assert [row[0] for row in rows] == ["Decision", "Idea", "Info"]
    decision, idea, info = rows
    for row in rows:
        assert len(row) == 4 and all(row), f"ledger row incomplete: {row}"
    assert "../mold/references/adr.md" in decision[2], "decisions reuse Mold's ADR contract"
    assert "docs/adr/<slug>-NNN.md" in decision[3], "same file fallback as Mold's ADRs"
    assert "ideas/<slug>.md" in idea[2]
    assert "overwrite: true" in info[2], "info folds into the page it extends"


def test_targets_resolve_dynamically_and_degrade_loudly() -> None:
    ledger = _section(_body(), "Record ledger")
    assert "adr_target()" in ledger and "never a literal name" in ledger
    assert re.search(r"hallouminate is absent[^.]*loud", ledger), (
        "the file fallback must be announced, never a silent degrade"
    )


def test_records_flush_on_user_ask_and_before_the_wheypoint() -> None:
    body = _body()
    ledger = _section(body, "Record ledger")
    for phrase in ("`record that`", "`note that`", "`remember that`"):
        assert phrase in ledger, f"explicit record trigger {phrase} missing"
    assert re.search(r"user calls the thread over, before the wheypoint", ledger)
    assert re.search(r"never record a passing thought", ledger, re.I)
    flow = _section(body, "Flow")
    assert "flush the ledger, then end the session by writing the wheypoint" in flow


def test_internal_mode_returns_the_ledger_and_writes_nothing() -> None:
    body = _body()
    assert re.search(r"\*\*internal mode\*\* it writes nothing at all", _section(body, "Invariant"))
    ledger = _section(body, "Record ledger")
    assert "Internal mode writes nothing" in ledger
    assert "returns the ledger inside its decision" in ledger


def test_invariant_keeps_code_specs_commits_and_prs_off_limits() -> None:
    body = _body()
    invariant = _section(body, "Invariant")
    assert "writes no production code and no spec" in invariant
    assert "does not commit changes, open PRs" in invariant
    assert "## Record ledger" in invariant, "the invariant must name what culture does write"
    rules = _section(body, "Rules")
    assert "never code, specs, commits, or PRs" in rules


def test_handoff_packet_and_readme_carry_the_records() -> None:
    assert "records: [" in _section(_body(), "Handoff")
    readme = README.read_text(encoding="utf-8")
    assert "Records the session's ideas, decisions, and info" in readme
    assert "opt-in `.cheese/notes/<slug>.md` handoff" not in readme, (
        "README still describes the pre-ledger invariant"
    )
