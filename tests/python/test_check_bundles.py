from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts import check_bundles


def _non_shiv_zipapp() -> bytes:
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("__main__.py", b"print('not Shiv')\n")
    return data.getvalue()


def test_bundle_manifest_rejects_non_shiv_zipapp() -> None:
    with pytest.raises(ValueError, match=r"not a Shiv archive: missing _bootstrap/"):
        _ = check_bundles._manifest(_non_shiv_zipapp())  # pyright: ignore[reportPrivateUsage]


def test_bundle_checker_rejects_new_non_shiv_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "skills" / "demo" / "scripts" / "demo.pyz"
    bundle.parent.mkdir(parents=True)
    _ = bundle.write_bytes(_non_shiv_zipapp())
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main() == 1
    output = capsys.readouterr().out
    assert ".pyz bundles are invalid or stale" in output
    assert "not a Shiv archive" in output
