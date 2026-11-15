"""Keep Python and Rust relative-reference extraction on one fixture contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from ref_extraction import relative_md_refs  # pyright: ignore[reportImplicitRelativeImport]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_relative_reference_fixture_contract() -> None:
    cases = cast(
        list[dict[str, object]],
        json.loads(
            (REPO_ROOT / "tools/skill-overlap/fixtures/relative-md-refs.json").read_text()
        ),
    )
    assert len(cases) == 3, "fixture case count changed; update this guard alongside the fixture"
    for case in cases:
        assert relative_md_refs(cast(str, case["text"])) == case["refs"], case["name"]


def test_fenced_code_block_does_not_desync_backtick_pairing() -> None:
    """A ``` fence is itself a run of backtick characters; if it isn't
    stripped first, _BACKTICK_RE's positional pairing desyncs and every real
    ref after the fence in the same document goes unreported."""
    text = (
        "# Doc\n"
        "```python\n"
        "x = `not a ref`\n"
        "```\n"
        "See `references/missing.md` for detail.\n"
    )
    assert relative_md_refs(text) == ["references/missing.md"]
