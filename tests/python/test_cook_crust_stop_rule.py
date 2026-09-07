"""Cook stops at the crust, and the shape check is a precondition, not a step.

The adherence analysis measured ~1% adherence to hedged numbered steps and
near-total adherence to imperative preconditions on the next artifact. The
shape check was a hedged step, so no mold or cook run ever called
`tilth_deps`. Cook also had no rule to stop before changing a crust.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COOK = REPO_ROOT / "skills" / "cook" / "SKILL.md"
MODES = REPO_ROOT / "skills" / "mold" / "references" / "modes.md"
SHAPE_CHECK = REPO_ROOT / "skills" / "mold" / "references" / "shape-check.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    """Slice from ``heading`` to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    start = body.index(heading)
    nxt = re.compile(r"\n#{1,%d} " % level).search(body, start + len(heading))
    return body[start : nxt.start() if nxt else len(body)]


class TestShapeCheckIsAPrecondition:
    def test_cook_contract_requires_the_block_before_any_edit(self) -> None:
        flow = _section(_text(COOK), "## Flow")
        contract = flow[: flow.index("2. **Implement**")]
        assert "Print the shape-check block from `../mold/references/shape-check.md`" in contract
        assert "No block, no code." in contract

    def test_sketch_requires_the_block_before_drafting(self) -> None:
        sketch = _section(_text(MODES), "### Sketch")
        assert "### Grill" not in sketch
        assert "print its summary block first. No block, no sketch." in sketch

    def test_cook_and_mold_share_the_single_module_skip_line(self) -> None:
        flow = _section(_text(COOK), "## Flow")
        contract = flow[: flow.index("2. **Implement**")]
        assert "or the line `shape check skipped: single-module change`" in contract
        sketch = _section(_text(MODES), "### Sketch")
        assert '"shape check skipped: single-module change"' in sketch
        skip = _section(_text(SHAPE_CHECK), "## When to skip")
        assert "`shape check skipped: <reason>`" in skip
        assert 'satisfies the "no block, no code" precondition' in skip


class TestCookStopsAtTheCrust:
    def test_rules_name_the_three_crust_deltas(self) -> None:
        rules = _section(_text(COOK), "## Rules")
        assert (
            "Stop before a new crust export, a cross-slice import of an internal, "
            + "or a schema or contract change the spec does not name. Ask the user."
        ) in rules
        assert "../cheese/references/sliced-bread.md" in rules
