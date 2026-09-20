"""The publication gateway dispatches deep validation through a registry.

The generic gateway knows only which payload schema URIs require a host-side
pass over the bytes they reference. The owning module supplies that pass. A
required URI with no registered validator must fail closed, because a silent
skip would let an unvalidated handoff reach a consumer.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from easy_cheese_schemas.mold_cook import MOLD_COOK_HANDOFF_SCHEMA_URI

from easy_cheese.shared import mold_cook_handoff, publication
from tests.python.test_mold_cook_publication import _published_handoff  # pyright: ignore[reportPrivateUsage]

_REGISTERED_AFTER_OWNER_IMPORT = """
import easy_cheese.shared.mold_cook_handoff
import easy_cheese.shared.publication as publication
from easy_cheese_schemas.mold_cook import MOLD_COOK_HANDOFF_SCHEMA_URI
print(MOLD_COOK_HANDOFF_SCHEMA_URI in publication._DEEP_VALIDATORS)
"""

_SEAM_LOADED_BY_GATEWAY = """
import sys
import easy_cheese.shared.publication
print('easy_cheese.shared.mold_cook_handoff' in sys.modules)
"""


def test_required_uri_without_a_registered_validator_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointer_path, _ = _published_handoff(tmp_path)
    monkeypatch.setattr(publication, "_DEEP_VALIDATORS", {})

    with pytest.raises(
        publication.PublicationError,
        match=f"no deep validator registered for {MOLD_COOK_HANDOFF_SCHEMA_URI}",
    ):
        _ = mold_cook_handoff.accept_mold_cook_handoff(
            pointer_path, artifact_root=tmp_path
        )


def test_registered_validator_receives_the_canonical_value_and_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointer_path, handoff = _published_handoff(tmp_path)
    seen: list[tuple[object, Path]] = []

    def _record(value: object, artifact_root: Path) -> object:
        seen.append((value, artifact_root))
        return value

    monkeypatch.setattr(
        publication, "_DEEP_VALIDATORS", {MOLD_COOK_HANDOFF_SCHEMA_URI: _record}
    )

    accepted = mold_cook_handoff.accept_mold_cook_handoff(
        pointer_path, artifact_root=tmp_path
    )

    assert accepted.canonical.value == handoff
    assert seen == [(handoff, tmp_path)]


def test_importing_the_owner_module_registers_the_handoff_validator() -> None:
    """Importing the Mold-to-Cook seam alone arms deep validation.

    The check runs in a child process so that the imports this test module
    already performed cannot register the validator on its behalf. The
    gateway itself must not import the seam, so a consumer that only imports
    ``publication`` gets the fail-closed error above instead of a skip.
    """
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _REGISTERED_AFTER_OWNER_IMPORT,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == "True"


def test_the_gateway_does_not_import_the_phase_seam() -> None:
    """The generic gateway must not depend downward on one phase pair."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _SEAM_LOADED_BY_GATEWAY,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == "False"


def test_the_mold_cook_handoff_uri_requires_deep_validation() -> None:
    assert MOLD_COOK_HANDOFF_SCHEMA_URI in publication._DEEP_VALIDATION_REQUIRED  # pyright: ignore[reportPrivateUsage]
    assert (
        publication._DEEP_VALIDATORS[MOLD_COOK_HANDOFF_SCHEMA_URI]  # pyright: ignore[reportPrivateUsage]
        is mold_cook_handoff.validate_mold_cook_handoff
    )
