"""Skill markdown files must use repo-relative paths, not CLAUDE_SKILL_DIR.

Claude Code substitutes ${CLAUDE_SKILL_DIR} in SKILL.md content before the
model sees it, but Codex CLI has no equivalent — the literal variable lands
in the model's context and fails at runtime. Repo-relative paths
(``skills/<skill>/scripts/...``) work on both hosts.

See skills/cheese/references/harness-portability.md § Helper resolution.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

# Matches ${CLAUDE_SKILL_DIR}/ used in invocation paths — the trailing slash
# distinguishes path usage from prose mentions of the variable name.
_INVOCATION_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/")


def _skill_md_files() -> list[Path]:
    """All .md files under skills/, excluding worktree copies."""
    return sorted(
        p
        for p in SKILLS_DIR.rglob("*.md")
        if ".worktrees" not in str(p)
    )


def test_no_claude_skill_dir_in_invocation_paths() -> None:
    """No skill markdown may use ${CLAUDE_SKILL_DIR}/ in a path."""
    violations: list[str] = []
    for md_file in _skill_md_files():
        text = md_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _INVOCATION_RE.search(line):
                rel = md_file.relative_to(REPO_ROOT)
                violations.append(f"  {rel}:{lineno}: {line.strip()}")

    assert not violations, (
        "Skill files must use repo-relative paths (skills/<skill>/scripts/...), "
        "not ${CLAUDE_SKILL_DIR}/ interpolation — Codex CLI has no equivalent.\n"
        + "\n".join(violations)
    )
