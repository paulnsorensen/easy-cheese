"""Tests for src/easy_cheese/skills/hard_cheese/rank_hunks.py.

Builds temporary git repositories per test and exercises
`easy_cheese.skills.hard_cheese.rank_hunks.main` directly, matching the
conftest module-fixture pattern used for freshness-check.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest


class _RankHunksModule(Protocol):
    def main(self, argv: list[str]) -> int: ...

    def _unquote_git_path(self, token: str) -> str: ...


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "HOME": str(cwd),  # avoid touching the user's git config
            "PATH": os.environ.get("PATH", ""),
        },
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A tmp git repo with local author config; returns the repo path."""
    _ = _git(tmp_path, "init", "-q", "-b", "main")
    _ = _git(tmp_path, "config", "user.name", "test")
    _ = _git(tmp_path, "config", "user.email", "test@example.com")
    return tmp_path


def test_top_hunks_are_sorted_and_deterministic(
    repo: Path,
    rank_hunks: _RankHunksModule,
    capsys: pytest.CaptureFixture[str],
    bundle: Path,
) -> None:
    file_a = repo / "a.py"
    _ = file_a.write_text(
        "\n".join(f"a{i}" for i in range(1, 21)) + "\n", encoding="utf-8"
    )
    file_b = repo / "b.py"
    _ = file_b.write_text(
        "\n".join(f"b{i}" for i in range(1, 21)) + "\n", encoding="utf-8"
    )
    _ = _git(repo, "add", "a.py", "b.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    lines_a = file_a.read_text(encoding="utf-8").splitlines()
    lines_a[1] = "a2-changed"
    lines_a[14] = "a15-changed"
    _ = file_a.write_text("\n".join(lines_a) + "\n", encoding="utf-8")

    lines_b = file_b.read_text(encoding="utf-8").splitlines()
    lines_b[2] = "b3-changed"
    lines_b[17] = "b18-changed"
    _ = file_b.write_text("\n".join(lines_b) + "\n", encoding="utf-8")

    _ = _git(repo, "add", "a.py", "b.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    argv = ["--base", base, "--head", head, "--top", "3", "--cwd", str(repo)]
    status: int = rank_hunks.main(argv)
    out1 = capsys.readouterr().out
    assert status == 0

    status2: int = rank_hunks.main(argv)
    out2 = capsys.readouterr().out
    assert status2 == 0
    assert out1 == out2

    payload = cast("list[dict[str, object]]", json.loads(out1))
    assert len(payload) == 3
    assert [item["id"] for item in payload] == ["a.py:2-2", "a.py:15-15", "b.py:3-3"]
    assert [(item["start"], item["end"]) for item in payload] == [
        (2, 2),
        (15, 15),
        (3, 3),
    ]
    for item in payload:
        assert set(item) == {"id", "path", "start", "end", "score", "reasons"}
        assert item["reasons"]
    scores = [cast(float, item["score"]) for item in payload]
    assert scores == sorted(scores, reverse=True)

    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    bundle_result = subprocess.run(
        [sys.executable, str(bundle), "rank-hunks", *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )
    assert bundle_result.returncode == 0
    assert bundle_result.stdout == out1


def test_flagged_hunk_outscores_plain_hunk(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    risky = repo / "risky.py"
    _ = risky.write_text("def handle():\n    return 1\n", encoding="utf-8")
    _ = _git(repo, "add", "risky.py")
    _ = _git(repo, "commit", "-q", "-m", "c1")
    _ = risky.write_text("def handle():\n    return 2\n", encoding="utf-8")
    _ = _git(repo, "add", "risky.py")
    _ = _git(repo, "commit", "-q", "-m", "c2")
    _ = risky.write_text("def handle():\n    return 3\n", encoding="utf-8")
    _ = _git(repo, "add", "risky.py")
    _ = _git(repo, "commit", "-q", "-m", "c3")
    base = _git(repo, "rev-parse", "HEAD")

    risky_body = (
        "def handle():\n"
        "    try:\n"
        "        return 3\n"
        "    except Exception:\n"
        "        raise\n"
    )
    _ = risky.write_text(risky_body, encoding="utf-8")
    plain = repo / "plain.py"
    _ = plain.write_text("value = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "risky.py", "plain.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    argv = ["--base", base, "--head", head, "--top", "10", "--cwd", str(repo)]
    status: int = rank_hunks.main(argv)
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))
    assert status == 0

    assert payload[0]["path"] == "risky.py"
    assert "error-path" in cast("list[str]", payload[0]["reasons"])
    assert "prior-changes" in cast("list[str]", payload[0]["reasons"])

    plain_item = next(item for item in payload if item["path"] == "plain.py")
    assert cast(float, payload[0]["score"]) > cast(float, plain_item["score"])


def test_added_line_starting_with_plus_plus_is_not_a_new_header(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """An added `++ note` line must not be parsed as a `+++ ` file header."""
    file_a = repo / "note.py"
    _ = file_a.write_text("line1\nline2\n", encoding="utf-8")
    _ = _git(repo, "add", "note.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_a.write_text("line1\n++ note\nline2\n", encoding="utf-8")
    _ = _git(repo, "add", "note.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert {cast(str, item["path"]) for item in payload} == {"note.py"}


def test_dash_prefixed_base_is_rejected(
    repo: Path, bundle: Path, tmp_path: Path
) -> None:
    """`--base` starting with `-` must not reach git as a positional arg."""
    output_path = tmp_path / "escape.txt"
    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base=--output=" + str(output_path),
            "--head",
            "HEAD",
            "--cwd",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )

    assert result.returncode != 0
    assert not output_path.exists()


def test_config_substring_inside_word_is_not_flagged(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """`latest_config.py` must not trigger the config-or-secret-file pattern."""
    file_a = repo / "latest_config.py"
    _ = file_a.write_text("value = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "latest_config.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_a.write_text("value = 2\n", encoding="utf-8")
    _ = _git(repo, "add", "latest_config.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "config-or-secret-file" not in reasons
    assert "deleted-tests" not in reasons


def test_empty_diff_emits_empty_list(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _git(repo, "add", "seed.txt")
    _ = _git(repo, "commit", "-q", "-m", "seed")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", head, "--head", head, "--cwd", str(repo)])
    out = capsys.readouterr().out.strip()

    assert status == 0
    assert out == "[]"


# --- Wrecker attack: paths, boundaries, refs, tie-break, patterns, cwd ---


def test_binary_file_change_produces_no_hunks_and_does_not_crash(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """A binary file diff has no `@@` hunk header; it must be skipped, not crash."""
    binfile = repo / "bin.dat"
    _ = binfile.write_bytes(b"\x00\x01binarydata")
    _ = _git(repo, "add", "bin.dat")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = binfile.write_bytes(b"\x00\x01binarydatamore")
    _ = _git(repo, "add", "bin.dat")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    out = capsys.readouterr().out.strip()

    assert status == 0
    assert out == "[]"


def test_deleted_file_entirely_uses_old_path_and_correct_range(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fully deleted file must report its old path, not a bogus or missing one."""
    doomed = repo / "doomed.py"
    _ = doomed.write_text("line1\nline2\nline3\n", encoding="utf-8")
    _ = _git(repo, "add", "doomed.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    doomed.unlink()
    _ = _git(repo, "add", "-A")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert len(payload) == 1
    assert payload[0]["path"] == "doomed.py"
    assert payload[0]["start"] == 1
    assert payload[0]["end"] == 1


def test_new_empty_file_added_produces_no_crash(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """Adding a zero-byte file has no hunk lines; it must not crash."""
    _ = (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _git(repo, "add", "seed.txt")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = (repo / "empty.py").write_text("", encoding="utf-8")
    _ = _git(repo, "add", "empty.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    out = capsys.readouterr().out.strip()

    assert status == 0
    assert out == "[]"


def test_renamed_file_reports_new_path_without_crash(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """`git mv` plus an edit must parse cleanly and name the new path."""
    orig = repo / "orig.py"
    _ = orig.write_text("line1\nline2\nline3\n", encoding="utf-8")
    _ = _git(repo, "add", "orig.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = _git(repo, "mv", "orig.py", "renamed.py")
    renamed = repo / "renamed.py"
    _ = renamed.write_text("line1\nline2-changed\nline3\n", encoding="utf-8")
    _ = _git(repo, "add", "-A")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    paths = {cast(str, item["path"]) for item in payload}
    assert "renamed.py" in paths
    for path in paths:
        assert not path.startswith('"')
        assert "\\" not in path


def test_unicode_path_with_space_is_reported_as_real_filename_not_quoted_escape(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    unicode_name = "café γ.py"
    orig = repo / "a b.py"
    _ = orig.write_text("hello\nworld\n", encoding="utf-8")
    _ = _git(repo, "add", "a b.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = _git(repo, "mv", "a b.py", unicode_name)
    renamed = repo / unicode_name
    _ = renamed.write_text("hello\nworld2\n", encoding="utf-8")
    _ = _git(repo, "add", "-A")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    paths = {cast(str, item["path"]) for item in payload}
    assert unicode_name in paths


def test_top_greater_than_hunk_count_returns_all_hunks(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    file_a = repo / "solo.py"
    _ = file_a.write_text("line1\nline2\n", encoding="utf-8")
    _ = _git(repo, "add", "solo.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_a.write_text("line1\nline2-changed\n", encoding="utf-8")
    _ = _git(repo, "add", "solo.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(
        ["--base", base, "--head", head, "--top", "1000", "--cwd", str(repo)]
    )
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert len(payload) == 1


@pytest.mark.parametrize("top_value", ["0", "-1"])
def test_top_out_of_range_is_rejected_by_argparse(
    repo: Path, bundle: Path, top_value: str
) -> None:
    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base",
            "HEAD",
            "--head",
            "HEAD",
            "--top",
            top_value,
            "--cwd",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_unknown_base_ref_exits_nonzero_without_traceback(
    repo: Path, bundle: Path
) -> None:
    _ = (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _git(repo, "add", "seed.txt")
    _ = _git(repo, "commit", "-q", "-m", "seed")
    head = _git(repo, "rev-parse", "HEAD")

    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base",
            "no-such-ref",
            "--head",
            head,
            "--cwd",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("ERROR:")
    stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(stderr_lines) == 1


def test_unknown_head_ref_exits_nonzero_without_traceback(
    repo: Path, bundle: Path
) -> None:
    _ = (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _git(repo, "add", "seed.txt")
    _ = _git(repo, "commit", "-q", "-m", "seed")
    base = _git(repo, "rev-parse", "HEAD")

    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base",
            base,
            "--head",
            "no-such-ref",
            "--cwd",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("ERROR:")


def test_non_directory_cwd_exits_nonzero_without_traceback(
    repo: Path, bundle: Path, tmp_path: Path
) -> None:
    """`--cwd <file>` must reject cleanly, not crash with `NotADirectoryError`."""
    not_a_dir = tmp_path / "plain-file.txt"
    _ = not_a_dir.write_text("not a directory\n", encoding="utf-8")

    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base",
            "HEAD",
            "--head",
            "HEAD",
            "--cwd",
            str(not_a_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(stderr_lines) == 1


def test_tied_scores_across_files_order_by_path_then_start(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two plain hunks with equal score must sort by (path, start), not diff order."""
    file_b = repo / "b.py"
    _ = file_b.write_text("plain1\nplain2\n", encoding="utf-8")
    file_a = repo / "a.py"
    _ = file_a.write_text("plain1\nplain2\n", encoding="utf-8")
    _ = _git(repo, "add", "a.py", "b.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_b.write_text("plain1\nplain2-changed\n", encoding="utf-8")
    _ = file_a.write_text("plain1\nplain2-changed\n", encoding="utf-8")
    _ = _git(repo, "add", "a.py", "b.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert len(payload) == 2
    scores = {cast(float, item["score"]) for item in payload}
    assert len(scores) == 1, (
        "test setup must produce equal scores to exercise tie-break"
    )
    assert [cast(str, item["path"]) for item in payload] == ["a.py", "b.py"]


def test_auth_pattern_does_not_fire_on_prose_word_author_alone(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """A comment mentioning "author" (not "auth") must not fire the auth pattern."""
    file_a = repo / "notes.py"
    _ = file_a.write_text("# notes\nvalue = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "notes.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_a.write_text(
        "# the author wrote this module\nvalue = 1\n", encoding="utf-8"
    )
    _ = _git(repo, "add", "notes.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "auth" not in reasons


def test_auth_pattern_fires_on_snake_case_permission_identifier(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    file_a = repo / "authz.py"
    _ = file_a.write_text("def handle():\n    return 1\n", encoding="utf-8")
    _ = _git(repo, "add", "authz.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = file_a.write_text("def check_permission():\n    return 1\n", encoding="utf-8")
    _ = _git(repo, "add", "authz.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "auth" in reasons


def test_deleted_tests_does_not_fire_on_added_lines_in_a_test_file(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only deleted lines in a test file should fire `deleted-tests`, not additions."""
    test_file = repo / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    _ = test_file.write_text("def test_one():\n    assert True\n", encoding="utf-8")
    _ = _git(repo, "add", "tests/test_x.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = test_file.write_text(
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
        encoding="utf-8",
    )
    _ = _git(repo, "add", "tests/test_x.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "deleted-tests" not in reasons


def test_deleted_tests_does_not_fire_on_deleted_lines_in_a_non_test_file(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    src_file = repo / "app.py"
    _ = src_file.write_text(
        "def run():\n    old_line()\n    return 1\n", encoding="utf-8"
    )
    _ = _git(repo, "add", "app.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = src_file.write_text("def run():\n    return 1\n", encoding="utf-8")
    _ = _git(repo, "add", "app.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "deleted-tests" not in reasons


def test_deleted_tests_fires_on_deleted_lines_in_a_test_file(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = repo / "tests" / "test_y.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    _ = test_file.write_text(
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
        encoding="utf-8",
    )
    _ = _git(repo, "add", "tests/test_y.py")
    _ = _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = test_file.write_text("def test_one():\n    assert True\n", encoding="utf-8")
    _ = _git(repo, "add", "tests/test_y.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "deleted-tests" in reasons


def test_paths_stay_repo_relative_when_cwd_is_a_subdirectory(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--cwd` pointed at a subdirectory of the repo must still yield root-relative paths."""
    subdir = repo / "pkg" / "sub"
    subdir.mkdir(parents=True)
    target = repo / "pkg" / "mod.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_text("value = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c1")
    _ = target.write_text("value = 2\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c2")
    _ = target.write_text("value = 3\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c3")
    base = _git(repo, "rev-parse", "HEAD")

    _ = target.write_text("value = 4\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(
        ["--base", base, "--head", head, "--cwd", str(subdir)]
    )
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert len(payload) == 1
    assert payload[0]["path"] == "pkg/mod.py"
    reasons = cast("list[str]", payload[0]["reasons"])
    assert "prior-changes" in reasons
    assert "diffusion" not in reasons


def test_bundle_from_subdirectory_without_cwd_uses_repo_root(
    repo: Path, bundle: Path
) -> None:
    """With no `--cwd`, the process's own cwd must still resolve to the repo root."""
    subdir = repo / "pkg" / "sub"
    subdir.mkdir(parents=True)
    target = repo / "pkg" / "mod.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_text("value = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c1")
    _ = target.write_text("value = 2\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c2")
    _ = target.write_text("value = 3\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c3")
    base = _git(repo, "rev-parse", "HEAD")

    _ = target.write_text("value = 4\n", encoding="utf-8")
    _ = _git(repo, "add", "pkg/mod.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    env = os.environ.copy()
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            str(bundle),
            "rank-hunks",
            "--base",
            base,
            "--head",
            head,
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(subdir),
    )

    assert result.returncode == 0, result.stderr
    payload = cast("list[dict[str, object]]", json.loads(result.stdout))
    assert len(payload) == 1
    assert payload[0]["path"] == "pkg/mod.py"
    assert "prior-changes" in cast("list[str]", payload[0]["reasons"])


def test_unset_user_email_does_not_flag_author_new_to_file(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unset `user.email` must not spuriously flag every hunk as a new author."""
    target = repo / "mod.py"
    _ = target.write_text("value = 1\n", encoding="utf-8")
    _ = _git(repo, "add", "mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c1")
    base = _git(repo, "rev-parse", "HEAD")

    _ = target.write_text("value = 2\n", encoding="utf-8")
    _ = _git(repo, "add", "mod.py")
    _ = _git(repo, "commit", "-q", "-m", "c2")
    head = _git(repo, "rev-parse", "HEAD")

    _ = _git(repo, "config", "user.email", "")

    status: int = rank_hunks.main(["--base", base, "--head", head, "--cwd", str(repo)])
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert len(payload) == 1
    assert "author-new-to-file" not in cast("list[str]", payload[0]["reasons"])


def test_small_flagged_hunk_outranks_large_plain_hunk(
    repo: Path, rank_hunks: _RankHunksModule, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uncapped churn must not let a large plain hunk outscore a small flagged one."""
    authz = repo / "authz.py"
    _ = authz.write_text("def handle():\n    return 1\n", encoding="utf-8")
    _ = _git(repo, "add", "authz.py")
    _ = _git(repo, "commit", "-q", "-m", "c1")
    _ = authz.write_text("def handle():\n    return 2\n", encoding="utf-8")
    _ = _git(repo, "add", "authz.py")
    _ = _git(repo, "commit", "-q", "-m", "c2")
    _ = authz.write_text("def handle():\n    return 3\n", encoding="utf-8")
    _ = _git(repo, "add", "authz.py")
    _ = _git(repo, "commit", "-q", "-m", "c3")

    plain = repo / "plain.py"
    _ = plain.write_text(
        "\n".join(f"line{i}" for i in range(1, 21)) + "\n", encoding="utf-8"
    )
    _ = _git(repo, "add", "plain.py")
    _ = _git(repo, "commit", "-q", "-m", "plain-base")
    base = _git(repo, "rev-parse", "HEAD")

    _ = authz.write_text("def check_permission():\n    return 3\n", encoding="utf-8")
    _ = plain.write_text(
        "\n".join(f"line{i}-changed" for i in range(1, 21)) + "\n", encoding="utf-8"
    )
    _ = _git(repo, "add", "authz.py", "plain.py")
    _ = _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    status: int = rank_hunks.main(
        ["--base", base, "--head", head, "--top", "10", "--cwd", str(repo)]
    )
    payload = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))

    assert status == 0
    authz_item = next(item for item in payload if item["path"] == "authz.py")
    plain_item = next(item for item in payload if item["path"] == "plain.py")
    assert "auth" in cast("list[str]", authz_item["reasons"])
    assert cast(float, authz_item["score"]) > cast(float, plain_item["score"])


def test_unquote_git_path_decodes_escapes_in_a_single_pass(
    rank_hunks: _RankHunksModule,
) -> None:
    """A quoted token that escapes a literal backslash keeps that backslash."""
    unquote = rank_hunks._unquote_git_path  # pyright: ignore[reportPrivateUsage]
    result = unquote('"back\\\\tslash.py"')
    assert result == "back\\tslash.py"
    assert "\t" not in result
    assert unquote("back\\tslash.py") == "back\\tslash.py"
    assert unquote('"caf\\303\\251.py"') == "café.py"
    assert unquote('"a\\rb.py"') == "a\rb.py"
