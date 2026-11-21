"""Review evidence for easy-cheese reviewers.

`scan` runs the packaged ast-grep rule pack over a change and computes the
`compat`, `dependencies`, `tests`, and `scope` facts. `severity` holds the
/age severity rubric.
"""

from __future__ import annotations

from easy_cheese_review._evidence import facts, hunks_from_diff, scan
from easy_cheese_review._facts import CODE_SUFFIXES
from easy_cheese_review._model import FACT_NAMES, Evidence, Fact, FactValue, Hit

__all__ = [
    "CODE_SUFFIXES",
    "FACT_NAMES",
    "Evidence",
    "Fact",
    "FactValue",
    "Hit",
    "facts",
    "hunks_from_diff",
    "scan",
]
