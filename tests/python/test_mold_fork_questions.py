"""Regression guard: mold fork questions are explicit and offer an explain path.

A consequential fork question must state what it decides, show the branches
with a symbol table or a plain-text graph, and offer an `Explain more` choice.
An unclear or terse reply must re-render the same fork with more context
instead of a guess or a new fork.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold"
SKILL = MOLD / "SKILL.md"
FORK_QUESTIONS = MOLD / "references" / "fork-questions.md"
MODES = MOLD / "references" / "modes.md"
EVALS = MOLD / "references" / "evals.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    level = heading.split(" ", 1)[0]
    start = body.index(heading)
    rest = body[start + len(heading) :]
    nxt = re.search(rf"^{re.escape(level)} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _rules_bullet(name: str) -> str:
    rules = _section(_text(SKILL), "## Rules")
    match = re.search(rf"-\s*\*\*{re.escape(name)}\.\*\*.*?(?=\n- |\Z)", rules, re.S)
    assert match, f"mold Rules has no '{name}' bullet"
    return match.group(0)


def test_rules_bullet_routes_fork_questions_to_the_reference() -> None:
    bullet = _rules_bullet("Fork cards")
    assert "(references/fork-questions.md)" in bullet
    assert "`Explain more`" in bullet
    assert FORK_QUESTIONS.is_file()


def test_fork_card_states_the_decision_and_draws_the_branches() -> None:
    card = _section(_text(FORK_QUESTIONS), "## Fork card")
    for field in ("Basis:", "Decides:", "Moves:", "Today:", "Legend:"):
        assert field in card, field
    # The worked example leads into the fork from cited ledger ids.
    assert re.search(r"Basis: +Based on ev-\d+ .* the next question is", card, re.S)
    # The worked example must draw branches, not only list labels.
    assert re.search(r"```text\n.*──▶.*```", card, re.S)
    assert "✔" in card and "✘" in card


def test_basis_leads_from_ledger_evidence_into_the_fork() -> None:
    basis = _section(_text(FORK_QUESTIONS), "## Basis")
    assert "Based on X and Y, the next question is" in _rules_bullet("Fork cards")
    assert "ledger id" in basis
    assert "Cite only settled forks" in basis
    assert "not ready" in basis


def test_ledger_decisions_are_ears_requirements() -> None:
    bullet = _rules_bullet("Decision ledger")
    assert "EARS requirement" in bullet
    assert "(references/decision-ledger.md)" in bullet
    ledger = _text(MOLD / "references" / "decision-ledger.md")
    example = _section(ledger, "## EARS requirements")
    entries = cast(list[str], re.findall(r"^  (?:F|AD)-\d+: (.*)$", example, re.M))
    # `Asking` lines carry a basis; every other entry is a decision.
    decided = [line for line in entries if "Basis:" not in line]
    assert decided, "the example ledger has no decisions"
    assert all(" SHALL " in line for line in decided), decided
    assert "[prose-fallback]" in example


def test_explain_more_is_an_explicit_choice_that_keeps_the_fork_open() -> None:
    explain = _section(_text(FORK_QUESTIONS), "## Explain more")
    assert "explicit choice" in explain
    assert "numbered fallback" in explain
    assert "same fork id" in explain
    assert "does not count toward the fork-round cap" in explain
    assert "Never repeat earlier text" in explain


def test_unclear_reply_triggers_explain_not_a_guess() -> None:
    explain = _section(_text(FORK_QUESTIONS), "## Explain more")
    assert "unclear" in explain and "Do not guess" in explain


def test_explain_is_a_user_knob() -> None:
    knobs = _section(_text(MODES), "## User knobs")
    assert "`explain [fork-id]`" in knobs


def test_evals_watch_for_terse_forks() -> None:
    assert "**Terse fork**" in _text(EVALS)
