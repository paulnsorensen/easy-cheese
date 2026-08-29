"""Tests for shared/scripts/worktree.py — create / harvest / teardown.

Locks acceptance #5: the helper harvests a curd branch onto the orchestrator
branch with no `git fetch` (shared object store), and tears the worktree and
branch down afterwards so no `worktree-agent-*` branch or
`.claude/worktrees/agent-*` dir leaks.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from easy_cheese.shared import cli, worktree


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _ = _run(r, "init", "-b", "main")
    _ = _run(r, "config", "user.email", "t@example.com")
    _ = _run(r, "config", "user.name", "Tester")
    _ = (r / "base.txt").write_text("base\n", encoding="utf-8")
    _ = _run(r, "add", "-A")
    _ = _run(r, "commit", "-m", "init")
    return r


class TestCreate:
    def test_native_path_and_branch_shape(self, repo: Path) -> None:
        info = worktree.create("curd1", "main", repo=str(repo))
        assert info["path"] == ".claude/worktrees/agent-curd1"
        assert info["branch"] == "worktree-agent-curd1"
        assert (repo / str(info["path"])).is_dir()
        branches = _run(repo, "branch", "--list", "worktree-agent-curd1").stdout
        assert "worktree-agent-curd1" in branches


    def test_inherits_uncommitted_cut_oracle_without_committing_it(
        self, repo: Path
    ) -> None:
        oracle = repo / "tests/oracle.py"
        oracle.parent.mkdir()
        _ = oracle.write_text("assert feature() == 'ready'\n", encoding="utf-8")
        digest = hashlib.sha256(oracle.read_bytes()).hexdigest()
        token = repo / ".cheese/cut/example.phase.json"
        token.parent.mkdir(parents=True)
        _ = token.write_text('{"phase": "entry"}\n', encoding="utf-8")
        token_digest = hashlib.sha256(token.read_bytes()).hexdigest()
        receipt = repo / ".cheese/cut/example.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "phase_token_ref": ".cheese/cut/example.phase.json",
                    "phase_token_sha256": token_digest,
                    "protected_files": [
                        {"path": "tests/oracle.py", "sha256": digest}
                    ],
                }
            ),
            encoding="utf-8",
        )

        info = worktree.create(
            "oracle", "main", repo=str(repo), receipt=".cheese/cut/example.json"
        )
        child = repo / str(info["path"])
        assert (child / "tests/oracle.py").read_bytes() == oracle.read_bytes()
        assert (
            child / ".cheese/cut/example.phase.json"
        ).read_bytes() == token.read_bytes()
        assert (child / ".cheese/cut/example.json").read_bytes() == receipt.read_bytes()
        assert info["inherited"] == [
            "tests/oracle.py",
            ".cheese/cut/example.phase.json",
            ".cheese/cut/example.json",
        ]
        assert _run(repo, "rev-list", "--count", "main..worktree-agent-oracle").stdout.strip() == "0"

    def test_failed_oracle_inheritance_rolls_back_worktree(
        self, repo: Path
    ) -> None:
        oracle = repo / "oracle.py"
        _ = oracle.write_text("assert False\n", encoding="utf-8")
        receipt = repo / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [
                        {"path": "oracle.py", "sha256": "0" * 64}
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(cli.CliError, match="digest mismatch"):
            _ = worktree.create(
                "bad-oracle", "main", repo=str(repo), receipt="receipt.json"
            )
        assert "agent-bad-oracle" not in _run(repo, "worktree", "list").stdout
        assert "worktree-agent-bad-oracle" not in _run(
            repo, "branch", "--list"
        ).stdout


class TestOracleHarvest:
    def test_harvests_child_press_receipt_and_tests_before_teardown(
        self, repo: Path
    ) -> None:
        info = worktree.create("press-oracle", "main", repo=str(repo))
        child = repo / str(info["path"])
        oracle = child / "tests/hardening.py"
        oracle.parent.mkdir()
        _ = oracle.write_text("assert boundary_is_guarded()\n", encoding="utf-8")
        digest = hashlib.sha256(oracle.read_bytes()).hexdigest()
        receipt = child / ".cheese/press/curd.json"
        receipt.parent.mkdir(parents=True)
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "press",
                    "disposition": "red",
                    "protected_files": [
                        {"path": "tests/hardening.py", "sha256": digest}
                    ],
                }
            ),
            encoding="utf-8",
        )

        inherited = worktree.inherit_oracle(
            ".cheese/press/curd.json",
            str(repo),
            repo=str(child),
            expected_producer="press",
            overwrite=False,
        )

        assert inherited == [
            "tests/hardening.py",
            ".cheese/press/curd.json",
        ]
        assert (repo / "tests/hardening.py").read_bytes() == oracle.read_bytes()
        assert (repo / ".cheese/press/curd.json").read_bytes() == receipt.read_bytes()

    def test_harvest_refuses_cross_curd_oracle_conflict(
        self, repo: Path
    ) -> None:
        info = worktree.create("press-conflict", "main", repo=str(repo))
        child = repo / str(info["path"])
        child_oracle = child / "oracle.py"
        _ = child_oracle.write_text("assert new_contract()\n", encoding="utf-8")
        digest = hashlib.sha256(child_oracle.read_bytes()).hexdigest()
        receipt = child / "press.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "press",
                    "disposition": "red",
                    "protected_files": [{"path": "oracle.py", "sha256": digest}],
                }
            ),
            encoding="utf-8",
        )
        parent_oracle = repo / "oracle.py"
        _ = parent_oracle.write_text("assert other_contract()\n", encoding="utf-8")

        with pytest.raises(cli.CliError, match="oracle harvest conflict"):
            _ = worktree.inherit_oracle(
                "press.json",
                str(repo),
                repo=str(child),
                expected_producer="press",
                overwrite=False,
            )
        assert parent_oracle.read_text(encoding="utf-8") == "assert other_contract()\n"

class TestOracleTransferTransaction:
    def test_later_staging_failure_restores_destination(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        _ = (destination_root / "existing.txt").write_text(
            "keep me\n", encoding="utf-8"
        )
        source_nested = source_root / "nested"
        source_nested.mkdir()
        for name in ("first.txt", "second.txt"):
            _ = (source_nested / name).write_text(f"{name}\n", encoding="utf-8")
        receipt = source_root / "receipt.json"
        protected_files = [
            {
                "path": f"nested/{name}",
                "sha256": hashlib.sha256(
                    (source_nested / name).read_bytes()
                ).hexdigest(),
            }
            for name in ("first.txt", "second.txt")
        ]
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": protected_files,
                }
            ),
            encoding="utf-8",
        )
        original_copy2 = shutil.copy2
        calls = 0

        def fail_on_second_copy(source: Path, target: Path) -> Path | str:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected staging failure")
            return original_copy2(source, target)

        monkeypatch.setattr(shutil, "copy2", fail_on_second_copy)

        with pytest.raises(cli.CliError, match="oracle transfer failed"):
            _ = worktree.inherit_oracle(
                "receipt.json", str(destination_root), repo=str(source_root)
            )

        assert sorted(path.name for path in destination_root.iterdir()) == [
            "existing.txt"
        ]
        assert (destination_root / "existing.txt").read_text() == "keep me\n"
        assert not (destination_root / "nested").exists()

    def test_later_commit_failure_restores_overwrites_and_new_files(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        _ = (source_root / "first.txt").write_text("new first\n", encoding="utf-8")
        _ = (source_root / "second.txt").write_text("new second\n", encoding="utf-8")
        _ = (destination_root / "first.txt").write_text(
            "old first\n", encoding="utf-8"
        )
        receipt = source_root / "receipt.json"
        protected_files = [
            {
                "path": name,
                "sha256": hashlib.sha256(
                    (source_root / name).read_bytes()
                ).hexdigest(),
            }
            for name in ("first.txt", "second.txt")
        ]
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": protected_files,
                }
            ),
            encoding="utf-8",
        )
        original_replace = os.replace
        calls = 0

        def fail_on_second_commit(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected commit failure")
            original_replace(source, target)

        monkeypatch.setattr(os, "replace", fail_on_second_commit)

        with pytest.raises(cli.CliError, match="oracle transfer failed"):
            _ = worktree.inherit_oracle(
                "receipt.json", str(destination_root), repo=str(source_root)
            )

        assert (destination_root / "first.txt").read_text() == "old first\n"
        assert not (destination_root / "second.txt").exists()
        assert not (destination_root / "receipt.json").exists()


class TestOracleTransferPaths:
    def test_receipt_symlink_is_rejected(
        self, repo: Path
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        receipt = source_root / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [{"path": "oracle.py", "sha256": "0" * 64}],
                }
            ),
            encoding="utf-8",
        )
        (source_root / "receipt-link.json").symlink_to(receipt)

        with pytest.raises(cli.CliError, match="symlink"):
            _ = worktree.inherit_oracle(
                "receipt-link.json",
                str(destination_root),
                repo=str(source_root),
            )
        assert list(destination_root.iterdir()) == []

    def test_protected_source_symlink_is_rejected(
        self, repo: Path
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        oracle = source_root / "oracle.py"
        _ = oracle.write_text("assert guarded()\n", encoding="utf-8")
        (source_root / "oracle-link.py").symlink_to(oracle)
        receipt = source_root / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [
                        {
                            "path": "oracle-link.py",
                            "sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(cli.CliError, match="symlink"):
            _ = worktree.inherit_oracle(
                "receipt.json", str(destination_root), repo=str(source_root)
            )
        assert list(destination_root.iterdir()) == []

    def test_destination_symlink_traversal_is_rejected(
        self, repo: Path, tmp_path: Path
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        outside = tmp_path / "outside"
        source_root.mkdir()
        destination_root.mkdir()
        outside.mkdir()
        oracle = source_root / "nested" / "oracle.py"
        oracle.parent.mkdir()
        _ = oracle.write_text("assert guarded()\n", encoding="utf-8")
        (destination_root / "nested").symlink_to(outside, target_is_directory=True)
        receipt = source_root / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [
                        {
                            "path": "nested/oracle.py",
                            "sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(cli.CliError, match="symlink"):
            _ = worktree.inherit_oracle(
                "receipt.json", str(destination_root), repo=str(source_root)
            )
        assert list(outside.iterdir()) == []
        assert (destination_root / "nested").is_symlink()

    @pytest.mark.parametrize("bad_receipt", ["../receipt.json", "/tmp/receipt.json"])
    def test_receipt_escape_is_rejected(
        self, repo: Path, bad_receipt: str
    ) -> None:
        destination_root = repo / "destination"
        destination_root.mkdir()

        with pytest.raises(cli.CliError, match="project-relative"):
            _ = worktree.inherit_oracle(
                bad_receipt, str(destination_root), repo=str(repo)
            )
        assert list(destination_root.iterdir()) == []

    def test_protected_path_escape_is_rejected(
        self, repo: Path
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        receipt = source_root / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [
                        {"path": "../outside.py", "sha256": "0" * 64}
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(cli.CliError, match="project-relative"):
            _ = worktree.inherit_oracle(
                "receipt.json", str(destination_root), repo=str(source_root)
            )
        assert list(destination_root.iterdir()) == []

    def test_destination_root_escape_is_rejected(
        self, repo: Path
    ) -> None:
        source_root = repo / "source"
        destination_root = repo / "destination"
        source_root.mkdir()
        destination_root.mkdir()
        receipt = source_root / "receipt.json"
        _ = receipt.write_text(
            json.dumps(
                {
                    "producer": "cut",
                    "disposition": "red",
                    "protected_files": [
                        {"path": "oracle.py", "sha256": "0" * 64}
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(cli.CliError, match="remain within"):
            _ = worktree.inherit_oracle(
                "receipt.json", "../destination", repo=str(source_root)
            )
        assert list(destination_root.iterdir()) == []

class TestHarvest:
    def test_cherry_picks_curd_commit_without_fetch(
        self, repo: Path
    ) -> None:
        info = worktree.create("curd2", "main", repo=str(repo))
        wt = repo / str(info["path"])
        _ = (wt / "feature.txt").write_text("feature\n", encoding="utf-8")
        _ = _run(wt, "add", "-A")
        _ = _run(wt, "commit", "-m", "add feature")

        # No remote is configured, so a successful harvest proves no fetch.
        assert _run(repo, "remote").stdout.strip() == ""
        picked = worktree.harvest(str(info["branch"]), "main", repo=str(repo))

        assert len(picked) == 1
        assert (repo / "feature.txt").exists()
        head_branch = _run(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        assert head_branch == "main"

    def test_empty_range_returns_empty(self, repo: Path) -> None:
        info = worktree.create("curd3", "main", repo=str(repo))
        assert worktree.harvest(str(info["branch"]), "main", repo=str(repo)) == []

    def test_multiple_commits_harvested_in_order(
        self, repo: Path
    ) -> None:
        info = worktree.create("curd5", "main", repo=str(repo))
        wt = repo / str(info["path"])
        for i in range(3):
            _ = (wt / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
            _ = _run(wt, "add", "-A")
            _ = _run(wt, "commit", "-m", f"commit {i}")
        # Oldest-first: the picked SHAs must equal `git rev-list --reverse`.
        expected = _run(
            repo, "rev-list", "--reverse", f"main..{info['branch']}"
        ).stdout.split()
        picked = worktree.harvest(str(info["branch"]), "main", repo=str(repo))
        assert picked == expected
        assert len(expected) == 3
        for i in range(3):
            assert (repo / f"f{i}.txt").exists()

    def test_conflict_aborts_and_leaves_repo_clean(
        self, repo: Path
    ) -> None:
        # Two commits edit the same file on branch and onto → cherry-pick
        # conflict. harvest must raise AND abort, so the repo is not left
        # mid-cherry-pick (which would poison the next harvest's checkout).
        info = worktree.create("curd8", "main", repo=str(repo))
        wt = repo / str(info["path"])
        _ = (wt / "base.txt").write_text("worktree edit\n", encoding="utf-8")
        _ = _run(wt, "add", "-A")
        _ = _run(wt, "commit", "-m", "wt edit")
        _ = (repo / "base.txt").write_text("main edit\n", encoding="utf-8")
        _ = _run(repo, "add", "-A")
        _ = _run(repo, "commit", "-m", "main edit")

        with pytest.raises(cli.CliError):
            _ = worktree.harvest(str(info["branch"]), "main", repo=str(repo))

        # No CHERRY_PICK_HEAD left behind.
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD"],
            capture_output=True,
            text=True,
        )
        assert head.returncode != 0
        # A subsequent checkout succeeds — repo is clean for the /melt fallback.
        _ = _run(repo, "checkout", "main")


class TestTeardown:
    def test_no_worktree_or_branch_leaks(self, repo: Path) -> None:
        info = worktree.create("curd4", "main", repo=str(repo))
        worktree.teardown(str(info["path"]), str(info["branch"]), repo=str(repo))

        assert not (repo / str(info["path"])).exists()
        branches = _run(repo, "branch", "--list", "worktree-agent-curd4").stdout
        assert "worktree-agent-curd4" not in branches
        assert "agent-curd4" not in _run(repo, "worktree", "list").stdout

    def test_full_lifecycle_leaves_clean_tree(
        self, repo: Path
    ) -> None:
        info = worktree.create("curd6", "main", repo=str(repo))
        wt = repo / str(info["path"])
        _ = (wt / "x.txt").write_text("x\n", encoding="utf-8")
        _ = _run(wt, "add", "-A")
        _ = _run(wt, "commit", "-m", "x")
        _ = worktree.harvest(str(info["branch"]), "main", repo=str(repo))
        worktree.teardown(str(info["path"]), str(info["branch"]), repo=str(repo))

        # No leaked worktree registrations or branches for a completed run.
        listing = _run(repo, "worktree", "list").stdout
        assert "agent-curd6" not in listing
        assert "worktree-agent-curd6" not in _run(repo, "branch", "--list").stdout

    def test_partial_teardown_still_deletes_branch(
        self, repo: Path
    ) -> None:
        # Worktree dir vanishes out from under us (remove will fail), but the
        # branch still exists. teardown must still delete the branch — the
        # remove failure must not skip the branch delete, or the branch leaks.
        info = worktree.create("curd7", "main", repo=str(repo))
        shutil.rmtree(repo / str(info["path"]))
        _ = _run(repo, "worktree", "prune")

        with pytest.raises(cli.CliError):
            worktree.teardown(str(info["path"]), str(info["branch"]), repo=str(repo))

        branches = _run(repo, "branch", "--list", "worktree-agent-curd7").stdout
        assert "worktree-agent-curd7" not in branches


class TestFailsLoud:
    def test_teardown_of_missing_worktree_raises(
        self, repo: Path
    ) -> None:
        with pytest.raises(cli.CliError):
            worktree.teardown(
                ".claude/worktrees/agent-nope", "worktree-agent-nope", repo=str(repo)
            )


class TestCreateValidatesSlug:
    """Review fix: create() must reject a slug that escapes
    .claude/worktrees/agent-<slug> — a path separator or '..' would place the
    worktree and branch at an attacker-chosen location."""

    @pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "", "a\\b"])
    def test_bad_slug_raises_and_creates_nothing(
        self, repo: Path, bad: str
    ) -> None:
        with pytest.raises(cli.CliError, match="invalid slug"):
            _ = worktree.create(bad, "main", repo=str(repo))
        assert "agent-" not in _run(repo, "worktree", "list").stdout


class TestTeardownGuardsTarget:
    """Review fix: teardown() must refuse a path outside
    .claude/worktrees/agent-* or a branch not named worktree-agent-*, so a bad
    argument cannot force-remove an arbitrary path or force-delete a branch."""

    def test_path_outside_worktree_dir_refused(
        self, repo: Path
    ) -> None:
        with pytest.raises(cli.CliError, match="refusing to tear down"):
            worktree.teardown("some/other/dir", "worktree-agent-x", repo=str(repo))

    def test_escaping_path_refused(self, repo: Path) -> None:
        with pytest.raises(cli.CliError, match="refusing to tear down"):
            worktree.teardown(
                ".claude/worktrees/../../etc/agent-x", "worktree-agent-x", repo=str(repo)
            )

    def test_non_worktree_branch_refused(
        self, repo: Path
    ) -> None:
        with pytest.raises(cli.CliError, match="refusing to delete branch"):
            worktree.teardown(".claude/worktrees/agent-x", "main", repo=str(repo))