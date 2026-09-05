"""The `/briesearch` research layout as its own slug and artifact contract.

`SKILL.md:40,62` and `references/context-isolation.md:19-20` size a research
slug at four to six kebab-case words. The shared `validate_slug` helper only
enforces generic kebab-case, so a one-word slug produced a directory the prose
forbids (`review-briesearch.md`, `hub-shared.md`). `edge-briesearch-mold.md`
also needs the corpus-relative artifact path that a Mold `## Provenance` bullet
records, because a Mold document cannot carry an absolute private path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.skills.briesearch.research_layout import (
    research_layout,
    validate_research_slug,
)


@pytest.mark.parametrize(
    "slug",
    ["hybrid", "hybrid-retrieval", "hybrid-retrieval-fusion"],
)
def test_a_slug_below_four_words_is_rejected(slug: str) -> None:
    assert "4-6 kebab-case words" in (validate_research_slug(slug) or "")


def test_a_slug_above_six_words_is_rejected() -> None:
    slug = "one-two-three-four-five-six-seven"
    assert "7 word(s)" in (validate_research_slug(slug) or "")


@pytest.mark.parametrize(
    "slug",
    [
        "hybrid-retrieval-fusion-study",
        "hybrid-retrieval-fusion-study-notes",
        "hybrid-retrieval-fusion-study-notes-two",
    ],
)
def test_four_to_six_words_are_accepted(slug: str) -> None:
    assert validate_research_slug(slug) is None


def test_a_non_kebab_slug_keeps_the_shared_error() -> None:
    assert "kebab-case" in (validate_research_slug("Not A Slug") or "")


def test_research_layout_rejects_a_slug_outside_the_word_range() -> None:
    with pytest.raises(ValueError, match="4-6 kebab-case words"):
        _ = research_layout("fix-auth", root=Path("/tmp"))


def test_the_artifact_field_is_corpus_relative(tmp_path: Path) -> None:
    layout = research_layout("hybrid-retrieval-fusion-study", root=tmp_path)
    assert layout["artifact"] == (
        "research/hybrid-retrieval-fusion-study/hybrid-retrieval-fusion-study.md"
    )
    assert not Path(layout["artifact"]).is_absolute()
    assert layout["report"] == str(Path(layout["corpus_root"]) / layout["artifact"])
