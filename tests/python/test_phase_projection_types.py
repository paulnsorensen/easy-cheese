"""The build's phase projection types must match the emitted phase data."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import cast, get_type_hints

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _extra in (ROOT / "vendor", ROOT / "src", ROOT):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("attrs") is None,
    reason="runtime requirements are not installed",
)

from easy_cheese_schemas import COMPILED_TRANSITION_REGISTRY  # noqa: E402

from scripts import render_generated_regions as render  # noqa: E402


def _hints(declaration: type) -> dict[str, type]:
    return cast("dict[str, type]", get_type_hints(declaration))


def test_projected_phase_fields_match_their_declared_types() -> None:
    """Every projected phase field carries the type the build declares.

    `TransitionRegistry.to_data()` emits the contract version numbers as
    strings. A wrong declaration hides that behind the projection cast.
    """
    phases = cast(
        "list[render._Phase]",  # pyright: ignore[reportPrivateUsage]
        COMPILED_TRANSITION_REGISTRY.to_data(),
    )
    assert phases, "expected at least one compiled phase"

    phase_hints = _hints(render._Phase)  # pyright: ignore[reportPrivateUsage]
    version_hints = _hints(render._ContractVersion)  # pyright: ignore[reportPrivateUsage]
    output_hints = _hints(render._PhaseOutput)  # pyright: ignore[reportPrivateUsage]

    for phase in phases:
        row = cast("dict[str, object]", cast(object, phase))
        assert set(row) == set(phase_hints)
        assert isinstance(row["source"], str)
        assert isinstance(row["input_schema_uris"], list)
        assert all(isinstance(uri, str) for uri in phase["input_schema_uris"])

        version = cast("dict[str, object]", cast(object, phase["contract_version"]))
        assert set(version) == set(version_hints)
        for name, declared in version_hints.items():
            assert isinstance(version[name], declared), (name, version[name])

        for output in phase["outputs"]:
            fields = cast("dict[str, object]", cast(object, output))
            assert set(fields) == set(output_hints)
            for name, declared in output_hints.items():
                assert isinstance(fields[name], declared), (name, fields[name])
