from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import stage_release  # noqa: E402


def test_distill_is_a_tracked_repo_local_skill() -> None:
    skill = REPO_ROOT / ".agents" / "skills" / "distill" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert text.startswith("---\nname: distill\n")
    assert "experimental" in text.lower()
    assert "!.agents/skills/distill/" in ignore
    assert not (REPO_ROOT / "skills" / "distill").exists()


def test_release_allowlist_excludes_repo_local_agent_skills() -> None:
    assert ".agents" not in stage_release.SHIP


def test_distillation_gates_are_separated_in_justfile() -> None:
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert "test: test-skill-distill" in justfile
    assert "test-skill-distill:" in justfile
    assert "python3 -m pytest tests/skill-distill/python -q" in justfile
    assert "distill-pilot *args:" in justfile
    assert "python -m skill_distill prepare {{args}}" in justfile
    assert "current-harness" not in justfile.lower()
    assert "llm" not in justfile.lower()
