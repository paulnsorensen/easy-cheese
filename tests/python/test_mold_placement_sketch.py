"""Sketch places a change in the architecture; it does not write bodies.

Sketch used to lock a pseudocode signature per seam and, under the
concrete-seam rule, write full bodies for anything under ~20 lines. That is
cook work happening inside mold, and it never asked which slice, which spine
step, or what the crust delta is. The Placement block replaces it, and the
Sliced Bread digest gives mold, cook, and age one shared vocabulary.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"
MODES = SKILLS / "mold" / "references" / "modes.md"
CURDLE = SKILLS / "mold" / "references" / "curdle.md"
SHAPE_CHECK = SKILLS / "mold" / "references" / "shape-check.md"
HANDSHAKE = SKILLS / "mold" / "references" / "handshake.md"
SLICED_BREAD = SKILLS / "cheese" / "references" / "sliced-bread.md"
COOK = SKILLS / "cook" / "SKILL.md"
DIMENSIONS = SKILLS / "age" / "references" / "dimensions.md"

PLACEMENT_FIELDS = ("slice:", "spine step:", "public interface:", "private:", "crust delta:", "arrows:")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start : end if end != -1 else len(body)]


class TestSketchIsPlacement:
    def test_sketch_names_every_placement_field(self) -> None:
        sketch = _section(_text(MODES), "### Sketch")
        for field in PLACEMENT_FIELDS:
            assert f"`{field}`" in sketch, field

    def test_sketch_dropped_the_concrete_seam_rule(self) -> None:
        body = _text(MODES)
        assert "Concrete-seam rule" not in body
        assert "write the full implementation instead of pseudocode" not in body
        assert "those belong to `/cook`" in body

    def test_spec_template_carries_the_placement_block(self) -> None:
        section = _section(_text(CURDLE), "## Interface sketches")
        for field in PLACEMENT_FIELDS:
            assert field in section, field
        assert "<signatures, schemas, seams>" not in section

    def test_handshake_checks_the_placement_block(self) -> None:
        body = _text(HANDSHAKE)
        assert "Interface sketches: Placement block complete" in body
        assert "every public seam has a pseudocode signature" not in body

    def test_crust_delta_forces_a_high_verdict(self) -> None:
        body = _text(SHAPE_CHECK)
        assert "crust delta:   <new exports | cross-slice imports | contract changes | none>" in body
        assert "or a non-empty crust delta" in body


class TestSlicedBreadIsSharedVocabulary:
    def test_digest_defines_the_terms_and_arrows(self) -> None:
        body = _text(SLICED_BREAD)
        for term in ("**Slice**", "**Spine**", "**Crust**", "**Deep module**", "**Crust delta**"):
            assert term in body, term
        assert "domains/*    →  adapters/*" in body

    def test_mold_cook_and_age_link_the_same_digest(self) -> None:
        assert "../../cheese/references/sliced-bread.md" in _text(MODES)
        assert "../../cheese/references/sliced-bread.md" in _text(SHAPE_CHECK)
        assert "../cheese/references/sliced-bread.md" in _text(COOK)
        encapsulation = _section(_text(DIMENSIONS), "### encapsulation")
        assert "../../cheese/references/sliced-bread.md" in encapsulation
        assert "crust delta the spec's Placement block did not name" in encapsulation
