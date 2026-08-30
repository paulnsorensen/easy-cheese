"""Tests for src/fanout/review_surface_cli.py -- the impure CLI sibling of
review_surface.py.

Spec: deterministic-fanout-sizing.md `### 1. review_surface` and curd
`wire-up`. Mirrors baseline.py's argparse + cli.run + cli.CliError house
pattern: no `main(argv)` entry point -- tests construct `argparse.Namespace`
directly and call `_cmd_score`/dispatch functions, asserting on captured
stdout or `pytest.raises(cli.CliError, ...)`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared import cli, git_utils  # noqa: E402
from easy_cheese.shared.fanout import review_surface, review_surface_cli  # noqa: E402
from easy_cheese.shared.fanout.review_surface_cli import _Args  # noqa: E402  # pyright: ignore[reportPrivateUsage]
from easy_cheese.shared.fanout.review_surface import ReviewScore  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _ns(repo: str, config: str | None = None, diff_args: list[str] | None = None) -> _Args:
    return cast(
        _Args,
        cast(
            object,
            argparse.Namespace(
                repo=repo,
                config=config,
                diff_args=diff_args or ["HEAD"],
                stdout=sys.stdout,
            ),
        ),
    )


def _stub_run_git(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    """Patch git_utils.run_git to return canned -z numstat output without
    touching a real repo."""

    def fake_run_git(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_utils, "run_git", fake_run_git)


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _ = _git(repo, "init", "-q")
    _ = _git(repo, "config", "user.email", "test@example.com")
    _ = _git(repo, "config", "user.name", "Test")
    _ = (repo / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    _ = _git(repo, "add", "a.txt")
    _ = _git(repo, "commit", "-q", "-m", "initial")

    # Two extra lines on a tracked file (weight 1.0) plus a new lockfile
    # (weight 0.0, five lines) -- staged so `git diff --numstat HEAD` sees it.
    _ = (repo / "a.txt").write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")
    _ = (repo / "Cargo.lock").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
    _ = _git(repo, "add", "-A")
    return repo


class TestReviewSurfaceSubcommand:
    def test_prints_json_matching_score(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli._cmd_score(_ns(str(fixture_repo)))  # pyright: ignore[reportPrivateUsage]
        result = cast(ReviewScore, json.loads(capsys.readouterr().out))

        expected = review_surface.score(
            [("a.txt", 2, 0), ("Cargo.lock", 5, 0)], weights_source="defaults"
        )
        assert result == expected
        assert result["zeroed"] == ["Cargo.lock"]
        assert result["score"] == pytest.approx(  # pyright: ignore[reportUnknownMemberType]
            2.0 + review_surface.FILE_COST * 1.0
        )


class TestTomlOverride:
    def test_default_zeros_lockfile(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli._cmd_score(_ns(str(fixture_repo)))  # pyright: ignore[reportPrivateUsage]
        result = cast(ReviewScore, json.loads(capsys.readouterr().out))
        assert result["zeroed"] == ["Cargo.lock"]

    def test_override_changes_score(self, fixture_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = tmp_path / "config.toml"
        _ = config.write_text(
            '[review_surface]\nweights = [["*.lock", 1.0]]\n', encoding="utf-8"
        )
        review_surface_cli._cmd_score(  # pyright: ignore[reportPrivateUsage]
            _ns(str(fixture_repo), config=str(config))
        )
        result = cast(ReviewScore, json.loads(capsys.readouterr().out))
        # Cargo.lock now weighs 1.0 instead of the module default's 0.0.
        assert result["zeroed"] == []
        assert result["score"] == pytest.approx(  # pyright: ignore[reportUnknownMemberType]
            review_surface.score(
                [("a.txt", 2, 0), ("Cargo.lock", 5, 0)],
                weights=(("*.lock", 1.0),),
            )["score"]
        )

    def test_omitted_config_uses_module_defaults(self, fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        review_surface_cli._cmd_score(_ns(str(fixture_repo)))  # pyright: ignore[reportPrivateUsage]
        result = cast(ReviewScore, json.loads(capsys.readouterr().out))
        # Independent literal (not computed by calling score()) so this
        # test can actually fail if _cmd_score stops using module defaults.
        assert result["weighted_files"] == pytest.approx(1.0)  # pyright: ignore[reportUnknownMemberType]
        assert result["weighted_lines"] == pytest.approx(2.0)  # pyright: ignore[reportUnknownMemberType]
        assert result["zeroed"] == ["Cargo.lock"]
        assert result["weights_source"] == "defaults"


class TestErrorHandling:
    def test_malformed_toml_exits_nonzero(self, fixture_repo: Path, tmp_path: Path) -> None:
        config = tmp_path / "bad.toml"
        _ = config.write_text("this is not [ valid toml", encoding="utf-8")
        with pytest.raises(cli.CliError, match="malformed TOML"):
            review_surface_cli._cmd_score(  # pyright: ignore[reportPrivateUsage]
                _ns(str(fixture_repo), config=str(config))
            )

    def test_unreadable_git_ref_exits_nonzero(self, fixture_repo: Path) -> None:
        with pytest.raises(cli.CliError, match="git diff"):
            review_surface_cli._cmd_score(  # pyright: ignore[reportPrivateUsage]
                _ns(str(fixture_repo), diff_args=["not-a-real-ref"])
            )


class TestInjectionGuard:
    """A diff_args element starting with '-' must be rejected before it ever
    reaches git -- the actual security property is that no argument can be
    smuggled through to git as a flag (e.g. an --output=<path> that would
    write a file git never intended to)."""

    def test_leading_dash_diff_arg_raises_and_writes_no_file(
        self, fixture_repo: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "should_not_exist"
        with pytest.raises(cli.CliError, match=r"must not start with '-'"):
            review_surface_cli._cmd_score(  # pyright: ignore[reportPrivateUsage]
                _ns(str(fixture_repo), diff_args=[f"--output={target}"])
            )
        assert not target.exists()


class TestNumstatRows:
    """review_surface_cli._numstat_rows -- git's binary-diff marker `-`
    must be converted to 0, split("\t", 2) must protect paths that contain
    spaces, and rename/non-ASCII paths (verified empirically against real
    `git diff --numstat -z --no-renames`) must parse and weigh correctly."""

    def test_binary_diff_rows_zeroed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_run_git(monkeypatch, "10\t5\tsrc/a.py\0-\t-\tassets/logo.png\0")
        rows = review_surface_cli._numstat_rows(  # pyright: ignore[reportPrivateUsage]
            "irrelevant-repo", ["HEAD"]
        )
        assert rows == [("src/a.py", 10, 5), ("assets/logo.png", 0, 0)]

    def test_path_with_spaces_parses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_run_git(monkeypatch, "3\t1\tsrc/file with spaces.py\0")
        rows = review_surface_cli._numstat_rows(  # pyright: ignore[reportPrivateUsage]
            "irrelevant-repo", ["HEAD"]
        )
        assert rows == [("src/file with spaces.py", 3, 1)]

    def test_rename_nonascii_and_binary_rows_weighted_correctly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Layout confirmed empirically: `--no-renames` turns a rename into a
        # delete + add pair; NUL-delimited records of "ins\tdel\tpath".
        stdout = (
            "0\t2\told.txt\0"
            "2\t0\tnew name.txt\0"
            "1\t0\tcafé.txt\0"
            "-\t-\tbin.dat\0"
        )
        _stub_run_git(monkeypatch, stdout)
        rows = review_surface_cli._numstat_rows(  # pyright: ignore[reportPrivateUsage]
            "irrelevant-repo", ["HEAD"]
        )
        assert rows == [
            ("old.txt", 0, 2),
            ("new name.txt", 2, 0),
            ("café.txt", 1, 0),
            ("bin.dat", 0, 0),
        ]
        for path, _ins, _del in rows:
            assert review_surface.weigh(path) == 1.0


class TestLoadWeightOverrideEdgeShapes:
    def test_table_without_weights_key_returns_none(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        _ = config.write_text("[review_surface]\nother_key = 1\n", encoding="utf-8")
        assert (
            review_surface_cli._load_weight_override(str(config))  # pyright: ignore[reportPrivateUsage]
            is None
        )

    def test_missing_table_returns_none(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        _ = config.write_text("[other_section]\nkey = 1\n", encoding="utf-8")
        assert (
            review_surface_cli._load_weight_override(str(config))  # pyright: ignore[reportPrivateUsage]
            is None
        )

    def test_empty_weights_list_returns_empty_tuple_not_none(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        _ = config.write_text("[review_surface]\nweights = []\n", encoding="utf-8")
        result = review_surface_cli._load_weight_override(str(config))  # pyright: ignore[reportPrivateUsage]
        assert result == ()
        assert result is not None

        # Deliberate "replaces wholesale" semantic: an empty override list
        # means NO exclusions at all, not "no override" -- weigh() falls
        # through to the 1.0 default for every path, so an all-lockfile
        # diff scored with an empty override is NOT zeroed.
        rows = [("pnpm-lock.yaml", 400, 276)]
        scored = review_surface.score(rows, weights=result)
        assert scored["zeroed"] == []
        assert scored["score"] == pytest.approx(  # pyright: ignore[reportUnknownMemberType]
            676.0 + review_surface.FILE_COST * 1.0
        )

    def test_missing_config_path_raises_cannot_read(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.toml"
        with pytest.raises(cli.CliError, match="cannot read config"):
            _ = review_surface_cli._load_weight_override(  # pyright: ignore[reportPrivateUsage]
                str(missing)
            )

    def test_malformed_toml_raises_malformed_toml(self, tmp_path: Path) -> None:
        config = tmp_path / "bad.toml"
        _ = config.write_text("this is not [ valid toml", encoding="utf-8")
        with pytest.raises(cli.CliError, match="malformed TOML"):
            _ = review_surface_cli._load_weight_override(  # pyright: ignore[reportPrivateUsage]
                str(config)
            )


class TestMalformedWeightTables:
    """Each shape must raise cli.CliError naming the offending entry --
    never a raw traceback from an out-of-range or wrong-typed value."""

    @pytest.mark.parametrize(
        "toml_text,match",
        [
            pytest.param(
                '[review_surface]\nweights = [["*", -1000.0]]\n',
                r"weights\[0\] weight must be finite in \[0\.0, 1\.0\]",
                id="weight-out-of-range",
            ),
            pytest.param(
                '[review_surface]\nweights = [["*.lock", 1.0, "extra"]]\n',
                r"weights\[0\] must be a \[glob, weight\] pair",
                id="triple-entry",
            ),
            pytest.param(
                '[review_surface]\nweights = [["*.lock"]]\n',
                r"weights\[0\] must be a \[glob, weight\] pair",
                id="single-entry",
            ),
            pytest.param(
                '[review_surface]\nweights = [["*.lock", "high"]]\n',
                r"weights\[0\] weight must be a number",
                id="non-numeric-weight",
            ),
            pytest.param(
                "[review_surface]\nweights = 5\n",
                r"weights must be a list, got int",
                id="weights-not-a-list",
            ),
        ],
    )
    def test_malformed_shape_raises_cli_error(self, tmp_path: Path, toml_text: str, match: str) -> None:
        config = tmp_path / "config.toml"
        _ = config.write_text(toml_text, encoding="utf-8")
        with pytest.raises(cli.CliError, match=match):
            _ = review_surface_cli._load_weight_override(  # pyright: ignore[reportPrivateUsage]
                str(config)
            )
