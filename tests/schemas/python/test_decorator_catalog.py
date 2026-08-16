"""Decorator-marker to schema-catalog wiring: contracts.py, schema_runtime.py,
and the build-only _schema_catalog_compiler.py."""

from __future__ import annotations

import ast
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import build_pyz
import pytest
from easy_cheese_schemas import _schema_catalog as catalog
from easy_cheese_schemas import _schema_catalog_compiler as compiler
from easy_cheese_schemas import contracts, schema_runtime

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_catalog_omits_uri_for_contract_without_marker() -> None:
    marker = contracts.CurdPlan.__contract_slug__
    del contracts.CurdPlan.__contract_slug__
    try:
        namespace: dict[str, Any] = {}
        exec(compiler.render(compiler.collect(contracts)), namespace)
    finally:
        contracts.CurdPlan.__contract_slug__ = marker
    assert namespace["REGISTERED_CONTRACT_SCHEMA_URIS"] == (
        catalog.REGISTERED_CONTRACT_SCHEMA_URIS - {catalog.CURD_PLAN_SCHEMA_URI}
    )


def test_registry_contracts_match_marked_classes() -> None:
    marked = {
        value
        for value in vars(contracts).values()
        if isinstance(value, type) and getattr(value, "__contract_slug__", None)
    }
    registered = {entry.contract for entry in schema_runtime._REGISTERED_CONTRACTS}
    assert registered == marked


def test_schema_constraints_assignments_are_marker_scoped() -> None:
    source = REPO_ROOT / "src" / "easy_cheese_schemas" / "contracts.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignments = []
    for statement in tree.body:
        scope = statement.name if isinstance(statement, ast.FunctionDef) else None
        for node in ast.walk(statement):
            if not isinstance(node, ast.Assign):
                continue
            assignments.extend(
                (scope, target.value.id)
                for target in node.targets
                if isinstance(target, ast.Attribute)
                and target.attr == "__schema_constraints__"
                and isinstance(target.value, ast.Name)
            )

    assert not hasattr(schema_runtime, "_model_constraints")
    assert assignments == [
        ("_list_of", "validate"),
        ("_string_list", "validate"),
    ]
    assert contracts._list_of(str, non_empty=True, limit=3).__schema_constraints__ == {
        "maxItems": 3,
        "minItems": 1,
    }
    assert contracts._string_list(non_empty=True, limit=4).__schema_constraints__ == {
        "maxItems": 4,
        "uniqueItems": True,
        "minItems": 1,
    }


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_schema_catalog_compiler_is_absent_from_runtime_artifacts(tmp_path: Path) -> None:
    compiler_source = (
        REPO_ROOT / "src" / "easy_cheese_schemas" / "_schema_catalog_compiler.py"
    )
    assert compiler_source.is_file()
    built = [
        build_pyz.build_bundle(skill, tmp_path / f"{skill}.pyz")
        for skill in build_pyz.PACKAGE_TREES
    ]
    assert len(built) == 6
    leaked = [
        archive.name
        for archive in built
        if any(
            name.endswith("/_schema_catalog_compiler.py")
            or name == "_schema_catalog_compiler.py"
            for name in zipfile.ZipFile(archive).namelist()
        )
    ]
    wheel_dir = tmp_path / "wheel"
    wheel = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert wheel.returncode == 0, wheel.stdout + wheel.stderr
    wheel_path = next(wheel_dir.glob("*.whl"), None)
    assert wheel_path is not None, wheel.stdout + wheel.stderr
    wheel_names = zipfile.ZipFile(wheel_path).namelist()
    assert not leaked and not any(
        name.endswith("/_schema_catalog_compiler.py") for name in wheel_names
    )
