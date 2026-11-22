"""The PyPI release check decides whether a publish job uploads a version."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pypi_release_check  # noqa: E402


def _run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: dict[str, object] | int
) -> str:
    """Run main() against a stubbed PyPI and return what it wrote to GITHUB_OUTPUT."""
    pyproject = tmp_path / "pyproject.toml"
    _ = pyproject.write_text('[project]\nname = "pkg"\nversion = "1.2.3"\n', encoding="utf-8")
    output = tmp_path / "github_output"
    monkeypatch.setenv("PROJECT", "pkg")
    monkeypatch.setenv("PYPROJECT", str(pyproject))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def fake_urlopen(url: str, timeout: float) -> io.BytesIO:
        assert url == "https://pypi.org/pypi/pkg/json"
        assert timeout == 30
        if isinstance(response, int):
            raise urllib.error.HTTPError(url, response, "stub", Message(), None)
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    pypi_release_check.main()
    return output.read_text(encoding="utf-8")


def test_first_release_publishes_when_pypi_has_no_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(tmp_path, monkeypatch, 404) == "version=1.2.3\nshould_publish=true\n"


def test_new_version_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run(tmp_path, monkeypatch, {"releases": {"1.2.2": []}})
    assert out == "version=1.2.3\nshould_publish=true\n"


def test_released_version_skips_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run(tmp_path, monkeypatch, {"releases": {"1.2.2": [], "1.2.3": []}})
    assert out == "version=1.2.3\nshould_publish=false\n"


def test_pypi_error_other_than_404_fails_the_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(urllib.error.HTTPError):
        _ = _run(tmp_path, monkeypatch, 503)
    assert not (tmp_path / "github_output").exists()
