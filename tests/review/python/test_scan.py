"""scan(): packaged rules only, changed lines only, and no ast-grep (AC-3, AC-5, AC-6)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from easy_cheese_review import FACT_NAMES, hunks_from_diff, scan
from tests.review.python.support import WriteTree, fake_ast_grep

BEFORE = """\
def load(path):
    try:
        return read(path)
    except Exception:
        pass


def save(path, data):
    write(path, data)
"""

AFTER = """\
def load(path):
    try:
        return read(path)
    except Exception:
        pass


def save(path, data):
    try:
        write(path, data)
    except Exception:
        pass
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, write_tree: WriteTree) -> Path:
    """A git repository whose working tree adds one swallowed exception."""
    root = write_tree(tmp_path / "repo", {"src/store.py": BEFORE})
    _ = _git(root, "init", "-q")
    _ = _git(root, "add", ".")
    _ = _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    _ = write_tree(root, {"src/store.py": AFTER})
    return root


def test_hit_on_changed_line_only(repo: Path, ast_grep_binary: str) -> None:
    hunks = hunks_from_diff(_git(repo, "diff", "--unified=0"))
    evidence = scan(repo, ["src/store.py"], hunks=hunks, ast_grep=ast_grep_binary)

    assert evidence.status == "ok"
    assert [(hit.rule_id, hit.dimension, hit.line) for hit in evidence.hits] == [
        ("py-swallowed-exception", "correctness", 11)
    ]
    assert evidence.hits[0].base == "high"


def test_without_hunks_every_hit_on_changed_files_stays(repo: Path, ast_grep_binary: str) -> None:
    evidence = scan(repo, ["src/store.py"], ast_grep=ast_grep_binary)
    assert [hit.line for hit in evidence.hits] == [4, 11]


def test_planted_sgconfig_and_rules_change_nothing(
    repo: Path, ast_grep_binary: str, write_tree: WriteTree
) -> None:
    """AC-6 negative control: a PR's own sgconfig.yml and rules never load."""
    hunks = hunks_from_diff(_git(repo, "diff", "--unified=0"))
    clean = scan(repo, ["src/store.py"], hunks=hunks, ast_grep=ast_grep_binary)
    planted_rule = (
        "id: planted-rule\nlanguage: python\nseverity: warning\nmessage: planted\n"
        "metadata: {dimension: correctness, base: blocker}\nrule:\n  pattern: write($$$A)\n"
    )
    _ = write_tree(
        repo,
        {
            "sgconfig.yml": "ruleDirs: [evil]\n",
            "evil/planted.yml": planted_rule,
            "src/sgconfig.yml": "ruleDirs: [../evil]\n",
        },
    )
    # The plant is live: ast-grep without -c loads it from the scanned tree.
    live = subprocess.run(
        [ast_grep_binary, "scan", "--json=stream", "src/store.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "planted-rule" in {json.loads(line)["ruleId"] for line in live.stdout.splitlines()}

    changed = ["src/store.py", "sgconfig.yml", "evil/planted.yml", "src/sgconfig.yml"]
    planted = scan(repo, changed, hunks=hunks, ast_grep=ast_grep_binary)
    assert planted.hits == clean.hits
    assert {hit.rule_id for hit in planted.hits} == {"py-swallowed-exception"}


def test_missing_ast_grep_returns_no_hits_and_keeps_tests_known(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: without ast-grep on PATH no hit exists and only `tests` stays known."""
    monkeypatch.setenv("PATH", str(repo / "empty-bin"))
    evidence = scan(repo, ["src/store.py"], base=repo)

    assert evidence.status == "failed:ast-grep-missing"
    assert evidence.hits == ()
    assert list(evidence.facts) == list(FACT_NAMES)
    assert {name: fact.value for name, fact in evidence.facts.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "yes",
        "scope": "unknown",
    }
    assert evidence.facts["compat"].detail == {"reason": "ast-grep ast-grep-missing"}
    assert evidence.to_json()["scan"] == {"status": "failed:ast-grep-missing", "skipped": []}


def test_failed_run_reports_reason(repo: Path, tmp_path: Path, write_tree: WriteTree) -> None:
    fake = fake_ast_grep(tmp_path, write_tree, "#!/bin/sh\nexit 3\n")
    evidence = scan(repo, ["src/store.py"], base=repo, ast_grep=fake)
    assert evidence.status == "failed:exit-3"
    assert evidence.hits == ()
    assert {name: fact.value for name, fact in evidence.facts.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "yes",
        "scope": "unknown",
    }
    assert evidence.facts["scope"].detail == {"reason": "ast-grep exit-3"}


def test_a_changed_file_without_a_hunk_entry_keeps_every_hit(
    repo: Path, ast_grep_binary: str, write_tree: WriteTree
) -> None:
    """A reviewed tree's `.gitattributes` cannot hide hits by making git print no hunk."""
    _ = write_tree(repo, {".gitattributes": "*.py -diff\n"})
    diff = _git(repo, "diff", "--unified=0")
    assert "Binary files" in diff
    evidence = scan(repo, ["src/store.py"], hunks=hunks_from_diff(diff), ast_grep=ast_grep_binary)
    assert evidence.status == "ok"
    assert [hit.line for hit in evidence.hits] == [4, 11]


def test_a_deletion_that_creates_a_hit_keeps_it(
    tmp_path: Path, ast_grep_binary: str, write_tree: WriteTree
) -> None:
    before = "def save(path, data):\n    try:\n        write(path, data)\n    except Exception:\n        log(path)\n        pass\n"
    root = write_tree(tmp_path / "del", {"src/store.py": before})
    _ = _git(root, "init", "-q")
    _ = _git(root, "add", ".")
    _ = _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    _ = write_tree(root, {"src/store.py": before.replace("        log(path)\n", "")})
    hunks = hunks_from_diff(_git(root, "diff", "--unified=0"))
    evidence = scan(root, ["src/store.py"], hunks=hunks, ast_grep=ast_grep_binary)
    assert [(hit.rule_id, hit.line) for hit in evidence.hits] == [("py-swallowed-exception", 4)]


def test_symlink_out_of_tree_is_not_scanned(
    repo: Path, tmp_path: Path, ast_grep_binary: str, write_tree: WriteTree
) -> None:
    outside = write_tree(tmp_path / "outside", {"secret.py": "eval(token)\n"}) / "secret.py"
    (repo / "src" / "link.py").symlink_to(outside)
    evidence = scan(repo, ["src/link.py"], ast_grep=ast_grep_binary)
    assert evidence.status == "ok"
    assert evidence.hits == ()


@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", ""])
def test_changed_paths_must_stay_inside_the_tree(repo: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="relative and inside the tree"):
        _ = scan(repo, [bad])


def test_hunks_from_diff_reads_head_side_ranges() -> None:
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -3,0 +4,2 @@\n+x\n+y\n@@ -9 +11 @@\n-z\n+w\n@@ -20,2 +22,0 @@\n-q\n-r\n"
        "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
    )
    assert hunks_from_diff(diff) == {"a.py": [(4, 5), (11, 11), (22, 23)]}
