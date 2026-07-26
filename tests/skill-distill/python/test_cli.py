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
    output = tmp_path / ".context" / "dataset.json"

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


def test_cli_exposes_the_complete_locked_lifecycle() -> None:
    from skill_distill.cli import _parser

    parser = _parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, __import__("argparse")._SubParsersAction)
    )
    assert set(subparsers.choices) == {
        "prepare",
        "freeze-human-labels",
        "export-llm-pairs",
        "record-llm-labels",
        "reconcile",
        "score",
        "validate",
        "propose",
        "apply",
        "verify",
    }


def test_generated_output_outside_context_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepare = ModuleType("skill_distill.prepare")
    prepare.prepare_to_path = lambda *_: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "skill_distill.prepare", prepare)

    with pytest.raises(SystemExit) as error:
        main([
            "prepare",
            "--report", str(tmp_path / "report.json"),
            "--adversarial-controls", str(tmp_path / "controls.json"),
            "--out", str(tmp_path / "dataset.json"),
        ])

    assert error.value.code == 2
