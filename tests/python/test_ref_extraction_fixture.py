"""Keep Python and Rust relative-reference extraction on one fixture contract."""
from __future__ import annotations

import json
from pathlib import Path

from ref_extraction import relative_md_refs

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_relative_reference_fixture_contract() -> None:
    cases = json.loads((REPO_ROOT / "tools/skill-overlap/fixtures/relative-md-refs.json").read_text())
    for case in cases:
        assert relative_md_refs(case["text"]) == case["refs"], case["name"]
