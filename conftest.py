"""Repo-root pytest config for canonical packages under src/."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
os.environ["PYTHONPATH"] = os.pathsep.join(
    part for part in (str(SRC_ROOT), os.environ.get("PYTHONPATH", "")) if part
)
