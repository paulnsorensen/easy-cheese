"""Tests for skills/hard-cheese/scripts/freshness-check.py.

Mocks a tiny git repo + `.cheese/hard-cheese/<slug>.md` fixture per state
(previously_passed / stale / new) and asserts both the script-as-CLI path
and the imported module's pure functions.

Inline importlib loader per the curd seed (no conftest in this tests/
subtree). The repo root is resolved via parents[N] from this file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("hard-cheese")


# ---------- git fixture --------------------------------------------------- #


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
            "PATH": __import__("os").environ.get("PATH", ""),
        },
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A tmp git repo with one commit; returns the repo path."""
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "seed.txt")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _write_log(repo: Path, slug: str, body: str) -> Path:
    log_dir = repo / ".cheese" / "hard-cheese"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


def _heading_log(slug: str, sha: str, status: str = "PASS") -> str:
    return (
        f"---\nslug: {slug}\nstatus: {status}\nattempts: 1\n---\n\n"
        f"## Attempt 1 ({status} — SOLO 4 Relational)\n"
        f"git: {sha}\n\n"
        f"> I get it.\n\n"
        f"**Judge feedback**: solid.\n"
    )


def _table_log(slug: str, sha: str, status: str = "pass") -> str:
    """Canonical attempt-log table per skills/hard-cheese/scripts/append-attempt.py."""
    return (
        f"# freshness log for {slug}\n\n"
        f"| timestamp | head_sha | status | score | feedback | explanation |\n"
        f"| --- | --- | --- | --- | --- | --- |\n"
        f"| 2026-05-19T10:00:00+00:00 | {sha} | {status} | 4 | solid | I get it |\n"
    )


def _legacy_table_log(slug: str, sha: str, status: str = "pass") -> str:
    """Pre-canonical table shape (status first, head_sha at column 2 — the
    seed's documented but never-actually-written order). Kept to lock the
    parser's fallback for any logs that predate the schema alignment."""
    return (
        f"# freshness log for {slug}\n\n"
        f"| {status} | 4 | {sha} | 2026-05-19T10:00 |\n"
    )


# ---------- CLI: full state matrix --------------------------------------- #


def _run_cli(repo: Path, slug: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUNDLE),
            "freshness-check",
            "--slug",
            slug,
            "--cheese-root",
            str(repo / ".cheese"),
            "--repo-root",
            str(repo),
            *extra,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


class TestStateNew:
    def test_unknown_slug_exits_3_state_new(self, repo: Path) -> None:
        result = _run_cli(repo, "never-seen")
        assert result.returncode == 3
        assert result.stdout.strip() == "new"

    def test_json_payload_carries_head(self, repo: Path) -> None:
        result = _run_cli(repo, "never-seen", "--json")
        assert result.returncode == 3
        payload = json.loads(result.stdout)
        assert payload == {"state": "new", "diff_head": _head(repo)}

    def test_missing_log_file_is_new(self, repo: Path) -> None:
        # Directory exists but the specific slug file does not.
        (repo / ".cheese" / "hard-cheese").mkdir(parents=True)
        result = _run_cli(repo, "absent")
        assert result.returncode == 3
        assert result.stdout.strip() == "new"


class TestStatePreviouslyPassed:
    def test_heading_log_matching_head(self, repo: Path) -> None:
        head = _head(repo)
        _write_log(repo, "feat-a", _heading_log("feat-a", head))
        result = _run_cli(repo, "feat-a")
        assert result.returncode == 0
        assert result.stdout.strip() == "previously_passed"

    def test_table_log_matching_head(self, repo: Path) -> None:
        head = _head(repo)
        _write_log(repo, "feat-b", _table_log("feat-b", head))
        result = _run_cli(repo, "feat-b", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "state": "previously_passed",
            "diff_head": head,
        }

    def test_picks_last_pass_when_multiple_attempts(self, repo: Path) -> None:
        # Earlier PASS at a stale sha; later PASS at HEAD — the later wins.
        head = _head(repo)
        body = (
            _heading_log("multi", "deadbeef" * 5).rstrip()
            + "\n\n"
            + "## Attempt 2 (PASS — SOLO 5 Extended Abstract)\n"
            + f"git: {head}\n\n"
            + "> better\n"
        )
        _write_log(repo, "multi", body)
        result = _run_cli(repo, "multi")
        assert result.returncode == 0
        assert result.stdout.strip() == "previously_passed"


class TestStateStale:
    def test_head_moved_since_pass(self, repo: Path) -> None:
        old_head = _head(repo)
        _write_log(repo, "feat-c", _heading_log("feat-c", old_head))
        # Add a new commit so HEAD moves.
        (repo / "new.txt").write_text("more\n", encoding="utf-8")
        _git(repo, "add", "new.txt")
        _git(repo, "commit", "-q", "-m", "second")
        new_head = _head(repo)
        assert new_head != old_head

        result = _run_cli(repo, "feat-c", "--json")
        assert result.returncode == 2
        payload = json.loads(result.stdout)
        assert payload == {"state": "stale", "diff_head": new_head}

    def test_table_log_stale(self, repo: Path) -> None:
        _write_log(repo, "feat-d", _table_log("feat-d", "abc123" * 7))  # not current HEAD
        result = _run_cli(repo, "feat-d")
        assert result.returncode == 2
        assert result.stdout.strip() == "stale"


