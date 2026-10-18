"""The retired lint, lineage, shape, and graph modules stay gone."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "easy_cheese"
RETIRED = ("lint", "lint_freshness", "lineage", "shape", "graph", "fork_reconcile")
RETIRED_FILES = (
    "shared/wheypoint/lint.py",
    "shared/wheypoint/lint_freshness.py",
    "shared/wheypoint/lineage.py",
    "shared/wheypoint/shape.py",
    "shared/wheypoint/fork_reconcile.py",
    "cli/wheypoint/graph.py",
)
_NAMES = "|".join(RETIRED)
_IMPORT = re.compile(
    rf"^\s*(?:from\s+[\w.]*\b(?:{_NAMES})\s+import\b"
    + rf"|from\s+[\w.]*wheypoint\S*\s+import\s+[^\n#]*\b(?:{_NAMES})\b"
    + rf"|import\s+[\w.]*wheypoint[\w.]*\.(?:{_NAMES})\b)",
    re.MULTILINE,
)


def test_retired_modules_are_absent() -> None:
    assert [name for name in RETIRED_FILES if (SRC / name).exists()] == []


def test_no_wheypoint_source_imports_a_retired_module() -> None:
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if _IMPORT.search(path.read_text())
    ]
    assert offenders == []
