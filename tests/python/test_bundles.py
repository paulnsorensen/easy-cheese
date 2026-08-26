from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.bundles import bundle_name, minimal_closure


def _package(tmp_path: Path, commands: str, *, helper: str | None = None) -> Path:
    root = tmp_path / "src" / "easy_cheese"
    skill = root / "skills" / "mold"
    skill.mkdir(parents=True)
    for package in (root, root / "skills", skill):
        (package / "__init__.py").write_text("", encoding="utf-8")
    (skill / "commands.py").write_text(commands, encoding="utf-8")
    if helper is not None:
        (skill / "helper.py").write_text(helper, encoding="utf-8")
    return root


def test_bundle_name_is_owned_by_one_skill() -> None:
    assert bundle_name("mold") == "mold.pyz"
    for invalid in ("", "mold/cook", "mold\\cook"):
        with pytest.raises(ValueError, match="invalid skill name"):
            bundle_name(invalid)


def test_minimal_closure_includes_deferred_same_skill_import(tmp_path: Path) -> None:
    root = _package(
        tmp_path,
        "def run():\n    from easy_cheese.skills.mold import helper\n    return helper.VALUE\n",
        helper="VALUE = 1\n",
    )

    assert minimal_closure("mold", root) == (
        root / "skills" / "mold" / "commands.py",
        root / "skills" / "mold" / "helper.py",
    )


def test_minimal_closure_includes_flat_shared_import(tmp_path: Path) -> None:
    root = _package(tmp_path, "import paths\n")
    shared = tmp_path / "shared"
    shared.mkdir()
    helper = shared / "paths.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")

    assert minimal_closure("mold", root, shared) == (
        helper,
        root / "skills" / "mold" / "commands.py",
    )


def test_minimal_closure_rejects_cross_skill_import(tmp_path: Path) -> None:
    root = _package(tmp_path, "from easy_cheese.skills.cook import commands\n")
    cook = root / "skills" / "cook"
    cook.mkdir()
    (cook / "commands.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="cross-skill import"):
        minimal_closure("mold", root)


def test_minimal_closure_rejects_ambient_and_native_dependencies(
    tmp_path: Path,
) -> None:
    root = _package(tmp_path, "import requests\n")
    with pytest.raises(ValueError, match="ambient dependency"):
        minimal_closure("mold", root)

    commands = root / "skills" / "mold" / "commands.py"
    commands.write_text("import native\n", encoding="utf-8")
    commands.with_name("native.so").write_bytes(b"native")
    with pytest.raises(ValueError, match="native ambient dependency"):
        minimal_closure("mold", root)
