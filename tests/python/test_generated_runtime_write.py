"""The build writes the same generated runtime sources it checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _extra in (ROOT / "vendor", ROOT / "src", ROOT / "scripts"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("attrs") is None,
    reason="runtime requirements are not installed",
)

import build_pyz  # noqa: E402


def test_write_generated_runtime_leaves_current_sources_unchanged() -> None:
    """A repository whose generated sources are current needs no write."""
    build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]

    assert build_pyz.write_generated_runtime() == []


def test_write_generated_runtime_restores_a_stale_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writer produces exactly what the staleness check demands."""
    source, artifact_name, render = build_pyz.GENERATED_RUNTIME_SOURCES[0]
    stale = tmp_path / source.name
    _ = stale.write_bytes(b"# stale\n")
    monkeypatch.setattr(
        build_pyz, "GENERATED_RUNTIME_SOURCES", ((stale, artifact_name, render),)
    )

    with pytest.raises(RuntimeError, match=r"is stale"):
        build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]

    assert build_pyz.write_generated_runtime() == [stale]
    assert stale.read_bytes() == source.read_bytes()
    build_pyz._validate_generated_runtime()  # pyright: ignore[reportPrivateUsage]


def test_write_generated_command_reports_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command exits successfully and builds no archive."""
    assert build_pyz.main(["build_pyz.py", "--write-generated"]) == 0
    assert "built " not in capsys.readouterr().out
