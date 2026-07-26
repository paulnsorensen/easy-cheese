from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import pytest

from skill_distill.cli import main


def test_prepare_routes_validated_paths_to_dataset_builder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, Path, Path]] = []
    prepare = ModuleType("skill_distill.prepare")
    prepare.prepare_to_path = lambda report, controls, output: calls.append(  # type: ignore[attr-defined]
        (report, controls, output)
    )
    monkeypatch.setitem(sys.modules, "skill_distill.prepare", prepare)

    report = tmp_path / "overlap.json"
    controls = tmp_path / "adversarial.json"
    output = tmp_path / "dataset.json"

    assert main(
        [
            "prepare",
            "--report",
            str(report),
            "--adversarial-controls",
            str(controls),
            "--out",
            str(output),
        ]
    ) == 0
    assert calls == [(report, controls, output)]


def test_prepare_dependency_is_loaded_only_when_command_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "skill_distill.prepare", raising=False)

    with pytest.raises(SystemExit) as error:
        main([])

    assert error.value.code == 2
