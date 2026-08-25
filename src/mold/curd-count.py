#!/usr/bin/env python3
"""Compatibility entrypoint for Mold's package-layout curd counter."""
from __future__ import annotations

import sys
from pathlib import Path

# PARALLEL_THRESHOLD remains package-owned; this wrapper preserves the legacy
# source path for callers during migration.
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from easy_cheese.skills.mold import curd_count as _implementation  # noqa: E402

for _name, _value in vars(_implementation).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

main = _implementation.main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
