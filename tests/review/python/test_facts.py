"""facts(): compat, dependencies, tests, and scope (AC-4, AC-13, AC-14, AC-15)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from easy_cheese_review import FACT_NAMES, Fact, facts
from easy_cheese_schemas import ReviewDimension

WriteTree = Callable[[Path, Mapping[str, str]], Path]


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "base", tmp_path / "head"


def _facts(
    trees: tuple[Path, Path],
    write_tree: WriteTree,
    binary: str,
    *,
    base: Mapping[str, str],
    head: Mapping[str, str],
    changed: list[str],
) -> dict[str, Fact]:
    base_root, head_root = trees
    base_root.mkdir(exist_ok=True)
    head_root.mkdir(exist_ok=True)
    _ = write_tree(base_root, base)
    _ = write_tree(head_root, head)
    return facts(head_root, changed, base=base_root, ast_grep=binary)


def test_every_fact_names_a_review_dimension() -> None:
    assert [ReviewDimension(name).value for name in FACT_NAMES] == list(FACT_NAMES)


# --- compat ---------------------------------------------------------------


def test_compat_records_a_removed_python_function(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"src/api.py": "def keep():\n    pass\n\n\ndef drop():\n    pass\n\n\ndef _private():\n    pass\n"}
    head = {"src/api.py": "def keep():\n    pass\n"}
    result = _facts(trees, write_tree, ast_grep_binary, base=base, head=head, changed=["src/api.py"])
    assert result["compat"] == Fact("yes", {"removed": [{"path": "src/api.py", "name": "drop"}]})


def test_compat_records_typescript_exports_and_a_deleted_file(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {
        "lib/index.ts": "export function open() {}\nexport const close = () => 1;\nconst h = 2;\nexport { h as handle };\n",
        "lib/old.ts": "export class Legacy {}\n",
    }
    head = {"lib/index.ts": "export function open() {}\n"}
    changed = ["lib/index.ts", "lib/old.ts"]
    result = _facts(trees, write_tree, ast_grep_binary, base=base, head=head, changed=changed)
    removed = result["compat"].detail["removed"]
    assert removed == [
        {"path": "lib/index.ts", "name": "close"},
        {"path": "lib/index.ts", "name": "handle"},
        {"path": "lib/old.ts", "name": "Legacy"},
    ]


def test_compat_is_no_when_exports_only_grow(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"src/api.py": "def keep():\n    pass\n"}
    head = {"src/api.py": "def keep():\n    pass\n\n\ndef extra():\n    pass\n"}
    result = _facts(trees, write_tree, ast_grep_binary, base=base, head=head, changed=["src/api.py"])
    assert result["compat"] == Fact("no", {"removed": []})


# --- tests ----------------------------------------------------------------


def test_tests_is_yes_for_source_without_test_change(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"src/x.py": "VALUE = 1\n"}
    result = _facts(trees, write_tree, ast_grep_binary, base={}, head=files, changed=["src/x.py"])
    assert result["tests"] == Fact("yes", {"untested": ["src/x.py"], "sources": 1})


def test_tests_is_no_when_the_matching_test_changes(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"src/x.py": "VALUE = 1\n", "tests/test_x.py": "from x import VALUE\n"}
    changed = ["src/x.py", "tests/test_x.py"]
    result = _facts(trees, write_tree, ast_grep_binary, base={}, head=files, changed=changed)
    assert result["tests"] == Fact("no", {"untested": [], "sources": 1})


def test_tests_matches_typescript_spec_and_test_files(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {
        "src/cart.ts": "export const a = 1;\n",
        "src/cart.test.ts": "import { a } from './cart';\n",
        "src/user/index.ts": "export const b = 1;\n",
        "src/user.spec.ts": "",
        "src/other.ts": "export const c = 1;\n",
    }
    result = _facts(trees, write_tree, ast_grep_binary, base={}, head=files, changed=sorted(files))
    assert result["tests"].detail["untested"] == ["src/other.ts"]


# --- dependencies ---------------------------------------------------------


def test_dependencies_lists_a_new_third_party_import(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {
        "app/main.py": "import json\n",
        "app/helpers.py": "import yaml\n",
        "app/util.py": "VALUE = 1\n",
    }
    head = {
        **base,
        "app/main.py": (
            "import json\nimport os.path\nimport requests\nimport yaml\n"
            "from app import util\nfrom . import helpers\nfrom httpx import (\n    Client,\n)\n"
        ),
    }
    result = _facts(trees, write_tree, ast_grep_binary, base=base, head=head, changed=["app/main.py"])
    dependencies = result["dependencies"]
    assert dependencies.value == "yes"
    assert dependencies.detail["added_imports"] == [
        {"path": "app/main.py", "module": "httpx"},
        {"path": "app/main.py", "module": "requests"},
    ]


def test_dependencies_lists_a_new_npm_package(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"web/a.ts": "import fs from 'fs';\n"}
    head = {
        "web/a.ts": (
            "import fs from 'fs';\nimport path from 'node:path';\nimport { z } from 'zod';\n"
            "import { q } from '@tanstack/query/core';\nimport { b } from './b';\n"
        )
    }
    result = _facts(trees, write_tree, ast_grep_binary, base=base, head=head, changed=["web/a.ts"])
    assert result["dependencies"].detail["added_imports"] == [
        {"path": "web/a.ts", "module": "@tanstack/query"},
        {"path": "web/a.ts", "module": "zod"},
    ]


def test_dependencies_records_manifest_without_its_lockfile(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"pyproject.toml": "[project]\n", "uv.lock": "", "web/package.json": "{}", "web/pnpm-lock.yaml": ""}
    changed = ["pyproject.toml", "web/package.json", "web/pnpm-lock.yaml"]
    result = _facts(trees, write_tree, ast_grep_binary, base=files, head=files, changed=changed)
    dependencies = result["dependencies"]
    assert dependencies.value == "yes"
    assert dependencies.detail["unpaired"] == [{"manifest": "pyproject.toml", "lockfile": "uv.lock"}]
    assert dependencies.detail["lockfiles"] == ["web/pnpm-lock.yaml"]


def test_dependencies_is_no_without_new_imports_or_manifests(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"app/main.py": "import json\n"}
    result = _facts(trees, write_tree, ast_grep_binary, base=files, head=files, changed=["app/main.py"])
    assert result["dependencies"].value == "no"


# --- scope ----------------------------------------------------------------


def test_scope_reports_two_unconnected_groups(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {
        "billing/invoice.py": "from billing.tax import (\n    rate,\n)\n",
        "billing/tax.py": "def rate():\n    return 1\n",
        "tests/test_invoice.py": "from billing import invoice\n",
        "web/app.ts": "import { view } from './view';\n",
        "web/view.ts": "export const view = 1;\n",
    }
    result = _facts(trees, write_tree, ast_grep_binary, base={}, head=files, changed=sorted(files))
    assert result["scope"] == Fact(
        "yes",
        {
            "groups": [
                ["billing/invoice.py", "billing/tax.py", "tests/test_invoice.py"],
                ["web/app.ts", "web/view.ts"],
            ]
        },
    )


def test_scope_joins_relative_python_imports(
    trees: tuple[Path, Path], write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"pkg/a.py": "from . import b\n", "pkg/b.py": "from .c import thing\n", "pkg/c.py": "thing = 1\n"}
    result = _facts(trees, write_tree, ast_grep_binary, base={}, head=files, changed=sorted(files))
    assert result["scope"] == Fact("no", {"groups": [["pkg/a.py", "pkg/b.py", "pkg/c.py"]]})


def test_without_base_compat_and_dependencies_are_unknown(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"src/x.py": "VALUE = 1\n"})
    result = facts(head, ["src/x.py"], ast_grep=ast_grep_binary)
    assert result["compat"].value == "unknown"
    assert result["dependencies"].value == "unknown"
    assert result["tests"].value == "yes"
    assert result["scope"].value == "no"


def test_missing_ast_grep_makes_every_fact_unknown(
    tmp_path: Path, write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = write_tree(tmp_path / "head", {"src/x.py": "VALUE = 1\n"})
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    result = facts(head, ["src/x.py"], base=head)
    assert {name: fact.value for name, fact in result.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "unknown",
        "scope": "unknown",
    }
