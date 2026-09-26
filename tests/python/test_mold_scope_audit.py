"""Scope audits display draft defaults without granting Cook consent.

The audit runs before a draft save. Leverage rows and unresolved bindings
still block execution until the user settles them.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold" / "SKILL.md"
HANDSHAKE = REPO_ROOT / "skills" / "mold" / "references" / "handshake.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start : end if end != -1 else len(body)]


class TestOneTableOneConfirm:
    def test_table_is_presented_once_before_execution(self) -> None:
        section = _section(_text(HANDSHAKE), "## Scope audit table")
        assert "one table, presented once, before execution" in section
        assert "Mold may save the displayed defaults without a confirm" in section
        for kind in ("| scope |", "| non-goal |", "| entity |", "| follow-up |"):
            assert kind in section, kind

    def test_only_leverage_rows_and_unresolved_bindings_need_a_verb(self) -> None:
        body = _text(HANDSHAKE)
        assert "A row needs its own explicit verb only when it fires a leverage trigger" in body
        assert "A row that fires a leverage trigger needs its own verb" in body
        assert "A `Bound` row needs no approval" in body

    def test_leverage_rows_render_as_blocking_in_the_template(self) -> None:
        section = _section(_text(HANDSHAKE), "## Scope audit table")
        assert "| needs your verb | contract |" in section
        assert "| needs your verb (ALIAS <referent>) | — |" in section
        assert "Rows marked `needs your verb` block execution until you name a verb for each." in section
        assert "Confirm the table, or name the rows to change." not in section
        assert "would itself fire one of the eight ids if kept" in section

    def test_only_an_explicit_drop_writes_a_rejection_record(self) -> None:
        body = _text(HANDSHAKE)
        assert "only when the user typed `drop` or explicitly confirmed a displayed `drop` default" in body
        assert "Do not write one for an unchallenged default." in body
        assert "left a displayed `drop` default unchallenged" not in body

    def test_agent_decided_non_goals_enter_the_table(self) -> None:
        body = _text(HANDSHAKE)
        assert "authored as `[AGENT-DECIDED]` are agent-introduced by definition" in body

    def test_per_row_approval_rounds_are_gone(self) -> None:
        body = _text(HANDSHAKE)
        assert "The user must explicitly approve each row" not in body
        assert "The user must explicitly keep, drop, or reword it." not in body
        assert 'Vague "looks good" is not approval' not in body
        assert "inline, per dialogue round" not in body
        assert "inline per round" not in body
        assert "per-term approval" not in body
        assert "approves each grouping" not in body
        assert "approves each reuse" not in body
        assert "receive per-term approval" not in body
        curdle = _text(REPO_ROOT / "skills" / "mold" / "references" / "curdle.md")
        assert "each approved per `handshake.md` § Agent-introduced scope" not in curdle

    def test_follow_up_default_is_non_goal_only(self) -> None:
        section = _section(_text(HANDSHAKE), "## Follow-up disposition")
        assert "The default destination is **non-goal only**" in section
        assert "every other destination is a user edit on the row" in section
        assert "Each unit is one `follow-up` row whose cell lists its members" in section
        assert "A semantic match is surfaced on the row as a recommended `link #<id>`" in section
        assert "the default destination stays non-goal only" in section
        assert "needs no approval to save" in section

    def test_curdle_anyway_accepts_the_defaults(self) -> None:
        body = _text(HANDSHAKE)
        assert "It accepts every other default." in body
        assert "explicit per-term approval" not in body

    def test_skill_execution_gate_names_the_table(self) -> None:
        gate = _section(_text(MOLD), "## Execution gate")
        assert "scope audit table before presenting any Cook option" in gate
        assert "save a validated parent spec or early curd mini-spec without an approval turn" in gate
        assert "Require explicit approval for each term" not in gate
