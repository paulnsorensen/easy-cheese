"""The generic publication gateway does not import a phase-specific seam."""

from __future__ import annotations

import os
import subprocess
import sys

_SEAM_LOADED_BY_GATEWAY = """
import sys
import easy_cheese.shared.publication
print('easy_cheese.shared.mold_cook_handoff' in sys.modules)
"""


def test_the_gateway_does_not_import_the_phase_seam() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    completed = subprocess.run(
        [sys.executable, "-c", _SEAM_LOADED_BY_GATEWAY],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == "False"
