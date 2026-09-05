"""Curd 3 of the wheypoint-ergonomics spec: the skill prose is short, STE100, and honest.

AC-21: SKILL.md is at most 130 lines, one sentence per line, and no longer licenses
dropping state for a focus; the legacy-note guidance lives in a reference.
AC-29: parallel-handoffs.md documents tasks/parallel as intent fields, places
`mode:` after `artifact:`, and never says checkpoint refuses those keys.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "wheypoint"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"

# A sentence boundary inside one line: terminal punctuation, a space, then a capital.
_TWO_SENTENCES = re.compile(r"(?<![0-9])[.!?] +[A-Z]")


def _prose_lines(text: str) -> list[str]:
    lines: list[str] = []
    fenced = False
    front_matter = 0
    for line in text.splitlines():
        if line.strip() == "---":
            front_matter += 1
            continue
        if front_matter == 1:
            continue
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or line.startswith("|") or line.startswith("#") or not line.strip():
            continue
        lines.append(line)
    return lines


def test_ac21_skill_md_is_short_and_one_sentence_per_line() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 130
    offenders = [line for line in _prose_lines(text) if _TWO_SENTENCES.search(re.sub(r"`[^`]*`", "", line))]
    assert offenders == [], offenders


def test_ac21_the_lens_no_longer_licenses_dropping_state() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "Reduce unrelated state" not in text
    assert "Drop state" not in text and "drop state" not in text
    assert "never removes a decision, question, blocker, or directive" in text


def test_ac21_legacy_note_guidance_lives_in_a_reference() -> None:
    legacy = REFERENCES / "legacy-notes.md"
    assert legacy.is_file()
    text = legacy.read_text(encoding="utf-8")
    assert "halt: <one-line reason>" in text and "baseline:" in text
    assert "legacy-notes.md" in SKILL.read_text(encoding="utf-8")
    assert "### Handwritten legacy notes" not in SKILL.read_text(encoding="utf-8")


def _preamble_blocks(text: str) -> list[list[str]]:
    """Every fenced block that starts with a `status:` line, as its lines."""
    blocks: list[list[str]] = []
    fenced: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("```"):
            if fenced is not None and fenced and fenced[0].startswith("status:"):
                blocks.append(fenced)
            fenced = [] if fenced is None else None
        elif fenced is not None:
            fenced.append(line)
    return blocks


def test_ac29_parallel_handoffs_documents_the_intent_fields() -> None:
    text = (REFERENCES / "parallel-handoffs.md").read_text(encoding="utf-8")
    assert "refuses" not in text
    assert "`tasks` and `parallel` are `CheckpointIntent` fields" in text
    cheese = SKILL_DIR.parent / "cheese" / "references" / "continue-resume.md"
    assert "`mode:` is a keyed line after `artifact:`" in cheese.read_text(encoding="utf-8")
    checked = 0
    for block in _preamble_blocks(text) + _preamble_blocks(cheese.read_text(encoding="utf-8")):
        keys = [line.split(":", 1)[0] for line in block if ":" in line]
        if "mode" in keys:
            assert keys.index("mode") == keys.index("artifact") + 1, block
            checked += 1
    assert checked >= 1, "no preamble example carries a mode: line"
