"""Every phase that reads or writes named code consumes the per-slug glossary.

`/mold` writes `.cheese/glossary/<slug>.md` (mold/references/curdle.md
§ Durable glossary) and names cook, age, and press as its consumers. Cook —
the phase that actually writes the code the canonical terms should shape — had
no glossary step at all (#555), so the terms reached review but never the
naming decision they exist to constrain.

A substring check alone accepts a *negated* rule ("do not read the glossary"),
so these tests assert a positive read directive on the glossary line itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GLOSSARY_PATH = ".cheese/glossary/<slug>.md"
CONSUMERS = ("cook", "press", "age")
# The verb has to govern the glossary path in the same sentence.
_READ_DIRECTIVE = re.compile(r"\b(read|consult|apply|use|load)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(do not|don't|never|skip|ignore|without)\b", re.IGNORECASE)


def _skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _flow(name: str) -> str:
    return _skill(name).split("\n## Flow\n", 1)[1].split("\n## ", 1)[0]


def _glossary_sentences(text: str) -> list[str]:
    return [line for line in text.splitlines() if GLOSSARY_PATH in line]


@pytest.mark.parametrize("name", CONSUMERS)  # noqa: V107
def test_the_flow_step_reads_the_per_slug_glossary(name: str) -> None:
    """A pointer buried in prose is not a step; the read has to be in Flow."""
    sentences = _glossary_sentences(_flow(name))

    assert sentences, f"{name} names no glossary path in its Flow section"
    assert any(_READ_DIRECTIVE.search(line) for line in sentences), sentences


@pytest.mark.parametrize("name", CONSUMERS)  # noqa: V107
def test_no_flow_step_negates_the_glossary_read(name: str) -> None:
    for line in _glossary_sentences(_flow(name)):
        assert not _NEGATION.search(line), f"{name} negates the glossary read: {line}"


def test_mold_still_advertises_cook_as_a_glossary_consumer() -> None:
    curdle = (ROOT / "skills" / "mold" / "references" / "curdle.md").read_text(
        encoding="utf-8"
    )
    section = curdle.split("## Durable glossary", 1)[1].split("\n## ", 1)[0]
    assert GLOSSARY_PATH in section
    assert "/cook" in section
