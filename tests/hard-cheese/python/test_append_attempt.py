"""Tests for skills/hard-cheese/scripts/append-attempt.py.

The script atomically appends an attempt row to `.cheese/hard-cheese/<slug>.md`.
Acceptance:

* a successful append produces a new row whose fields match the flags
* missing --slug exits 2
* two serial appends produce two distinct rows with no overwrite
* two concurrent appends (multiprocessing) both land
* --slug with `..` or slashes is rejected

No conftest — the script is loaded inline via importlib so this test file
is self-contained.
"""
from __future__ import annotations

import importlib.util
import multiprocessing as mp
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills" / "hard-cheese" / "scripts" / "append-attempt.py"


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("append_attempt", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["append_attempt"] = module
    spec.loader.exec_module(module)
    return module


def _run(env_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HARD_CHEESE_ARTIFACT_DIR"] = str(env_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )


def _read_rows(artifact: Path) -> list[str]:
    lines = artifact.read_text(encoding="utf-8").splitlines()
    # Drop header (lines 0-1: header row + separator).
    return [ln for ln in lines[2:] if ln.strip()]


class TestSlugValidation:
    def test_rejects_traversal(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError):
            mod._validate_slug("../escape")

    def test_rejects_forward_slash(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError):
            mod._validate_slug("foo/bar")

    def test_rejects_backslash(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError):
            mod._validate_slug("foo\\bar")

    def test_rejects_empty(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError):
            mod._validate_slug("")

    def test_accepts_kebab(self, mod: ModuleType) -> None:
        assert mod._validate_slug("my-slug-42") == "my-slug-42"


class TestEscapeCell:
    def test_pipe_is_escaped(self, mod: ModuleType) -> None:
        assert mod._escape_cell("a | b") == "a \\| b"

    def test_newline_becomes_br(self, mod: ModuleType) -> None:
        assert mod._escape_cell("line1\nline2") == "line1<br>line2"


class TestCli:
    def test_happy_path_writes_matching_row(self, tmp_path: Path) -> None:
        result = _run(
            tmp_path,
            "--slug", "feature-x",
            "--status", "PASS",
            "--score", "4",
            "--feedback", "diff-grounded reasoning",
            "--explanation", "the diff swaps X for Y because of invariant Z",
        )
        assert result.returncode == 0, result.stderr
        artifact = tmp_path / "feature-x.md"
        assert artifact.exists()
        rows = _read_rows(artifact)
        assert len(rows) == 1
        row = rows[0]
        # Each flag must round-trip into the row.
        assert "PASS" in row
        assert "| 4 |" in row
        assert "diff-grounded reasoning" in row
        assert "the diff swaps X for Y because of invariant Z" in row

    def test_header_present_on_first_write(self, tmp_path: Path) -> None:
        result = _run(
            tmp_path,
            "--slug", "hdr",
            "--status", "PASS", "--score", "3",
            "--feedback", "fb", "--explanation", "ex",
        )
        assert result.returncode == 0
        body = (tmp_path / "hdr.md").read_text(encoding="utf-8")
        assert body.startswith("| timestamp | head_sha | status | score | feedback | explanation |\n")
        assert "| --- |" in body

    def test_missing_slug_exits_two(self, tmp_path: Path) -> None:
        result = _run(
            tmp_path,
            "--status", "PASS", "--score", "3",
            "--feedback", "fb", "--explanation", "ex",
        )
        assert result.returncode == 2, result.stdout
        assert "--slug" in result.stderr

    def test_traversal_slug_rejected_via_cli(self, tmp_path: Path) -> None:
        result = _run(
            tmp_path,
            "--slug", "../escape",
            "--status", "PASS", "--score", "3",
            "--feedback", "fb", "--explanation", "ex",
        )
        assert result.returncode == 2
        assert "ERROR" in result.stderr

    def test_two_serial_appends_produce_two_rows(self, tmp_path: Path) -> None:
        for status, score, feedback in [
            ("FAIL", "2", "first-attempt"),
            ("PASS", "4", "second-attempt"),
        ]:
            result = _run(
                tmp_path,
                "--slug", "serial",
                "--status", status, "--score", score,
                "--feedback", feedback,
                "--explanation", f"explanation for {status}",
            )
            assert result.returncode == 0, result.stderr
        rows = _read_rows(tmp_path / "serial.md")
        assert len(rows) == 2, rows
        assert "first-attempt" in rows[0]
        assert "second-attempt" in rows[1]
        # First row was not clobbered.
        assert "FAIL" in rows[0]
        assert "PASS" in rows[1]


def _spawn_one(args: tuple[str, str, int]) -> int:
    """Top-level so multiprocessing can pickle it."""
    artifact_dir, slug, idx = args
    env = os.environ.copy()
    env["HARD_CHEESE_ARTIFACT_DIR"] = artifact_dir
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--slug", slug,
            "--status", "FAIL" if idx % 2 == 0 else "PASS",
            "--score", str(2 + (idx % 3)),
            "--feedback", f"concurrent-{idx}",
            "--explanation", f"explanation-{idx}",
        ],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    return result.returncode


class TestConcurrency:
    def test_two_concurrent_appends_both_land(self, tmp_path: Path) -> None:
        """Force a race: two processes append the same slug; both rows must land.

        The flock sidecar serialises them; the tmpfile+rename keeps each
        rewrite atomic. Without either, the second writer could read the
        pre-first-write state and clobber it.
        """
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=2) as pool:
            codes = pool.map(
                _spawn_one,
                [(str(tmp_path), "concurrent", i) for i in range(2)],
            )
        assert codes == [0, 0]
        rows = _read_rows(tmp_path / "concurrent.md")
        assert len(rows) == 2, rows
        # Both feedback markers must be present — nothing was clobbered.
        feedbacks = " ".join(rows)
        assert "concurrent-0" in feedbacks
        assert "concurrent-1" in feedbacks

    def test_many_concurrent_appends_all_land(self, tmp_path: Path) -> None:
        """Stress: 8 concurrent appends must produce exactly 8 rows.

        Pushes the lock harder than the 2-process happy path; if the
        read-modify-write isn't actually atomic some rows will be lost.
        """
        N = 8
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=N) as pool:
            codes = pool.map(
                _spawn_one,
                [(str(tmp_path), "stress", i) for i in range(N)],
            )
        assert all(c == 0 for c in codes), codes
        rows = _read_rows(tmp_path / "stress.md")
        assert len(rows) == N, f"expected {N} rows, got {len(rows)}: {rows}"
        feedbacks = " ".join(rows)
        for i in range(N):
            assert f"concurrent-{i}" in feedbacks
