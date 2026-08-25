#!/usr/bin/env python3
"""Compatibility entrypoint for Mold's package-layout gate graph."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from easy_cheese.skills.mold import gate_graph as _implementation  # noqa: E402

for _name, _value in vars(_implementation).items():
    if not _name.startswith("__"):
        globals()[_name] = _value
dot_available = _implementation.dot_available


def main(argv: list[str]) -> int:
    """Delegate after forwarding monkeypatchable compatibility attributes."""
    _implementation.dot_available = dot_available
    _implementation.subprocess = subprocess
    return _implementation.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
