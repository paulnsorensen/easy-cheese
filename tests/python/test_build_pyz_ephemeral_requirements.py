from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402


def test_bundle_requirements_are_written_beside_the_temporary_wheelhouse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    expected = "demo==1.0 --hash=sha256:" + "a" * 64 + "\n"

    def _stub_resolved_requirements(_skill: str, _wheelhouse: Path) -> str:
        return expected

    monkeypatch.setattr(build_pyz, "_resolved_requirements", _stub_resolved_requirements)

    requirements = build_pyz._requirements_for("cut", wheelhouse)

    assert requirements == tmp_path / "cut-requirements.txt", (
        "ephemeral-requirements-path"
    )
    assert requirements.read_text(encoding="utf-8") == expected


def test_build_cli_rejects_removed_update_locks_option(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(build_pyz, "SKILLS", ("cut",))

    def _stub_build_bundles(_destinations: dict[str, Path]) -> dict[str, Path]:
        return {}

    monkeypatch.setattr(build_pyz, "build_bundles", _stub_build_bundles)

    with pytest.raises(SystemExit) as exc:
        _ = build_pyz.main(
            [
                "build_pyz.py",
                "--update-locks",
                "--out-dir",
                str(tmp_path),
                "cut",
            ]
        )
    assert exc.value.code == 2
