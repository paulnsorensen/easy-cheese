"""Every phase that reads or writes named code consumes the per-slug glossary.

`/mold` writes `.cheese/glossary/<slug>.md` (mold/references/curdle.md
§ Durable glossary) and names cook, age, and press as its consumers. Cook —
the phase that actually writes the code the canonical terms should shape — had
no glossary step at all (#555), so the terms reached review but never the
naming decision they exist to constrain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GLOSSARY_PATH = ".cheese/glossary/<slug>.md"
CONSUMERS = ("cook", "press", "age")


def _skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", CONSUMERS)  # noqa: V107
def test_downstream_skills_consume_the_per_slug_glossary(name: str) -> None:
    assert GLOSSARY_PATH in _skill(name)


@pytest.mark.parametrize("name", CONSUMERS)  # noqa: V107
def test_the_glossary_read_sits_in_the_skills_flow(name: str) -> None:
    """A pointer buried in prose is not a step; the read has to be in Flow."""
    flow = _skill(name).split("\n## Flow\n", 1)[1].split("\n## ", 1)[0]
    assert GLOSSARY_PATH in flow


def test_mold_still_advertises_cook_as_a_glossary_consumer() -> None:
    curdle = (ROOT / "skills" / "mold" / "references" / "curdle.md").read_text(encoding="utf-8")
    section = curdle.split("## Durable glossary", 1)[1].split("\n## ", 1)[0]
    assert GLOSSARY_PATH in section
    assert "/cook" in section
