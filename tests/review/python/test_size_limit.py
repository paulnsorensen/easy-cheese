"""The file size limit: oversized files are not scanned, are reported, and never make a fact wrong."""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese_review import Skipped, facts, scan
from tests.review.python.support import WriteTree

LIMIT = 200
PAD = "\n" + "# pad\n" * 60  # 360 bytes: above LIMIT


def _trees(tmp_path: Path, write_tree: WriteTree, base: dict[str, str], head: dict[str, str]) -> tuple[Path, Path]:
    base_root = write_tree(tmp_path / "base", base)
    head_root = write_tree(tmp_path / "head", head)
    base_root.mkdir(exist_ok=True)
    head_root.mkdir(exist_ok=True)
    return base_root, head_root


def test_oversized_head_file_has_no_hits_and_is_reported(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    head = write_tree(tmp_path / "head", {"big.py": "eval(x)" + PAD, "small.py": "eval(x)\n"})

    evidence = scan(head, ["big.py", "small.py"], ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert evidence.status == "ok"
    assert [hit.path for hit in evidence.hits] == ["small.py"]
    assert evidence.skipped == (Skipped("head", "big.py", (head / "big.py").stat().st_size),)
    assert evidence.to_json()["scan"] == {
        "status": "ok",
        "skipped": [{"tree": "head", "path": "big.py", "bytes": (head / "big.py").stat().st_size}],
    }


def test_a_file_at_the_limit_is_scanned(tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str) -> None:
    body = "eval(x)\n"
    head = write_tree(tmp_path / "head", {"edge.py": body})

    evidence = scan(head, ["edge.py"], ast_grep=ast_grep_binary, max_file_bytes=len(body))

    assert evidence.skipped == ()
    assert [hit.path for hit in evidence.hits] == ["edge.py"]


def test_tests_fact_stays_known_with_a_skip_and_no_ast_grep(
    tmp_path: Path, write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = write_tree(tmp_path / "head", {"big.py": "x = 1" + PAD})
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    evidence = scan(head, ["big.py"], max_file_bytes=LIMIT)

    assert evidence.status == "failed:ast-grep-missing"
    assert [item.path for item in evidence.skipped] == ["big.py"]
    assert evidence.facts["tests"].value == "yes"
    assert evidence.facts["tests"].detail == {"untested": ["big.py"], "sources": 1}


def test_scope_no_stays_when_a_skipped_file_is_already_joined(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    """A skipped file can only add imports, and added imports never split a group."""
    _, head = _trees(tmp_path, write_tree, {}, {"pkg/a.py": "from pkg import big\n", "pkg/big.py": "x = 1" + PAD})

    result = facts(head, ["pkg/a.py", "pkg/big.py"], ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert result["scope"].value == "no"


def test_scope_yes_becomes_unknown(tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str) -> None:
    _, head = _trees(tmp_path, write_tree, {}, {"a.py": "x = 1\n", "big.py": "import a" + PAD})

    result = facts(head, ["a.py", "big.py"], ast_grep=ast_grep_binary, max_file_bytes=LIMIT)
    unlimited = facts(head, ["a.py", "big.py"], ast_grep=ast_grep_binary)

    assert unlimited["scope"].value == "no"
    assert result["scope"].value == "unknown"
    assert result["scope"].detail["reason"] == "file-too-large"
    assert result["scope"].detail["skipped"] == ["big.py"]


@pytest.mark.parametrize("tree", ["base", "head"])
def test_compat_no_becomes_unknown_when_a_compared_file_is_skipped(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, tree: str
) -> None:
    small, big = "def gone():\n    pass\n", "def gone():\n    pass\n" + PAD
    base_root, head = _trees(
        tmp_path,
        write_tree,
        {"lib.py": big if tree == "base" else small},
        {"lib.py": big if tree == "head" else small},
    )

    result = facts(head, ["lib.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert result["compat"].value == "unknown"
    assert result["compat"].detail["reason"] == "file-too-large"
    assert result["compat"].detail["skipped"] == ["lib.py"]


def test_compat_yes_stays_for_the_files_it_compared(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(
        tmp_path,
        write_tree,
        {"lib.py": "def gone():\n    pass\n", "big.py": "def a():\n    pass\n" + PAD},
        {"lib.py": "x = 1\n", "big.py": "def a():\n    pass\n" + PAD},
    )

    result = facts(head, ["lib.py", "big.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert result["compat"].value == "yes"
    assert result["compat"].detail == {"removed": [{"path": "lib.py", "name": "gone"}]}


def test_dependencies_no_becomes_unknown_when_a_head_file_is_skipped(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(tmp_path, write_tree, {}, {"big.py": "import requests" + PAD})

    result = facts(head, ["big.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert result["dependencies"].value == "unknown"
    assert result["dependencies"].detail["reason"] == "file-too-large"
    assert result["dependencies"].detail["skipped"] == ["big.py"]


def test_a_manifest_change_keeps_dependencies_yes_despite_a_base_skip(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(
        tmp_path,
        write_tree,
        {"vendor.py": "import requests" + PAD},
        {"app.py": "import requests\n", "pyproject.toml": "[project]\n"},
    )

    result = facts(
        head, ["app.py", "pyproject.toml"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT
    )

    assert result["dependencies"].value == "yes"
    assert result["dependencies"].detail["manifests"] == ["pyproject.toml"]


@pytest.mark.parametrize("name", ["w[x]/b*g.py", "a b {c}.py", "!e.py", "#f.py", "g\\h.py"])
def test_a_skipped_base_file_is_excluded_whatever_its_name(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, name: str
) -> None:
    """The exclusion glob matches the oversized file by its literal name, and only that file."""
    base_root, head = _trees(
        tmp_path,
        write_tree,
        {name: "import requests" + PAD, "sub/" + name: "import requests\n"},
        {"app.py": "import requests\n"},
    )

    evidence = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert [(item.tree, item.path) for item in evidence.skipped] == [("base", name)]
    # The same name one folder down is read, so `requests` is not new.
    assert evidence.facts["dependencies"].value == "no"


@pytest.mark.parametrize("name", ["w[x]/b*g.py", "a b {c}.py", "!e.py", "#f.py", "g\\h.py"])
def test_the_exclusion_glob_matches_a_special_named_file(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str, name: str
) -> None:
    """Only the oversized file imports `requests`; if its glob matched nothing, the scan would read it."""
    base_root, head = _trees(tmp_path, write_tree, {name: "import requests" + PAD}, {"app.py": "import requests\n"})

    evidence = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    # A read file would make `requests` known, so `dependencies` would be `no`.
    assert evidence.facts["dependencies"].value == "unknown"
    assert evidence.facts["dependencies"].detail["skipped"] == [name]


def test_an_oversized_base_file_alone_makes_added_imports_unknown(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(
        tmp_path, write_tree, {"vendor.py": "import requests" + PAD}, {"app.py": "import requests\n"}
    )

    unlimited = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary)
    limited = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert unlimited.facts["dependencies"].value == "no"
    assert limited.facts["dependencies"].value == "unknown"
    detail = limited.facts["dependencies"].detail
    assert (detail["reason"], detail["skipped"]) == ("file-too-large", ["vendor.py"])
    # The unknown fact keeps what the reader needs to judge it.
    assert detail["added_imports"] == [{"path": "app.py", "module": "requests"}]


def test_an_oversized_script_file_in_base_does_not_hide_an_added_python_import(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(
        tmp_path, write_tree, {"vendor.js": "import x from 'requests';" + PAD}, {"app.py": "import requests\n"}
    )

    evidence = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert evidence.facts["dependencies"].value == "yes"
    assert [item.path for item in evidence.skipped] == ["vendor.js"]


def test_an_oversized_python_file_in_base_still_hides_an_added_python_import(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    base_root, head = _trees(
        tmp_path, write_tree, {"vendor.py": "import requests" + PAD}, {"app.py": "import requests\n"}
    )

    evidence = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert evidence.facts["dependencies"].value == "unknown"
    assert evidence.facts["dependencies"].detail["reason"] == "file-too-large"


def test_an_oversized_bazel_file_in_base_is_excluded_from_the_import_scan(
    tmp_path: Path, write_tree: WriteTree, ast_grep_binary: str
) -> None:
    """ast-grep parses `.bazel` as Python in a directory walk, so the size limit must cover it."""
    base_root, head = _trees(
        tmp_path, write_tree, {"BUILD.bazel": "import requests" + PAD}, {"app.py": "import requests\n"}
    )

    evidence = scan(head, ["app.py"], base=base_root, ast_grep=ast_grep_binary, max_file_bytes=LIMIT)

    assert [item.path for item in evidence.skipped] == ["BUILD.bazel"]
