"""Decide from a diff's changed paths whether a PR body needs a Mermaid diagram.

Code applies the first row of `ordinary-pr.md` § Diagram so the same diff always
gets the same answer: a flow that crosses three or more modules needs a flowchart,
while a small fix, a docs-only change, and an independent PR need none.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from easy_cheese_schemas.pr_plan import PrShape

# ordinary-pr.md § Diagram: "A data or control flow that crosses three or more modules".
MIN_FLOW_MODULES = 3
FLOW_DIAGRAM = "flowchart"
SOURCE_SUFFIXES = frozenset(
    {
        ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte",
        ".go", ".rs", ".java", ".kt", ".scala", ".swift", ".rb", ".php", ".cs",
        ".c", ".h", ".cc", ".cpp", ".hpp", ".ex", ".exs", ".lua", ".dart", ".sh",
    }
)
DOC_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".adoc"})
# Tests, fixtures, vendored code, and built assets hold no module a flow diagram draws.
NON_MODULE_DIRS = frozenset(
    {"test", "tests", "__tests__", "spec", "fixtures", "testdata", "snapshots",
     "vendor", "node_modules", "dist", "assets"}
)
_TEST_STEM = re.compile(r"test_.*|conftest|.*[._](test|spec)")
# git name-status letters for an added, copied, deleted, or renamed path.
_STRUCTURAL = frozenset("ACDR")


@dataclass(frozen=True)
class Change:
    status: str
    path: str


@dataclass(frozen=True)
class DiagramNeed:
    """The Mermaid kind a body must carry (`None` when no diagram is required) and why."""

    kind: str | None
    reason: str


def parse_name_status(output: str) -> list[Change]:
    """Parse `git diff --name-status -z` output; a rename or copy keeps its new path."""
    fields = output.removesuffix("\0").split("\0") if output else []
    changes: list[Change] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        width = 3 if status.startswith(("R", "C")) else 2
        if not status or index + width > len(fields):
            raise ValueError(f"malformed git name-status record: {fields[index:index + width]!r}")
        changes.append(Change(status[0], fields[index + width - 1]))
        index += width
    return changes


def _is_module(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        pure.suffix.lower() in SOURCE_SUFFIXES
        and NON_MODULE_DIRS.isdisjoint(pure.parts[:-1])
        and _TEST_STEM.fullmatch(pure.stem) is None
    )


def decide(changes: Sequence[Change], *, shape: str | None = None) -> DiagramNeed:
    """Return the diagram the changed paths call for, or the reason they call for none."""
    if not changes:
        return DiagramNeed(None, "the diff is empty")
    if shape == PrShape.ORTHOGONAL_FLAT.value:
        return DiagramNeed(None, f"independent PR (Plated as {shape})")
    if all(PurePosixPath(change.path).suffix.lower() in DOC_SUFFIXES for change in changes):
        return DiagramNeed(None, "docs-only change")
    modules = [change for change in changes if _is_module(change.path)]
    structural = sum(change.status in _STRUCTURAL for change in modules)
    counts = f"code modules: {len(modules)} changed, {structural} added, removed, or renamed"
    if len(modules) < MIN_FLOW_MODULES:
        return DiagramNeed(None, f"{counts}; a flow diagram needs {MIN_FLOW_MODULES} or more changed")
    if structural == 0:
        return DiagramNeed(None, f"{counts}; a flow diagram needs one added, removed, or renamed")
    return DiagramNeed(FLOW_DIAGRAM, counts)
