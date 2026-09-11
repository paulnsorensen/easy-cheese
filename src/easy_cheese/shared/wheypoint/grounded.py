"""Parse and validate --grounded manifest entries.

Split out of `phase_commit` so `lint` can validate a record's
`working_context` against the same grammar the writer enforces without
creating an import cycle: lint -> phase_commit -> commit -> lint.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

MAX_GROUNDED_ENTRIES = 16
# The range suffix is anchored on the *last* `#`, so a repository file whose
# own name carries one is groundable rather than a grammar violation.
_GROUNDED_RE = re.compile(
    r"^(?P<path>.+?)(?:#(?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*))?$"
)


class GroundedEntryError(ValueError):
    """A --grounded entry does not satisfy the path-and-range contract."""


def parse_grounded_entry(entry: str) -> tuple[str, tuple[int, int] | None]:
    """Parse one --grounded entry into its path text and optional 1-based range."""
    match = _GROUNDED_RE.fullmatch(entry)
    if match is None:
        raise GroundedEntryError(
            f"--grounded entry must be path[#start-end]: {entry!r}"
        )
    path_text = match.group("path")
    start_text = match.group("start")
    end_text = match.group("end")
    if start_text is None or end_text is None:
        return path_text, None
    start, end = int(start_text), int(end_text)
    if start > end:
        raise GroundedEntryError(f"--grounded range must ascend: {entry!r}")
    return path_text, (start, end)


class GroundedPathIssue(Enum):
    """Why a grounded pointer names no readable file under the root.

    The three are kept apart because they send an operator to different
    places: an absolute or escaping path is wrong about *where* to look, a
    missing one is wrong about *what* is there.
    """

    ABSOLUTE = "is absolute"
    ESCAPES_ROOT = "escapes the repository root"
    MISSING = "is missing"


_WRITER_MESSAGES = {
    GroundedPathIssue.ABSOLUTE: "--grounded path must be under root",
    GroundedPathIssue.ESCAPES_ROOT: "--grounded path escapes the repository root",
    GroundedPathIssue.MISSING: "--grounded path not found",
}


def resolve_within(path_text: str, root: Path | str) -> Path | GroundedPathIssue:
    """The file `path_text` names under `root`, or why it names none.

    One containment rule for both sides of the contract: the writer refuses
    what this reports, and the reader reports what the writer would have
    refused.
    """
    candidate = Path(path_text)
    if candidate.is_absolute():
        return GroundedPathIssue.ABSOLUTE
    resolved_root = Path(root).resolve()
    try:
        resolved = (resolved_root / candidate).resolve()
    except (OSError, RuntimeError, ValueError):
        # `resolve()` raises ValueError for an embedded NUL, which is a path
        # that escapes nothing because it names nothing.
        return GroundedPathIssue.ESCAPES_ROOT
    if not resolved.is_relative_to(resolved_root):
        return GroundedPathIssue.ESCAPES_ROOT
    if not resolved.is_file():
        return GroundedPathIssue.MISSING
    return resolved


def validate_grounded(entries: Sequence[str], *, root: Path | str) -> tuple[str, ...]:
    """Validate and preserve the grounded manifest exactly as supplied."""
    if len(entries) > MAX_GROUNDED_ENTRIES:
        raise GroundedEntryError(
            f"--grounded accepts at most {MAX_GROUNDED_ENTRIES} entries"
        )
    resolved_root = Path(root).resolve()
    validated: list[str] = []
    for entry in entries:
        path_text, _range = parse_grounded_entry(entry)
        landed = resolve_within(path_text, resolved_root)
        if isinstance(landed, GroundedPathIssue):
            raise GroundedEntryError(f"{_WRITER_MESSAGES[landed]}: {path_text!r}")
        validated.append(entry)
    return tuple(validated)
