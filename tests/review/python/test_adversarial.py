"""Adversarial cases for hunks, scan edges, compat, dependencies, tests, and scope facts.

A test marked `xfail(strict=True)` pins a production defect. The reason names it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from easy_cheese_review import Fact, facts, hunks_from_diff, scan
from tests.review.python.support import WriteTree, compute_facts, fake_ast_grep

# The swallowed exception below is one hit that spans lines 4 to 5.
SWALLOW = "def a():\n    try:\n        x()\n    except Exception:\n        pass\n"


def _removed(result: Mapping[str, Fact]) -> list[tuple[str, str]]:
    removed = result["compat"].detail["removed"]
    assert isinstance(removed, list)
    return [(str(item["path"]), str(item["name"])) for item in removed]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]


# --- hunks_from_diff ------------------------------------------------------


def test_hunks_default_count_is_one_line() -> None:
    diff = "--- a/x.py\n+++ b/x.py\n@@ -3 +5 @@\n-a\n+b\n"
    assert hunks_from_diff(diff) == {"x.py": [(5, 5)]}


def test_hunks_map_a_deletion_to_its_neighbors_and_skip_deleted_files() -> None:
    diff = (
        "--- a/x.py\n+++ b/x.py\n@@ -4,2 +3,0 @@\n-a\n-b\n"
        "--- a/gone.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n"
    )
    assert hunks_from_diff(diff) == {"x.py": [(3, 4)]}


def test_hunks_follow_a_renamed_file_to_its_new_path() -> None:
    diff = (
        "diff --git a/old.py b/new.py\nsimilarity index 80%\nrename from old.py\nrename to new.py\n"
        "--- a/old.py\n+++ b/new.py\n@@ -2 +2,2 @@\n-a\n+b\n+c\n"
    )
    assert hunks_from_diff(diff) == {"new.py": [(2, 3)]}


def test_hunks_strip_the_timestamp_after_a_tab() -> None:
    diff = "--- a/x.py\t2024-01-01\n+++ b/x.py\t2024-01-02\n@@ -1 +1 @@\n-a\n+b\n"
    assert hunks_from_diff(diff) == {"x.py": [(1, 1)]}


def test_hunks_unquote_a_git_quoted_path() -> None:
    diff = '--- "a/we ird.py"\n+++ "b/we ird.py"\n@@ -1 +1 @@\n-a\n+b\n'
    assert hunks_from_diff(diff) == {"we ird.py": [(1, 1)]}


def test_hunks_ignore_an_added_line_that_looks_like_a_file_header() -> None:
    diff = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,0 +2,2 @@\n+first\n+++ trap\n"
        "@@ -9,0 +12 @@\n+later\n"
    )
    assert hunks_from_diff(diff) == {"x.py": [(2, 3), (12, 12)]}


# --- scan: hunk edges -----------------------------------------------------


@pytest.mark.parametrize(
    ("ranges", "kept"),
    [
        ([(4, 4)], True),
        ([(5, 5)], True),
        ([(1, 4)], True),
        ([(5, 9)], True),
        ([(2, 3)], False),
        ([(1, 3)], False),
        ([(6, 9)], False),
        ([], False),
    ],
)
def test_hit_survives_only_when_a_hunk_overlaps_its_lines(
    tmp_path: Path,
    write_tree: WriteTree,
    ast_grep_binary: str,
    ranges: list[tuple[int, int]],
    kept: bool,
) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    evidence = scan(head, ["src/s.py"], hunks={"src/s.py": ranges}, ast_grep=ast_grep_binary)
    assert evidence.status == "ok"
    assert [(hit.line, hit.end_line) for hit in evidence.hits] == ([(4, 5)] if kept else [])


def test_a_changed_file_missing_from_hunks_keeps_the_hit(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    evidence = scan(head, ["src/s.py"], hunks={"src/other.py": [(1, 9)]}, ast_grep=ast_grep_binary)
    assert [(hit.line, hit.end_line) for hit in evidence.hits] == [(4, 5)]


def test_empty_hunks_mapping_keeps_every_hit(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    assert len(scan(head, ["src/s.py"], hunks={}, ast_grep=ast_grep_binary).hits) == 1
    assert len(scan(head, ["src/s.py"], ast_grep=ast_grep_binary).hits) == 1


def test_changed_path_spelled_with_dot_slash_matches_the_hunk_key(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    evidence = scan(head, ["./src//s.py"], hunks={"src/s.py": [(4, 4)]}, ast_grep=ast_grep_binary)
    assert [hit.path for hit in evidence.hits] == ["src/s.py"]


# --- scan: odd paths ------------------------------------------------------


@pytest.mark.parametrize("name", ["src/-dash.py", "src/with space.py", "src/ünicöde.py", "src/a.b.py"])
def test_scan_reads_files_with_unusual_names(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, name: str
) -> None:
    head = write_tree(tmp_path / "head", {name: SWALLOW})
    evidence = scan(head, [name], ast_grep=ast_grep_binary)
    assert [hit.path for hit in evidence.hits] == [name]


def test_scan_skips_a_changed_directory_named_like_a_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"pkg.py/inner.py": SWALLOW})
    evidence = scan(head, ["pkg.py", "pkg.py/"], ast_grep=ast_grep_binary)
    assert evidence.status == "ok"
    assert evidence.hits == ()
    assert evidence.facts["tests"] == Fact("no", {"untested": [], "sources": 0})


def test_scan_skips_a_symlink_that_leaves_the_tree(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    outside = write_tree(tmp_path / "outside", {"s.py": SWALLOW})
    head = write_tree(tmp_path / "head", {"src/keep.py": "X = 1\n"})
    (head / "src/link.py").symlink_to(outside / "s.py")
    evidence = scan(head, ["src/link.py", "src/keep.py"], ast_grep=ast_grep_binary)
    assert evidence.hits == ()
    assert evidence.facts["tests"].detail["untested"] == ["src/keep.py"]


def test_scan_skips_a_deleted_changed_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"src/keep.py": SWALLOW})
    evidence = scan(head, ["src/keep.py", "src/gone.py"], ast_grep=ast_grep_binary)
    assert evidence.status == "ok"
    assert [hit.path for hit in evidence.hits] == ["src/keep.py"]


@pytest.mark.parametrize("folder", [".hidden", "gen"])
def test_scan_reads_a_changed_file_in_a_hidden_or_ignored_folder(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, folder: str
) -> None:
    head = write_tree(tmp_path / "head", {f"{folder}/s.py": SWALLOW, ".gitignore": "gen/\n"})
    evidence = scan(head, [f"{folder}/s.py"], ast_grep=ast_grep_binary)
    assert [hit.path for hit in evidence.hits] == [f"{folder}/s.py"]


# --- scan: fake binary failures -------------------------------------------


def test_scan_reports_bad_json_from_ast_grep(tmp_path: Path, write_tree: WriteTree) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    fake = fake_ast_grep(tmp_path, write_tree, "#!/bin/sh\necho 'not json'\n")
    evidence = scan(head, ["src/s.py"], ast_grep=fake)
    assert evidence.status == "failed:bad-json"
    assert evidence.hits == ()
    assert {name: fact.value for name, fact in evidence.facts.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "yes",
        "scope": "unknown",
    }
    assert evidence.facts["scope"].detail == {"reason": "ast-grep bad-json"}


def test_scan_reports_a_non_object_json_row(tmp_path: Path, write_tree: WriteTree) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    fake = fake_ast_grep(tmp_path, write_tree, "#!/bin/sh\necho '[1]'\n")
    assert scan(head, ["src/s.py"], ast_grep=fake).status == "failed:bad-json"


def test_scan_drops_a_row_with_missing_fields(tmp_path: Path, write_tree: WriteTree) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    fake = fake_ast_grep(tmp_path, write_tree, "#!/bin/sh\necho '{\"ruleId\": \"r\", \"file\": \"src/s.py\"}'\n")
    evidence = scan(head, ["src/s.py"], ast_grep=fake)
    assert evidence.status == "ok"
    assert evidence.hits == ()


def test_facts_are_unknown_when_every_ast_grep_run_fails(
    tmp_path: Path, write_tree: WriteTree
) -> None:
    head = write_tree(tmp_path / "head", {"src/s.py": SWALLOW})
    fake = fake_ast_grep(tmp_path, write_tree, "#!/bin/sh\nexit 2\n")
    result = facts(head, ["src/s.py"], base=head, ast_grep=fake)
    # `tests` needs no ast-grep run, so it stays known.
    assert {name: fact.value for name, fact in result.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "yes",
        "scope": "unknown",
    }
    assert result["compat"].detail == {"reason": "ast-grep exit-2"}


# --- compat ---------------------------------------------------------------


def test_compat_sees_async_and_decorated_python_exports(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {
        "a.py": (
            "async def fetch():\n    pass\n\n\n@deco\ndef wrapped():\n    pass\n\n\n"
            "class K:\n    pass\n\n\nCONST = 1\n\n\ndef _p():\n    pass\n"
        )
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head={"a.py": ""}, changed=["a.py"])
    assert _removed(result) == [("a.py", "CONST"), ("a.py", "K"), ("a.py", "fetch"), ("a.py", "wrapped")]


def test_compat_counts_a_rename_to_private_as_a_removal(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"a.py": "def keep():\n    pass\n"}
    head = {"a.py": "def _keep():\n    pass\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["a.py"])
    assert _removed(result) == [("a.py", "keep")]


def test_compat_counts_an_export_that_loses_its_keyword_as_removed(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"a.ts": "export const x = 1;\nexport function f() {}\n"}
    head = {"a.ts": "const x = 1;\nexport function f() {}\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["a.ts"])
    assert _removed(result) == [("a.ts", "x")]


def test_compat_sees_removed_typescript_type_exports_and_reexports(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {
        "b.ts": (
            "export default function main() {}\nexport { a } from './x';\nexport type T = number;\n"
            "export interface I {}\nexport enum E { A }\nexport { default as dflt } from './z';\n"
        )
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head={"b.ts": ""}, changed=["b.ts"])
    assert [name for _, name in _removed(result)] == ["E", "I", "T", "a", "default", "dflt"]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "export default 5;\n",
            marks=pytest.mark.xfail(
                strict=True,
                reason="ast-grep outline 0.51.2 omits `export default <expression>`, so its removal is not seen",
            ),
        ),
        "export * as ns from './w';\n",
        "export * from './all';\n",
    ],
)
def test_compat_sees_removed_default_value_and_namespace_reexport(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, text: str
) -> None:
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={"c.ts": text}, head={"c.ts": ""}, changed=["c.ts"])
    assert result["compat"].value == "yes"


def test_compat_ignores_the_inline_type_modifier_in_an_export_clause(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"a.ts": "type Foo = 1;\nconst bar = 2;\nexport { type Foo, bar };\n"}
    head = {"a.ts": "type Foo = 1;\nconst bar = 2;\nexport { Foo, bar };\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["a.ts"])
    assert result["compat"] == Fact("no", {"removed": []})


@pytest.mark.xfail(
    strict=True,
    reason="ast-grep outline 0.51.2 omits `export type { ... }`, so moving to it reads as a removal",
)
def test_compat_accepts_a_type_only_export_clause(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"a.ts": "type Foo = 1;\nexport { type Foo };\n"}
    head = {"a.ts": "type Foo = 1;\nexport type { Foo };\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["a.ts"])
    assert result["compat"] == Fact("no", {"removed": []})


def test_compat_does_not_report_a_renamed_default_export(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"a.ts": "export default function main() {}\n"}
    head = {"a.ts": "export default function start() {}\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["a.ts"])
    assert result["compat"] == Fact("no", {"removed": []})


def test_compat_reports_every_export_of_a_deleted_python_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"src/a.py": "def one():\n    pass\n", "src/b.py": "def two():\n    pass\n"}
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base=base, head={"src/b.py": "def two():\n    pass\n"},
        changed=["src/a.py", "src/b.py"],
    )
    assert _removed(result) == [("src/a.py", "one")]


# --- dependencies ---------------------------------------------------------


def _added(result: Mapping[str, Fact]) -> list[tuple[str, str]]:
    added = result["dependencies"].detail["added_imports"]
    assert isinstance(added, list)
    return [(str(item["path"]), str(item["module"])) for item in added]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]


def test_dependencies_ignore_future_and_stdlib_submodules(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"a.py": "from __future__ import annotations\nimport os.path\nimport xml.etree.ElementTree\nimport zoneinfo\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={"a.py": ""}, head=head, changed=["a.py"])
    assert result["dependencies"].value == "no"


def test_dependencies_find_an_import_inside_a_function_or_a_guard(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {
        "a.py": (
            "def f():\n    import requests\n\n\n"
            "try:\n    import yaml\nexcept ImportError:\n    yaml = None\n"
            "if True:\n    from httpx import (\n        Client,\n    )\n"
        )
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={"a.py": ""}, head=head, changed=["a.py"])
    assert _added(result) == [("a.py", "httpx"), ("a.py", "requests"), ("a.py", "yaml")]


def test_dependencies_treat_a_src_layout_package_as_local(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"src/mypkg/__init__.py": "", "tests/test_m.py": "import mypkg\nfrom mypkg.sub import thing\n"}
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=["tests/test_m.py"]
    )
    assert result["dependencies"].value == "no"


def test_dependencies_treat_a_sibling_module_as_local(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"scripts/run.py": "import helper\n", "scripts/helper.py": "X = 1\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=["scripts/run.py"])
    assert result["dependencies"].value == "no"


def test_dependencies_treat_a_monorepo_package_as_local(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {
        "packages/lib/src/lib/__init__.py": "",
        "packages/lib/tests/test_lib.py": "import lib\n",
    }
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=["packages/lib/tests/test_lib.py"]
    )
    assert result["dependencies"].value == "no"


def test_dependencies_do_not_mix_python_and_npm_packages(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"tool.py": "import yaml\n", "web/a.ts": "export const a = 1;\n"}
    head = {**base, "web/a.ts": "import yaml from 'yaml';\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["web/a.ts"])
    assert _added(result) == [("web/a.ts", "yaml")]


def test_dependencies_normalize_npm_subpaths_and_builtins(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"web/a.ts": "import { f } from 'lodash';\n"}
    head = {
        "web/a.ts": (
            "import { f } from 'lodash/fp';\nimport p from 'fs/promises';\n"
            "import q from 'node:test';\nimport r from 'assert/strict';\n"
            "import type { T } from '@scope/pkg/deep/er';\nimport { u } from '@/alias';\n"
            "import { v } from '#internal';\nexport * from 'rxjs/operators';\n"
            "import 'side-effect-pkg';\n"
        )
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=["web/a.ts"])
    assert _added(result) == [
        ("web/a.ts", "@scope/pkg"),
        ("web/a.ts", "rxjs"),
        ("web/a.ts", "side-effect-pkg"),
    ]


def test_dependencies_pair_a_nested_manifest_with_the_root_lockfile(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"web/package.json": "{}", "package-lock.json": "{}"}
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base=files, head=files, changed=["web/package.json"]
    )
    detail = result["dependencies"].detail
    assert detail["unpaired"] == [{"manifest": "web/package.json", "lockfile": "package-lock.json"}]


def test_dependencies_accept_a_changed_root_lockfile_for_a_nested_manifest(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"web/package.json": "{}", "package-lock.json": "{}"}
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base=files, head=files,
        changed=["web/package.json", "package-lock.json"],
    )
    assert result["dependencies"].detail["unpaired"] == []


def test_dependencies_prefer_the_nested_lockfile_over_the_root_one(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"web/package.json": "{}", "web/yarn.lock": "", "pnpm-lock.yaml": ""}
    result = compute_facts(
        tmp_path, write_tree, ast_grep_binary, base=files, head=files,
        changed=["web/package.json", "pnpm-lock.yaml"],
    )
    assert result["dependencies"].detail["unpaired"] == [
        {"manifest": "web/package.json", "lockfile": "web/yarn.lock"}
    ]


def test_dependencies_ignore_a_manifest_without_any_lockfile(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    files = {"pyproject.toml": "[project]\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=files, head=files, changed=["pyproject.toml"])
    assert result["dependencies"].value == "yes"
    assert result["dependencies"].detail["unpaired"] == []


# --- tests fact -----------------------------------------------------------


def test_tests_fact_treats_a_helper_in_a_test_folder_as_a_test_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"tests/helpers.py": "X = 1\n", "conftest.py": "", "app/mod_test.py": "", "app/mod.py": "Y = 1\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["tests"] == Fact("no", {"untested": [], "sources": 1})


def test_tests_fact_pairs_a_package_init_with_its_package_test(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"src/billing/__init__.py": "X = 1\n", "tests/test_billing.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["tests"].value == "no"


# --- scope ----------------------------------------------------------------


def _groups(result: Mapping[str, Fact]) -> list[list[str]]:
    groups = result["scope"].detail["groups"]
    assert isinstance(groups, list)
    return groups  # pyright: ignore[reportUnknownVariableType]


def test_scope_joins_a_two_level_relative_python_import(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {
        "pkg/sub/a.py": "from .. import b\nfrom ..side.mod import y\n",
        "pkg/b.py": "B = 1\n",
        "pkg/side/mod.py": "y = 1\n",
        "pkg/unrelated.py": "Z = 1\n",
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["pkg/b.py", "pkg/side/mod.py", "pkg/sub/a.py"], ["pkg/unrelated.py"]]
    assert result["scope"].value == "yes"


def test_scope_keeps_every_file_when_a_relative_import_climbs_above_the_root(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"a.py": "from ... import x\nfrom .... import y\n", "x.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert sorted(path for group in _groups(result) for path in group) == ["a.py", "x.py"]


def test_scope_joins_a_python_package_init_import(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"pkg/__init__.py": "from .a import A\n", "pkg/a.py": "A = 1\n", "other/__init__.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["other/__init__.py"], ["pkg/__init__.py", "pkg/a.py"]]


def test_scope_resolves_a_relative_import_to_one_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"a.py": "from . import b\n", "b.py": "", "docs/b.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["a.py", "b.py"], ["docs/b.py"]]


def test_scope_resolves_typescript_extension_and_index_imports(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {
        "web/app.ts": (
            "import { x } from './x.js';\nimport { lib } from './lib';\n"
            "import { s } from '../shared/s';\nimport './side';\nexport * from './re';\n"
        ),
        "web/x.ts": "export const x = 1;\n",
        "web/lib/index.ts": "export const lib = 1;\n",
        "shared/s.ts": "export const s = 1;\n",
        "web/side.ts": "",
        "web/re.ts": "",
        "web/lonely.ts": "",
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [
        ["shared/s.ts", "web/app.ts", "web/lib/index.ts", "web/re.ts", "web/side.ts", "web/x.ts"],
        ["web/lonely.ts"],
    ]


def test_scope_resolves_a_tsx_component_imported_as_jsx(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"web/page.tsx": "import { B } from './box.jsx';\n", "web/box.tsx": "export const B = 1;\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["scope"] == Fact("no", {"groups": [["web/box.tsx", "web/page.tsx"]]})


def test_scope_joins_a_multi_line_typescript_import(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"web/a.ts": "import {\n  one,\n  two,\n} from './b';\n", "web/b.ts": "export const one = 1;\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["scope"].value == "no"


def test_scope_does_not_join_python_and_script_files_by_name(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"a.py": "import b\n", "b.ts": "export const b = 1;\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["scope"].value == "yes"


def test_scope_ignores_a_python_file_with_a_syntax_error(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"a.py": "from . import (\n", "b.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["a.py"], ["b.py"]]


# --- normalize_changed through the public API ----------------------------


@pytest.mark.parametrize("bad", ["", "/etc/passwd", "a/../b.py", "../x.py", ".."])
def test_changed_paths_that_leave_the_tree_are_refused(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, bad: str
) -> None:
    head = write_tree(tmp_path / "head", {"a.py": ""})
    with pytest.raises(ValueError, match="relative and inside the tree"):
        _ = scan(head, ["a.py", bad], ast_grep=ast_grep_binary)
    with pytest.raises(ValueError, match="relative and inside the tree"):
        _ = facts(head, [bad], ast_grep=ast_grep_binary)


def test_changed_path_with_a_backslash_is_scanned(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    """A backslash is a legal POSIX file-name character, so the path is not refused."""
    head = write_tree(tmp_path / "head", {"a\\b.py": SWALLOW})
    evidence = scan(head, ["a\\b.py"], ast_grep=ast_grep_binary)
    assert [hit.path for hit in evidence.hits] == ["a\\b.py"]


def test_changed_path_with_dots_inside_a_name_is_accepted(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"..hidden.py": SWALLOW})
    evidence = scan(head, ["..hidden.py", "./..hidden.py"], ast_grep=ast_grep_binary)
    assert [hit.path for hit in evidence.hits] == ["..hidden.py"]


# --- review findings ------------------------------------------------------


def test_tests_fact_does_not_count_a_deleted_test(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"src/base.py": "A = 1\n", "tests/test_base.py": "import base\n"}
    head = {"src/base.py": "A = 2\n"}
    changed = ["src/base.py", "tests/test_base.py"]
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head=head, changed=changed)
    assert result["tests"] == Fact("yes", {"untested": ["src/base.py"], "sources": 1})


def test_tests_fact_pairs_private_modules_and_prefixed_test_names(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {
        "pkg/_facts.py": "A = 1\n",
        "tests/test_facts.py": "",
        "pkg/review_evidence.py": "B = 1\n",
        "tests/test_age_review_evidence.py": "",
        "pkg/other.py": "C = 1\n",
    }
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert result["tests"].detail["untested"] == ["pkg/other.py"]


def test_compat_ignores_names_removed_from_test_modules(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base = {"tests/test_x.py": "def test_a():\n    pass\n", "tests/conftest.py": "def fixture():\n    pass\n"}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base=base, head={}, changed=sorted(base))
    assert result["compat"] == Fact("no", {"removed": []})


def test_scope_ignores_an_ambiguous_suffix_match(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"app/main.py": "import utils\n", "billing/utils.py": "", "accounts/utils.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["accounts/utils.py"], ["app/main.py"], ["billing/utils.py"]]


def test_scope_keeps_a_unique_suffix_match(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = {"tests/test_m.py": "from pkg import m\n", "src/pkg/m.py": ""}
    result = compute_facts(tmp_path, write_tree, ast_grep_binary, base={}, head=head, changed=sorted(head))
    assert _groups(result) == [["src/pkg/m.py", "tests/test_m.py"]]


def test_a_failed_outline_run_spoils_only_compat(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    fake = fake_ast_grep(
        tmp_path,
        write_tree,
        f'#!/bin/sh\nif [ "$3" = outline ]; then exit 2; fi\nexec "{ast_grep_binary}" "$@"\n',
    )
    result = compute_facts(
        tmp_path,
        write_tree,
        fake,
        base={"src/x.py": "A = 1\n"},
        head={"src/x.py": "import requests\n"},
        changed=["src/x.py"],
    )
    assert result["compat"] == Fact("unknown", {"reason": "ast-grep exit-2"})
    assert result["dependencies"].value == "yes"
    assert result["tests"].value == "yes"
    assert result["scope"].value == "no"


def test_bare_run_with_shell_true_is_not_a_subprocess_hit(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(
        tmp_path / "head",
        {"a.py": "invoke.run(cmd, shell=True)\nrun(cmd, shell=True)\nsubprocess.run(cmd, shell=True)\n"},
    )
    evidence = scan(head, ["a.py"], ast_grep=ast_grep_binary)
    shell_hits = [hit.line for hit in evidence.hits if hit.rule_id == "py-subprocess-shell-true"]
    assert shell_hits == [3]
