from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from easy_cheese.shared.bundles import bundle_name, minimal_closure
from scripts import build_pyz

ROOT = Path(__file__).resolve().parents[2] / "src" / "easy_cheese"
SHARED = Path(__file__).resolve().parents[2] / "shared" / "scripts"


def _skill_root(tmp_path: Path, source: str, helper: str | None = None) -> Path:
    root = tmp_path / "src" / "easy_cheese"
    skill = root / "skills" / "mold"
    skill.mkdir(parents=True)
    for package in (root, root / "skills", skill):
        (package / "__init__.py").write_text("", encoding="utf-8")
    (skill / "commands.py").write_text(source, encoding="utf-8")
    if helper is not None:
        (skill / "helper.py").write_text(helper, encoding="utf-8")
    return root


def test_minimal_closure_excludes_unreachable_schema_and_other_skills():
    closure = minimal_closure("mold", ROOT, SHARED)
    relative = {
        path.relative_to(ROOT.parent).as_posix()
        for path in closure
        if path.is_relative_to(ROOT.parent)
    }
    assert "easy_cheese/skills/mold/commands.py" in relative
    assert "easy_cheese_schemas/handoff.py" in relative
    assert not any("easy_cheese/skills/cook" in name for name in relative)
    assert "easy_cheese_schemas/benchmarks.py" not in relative
    assert "easy_cheese_schemas/wheypoint.py" not in relative


def test_minimal_closure_derives_flat_shared_runtime_from_static_imports():
    closure = minimal_closure("cook", ROOT, SHARED)
    shared = {path.name for path in closure if path.parent == SHARED}
    assert {"cli.py", "findings_cli.py", "handoff.py", "paths.py"} <= shared
    assert "artifact_path.py" not in shared


def test_native_rejection(tmp_path):
    root = _skill_root(tmp_path, "import native\n")
    (root / "skills" / "mold" / "native.so").write_bytes(b"native")
    with pytest.raises(ValueError, match="native"):
        minimal_closure("mold", root)


def test_deferred_import_is_included(tmp_path):
    root = _skill_root(
        tmp_path,
        "def run():\n    from easy_cheese.skills.mold import helper\n    return helper.VALUE\n",
        "VALUE = 1\n",
    )
    closure = minimal_closure("mold", root)
    assert root / "skills" / "mold" / "helper.py" in closure


def test_ambient_and_cross_skill_dependencies_reject(tmp_path):
    root = _skill_root(tmp_path, "import requests\n")
    with pytest.raises(ValueError, match="ambient dependency"):
        minimal_closure("mold", root)
    (root / "skills" / "mold" / "commands.py").write_text(
        "from easy_cheese.skills.cook import commands\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="cross-skill"):
        minimal_closure("mold", root)


def test_subprocess_isolation_uses_a_same_named_minimal_layout_bundle(tmp_path):
    archive = build_pyz.build_layout_bundle("mold", tmp_path / "mold.pyz")
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert archive.name == bundle_name("mold")
    assert "easy_cheese_schemas/benchmarks.py" not in names
    assert "cattrs/preconf/orjson.py" not in names
    assert "cattrs/strategies/_subclasses.py" not in names
    assert not any(name.endswith((".so", ".pyd", ".dylib")) for name in names)
    assert not any("easy_cheese/skills/cook" in name for name in names)

    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(archive.resolve()), "--help"],
        cwd=tmp_path,
        env={"PATH": ""},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_layout_bundle_carries_canonical_schema_version(tmp_path):
    archive = build_pyz.build_layout_bundle("mold", tmp_path / "mold.pyz")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import easy_cheese_schemas; print(easy_cheese_schemas.__version__)",
        ],
        cwd=tmp_path,
        env={"PATH": "", "PYTHONPATH": str(archive)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.1.0"


def test_archive_name_must_match_owner(tmp_path):
    with pytest.raises(ValueError, match="archive name"):
        build_pyz.build_layout_bundle("mold", tmp_path / "other.pyz")
    with pytest.raises(ValueError):
        bundle_name("mold/cook")
