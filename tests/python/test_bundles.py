from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.bundles import (
    _resolve_bundle_closure,
    _resolve_bundle_sources,
)


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


def _vendor_source(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_resolve_bundle_closure_includes_minimal_vendored_dependencies(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "from . import helper\nimport cattrs\nimport typing_extensions\n",
        helper="VALUE = 1\n",
    )
    dependency_root = tmp_path / "vendor"
    _vendor_source(
        dependency_root,
        "cattrs/__init__.py",
        "from .converter import Converter\n",
    )
    _vendor_source(
        dependency_root,
        "cattrs/converter.py",
        "from attrs import define\nclass Converter: pass\n",
    )
    _vendor_source(dependency_root, "cattrs/unused.py", "UNUSED = True\n")
    _vendor_source(
        dependency_root, "attrs/__init__.py", "def define(value): return value\n"
    )
    _vendor_source(dependency_root, "typing_extensions.py", "Final = object()\n")

    closure = _resolve_bundle_closure("mold", source_root, dependency_root)

    assert {source.archive_path.as_posix() for source in closure} == {
        "attrs/__init__.py",
        "cattrs/__init__.py",
        "cattrs/converter.py",
        "easy_cheese/skills/mold/commands.py",
        "easy_cheese/skills/mold/helper.py",
        "typing_extensions.py",
    }


def test_resolve_bundle_closure_follows_python_312_runtime_branches(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "import sys\n"
        "from typing import TYPE_CHECKING\n"
        "if sys.version_info < (3, 11):\n"
        "    import exceptiongroup\n"
        "else:\n"
        "    import typing_extensions\n"
        "PY_3_14_PLUS = sys.version_info[:2] >= (3, 14)\n"
        "if PY_3_14_PLUS:\n"
        "    import annotationlib\n"
        "if TYPE_CHECKING:\n"
        "    import requests\n",
    )
    dependency_root = tmp_path / "vendor"
    _vendor_source(dependency_root, "typing_extensions.py", "Final = object()\n")

    closure = _resolve_bundle_closure("mold", source_root, dependency_root)

    assert {source.archive_path.as_posix() for source in closure} == {
        "easy_cheese/skills/mold/commands.py",
        "typing_extensions.py",
    }


def test_resolve_bundle_closure_keeps_imports_from_unknown_runtime_branches(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "FLAG = bool()\n"
        "if FLAG:\n"
        "    ACTIVE = True\n"
        "else:\n"
        "    ACTIVE = False\n"
        "def configure():\n"
        "    ACTIVE = False\n"
        "if ACTIVE:\n"
        "    import requests\n",
    )
    dependency_root = tmp_path / "vendor"
    dependency_root.mkdir()

    with pytest.raises(ValueError, match="ambient dependency in bundle: requests"):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_missing_approved_dependency(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    dependency_root = tmp_path / "vendor"
    dependency_root.mkdir()

    with pytest.raises(ValueError, match="approved dependency is unavailable: cattrs"):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_native_approved_dependency(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs._speedups\n")
    dependency_root = tmp_path / "vendor"
    _vendor_source(dependency_root, "cattrs/__init__.py", "")
    (dependency_root / "cattrs" / "_speedups.cpython-312-darwin.so").write_bytes(
        b"native"
    )

    with pytest.raises(
        ValueError, match="native approved dependency in bundle: cattrs._speedups"
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_native_package_initializer(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    native = tmp_path / "vendor" / "cattrs" / "__init__.pyd"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"native")

    with pytest.raises(
        ValueError, match="native approved dependency in bundle: cattrs"
    ):
        _resolve_bundle_closure("mold", source_root, tmp_path / "vendor")


def test_resolve_bundle_closure_rejects_ambient_vendored_dependency(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    dependency_root = tmp_path / "vendor"
    _vendor_source(dependency_root, "cattrs/__init__.py", "import requests\n")

    with pytest.raises(ValueError, match="ambient dependency in bundle: requests"):
        _resolve_bundle_closure("mold", source_root, dependency_root)
