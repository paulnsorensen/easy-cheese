"""Mold asks only about consequential forks, and consequential means leverage.

Before this rule, every scope, naming, and trade-off fork was a user turn.
Session analytics measured a median of 6.5 AskUserQuestion calls and 443
minutes of wall clock per mold run, with a fifth of runs reaching a spec.
The fix draws one line: a fork reaches the user only when it fires a leverage
trigger, changes a crust or import direction, or changes observable behavior.
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
    + r"[^\n]*?changes a crust or import direction"
    + r"[^\n]*?changes observable behavior",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start : end if end != -1 else len(body)]


class TestConsequentialMeansLeverage:
    def test_mold_flow_points_at_the_line(self) -> None:
        body = _text(MOLD)
        assert "consequential per the leverage line in `../age/references/voice.md`" in body
        assert "Every other fork is `[AGENT-DECIDED]`." in body

    def test_voice_kernel_carries_the_same_line(self) -> None:
        body = _text(VOICE)
        assert LEVERAGE_LINE.search(body), "voice.md must define consequential"
        assert "make the call, log a vetoable alternative, and do not ask" in body
        assert "These forks include scope, naming, and trade-offs" not in body

    def test_culture_points_at_the_line_instead_of_restating_it(self) -> None:
        body = _text(CULTURE)
        assert "per the leverage line in `../age/references/voice.md`" in body


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
