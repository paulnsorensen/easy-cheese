"""Melt skill prose routes bundled commands through repository-relative paths."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_melt_invokes_only_its_repo_relative_archive() -> None:
    prose = "\n".join(
        (REPO_ROOT / path).read_text()
        for path in ("skills/melt/SKILL.md", "skills/melt/references/cascade-stages.md")
    )

    assert "${CLAUDE_SKILL_DIR}" not in prose
    assert "python3 skills/melt/scripts/melt.pyz" in prose
