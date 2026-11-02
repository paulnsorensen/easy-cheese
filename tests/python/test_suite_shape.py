"""`press.pyz test-shape` reports test-suite bloat in a real temporary Git repository."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

import fromargs
import pytest

from easy_cheese.skills.press import commands
from easy_cheese.skills.press.suite_shape import Finding, suite_shape

BASE_FILE = '''
import pytest

OLD_TABLE = list(range(20))


@pytest.mark.ac(
    "gh-1:AC-1"
)
def test_widget_accepts_a_name():
    assert True


@pytest.mark.parametrize("value", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
def test_widget_old_table(value):
    assert value >= 0


@pytest.mark.parametrize("value", [0, 1, 2])
def test_widget_small_table(value):
    assert value >= 0


@pytest.mark.parametrize("trial", range(2))
def test_widget_trials(trial):
    assert trial >= 0
'''

GROWN_TABLE = '''
@pytest.mark.ac("gh-1:AC-1")
@pytest.mark.parametrize("value", [0, 1, 2, 3, 4, 5, 6, 7, 8])
def test_widget_small_table(value):
'''

BASE_FILE_ADDITION = '''

@pytest.mark.parametrize("value", [0, 1, 2, 3, 4, 5, 6, 7, 8])
def test_widget_new_table(value):
    assert value >= 0
'''

PRESS_FILE = '''
import subprocess
import sys
from subprocess import check_call

import pytest

HOSTILE = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7, "h": 8, "i": 9}
CLASSES = ["empty", "too-long", "bad-char"]


def run(code):
    return subprocess.run([sys.executable, "-c", code], check=False)


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile(name):
    assert name


@pytest.mark.parametrize("trial", range(200))
def test_trials(trial):
    assert trial >= 0


@pytest.mark.parametrize("trial", range(5))
def test_five_trials(trial):
    assert trial >= 0


@pytest.mark.parametrize("seed", range(3))
def test_three_seeds(seed):
    assert seed >= 0


@pytest.mark.parametrize("key", ["a", "b", "c"])
@pytest.mark.parametrize("shape", ["x", "y", "z"])
def test_cross(key, shape):
    assert key and shape


@pytest.mark.parametrize("left", [1, 2])
@pytest.mark.parametrize("right", [1, 2])
def test_small_cross(left, right):
    assert left and right


@pytest.mark.parametrize("code", ["0", "1"])
def test_exit(code):
    run(f"raise SystemExit({code})")


@pytest.mark.parametrize("code", [str(number) for number in range(2)])
def test_aliased_exit(code):
    check_call(["true", code])


@pytest.mark.parametrize("code", ["0", "1"])
def test_interpreter_argv(code, launch):
    command = [sys.executable, "-c", code]
    launch(command)


@pytest.mark.parametrize("module", ["a", "b"])
def test_argv_names_the_interpreter(module):
    assert [sys.executable, "-m", module][0]


def test_one_process():
    run("pass")


@pytest.mark.parametrize("value", CLASSES)
def test_classes(value):
    assert value


# A comment that quotes a marker is not a test: @pytest.mark.ac("gh-2:AC-1")
class TestGroup:
    @pytest.mark.ac("gh-1:AC-1")
    def test_marked(self):
        assert True

    @pytest.mark.ac("gh-2:AC-1")
    def test_unique_marker(self):
        assert True
'''

LONE_PRESS_FILE = '''
def test_gizmo_has_no_base_file():
    assert True
'''

NON_ASCII_FILE = '''
import pytest


@pytest.mark.parametrize("value", [0, 1, 2, 3, 4, 5, 6, 7, 8])
def test_café_table(value):
    assert value >= 0
'''

EXPECTED = {
    ("press-file-beside-base", "tests/test_press_widget.py", ""),
    ("rows-over-cap", "tests/test_press_widget.py", "test_hostile"),
    ("range-trials", "tests/test_press_widget.py", "test_trials"),
    ("range-trials", "tests/test_press_widget.py", "test_five_trials"),
    ("cross-product-over-cap", "tests/test_press_widget.py", "test_cross"),
    ("subprocess-per-row", "tests/test_press_widget.py", "test_exit"),
    ("subprocess-per-row", "tests/test_press_widget.py", "test_aliased_exit"),
    ("subprocess-per-row", "tests/test_press_widget.py", "test_interpreter_argv"),
    ("range-trials", "tests/test_widget.py", "test_widget_trials"),
    ("repeated-ac-marker", "tests/test_press_widget.py", "TestGroup.test_marked"),
    ("rows-over-cap", "tests/test_widget.py", "test_widget_new_table"),
    ("rows-over-cap", "tests/test_widget.py", "test_widget_small_table"),
    ("repeated-ac-marker", "tests/test_widget.py", "test_widget_small_table"),
    ("rows-over-cap", "tests/test_café.py", "test_café_table"),
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _ = git(tmp_path, "init", "-q", "-b", "main")
    _ = git(tmp_path, "config", "user.name", "Test")
    _ = git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "tests").mkdir()
    _ = (tmp_path / "tests" / "test_widget.py").write_text(BASE_FILE)
    _ = git(tmp_path, "add", ".")
    _ = git(tmp_path, "commit", "-qm", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def press_pass(repo: Path) -> None:
    """Add and grow the tests that a bloated Press pass writes, without committing them."""
    base = repo / "tests" / "test_widget.py"
    old_table = '@pytest.mark.parametrize("value", [0, 1, 2])\ndef test_widget_small_table(value):\n'
    trials = '@pytest.mark.parametrize("trial", range(2))\n'
    grown = base.read_text().replace(old_table, GROWN_TABLE.lstrip())
    grown = grown.replace(trials, '@pytest.mark.parametrize("attempt", range(2))\n' + trials)
    _ = base.write_text(grown + BASE_FILE_ADDITION)
    _ = (repo / "tests" / "test_press_widget.py").write_text(PRESS_FILE)
    _ = (repo / "tests" / "test_press_gizmo.py").write_text(LONE_PRESS_FILE)
    _ = (repo / "tests" / "test_café.py").write_text(NON_ASCII_FILE)


def keys(report: dict[str, object]) -> list[tuple[str, str, str]]:
    findings = cast(list[Finding], report["findings"])
    return [(item.kind, item.path, item.test) for item in findings]


def test_each_bloat_pattern_in_changed_tests_is_reported_once_and_unchanged_tests_are_not(repo: Path) -> None:
    press_pass(repo)

    worktree = suite_shape(base="HEAD")

    assert worktree["clean"] is False
    assert sorted(keys(worktree)) == sorted(EXPECTED)
    markers = {item.detail for item in cast(list[Finding], worktree["findings"]) if item.kind == "repeated-ac-marker"}
    assert markers == {"gh-1:AC-1 is on 3 tests"}

    _ = git(repo, "add", ".")
    _ = git(repo, "commit", "-qm", "press")
    committed = suite_shape(base="HEAD~1", head="HEAD")

    assert committed["findings"] == worktree["findings"]
    assert committed["head"] == "HEAD"


@pytest.mark.usefixtures("repo")
def test_a_diff_without_new_tests_is_clean() -> None:
    assert suite_shape(base="HEAD") == {
        "base": "HEAD", "head": "worktree", "row_cap": 8, "clean": True, "findings": [],
    }


def test_a_renamed_test_file_is_compared_with_its_old_path(repo: Path) -> None:
    _ = git(repo, "mv", "tests/test_widget.py", "tests/test_renamed_widget.py")

    staged = suite_shape(base="HEAD")
    _ = git(repo, "commit", "-qm", "rename")
    committed = suite_shape(base="HEAD~1", head="HEAD")

    assert (staged["clean"], committed["clean"]) == (True, True)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param({"base": "no-such-rev"}, "not a revision", id="unknown-revision"),
        pytest.param({"base": "--output=leak"}, "not a revision", id="option-shaped-revision"),
        pytest.param({"base": "HEAD", "row_cap": 0}, "row-cap must be 1 or more", id="cap-below-one"),
    ],
)
@pytest.mark.usefixtures("repo")
def test_bad_arguments_stop_with_a_named_error(arguments: dict[str, object], message: str) -> None:
    with pytest.raises(fromargs.CliError, match=message):
        _ = suite_shape(**arguments)  # pyright: ignore[reportArgumentType]


def test_the_press_bundle_dispatches_test_shape_with_a_row_cap(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _ = (repo / "tests" / "test_gadget.py").write_text(
        'import pytest\n\n@pytest.mark.parametrize("v", [1, 2, 3])\ndef test_gadget(v):\n    assert v\n'
    )

    status = commands.main(["test-shape", "--base", "HEAD", "--row-cap", "2"])

    report = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert status == 0
    assert report["clean"] is False
    assert report["findings"] == [{
        "kind": "rows-over-cap", "path": "tests/test_gadget.py", "line": 4,
        "test": "test_gadget", "detail": "3 rows, cap 2",
    }]
