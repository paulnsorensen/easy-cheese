"""Pin what `relative_md_refs` counts as a relative markdown reference.

These cases used to live in `tools/skill-overlap/fixtures/relative-md-refs.json`,
shared with the Rust overlap analyzer so both implementations agreed. The
analyzer is retired (issue #511); the cases stay because the live-tree resolve
gate (`test_reference_resolution.py`) and the staged-tree check
(`test_stage_release.py`) both fail open on anything this extractor misses.
"""
from __future__ import annotations

import pytest

from ref_extraction import relative_md_refs  # pyright: ignore[reportImplicitRelativeImport]


@pytest.mark.parametrize(
    "name,text,expected",
    [
        (
            "links and prose references",
            "[Doc](../age/references/voice.md#tone) and `references/formatting.md § style`.",
            ["../age/references/voice.md", "references/formatting.md"],
        ),
        (
            "external and fragments do not count",
            "[web](https://example.test/a.md) [anchor](#section) `skills/age/SKILL.md`",
            [],
        ),
        (
            # Quirk, pinned deliberately: `$` matches before a trailing newline,
            # so a ref broken across the closing backtick is reported with the
            # newline still attached rather than being dropped.
            "trailing newline before closing backtick",
            "see `references/a.md\n`",
            ["references/a.md\n"],
        ),
    ],
)
def test_relative_reference_cases(name: str, text: str, expected: list[str]) -> None:
    assert relative_md_refs(text) == expected, name


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
