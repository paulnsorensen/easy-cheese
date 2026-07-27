"""Tests for src/fanout/review_surface_cli.py -- the impure CLI sibling of
review_surface.py.

Spec: deterministic-fanout-sizing.md `### 1. review_surface` and curd
`wire-up`. Mirrors age_route_cli.py's pattern: run git, call the pure
scorer, print JSON on stdout; exit non-zero with a stderr message on
malformed TOML or an unreadable git ref.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import review_surface  # noqa: E402
import review_surface_cli  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "initial")

    # Two extra lines on a tracked file (weight 1.0) plus a new lockfile
    # (weight 0.0, five lines) -- staged so `git diff --numstat HEAD` sees it.
    (repo / "a.txt").write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")
    (repo / "Cargo.lock").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
    _git(repo, "add", "-A")
    return repo


class TestReviewSurfaceSubcommand:
    def test_matches_score_shape(self, fixture_repo: Path) -> None:
        exit_code = review_surface_cli.main(
            ["review_surface_cli.py", "--repo", str(fixture_repo)]
        )
        assert exit_code == 0

    def test_prints_json_matching_score(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli.main(["review_surface_cli.py", "--repo", str(fixture_repo)])
        result = json.loads(capsys.readouterr().out)

        expected = review_surface.score(
            [("a.txt", 2, 0), ("Cargo.lock", 5, 0)]
        )
        assert result == expected
        assert result["zeroed"] == ["Cargo.lock"]
        assert result["score"] == pytest.approx(2.0 + review_surface.FILE_COST * 1.0)


class TestTomlOverride:
    def test_default_zeros_lockfile(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli.main(["review_surface_cli.py", "--repo", str(fixture_repo)])
        result = json.loads(capsys.readouterr().out)
        assert result["zeroed"] == ["Cargo.lock"]

    def test_override_changes_score(self, fixture_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = tmp_path / "config.toml"
        config.write_text(
            '[review_surface]\nweights = [["*.lock", 1.0]]\n', encoding="utf-8"
        )
        exit_code = review_surface_cli.main(
            [
                "review_surface_cli.py",
                "--repo",
                str(fixture_repo),
                "--config",
                str(config),
            ]
        )
        assert exit_code == 0
        result = json.loads(capsys.readouterr().out)
        # Cargo.lock now weighs 1.0 instead of the module default's 0.0.
        assert result["zeroed"] == []
        assert result["score"] == pytest.approx(
            review_surface.score(
                [("a.txt", 2, 0), ("Cargo.lock", 5, 0)],
                weights=(("*.lock", 1.0),),
            )["score"]
        )

    def test_omitted_config_uses_module_defaults(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli.main(["review_surface_cli.py", "--repo", str(fixture_repo)])
        result = json.loads(capsys.readouterr().out)
        expected = review_surface.score([("a.txt", 2, 0), ("Cargo.lock", 5, 0)])
        assert result == expected


class TestErrorHandling:
    def test_malformed_toml_exits_nonzero(
        self, fixture_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = tmp_path / "bad.toml"
        config.write_text("this is not [ valid toml", encoding="utf-8")
        exit_code = review_surface_cli.main(
            [
                "review_surface_cli.py",
                "--repo",
                str(fixture_repo),
                "--config",
                str(config),
            ]
        )
        assert exit_code != 0
        assert "ERROR" in capsys.readouterr().err

    def test_unreadable_git_ref_exits_nonzero(
        self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = review_surface_cli.main(
            ["review_surface_cli.py", "--repo", str(fixture_repo), "not-a-real-ref"]
        )
        assert exit_code != 0
        assert "ERROR" in capsys.readouterr().err
