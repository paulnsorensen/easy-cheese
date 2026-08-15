"""Regression coverage for phase snapshots containing directory symlinks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CUT_ROOT = REPO_ROOT / "src" / "cut"


def _load_red_gate() -> ModuleType:
    sys.path.insert(0, str(CUT_ROOT))
    spec = importlib.util.spec_from_file_location(
        "red_gate_internal_symlink_under_test", CUT_ROOT / "red_gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


red_gate = _load_red_gate()


def test_phase_entry_accepts_snapshotted_directory_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    library = tmp_path / ".venv" / "lib"
    library.mkdir(parents=True)
    state = library / "state.txt"
    state.write_text("inside\n", encoding="utf-8")
    link = tmp_path / ".venv" / "lib64"
    link.symlink_to("lib", target_is_directory=True)
    (tmp_path / "production-state.txt").write_text("red\n", encoding="utf-8")

    namespace = tmp_path / ".cheese" / "cut"
    namespace.mkdir(parents=True)
    plan_path = namespace / "internal-symlink.plan.json"
    token_path = namespace / "internal-symlink.phase.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer": "cut",
                "work_id": "internal-directory-symlink",
                "project_key": "validator-project",
                "production_paths": ["production-state.txt"],
                "baseline_checks": [
                    {
                        "id": "baseline",
                        "argv": [sys.executable, "-c", "pass"],
                        "cwd": ".",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        red_gate.begin_phase(plan_path, token_path)
    except red_gate.GateValidationError as exc:
        pytest.fail(f"internal directory symlink rejected: {exc}")

    snapshot = json.loads(token_path.read_text(encoding="utf-8"))["snapshot"]
    link_mode = stat.S_IMODE(link.lstat().st_mode)
    library_mode = stat.S_IMODE(library.stat().st_mode)
    state_mode = stat.S_IMODE(state.stat().st_mode)
    state_digest = hashlib.sha256(state.read_bytes()).hexdigest()
    assert snapshot[".venv/lib64"] == (
        f"symlink:lib:mode:{link_mode:o}:target:directory:mode:{library_mode:o}"
    )
    assert snapshot[".venv/lib/state.txt"] == (
        f"file:{state_digest}:mode:{state_mode:o}"
    )