class TestAppendAttemptIntegration:
    """End-to-end: the canonical table written by append-attempt.py must be
    parseable by freshness-check.py. M3 regression."""

    def test_canonical_table_schema_round_trips(
        self, repo: Path, freshness_check: ModuleType
    ) -> None:
        # Write the *exact* table shape `append-attempt.py` produces (HEADER +
        # one row). The parser must read head_sha out of column 1, not 2 —
        # the pre-fix code mis-indexed every cell and silently returned None
        # for any real-world log.
        head = _head(repo)
        short_head = _git(repo, "rev-parse", "--short", "HEAD")
        artifact = (repo / ".cheese" / "hard-cheese")
        artifact.mkdir(parents=True, exist_ok=True)
        path = artifact / "real.md"
        path.write_text(
            "| timestamp | head_sha | status | score | feedback | explanation |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"| 2026-05-19T10:00:00+00:00 | {short_head} | PASS | 4 | solid | I get it |\n",
            encoding="utf-8",
        )

        # last_pass_sha returns the canonical-column head sha verbatim.
        assert freshness_check.last_pass_sha(path) == short_head

        # decide() treats the short sha as a prefix of the full HEAD sha so
        # the writer/reader pair round-trips end-to-end.
        result = freshness_check.decide(
            "real", cheese_root=repo / ".cheese", repo_root=repo
        )
        assert result == {"state": "previously_passed", "diff_head": head}

    def test_legacy_table_shape_still_parses(
        self, freshness_check: ModuleType, tmp_path: Path
    ) -> None:
        # Pre-canonical table (status at col 0, head_sha at col 2) still
        # parses via the legacy fallback so any old logs do not silently
        # report `new`.
        path = tmp_path / "legacy.md"
        path.write_text(_legacy_table_log("x", "feedface" * 5), encoding="utf-8")
        assert freshness_check.last_pass_sha(path) == "feedface" * 5

    def test_sha_matches_handles_short_and_full(
        self, freshness_check: ModuleType
    ) -> None:
        full = "deadbeef" * 5
        short = full[:7]
        assert freshness_check._sha_matches(short, full) is True
        assert freshness_check._sha_matches(full, short) is True
        assert freshness_check._sha_matches("cafebabe", full) is False
        # 'unknown' sentinel (writer fallback when git fails) must never
        # silently match — otherwise every diff would be previously_passed.
        assert freshness_check._sha_matches("unknown", full) is False
        assert freshness_check._sha_matches("", full) is False


class TestMalformedLog:
    def test_no_pass_attempts_is_new(self, repo: Path) -> None:
        # Only a FAIL attempt — no pass row exists, so we treat the slug as new.
        body = (
            "## Attempt 1 (FAIL — SOLO 1 Prestructural)\n"
            f"git: {_head(repo)}\n\n> nope\n"
        )
        _write_log(repo, "only-fail", body)
        result = _run_cli(repo, "only-fail")
        assert result.returncode == 3
        assert result.stdout.strip() == "new"

    def test_garbage_log_is_new(self, repo: Path) -> None:
        _write_log(repo, "garbage", "this is not a valid log at all\n")
        result = _run_cli(repo, "garbage")
        assert result.returncode == 3
        assert result.stdout.strip() == "new"

    def test_empty_log_is_new(self, repo: Path) -> None:
        _write_log(repo, "empty", "")
        result = _run_cli(repo, "empty")
        assert result.returncode == 3
        assert result.stdout.strip() == "new"

    def test_pass_attempt_without_git_line_is_ignored(self, repo: Path) -> None:
        body = (
            "## Attempt 1 (PASS — SOLO 4 Relational)\n"
            "> no git line follows\n"
        )
        _write_log(repo, "no-git-line", body)
        result = _run_cli(repo, "no-git-line")
        # No sha could be extracted → treat as new (still no actionable record).
        assert result.returncode == 3
        assert result.stdout.strip() == "new"


# ---------- CLI: arg handling --------------------------------------------- #


class TestArgHandling:
    def test_missing_slug_exits_2(self, repo: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "freshness-check"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "--slug" in result.stderr

    def test_empty_slug_exits_2(self, repo: Path) -> None:
        result = _run_cli(repo, "")
        assert result.returncode == 2
        assert "slug" in result.stderr.lower()


# ---------- Pure-module unit coverage ------------------------------------ #


class TestPureHelpers:
    def test_is_pass_status_matches_variants(
        self, freshness_check: ModuleType
    ) -> None:
        assert freshness_check._is_pass_status("PASS") is True
        assert freshness_check._is_pass_status("pass") is True
        assert freshness_check._is_pass_status("passed") is True
        assert freshness_check._is_pass_status("Pass — SOLO 4") is True
        assert freshness_check._is_pass_status("FAIL") is False
        assert freshness_check._is_pass_status("error") is False

    def test_last_pass_sha_returns_none_when_missing(
        self, freshness_check: ModuleType, tmp_path: Path
    ) -> None:
        assert freshness_check.last_pass_sha(tmp_path / "missing.md") is None

    def test_last_pass_sha_from_headings(
        self, freshness_check: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "log.md"
        path.write_text(_heading_log("x", "cafebabe" * 5), encoding="utf-8")
        assert freshness_check.last_pass_sha(path) == "cafebabe" * 5

    def test_last_pass_sha_from_table(
        self, freshness_check: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "log.md"
        path.write_text(_table_log("x", "feedface" * 5), encoding="utf-8")
        assert freshness_check.last_pass_sha(path) == "feedface" * 5

    def test_decide_uses_git_head(
        self, freshness_check: ModuleType, repo: Path
    ) -> None:
        head = _head(repo)
        _write_log(repo, "pure", _heading_log("pure", head))
        result = freshness_check.decide(
            "pure", cheese_root=repo / ".cheese", repo_root=repo
        )
        assert result == {"state": "previously_passed", "diff_head": head}
