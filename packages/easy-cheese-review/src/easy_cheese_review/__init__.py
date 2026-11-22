"""Review evidence for easy-cheese reviewers.

`scan` runs the packaged ast-grep rule pack over a change and computes the
`compat`, `dependencies`, `tests`, and `scope` facts. `severity` holds the
/age severity rubric.
"""

from __future__ import annotations

from easy_cheese_review._evidence import MAX_FILE_BYTES, facts, hunks_from_diff, scan
from easy_cheese_review._facts import CODE_SUFFIXES, SCAN_SUFFIXES
from easy_cheese_review._model import FACT_NAMES, Evidence, Fact, FactValue, Hit, Skipped

__all__ = [
    "CODE_SUFFIXES",
    "FACT_NAMES",
    "MAX_FILE_BYTES",
    "SCAN_SUFFIXES",
    "Evidence",
    "Fact",
    "FactValue",
    "Hit",
    "Skipped",
    "facts",
    "hunks_from_diff",
    "scan",
]
