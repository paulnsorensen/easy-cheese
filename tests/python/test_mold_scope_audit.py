"""The four handshake audits ask once, through one table with defaults.

Agent-introduced scope, the non-goals audit, entity-referent binding, and
follow-up disposition each demanded per-row approval, so question volume
scaled with noun count rather than with stakes. The grep and search that
populate the rows still run; only leverage rows and unresolved bindings
keep their own approval turn.
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
    def test_table_is_presented_once_before_the_handshake(self) -> None:
        section = _section(_text(HANDSHAKE), "## Scope audit table")
        assert "one table, presented once, before the handshake" in section
        assert "One confirm of the table approves every default." in section
        for kind in ("| scope |", "| non-goal |", "| entity |", "| follow-up |"):
            assert kind in section, kind

    def test_only_leverage_rows_and_unresolved_bindings_need_a_verb(self) -> None:
        body = _text(HANDSHAKE)
        assert "A row needs its own explicit verb only when it fires a leverage trigger" in body
        assert "A row that fires a leverage trigger needs its own verb" in body
        assert "A `Bound` row needs no approval" in body

    def test_per_row_approval_rounds_are_gone(self) -> None:
        body = _text(HANDSHAKE)
        assert "The user must explicitly approve each row" not in body
        assert "The user must explicitly keep, drop, or reword it." not in body
        assert 'Vague "looks good" is not approval' not in body
        assert "inline, per dialogue round" not in body

    def test_follow_up_default_is_non_goal_only(self) -> None:
        section = _section(_text(HANDSHAKE), "## Follow-up disposition")
        assert "The default destination is **non-goal only**" in section
        assert "by confirming the table's defaults or editing the rows" in section

    def test_curdle_anyway_accepts_the_defaults(self) -> None:
        body = _text(HANDSHAKE)
        assert "It accepts every other default." in body
        assert "explicit per-term approval" not in body

    def test_skill_approval_gate_names_the_table(self) -> None:
        approval = _section(_text(MOLD), "## Approval gate")
        assert "present the **scope audit table** once" in approval
        assert "One confirm approves the defaults" in approval
        assert "Require explicit approval for each term" not in approval
