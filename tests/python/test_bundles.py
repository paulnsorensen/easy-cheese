from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.bundles import _resolve_bundle_sources


def _source_tree(tmp_path: Path, commands: str, *, helper: str | None = None) -> Path:
    source_root = tmp_path / "src"
    package_root = source_root / "easy_cheese"
    skill = package_root / "skills" / "mold"
    skill.mkdir(parents=True)
    for package in (package_root, package_root / "skills", skill):
        (package / "__init__.py").write_text("", encoding="utf-8")
    (skill / "commands.py").write_text(commands, encoding="utf-8")
    if helper is not None:
        (skill / "helper.py").write_text(helper, encoding="utf-8")
    return source_root


def test_resolve_bundle_sources_includes_deferred_same_skill_import(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "def run():\n    from easy_cheese.skills.mold import helper\n    return helper.VALUE\n",
        helper="VALUE = 1\n",
    )
    package_root = source_root / "easy_cheese"

    assert _resolve_bundle_sources("mold", source_root) == (
        package_root / "skills" / "mold" / "commands.py",
        package_root / "skills" / "mold" / "helper.py",
    )


def test_resolve_bundle_sources_includes_canonical_shared_import(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "from easy_cheese.shared import paths\n")
    package_root = source_root / "easy_cheese"
    shared = package_root / "shared"
    shared.mkdir()
    (shared / "__init__.py").write_text("", encoding="utf-8")
    helper = shared / "paths.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")

    assert _resolve_bundle_sources("mold", source_root) == (
        helper,
        package_root / "skills" / "mold" / "commands.py",
    )


@pytest.mark.parametrize(
    "module", ("json", "attrs", "easy_cheese_schemas._schema_catalog")
)
def test_resolve_bundle_sources_allows_unbundled_dependencies(
    tmp_path: Path, module: str
) -> None:
    source_root = _source_tree(tmp_path, f"import {module}\n")

    assert _resolve_bundle_sources("mold", source_root) == (
        source_root / "easy_cheese" / "skills" / "mold" / "commands.py",
    )


def test_resolve_bundle_sources_rejects_cross_skill_import(tmp_path: Path) -> None:
    source_root = _source_tree(
        tmp_path, "from easy_cheese.skills.cook import commands\n"
    )
    cook = source_root / "easy_cheese" / "skills" / "cook"
    cook.mkdir()
    (cook / "commands.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="cross-skill import"):
        _resolve_bundle_sources("mold", source_root)


def test_resolve_bundle_sources_rejects_skill_name_prefix_collision(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "from easy_cheese.skills.moldy import commands\n",
    )
    sibling = source_root / "easy_cheese" / "skills" / "moldy"
    sibling.mkdir()
    (sibling / "commands.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="cross-skill import"):
        _resolve_bundle_sources("mold", source_root)


def test_resolve_bundle_sources_rejects_unresolved_internal_dependency(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import easy_cheese.missing\n")

    with pytest.raises(
        ValueError,
        match=r"unresolved internal dependency: easy_cheese\.missing",
    ):
        _resolve_bundle_sources("mold", source_root)


def test_resolve_bundle_sources_rejects_legacy_flat_shared_import(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import paths\n")
    shared = tmp_path / "shared" / "scripts"
    shared.mkdir(parents=True)
    (shared / "paths.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"ambient dependency in bundle: paths"):
        _resolve_bundle_sources("mold", source_root)


def test_resolve_bundle_sources_rejects_legacy_flat_schema_import(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import contracts\n")
    schemas = source_root / "easy_cheese_schemas"
    schemas.mkdir()
    (schemas / "__init__.py").write_text("", encoding="utf-8")
    (schemas / "contracts.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=r"ambient dependency in bundle: contracts"):
        _resolve_bundle_sources("mold", source_root)


def test_resolve_bundle_sources_requires_source_root(tmp_path: Path) -> None:
    source_root = _source_tree(tmp_path, "")

    with pytest.raises(ValueError, match="unknown Python skill: mold"):
        _resolve_bundle_sources("mold", source_root / "easy_cheese")


def test_resolve_bundle_sources_rejects_ambient_and_native_dependencies(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import requests\n")
    with pytest.raises(ValueError, match="ambient dependency"):
        _resolve_bundle_sources("mold", source_root)

    commands = source_root / "easy_cheese" / "skills" / "mold" / "commands.py"
    commands.write_text("import native\n", encoding="utf-8")
    commands.with_name("native.so").write_bytes(b"native")
    with pytest.raises(ValueError, match="native ambient dependency"):
        _resolve_bundle_sources("mold", source_root)
