"""Mold asks only about consequential forks, and consequential means leverage.

Before this rule, every scope, naming, and trade-off fork was a user turn.
Session analytics measured a median of 6.5 AskUserQuestion calls and 443
minutes of wall clock per mold run, with a fifth of runs reaching a spec.
The fix draws one line: a fork reaches the user only when it fires a leverage
trigger, changes a crust or import direction, or changes user-visible behavior.
Everything else is `[AGENT-DECIDED]` with a vetoable alternative.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"
MOLD = SKILLS / "mold" / "SKILL.md"
MODES = SKILLS / "mold" / "references" / "modes.md"
ADR = SKILLS / "mold" / "references" / "adr.md"
VOICE = SKILLS / "age" / "references" / "voice.md"
CULTURE = SKILLS / "culture" / "SKILL.md"

LEVERAGE_LINE = re.compile(
    r"consequential when it fires a leverage trigger"
    + r".*?changes a crust or import direction"
    + r".*?changes user-visible behavior or output",
    re.S,
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    """Slice from ``heading`` to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    start = body.index(heading)
    nxt = re.compile(r"\n#{1,%d} " % level).search(body, start + len(heading))
    return body[start : nxt.start() if nxt else len(body)]


class TestConsequentialMeansLeverage:
    def test_mold_flow_points_at_the_line(self) -> None:
        body = _text(MOLD)
        assert "consequential per the leverage line in `../age/references/voice.md`" in body
        assert "Every other fork is `[AGENT-DECIDED]`." in body

    def test_voice_kernel_carries_the_same_line(self) -> None:
        body = _text(VOICE)
        assert LEVERAGE_LINE.search(body), "voice.md must define consequential"
        assert "Internal behavior the user cannot observe" in body
        assert "changes observable behavior" not in body
        assert "make the call, log a vetoable alternative, and do not ask" in body
        assert "These forks include scope, naming, and trade-offs" not in body

    def test_culture_points_at_the_line_instead_of_restating_it(self) -> None:
        body = _text(CULTURE)
        assert "per the leverage line in `../age/references/voice.md`" in body
        assert "Consequential design choices need explicit user adjudication" in body
        assert "below the leverage line, pick one and log the alternative" in body

    def test_adr_and_shape_point_at_the_line_instead_of_restating_it(self) -> None:
        adr = _text(ADR)
        assert "(per the leverage line in `../../age/references/voice.md`)" in adr
        assert "changed observable" not in adr
        shape = _section(_text(MODES), "### Shape")
        assert "the leverage line in `../../age/references/voice.md`" in shape
        assert "Settle every fork below the line and log it." in shape

    def test_altitude_tag_and_leverage_line_compose(self) -> None:
        rules = _section(_text(MOLD), "## Rules")
        assert "or that sits below the leverage line, is `[AGENT-DECIDED]`" in rules
        grill = _section(_text(MODES), "### Grill")
        assert "Tag each grilled item with what it moves" in grill
        assert "or that sits below the leverage line, is not a user fork" in grill

    def test_bounds_pass_step_asks_only_above_the_line(self) -> None:
        flow = _section(_text(MOLD), "## Flow")
        assert "ask the user rather than assume" not in flow
        assert "as one `[AGENT-DECIDED]` line" in flow
        assert "ask the user only when the goal is genuinely unknown or a leverage trigger fires" in flow

    def test_grill_eval_requires_a_turn_only_for_consequential_items(self) -> None:
        evals = _text(SKILLS / "mold" / "references" / "evals.md")
        assert "for a grill of `[AGENT-DECIDED]` items" not in evals
        assert "One user-fork round or more for each consequential grilled item" in evals
        assert "a user turn spent on one is a regression" in evals
        assert "**Under-batching**" in evals


class TestBelowTheLineIsAgentDecided:
    def test_rules_bullet_makes_agent_decided_the_default(self) -> None:
        bullet = re.search(
            r"-\s*\*\*Tiered lettered options\.\*\*.*?(?=\n- \*\*)", _text(MOLD), re.S
        )
        assert bullet
        assert "is `[AGENT-DECIDED]` by default" in bullet.group(0)
        assert "do not ask" in bullet.group(0)
        assert "Minor mechanics use `[AGENT-DECIDED]`" not in bullet.group(0)

    def test_bounds_pass_is_a_ledger_line_for_a_concrete_ask(self) -> None:
        body = _text(MODES)
        assert "no longer skip asking" not in body
        assert "the pass is one ledger line" in body
        assert "becomes a question only when the goal is genuinely unknown" in body

    def test_section_helper_stops_at_the_next_sibling_heading(self) -> None:
        grill = _section(_text(MODES), "### Grill")
        assert "### Diagnose" not in grill

    def test_grill_skips_items_below_the_line(self) -> None:
        grill = _section(_text(MODES), "### Grill")
        assert "consequential forks and `high` blast-radius options only" in grill
        assert "never become a user turn" in grill
        assert "For each `[AGENT-DECIDED]` item or design decision" not in grill

    def test_agent_decided_calls_never_earn_an_adr(self) -> None:
        body = _text(ADR)
        assert "`[AGENT-DECIDED]` calls ride the spec's one-line" in body
        assert "never a full ADR" in body
        assert "could have vetoed earns an ADR" not in body
