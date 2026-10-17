"""Sketch places a change in the architecture; it does not write bodies.

Sketch used to lock a pseudocode signature per seam and, under the
concrete-seam rule, write full bodies for anything under ~20 lines. That is
cook work happening inside mold, and it never asked which slice, which spine
step, or what the crust delta is. The Placement block replaces it, and the
Sliced Bread digest gives mold, cook, and age one shared vocabulary.
"""

from __future__ import annotations

import re
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
    """Slice from ``heading`` to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    start = body.index(heading)
    nxt = re.compile(r"\n#{1,%d} " % level).search(body, start + len(heading))
    return body[start : nxt.start() if nxt else len(body)]


class TestSketchIsPlacement:
    def test_section_helper_stops_at_the_next_sibling_heading(self) -> None:
        assert "### Grill" not in _section(_text(MODES), "### Sketch")
        assert "### spec" not in _section(_text(DIMENSIONS), "### encapsulation")

    def test_shape_check_derives_slice_from_the_symbol_path(self) -> None:
        body = _text(SHAPE_CHECK)
        assert "the touched symbol's own path names the owning slice" in body
        assert "the importer list names the slice" not in body
        assert "Three consumers print this block" in body

    def test_curd_count_reads_footprints_from_the_typed_plan(self) -> None:
        body = _text(SKILLS / "mold" / "references" / "curd-count.md")
        assert "naming each curd's `scope`" in body
        assert "`## Interface sketches` itself carries no file paths" in body
        assert "file footprints\ncaptured in `## Interface sketches`" not in body

    def test_voice_depth_rule_stops_at_the_public_signature(self) -> None:
        body = _text(SKILLS / "age" / "references" / "voice.md")
        assert "Write full pseudocode signatures" not in body
        assert "bodies and helpers wait for `/cook`" in body

    def test_wiki_invariant_names_the_placement_block(self) -> None:
        body = _text(REPO_ROOT / ".hallouminate" / "wiki" / "workflow-invariants.md")
        assert "sketches as a complete Placement block" in body
        assert "pseudocode signatures" not in body

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
