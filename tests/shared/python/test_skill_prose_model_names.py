"""Shared skill prose names roles and tiers; model names live in one overlay section."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERLAY_FILE = Path("skills/cheese/references/routing-policy.md")
OVERLAY_HEADING = "## Roles x tiers"
MODEL_NAME = re.compile(
    r"\b(?:opus|sonnet|haiku|luna|sol|astra|terra)\b|\bgpt-\d", re.IGNORECASE
)


def _overlay_span(lines: list[str]) -> range:
    start = next(i for i, line in enumerate(lines) if line.startswith(OVERLAY_HEADING))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return range(start, end)


def find_model_name_hits(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted((root / "skills").rglob("*.md")):
        rel = path.relative_to(root)
        lines = path.read_text(encoding="utf-8").splitlines()
        allowed = _overlay_span(lines) if rel == OVERLAY_FILE else range(0)
        for i, line in enumerate(lines):
            if i not in allowed and MODEL_NAME.search(line):
                hits.append(f"{rel}:{i + 1}: {line.strip()[:80]}")
    return hits


def test_no_model_names_outside_overlay() -> None:
    assert find_model_name_hits(REPO_ROOT) == []


def test_overlay_section_exists_and_holds_model_names() -> None:
    lines = (REPO_ROOT / OVERLAY_FILE).read_text(encoding="utf-8").splitlines()
    span = _overlay_span(lines)
    assert any(MODEL_NAME.search(lines[i]) for i in span)


def test_check_rejects_planted_hits(tmp_path: Path) -> None:
    overlay = tmp_path / OVERLAY_FILE
    overlay.parent.mkdir(parents=True)
    _ = overlay.write_text(
        "# Policy\n\n## Roles x tiers (x)\n\nuses opus here\n\n## Next\n\nleaks Sonnet\n",
        encoding="utf-8",
    )
    other = tmp_path / "skills/foo/SKILL.md"
    other.parent.mkdir(parents=True)
    _ = other.write_text(
        "Use gpt-5 or haiku.\nplain solar words\nescalate to Astra\n", encoding="utf-8"
    )

    hits = find_model_name_hits(tmp_path)

    assert len(hits) == 3
    assert any(h.startswith("skills/cheese/references/routing-policy.md:9") for h in hits)
    assert any(h.startswith("skills/foo/SKILL.md:1") for h in hits)
    assert any(h.startswith("skills/foo/SKILL.md:3") for h in hits)
