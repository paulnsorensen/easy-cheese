"""Mold must carry `--hard` on every Cook command that it emits.

`tests/python/test_hard_cheese.py` only asserts that the token appears in
`skills/mold/SKILL.md`. That check passes while a route drops the requested
gate. These tests assert the propagation rule at each Mold producer surface.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MOLD = Path(__file__).resolve().parents[2] / "skills" / "mold"

HARD_RULE = re.compile(r"[Aa]ppend `--hard` when the user passed it\.")


def _read(relative: str) -> str:
    return (MOLD / relative).read_text(encoding="utf-8")


def test_mini_spec_mode_in_skill_appends_hard() -> None:
    """The tier-1 route dispatches Cook, so it must carry the flag."""
    line = next(
        line
        for line in _read("SKILL.md").splitlines()
        if "Return the resolved spec path with `/cook --auto" in line
    )
    assert HARD_RULE.search(line), line


def test_mini_spec_reference_appends_hard() -> None:
    """Every mini-spec disposition carries the flag, not only `red-required`."""
    body = _read("references/mini-spec-mode.md")
    assert "**Append `--hard`**" in body
    assert "Every disposition carries it." in body


def test_full_mode_handoff_appends_hard() -> None:
    """The full-mode Handoff recommendation carries the flag."""
    section = _read("SKILL.md").split("## Handoff", 1)[1]
    assert HARD_RULE.search(section), section[:400]


@pytest.mark.parametrize("row", ["Red-required Spec", "Spec"])
def test_curdle_handoff_rows_append_hard(row: str) -> None:
    """Both Curdle hand-off rows carry the flag."""
    line = next(
        line
        for line in _read("references/curdle.md").splitlines()
        if line.startswith(f"| {row} | `/cook")
    )
    assert "add `--hard` when the user passed it" in line, line


def test_mold_does_not_run_the_gate_itself() -> None:
    """Plate keeps sole ownership of the gate run."""
    body = _read("SKILL.md")
    assert "Mold never runs the metacognitive check." in body
    assert "Plate alone runs it" in body
