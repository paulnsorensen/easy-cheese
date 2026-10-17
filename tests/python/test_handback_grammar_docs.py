"""The `status:` handback grammar is stated once, in the handback contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"
HANDBACK_CONTRACT = SKILLS / "cheese" / "references" / "handback-contract.md"


STALE_PREAMBLES = ("status: ok | halt:", "ok | gated | halt")

EDITED_FILES = (
    SKILLS / "cheese" / "references" / "formatting.md",
    SKILLS / "cheese" / "references" / "handoff-gate.md",
    SKILLS / "cook" / "SKILL.md",
    SKILLS / "cure" / "SKILL.md",
    SKILLS / "press" / "SKILL.md",
    SKILLS / "affinage" / "SKILL.md",
    SKILLS / "pasteurize" / "SKILL.md",
    SKILLS / "age" / "references" / "report-example.md",
    SKILLS / "wheypoint" / "SKILL.md",
    SKILLS / "ultracook" / "references" / "wiring-prompt.md",
)


def test_stale_status_grammar_appears_only_in_handback_contract() -> None:
    offenders: list[str] = []
    for path in SKILLS.rglob("*.md"):
        if path == HANDBACK_CONTRACT:
            continue
        text = path.read_text(encoding="utf-8")
        if any(stale in text for stale in STALE_PREAMBLES):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, (
        "stale `status:` preamble grammar found outside handback-contract.md: "
        f"{offenders}"
    )


def test_each_edited_file_links_handback_contract_exactly_once() -> None:
    for path in EDITED_FILES:
        text = path.read_text(encoding="utf-8")
        count = text.count("handback-contract.md")
        assert count == 1, (
            f"{path.relative_to(REPO_ROOT)}: expected exactly one "
            f"handback-contract.md link, found {count}"
        )
