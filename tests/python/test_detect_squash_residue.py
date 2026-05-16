"""Tests for detect-squash-residue.

Covers detect() across all paths:
- gh-api positive: PR found, SHAs match → unique commits computed, no warning.
- gh-api positive: PR found, SHAs diverged → warning about manual review.
- gh-api positive: multiple PRs → most recent wins, warning emitted.
- Local-synthesis fallback when gh returns None.
- Negative path: neither detector fires.
- In-progress operation detection → correct abort command in remedy.
- Empty branch (no commits ahead of base) → not-detected with warning.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def make_completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _commits(*subjects: str) -> list[dict]:
    """Build branch_commits list. SHA is derived from subject for deterministic matching."""
    return [
        {"sha": f"{i:040x}", "short": f"{i:040x}"[:8], "subject": s}
        for i, s in enumerate(subjects, 1)
    ]


def _gh_payload(*, number: int, commit_oids: list[str], merged_at: str) -> dict:
    return {
        "number": number,
        "url": f"https://example.com/pr/{number}",
        "merge_commit": "f" * 40,
        "merged_at": merged_at,
        "pr_commits": commit_oids,
        "multiple_prs": False,
    }


class TestDetectViaGhApi:
    def test_pr_found_shas_match_yields_no_unique_commits(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("first commit", "second commit")
        gh = _gh_payload(
            number=42,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "gh-api"
        assert result["pr"]["number"] == 42
        assert result["unique_commits"] == []
        assert not any("verify the cherry-pick list" in w for w in result["warnings"])
        assert result["remedy"] == ["git reset --hard origin/main"]

    def test_pr_found_with_unique_followups_lists_cherry_picks(
        self, detect_squash_residue: ModuleType
    ) -> None:
        squashed = _commits("squashed-1", "squashed-2")
        followups = _commits("post-merge-fix", "another-post-merge")
        # Offset followup SHAs so they don't collide with squashed.
        for i, c in enumerate(followups, start=100):
            c["sha"] = f"{i:040x}"
            c["short"] = c["sha"][:8]
        all_commits = squashed + followups
        gh = _gh_payload(
            number=7,
            commit_oids=[c["sha"] for c in squashed],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=all_commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        unique_subjects = [c["subject"] for c in result["unique_commits"]]
        assert unique_subjects == ["post-merge-fix", "another-post-merge"]
        cherry_pick_line = next((r for r in result["remedy"] if "cherry-pick" in r), None)
        assert cherry_pick_line is not None
        assert all(c["sha"] in cherry_pick_line for c in followups)

    def test_force_pushed_branch_warns_on_sha_divergence(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # Local commits have completely different SHAs from PR commits (rebase after merge).
        local_commits = _commits("local-1", "local-2")
        gh = _gh_payload(
            number=99,
            commit_oids=["a" * 40, "b" * 40],  # don't match local SHAs
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=local_commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert any("verify the cherry-pick list" in w for w in result["warnings"])
        # All local commits treated as unique since none matched the PR.
        assert len(result["unique_commits"]) == len(local_commits)


class TestRemedyCompleteness:
    """The remedy must give the user a recovery path: a cherry-pick line when
    follow-up commits exist, and nothing extra when all branch commits were
    squashed (no follow-ups to recover)."""

    def test_force_pushed_branch_still_gets_cherry_pick_remedy(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # SHAs diverged from PR (post-merge rebase). All local commits become
        # unique → cherry-pick remedy lists every one of them.
        local = _commits("rebased-local-1", "rebased-local-2")
        gh = _gh_payload(
            number=1,
            commit_oids=["a" * 40],  # don't match local SHAs
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=local),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        cherry_pick_line = next((r for r in result["remedy"] if "cherry-pick" in r), None)
        assert cherry_pick_line is not None
        assert all(c["sha"] in cherry_pick_line for c in local)
        assert any("verify the cherry-pick list" in w for w in result["warnings"])

    def test_full_sha_match_remedy_is_reset_only(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # All local commits matched PR commits → no follow-ups → `reset --hard`
        # is the complete remedy. No cherry-pick, no manual review block.
        commits = _commits("squashed-a", "squashed-b")
        gh = _gh_payload(
            number=2,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["remedy"] == ["git reset --hard origin/main"]

    def test_multiple_prs_warns_and_uses_most_recent(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("c1")
        gh = _gh_payload(
            number=10,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        gh["multiple_prs"] = True
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert any("multiple merged PRs" in w for w in result["warnings"])


class TestDetectViaLocalSynthesis:
    def test_synth_positive_when_gh_returns_none(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a", "b")
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=True),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "local-synth"
        assert result["unique_commits"] == []
        assert any("review branch commits manually" in w for w in result["warnings"])
        # Remedy must include the manual-review comment block.
        assert any(r.startswith("# review") for r in result["remedy"])
        assert any(c["short"] in r for c in commits for r in result["remedy"] if r.startswith("#"))

    def test_synth_negative_yields_not_detected(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a")
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=False),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "not-detected"
        assert result["remedy"] == []


class TestEdgeCases:
    def test_no_commits_between_base_and_head(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=[]),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "not-detected"
        assert any("no commits between" in w for w in result["warnings"])

    def test_in_progress_rebase_prepends_abort(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a")
        gh = _gh_payload(
            number=1, commit_oids=[c["sha"] for c in commits], merged_at="2026-05-15T12:00:00Z"
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(
                detect_squash_residue, "_in_progress_abort", return_value="git rebase --abort"
            ),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["remedy"][0] == "git rebase --abort"
        assert result["remedy"][1] == "git reset --hard origin/main"

    def test_in_progress_cherry_pick_prepends_correct_abort(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a")
        gh = _gh_payload(
            number=1, commit_oids=[c["sha"] for c in commits], merged_at="2026-05-15T12:00:00Z"
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(
                detect_squash_residue,
                "_in_progress_abort",
                return_value="git cherry-pick --abort",
            ),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["remedy"][0] == "git cherry-pick --abort"


class TestInProgressAbort:
    def test_detects_rebase_apply(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        (gd / "rebase-apply").mkdir(parents=True)
        with patch.object(
            detect_squash_residue,
            "run_git",
            return_value=make_completed(stdout=str(gd)),
        ):
            assert detect_squash_residue._in_progress_abort() == "git rebase --abort"

    def test_detects_rebase_merge(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        (gd / "rebase-merge").mkdir(parents=True)
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._in_progress_abort() == "git rebase --abort"

    def test_detects_merge(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        gd.mkdir()
        (gd / "MERGE_HEAD").write_text("deadbeef")
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._in_progress_abort() == "git merge --abort"

    def test_detects_cherry_pick(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        gd.mkdir()
        (gd / "CHERRY_PICK_HEAD").write_text("deadbeef")
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._in_progress_abort() == "git cherry-pick --abort"

    def test_no_in_progress_returns_none(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        gd.mkdir()
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._in_progress_abort() is None


class TestGhApiCall:
    def test_returns_none_when_gh_missing(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(detect_squash_residue, "_gh_available", return_value=False):
            assert detect_squash_residue._check_via_gh("feature", "origin/main") is None

    def test_returns_none_on_gh_failure(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with (
            patch.object(detect_squash_residue, "_gh_available", return_value=True),
            patch.object(
                detect_squash_residue.subprocess,
                "run",
                return_value=make_completed(returncode=1),
            ),
        ):
            assert detect_squash_residue._check_via_gh("feature", "origin/main") is None

    def test_returns_none_on_empty_pr_list(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with (
            patch.object(detect_squash_residue, "_gh_available", return_value=True),
            patch.object(
                detect_squash_residue.subprocess,
                "run",
                return_value=make_completed(stdout="[]"),
            ),
        ):
            assert detect_squash_residue._check_via_gh("feature", "origin/main") is None

    def test_picks_most_recent_when_multiple_prs(
        self, detect_squash_residue: ModuleType
    ) -> None:
        payload = json.dumps([
            {
                "number": 1,
                "url": "https://example.com/pr/1",
                "mergeCommit": {"oid": "a" * 40},
                "mergedAt": "2026-01-01T00:00:00Z",
                "commits": [{"oid": "1" * 40}],
            },
            {
                "number": 2,
                "url": "https://example.com/pr/2",
                "mergeCommit": {"oid": "b" * 40},
                "mergedAt": "2026-05-15T00:00:00Z",
                "commits": [{"oid": "2" * 40}],
            },
        ])
        with (
            patch.object(detect_squash_residue, "_gh_available", return_value=True),
            patch.object(
                detect_squash_residue.subprocess,
                "run",
                return_value=make_completed(stdout=payload),
            ),
        ):
            result = detect_squash_residue._check_via_gh("feature", "origin/main")

        assert result is not None
        assert result["number"] == 2
        assert result["multiple_prs"] is True

    def test_passes_base_filter_to_gh(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # Regression: PRs merged to a different base must not trigger a
        # false-positive verdict against our base.
        captured = {}

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            captured["cmd"] = cmd
            return make_completed(stdout="[]")

        with (
            patch.object(detect_squash_residue, "_gh_available", return_value=True),
            patch.object(detect_squash_residue.subprocess, "run", side_effect=fake_run),
        ):
            detect_squash_residue._check_via_gh("feature", "origin/main")

        assert "--base" in captured["cmd"]
        base_idx = captured["cmd"].index("--base")
        assert captured["cmd"][base_idx + 1] == "main"  # remote prefix stripped
        # --head must still be present and use the raw branch name.
        head_idx = captured["cmd"].index("--head")
        assert captured["cmd"][head_idx + 1] == "feature"


class TestBaseBranchName:
    def test_strips_origin_prefix(self, detect_squash_residue: ModuleType) -> None:
        assert detect_squash_residue._base_branch_name("origin/main") == "main"

    def test_preserves_branch_without_remote(
        self, detect_squash_residue: ModuleType
    ) -> None:
        assert detect_squash_residue._base_branch_name("main") == "main"

    def test_handles_multi_segment_branch(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # `upstream/release/1.0` should yield `release/1.0`.
        assert (
            detect_squash_residue._base_branch_name("upstream/release/1.0")
            == "release/1.0"
        )


class TestRefValidation:
    """Inputs flow into a printed copy-paste remedy. Reject shell metacharacters
    so the printed remedy can't be made to mislead the user."""

    def test_safe_ref_accepts_normal_refs(
        self, detect_squash_residue: ModuleType
    ) -> None:
        for ref in ("origin/main", "main", "release/1.0", "feature_x", "v1.2.3-rc1"):
            assert detect_squash_residue._SAFE_REF.match(ref), ref

    def test_safe_ref_rejects_shell_metacharacters(
        self, detect_squash_residue: ModuleType
    ) -> None:
        for ref in (
            "origin/main; rm -rf ~",
            "origin/main`whoami`",
            "origin/main $(echo x)",
            "origin/main | cat",
            "origin/main\nrm -rf",
        ):
            assert not detect_squash_residue._SAFE_REF.match(ref), ref


class TestFormatTerse:
    def test_not_detected_prints_verdict(
        self, detect_squash_residue: ModuleType
    ) -> None:
        out = detect_squash_residue.format_terse({
            "verdict": "not-detected",
            "branch": "feature",
            "base": "origin/main",
            "warnings": [],
        })
        assert "verdict: not-detected" in out

    def test_squash_merged_includes_pr_and_remedy(
        self, detect_squash_residue: ModuleType
    ) -> None:
        d = {
            "verdict": "squash-merged",
            "method": "gh-api",
            "pr": {
                "number": 42,
                "url": "https://example.com/pr/42",
                "merged_at": "2026-05-15T12:00:00Z",
            },
            "warnings": [],
            "unique_commits": [
                {"sha": "a" * 40, "short": "a" * 8, "subject": "follow-up"}
            ],
            "branch_commits": [],
            "remedy": [
                "git rebase --abort",
                "git reset --hard origin/main",
                "git cherry-pick aaaaaaaa",
            ],
        }
        out = detect_squash_residue.format_terse(d)
        assert "SQUASH-MERGED via PR #42" in out
        assert "https://example.com/pr/42" in out
        assert "follow-up" in out
        assert "git rebase --abort" in out
        assert "destructive, review first" in out
