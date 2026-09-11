"""Parse and validate --grounded manifest entries.

Split out of `phase_commit` so `lint` can validate a record's
`working_context` against the same grammar the writer enforces without
creating an import cycle: lint -> commit -> phase_commit -> commit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

MAX_GROUNDED_ENTRIES = 16
_GROUNDED_RE = re.compile(
    r"^(?P<path>[^#]+?)(?:#(?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*))?$"
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
        candidate = Path(path_text)
        if candidate.is_absolute():
            raise GroundedEntryError(
                f"--grounded path must be under root: {path_text!r}"
            )
        try:
            resolved = (resolved_root / candidate).resolve()
        except (OSError, RuntimeError) as exc:
            raise GroundedEntryError(
                f"--grounded path escapes the repository root: {path_text!r}"
            ) from exc
        if not resolved.is_relative_to(resolved_root):
            raise GroundedEntryError(
                f"--grounded path escapes the repository root: {path_text!r}"
            )
        if not resolved.is_file():
            raise GroundedEntryError(f"--grounded path not found: {path_text!r}")
        validated.append(entry)
    return tuple(validated)
