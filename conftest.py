"""Repo-root pytest config for canonical packages under src/."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
# easy-cheese-review is its own distribution with its own src/ layout.
REVIEW_SRC_ROOT = REPO_ROOT / "packages" / "easy-cheese-review" / "src"
for entry in (REPO_ROOT / "scripts", REVIEW_SRC_ROOT, SRC_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
os.environ["PYTHONPATH"] = os.pathsep.join(
    part
    for part in (str(SRC_ROOT), str(REVIEW_SRC_ROOT), os.environ.get("PYTHONPATH", ""))
    if part
)