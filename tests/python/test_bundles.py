from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.bundles import (
    _STDLIB_MODULES,
    _VENDORED_CLOSURES,
    _VENDORED_OPTIONAL_IMPORTS,
    _VENDORED_ROOTS,
    _VendoredSources,
    _import_references,
    _resolve_bundle_closure,
    _resolve_bundle_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_resolve_bundle_sources_allows_attribute_reference_shadowed_by_native_sibling(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "from easy_cheese.skills.mold.helper import VALUE\n",
        helper="VALUE = 1\n",
    )
    commands = source_root / "easy_cheese" / "skills" / "mold" / "commands.py"
    helper = source_root / "easy_cheese" / "skills" / "mold" / "helper.py"
    commands.with_name("VALUE.so").write_bytes(b"native")

    assert _resolve_bundle_sources("mold", source_root) == (commands, helper)


def test_resolve_bundle_sources_stdlib_import_ignores_stray_native_sibling(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import json\n")
    commands = source_root / "easy_cheese" / "skills" / "mold" / "commands.py"
    commands.with_name("json.so").write_bytes(b"native")

    assert _resolve_bundle_sources("mold", source_root) == (commands,)


def _vendor_source(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _vendor_tree(root: Path) -> None:
    _vendor_source(root, "attr/__init__.py", "VALUE = 1\n")
    _vendor_source(root, "attrs/__init__.py", "from attr import VALUE\n")
    _vendor_source(
        root,
        "cattrs/__init__.py",
        "from .converter import Converter\n",
    )
    _vendor_source(
        root,
        "cattrs/converter.py",
        "from attrs import define\nclass Converter: pass\n",
    )
    _vendor_source(root, "cattrs/unused.py", "UNUSED = True\n")
    _vendor_source(root, "typing_extensions.py", "Final = object()\n")
    _vendor_source(root, "cattr/__init__.py", "from cattrs import Converter\n")
    _vendor_source(root, "cattr/converters.py", "from cattrs import Converter\n")


def test_resolve_bundle_closure_includes_only_reachable_vendored_root(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import attrs\n")
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)

    closure = _resolve_bundle_closure("mold", source_root, dependency_root)

    assert {source.archive_path.as_posix() for source in closure} == {
        "attr/__init__.py",
        "attrs/__init__.py",
        "easy_cheese/skills/mold/commands.py",
    }


def test_vendored_root_stages_whole_pinned_tree_not_just_reachable_modules(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path,
        "from . import helper\nimport cattrs\n",
        helper="VALUE = 1\n",
    )
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)

    closure = _resolve_bundle_closure("mold", source_root, dependency_root)

    assert {source.archive_path.as_posix() for source in closure} == {
        "attr/__init__.py",
        "attrs/__init__.py",
        "cattrs/__init__.py",
        "cattrs/converter.py",
        "cattrs/unused.py",
        "typing_extensions.py",
        "easy_cheese/skills/mold/commands.py",
        "easy_cheese/skills/mold/helper.py",
    }


def test_cattr_root_stages_full_five_root_closure(tmp_path: Path) -> None:
    source_root = _source_tree(tmp_path, "import cattr\n")
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)

    closure = _resolve_bundle_closure("mold", source_root, dependency_root)

    assert {source.archive_path.as_posix() for source in closure} == {
        "attr/__init__.py",
        "attrs/__init__.py",
        "cattr/__init__.py",
        "cattr/converters.py",
        "cattrs/__init__.py",
        "cattrs/converter.py",
        "cattrs/unused.py",
        "typing_extensions.py",
        "easy_cheese/skills/mold/commands.py",
    }


def test_resolve_bundle_closure_rejects_missing_vendored_root(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    dependency_root = tmp_path / "vendor"
    dependency_root.mkdir()

    with pytest.raises(
        ValueError, match="vendored dependency tree is missing: attr"
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_missing_vendored_submodule(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs.missing\n")
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)

    with pytest.raises(
        ValueError, match=r"vendored submodule is missing: cattrs\.missing"
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_first_party_import_of_optional_vendored_module(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(
        tmp_path, "from cattrs.preconf.orjson import make_converter\n"
    )
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    _vendor_source(dependency_root, "cattrs/preconf/__init__.py", "")
    _vendor_source(
        dependency_root,
        "cattrs/preconf/orjson.py",
        "from orjson import dumps\n\n\ndef make_converter():\n    return dumps\n",
    )

    with pytest.raises(
        ValueError,
        match=r"vendored module has unstaged optional imports: cattrs\.preconf\.orjson",
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_real_vendored_optional_import(
    tmp_path: Path,
) -> None:
    dependency_root = REPO_ROOT / "vendor"
    if not dependency_root.is_dir():
        pytest.skip("vendor tree not built; run `just vendor`")
    source_root = _source_tree(
        tmp_path, "from cattrs.preconf.orjson import make_converter\n"
    )

    with pytest.raises(
        ValueError,
        match=r"vendored module has unstaged optional imports: cattrs\.preconf\.orjson",
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_native_vendored_dependency(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    (dependency_root / "cattrs" / "_speedups.cpython-312-darwin.so").write_bytes(
        b"native"
    )

    with pytest.raises(
        ValueError, match="native vendored dependency in bundle: cattrs"
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_resolve_bundle_closure_rejects_native_vendored_package_initializer(
    tmp_path: Path,
) -> None:
    source_root = _source_tree(tmp_path, "import cattrs\n")
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    (dependency_root / "cattrs" / "__init__.pyd").write_bytes(b"native")

    with pytest.raises(
        ValueError, match="native vendored dependency in bundle: cattrs"
    ):
        _resolve_bundle_closure("mold", source_root, dependency_root)


def test_vendored_sources_load_rejects_duplicate_module(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_source(dependency_root, "typing_extensions.py", "Final = object()\n")
    _vendor_source(
        dependency_root, "typing_extensions/__init__.py", "Final = object()\n"
    )

    with pytest.raises(
        ValueError,
        match="duplicate module in vendored source roots",
    ):
        _VendoredSources.load(dependency_root)


def test_vendored_sources_has_native_matches_exact_suffix_file(
    tmp_path: Path,
) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    (dependency_root / "attr.so").write_bytes(b"native")

    sources = _VendoredSources.load(dependency_root)

    assert sources.has_native("attr")


def test_vendored_sources_has_native_matches_abi_tagged_glob(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    (dependency_root / "attr.cpython-312-darwin.so").write_bytes(b"native")

    sources = _VendoredSources.load(dependency_root)

    assert sources.has_native("attr")


def test_vendored_sources_stage_tests_module(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    _vendor_source(dependency_root, "cattrs/tests.py", "import cattrs\n")

    sources = _VendoredSources.load(dependency_root)

    assert sources.contains("cattrs.tests")


def test_vendored_sources_load_skips_pycache(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    _vendor_source(dependency_root, "cattrs/__pycache__/cattrs.foo.py", "")

    sources = _VendoredSources.load(dependency_root)

    assert not sources.contains("cattrs.__pycache__.cattrs.foo")


def test_vendored_sources_rejects_undeclared_ambient_import(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    _vendor_source(dependency_root, "attr/undeclared.py", "import requests\n")

    with pytest.raises(
        ValueError, match=r"undeclared vendored import in attr\.undeclared: requests"
    ):
        _VendoredSources.load(dependency_root)


def test_vendored_sources_allows_declared_optional_import(tmp_path: Path) -> None:
    dependency_root = tmp_path / "vendor"
    _vendor_tree(dependency_root)
    (dependency_root / "cattrs" / "_compat.py").write_text(
        "import exceptiongroup\n", encoding="utf-8"
    )

    sources = _VendoredSources.load(dependency_root)

    assert sources.contains("cattrs._compat")


def test_vendored_scan_matches_declared_optional_imports() -> None:
    dependency_root = REPO_ROOT / "vendor"
    if not dependency_root.is_dir():
        pytest.skip("vendor tree not built; run `just vendor`")

    sources = _VendoredSources.load(dependency_root)
    all_sources = sources.sources_for_roots(tuple(sorted(_VENDORED_ROOTS)))

    undeclared: dict[str, set[str]] = {}
    for source in all_sources:
        roots = (
            {
                reference.name.split(".", 1)[0]
                for reference in _import_references(source)
                if not reference.is_attribute_reference
            }
            - _STDLIB_MODULES
            - _VENDORED_ROOTS
        )
        if roots:
            undeclared[source.module] = roots

    declared = {
        module: set(roots) for module, roots in _VENDORED_OPTIONAL_IMPORTS.items()
    }
    assert undeclared == declared


def test_vendored_closures_match_real_vendor_import_graph() -> None:
    dependency_root = REPO_ROOT / "vendor"
    if not dependency_root.is_dir():
        pytest.skip("vendor tree not built; run `just vendor`")

    sources = _VendoredSources.load(dependency_root)
    all_sources = sources.sources_for_roots(tuple(sorted(_VENDORED_ROOTS)))

    edges: dict[str, set[str]] = {root: {root} for root in _VENDORED_ROOTS}
    for source in all_sources:
        source_root = source.module.split(".", 1)[0]
        for reference in _import_references(source):
            if reference.is_attribute_reference:
                continue
            target_root = reference.name.split(".", 1)[0]
            if target_root in _VENDORED_ROOTS:
                edges[source_root].add(target_root)

    closure = {root: set(reached) for root, reached in edges.items()}
    changed = True
    while changed:
        changed = False
        for root, reached in closure.items():
            for other in tuple(reached):
                if not closure[other] <= reached:
                    reached |= closure[other]
                    changed = True

    for root, expected in _VENDORED_CLOSURES.items():
        assert closure[root] == set(expected)
