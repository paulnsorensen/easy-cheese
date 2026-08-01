"""Repo-root pytest config: make the easy-cheese-schemas package importable.

`src/` puts `easy_cheese_schemas` on the path; `vendor/` supplies its attrs /
cattrs / typing_extensions dependencies as the same extracted trees the .pyz
bundles vendor, so the suite exercises the bytes that actually ship. Both are
prepended so a globally-installed copy never shadows the vendored one.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

for _path in (REPO_ROOT / "src", REPO_ROOT / "vendor"):
    entry = str(_path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
