"""Tests for detect-squash-residue.

Covers detect() across all paths:
- Tree-match positive: branch commit's tree found on base → strongest signal.
- Tree-match + gh: PR metadata enriches tree-match result.
- Tree-match negative + gh positive: falls back to SHA-overlap detection.
- gh-api positive: PR found, SHAs match → unique commits computed, no warning.
- gh-api positive: PR found, SHAs diverged → warning about manual review.
- gh-api positive: multiple PRs → most recent wins, warning emitted.
- Local-synthesis fallback when tree-match and gh both return nothing.
- Negative path: no detector fires.
- In-progress operation detection → correct abort command in both remedies.
- Empty branch (no commits ahead of base) → not-detected with warning.
- Dual remedy structure: merge (non-destructive) listed first, then reset+cherry-pick.
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


def _remedy(remedies: list[dict], name: str) -> dict:
    """Look up a remedy by name. Fails the test if missing."""
    for r in remedies:
        if r["name"] == name:
            return r
    raise AssertionError(f"remedy {name!r} missing; got {[r['name'] for r in remedies]}")


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
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "gh-api"
        assert result["pr"]["number"] == 42
        assert result["unique_commits"] == []
        assert not any("verify the cherry-pick list" in w for w in result["warnings"])
        merge = _remedy(result["remedies"], "merge")
        assert merge["destructive"] is False
        assert "git merge origin/main" in merge["commands"]
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        assert reset["destructive"] is True
        # No follow-ups → reset is just `reset --hard`, no cherry-pick line.
        assert "git reset --hard origin/main" in reset["commands"]
        assert not any("cherry-pick" in c for c in reset["commands"])

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
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        unique_subjects = [c["subject"] for c in result["unique_commits"]]
        assert unique_subjects == ["post-merge-fix", "another-post-merge"]
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        cherry_pick_line = next((c for c in reset["commands"] if "cherry-pick" in c), None)
        assert cherry_pick_line is not None
        assert all(c["sha"] in cherry_pick_line for c in followups)
        # Merge remedy is still offered as the non-destructive first choice.
        assert result["remedies"][0]["name"] == "merge"

    def test_zero_sha_overlap_downgrades_to_not_detected_when_synth_negative(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # PR name matched but SHAs don't overlap (reused branch name or fully
        # rebased branch). With local-synth also negative, verdict is
        # not-detected — too weak to emit a destructive remedy.
        local_commits = _commits("local-1", "local-2")
        gh = _gh_payload(
            number=99,
            commit_oids=["a" * 40, "b" * 40],  # don't match local SHAs
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=local_commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=False),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "not-detected"
        assert result["method"] is None
        assert result["pr"] is None
        assert result["remedies"] == []
        assert any("no local commits matched its SHAs" in w for w in result["warnings"])
        assert any("inconclusive" in w for w in result["warnings"])

    def test_zero_sha_overlap_falls_through_to_local_synth(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # PR name matched but SHAs don't overlap; local-synth detects
        # tree-equivalent residue → squash-merged via local-synth (not gh-api).
        local_commits = _commits("rebased-1", "rebased-2")
        gh = _gh_payload(
            number=99,
            commit_oids=["a" * 40, "b" * 40],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=local_commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=True),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "local-synth"
        assert result["pr"] is None  # gh-api result was discarded
        assert any("no local commits matched its SHAs" in w for w in result["warnings"])
        # Manual review block emitted in the destructive remedy since
        # local-synth has no SHA list.
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        assert any(c.startswith("# review") for c in reset["commands"])


class TestRemedyCompleteness:
    """Every squash-merged verdict must offer both options: a non-destructive
    merge and a destructive reset+cherry-pick. The destructive option must
    give the user a recovery path (cherry-pick line when follow-ups exist,
    manual-review block when local-synth, no extras when fully contained)."""

    def test_force_pushed_branch_recovery_via_local_synth(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # SHAs diverged from PR (post-merge rebase). Tree-match misses,
        # gh-api downgrades to inconclusive, local-synth confirms via tree
        # equivalence. The destructive remedy must include the manual-review
        # block listing all local commits.
        local = _commits("rebased-local-1", "rebased-local-2")
        gh = _gh_payload(
            number=1,
            commit_oids=["a" * 40],  # don't match local SHAs
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=local),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=True),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["method"] == "local-synth"
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        review_lines = [c for c in reset["commands"] if c.startswith("#   ")]
        assert review_lines, "manual-review block missing"
        # Every branch commit appears in the manual-review block.
        assert all(any(c["short"] in line for line in review_lines) for c in local)
        # The non-destructive option is still offered.
        assert _remedy(result["remedies"], "merge")["destructive"] is False

    def test_full_sha_match_destructive_path_is_reset_only(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # All local commits matched PR commits → no follow-ups → the destructive
        # remedy is just `reset --hard`. No cherry-pick, no manual review block.
        commits = _commits("squashed-a", "squashed-b")
        gh = _gh_payload(
            number=2,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        assert reset["commands"] == ["git reset --hard origin/main"]

    def test_remedies_listed_in_safety_order(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # The non-destructive merge remedy must always come first so the user
        # sees the safer option before the destructive one.
        commits = _commits("a")
        gh = _gh_payload(
            number=3,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert [r["name"] for r in result["remedies"]] == ["merge", "reset-and-cherry-pick"]
        assert [r["destructive"] for r in result["remedies"]] == [False, True]

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
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert any("multiple merged PRs" in w for w in result["warnings"])


class TestDetectViaLocalSynthesis:
    def test_synth_positive_when_tree_and_gh_return_none(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a", "b")
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=True),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "local-synth"
        assert result["unique_commits"] == []
        assert any("review branch commits manually" in w for w in result["warnings"])
        # Destructive remedy must include the manual-review comment block
        # listing all branch commits (no SHA enumeration available).
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        assert any(c.startswith("# review") for c in reset["commands"])
        for commit in commits:
            assert any(commit["short"] in c for c in reset["commands"] if c.startswith("#"))

    def test_synth_negative_yields_not_detected(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a")
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_check_via_synthesis", return_value=False),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "not-detected"
        assert result["remedies"] == []


class TestCommitsSince:
    def test_returns_none_on_git_failure(self, detect_squash_residue: ModuleType) -> None:
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(returncode=128)
        ):
            assert detect_squash_residue._commits_since("origin/main") is None

    def test_returns_empty_list_for_no_commits(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout="")
        ):
            assert detect_squash_residue._commits_since("origin/main") == []


class TestGitLogFailurePropagation:
    def test_git_log_failure_warns_with_fetch_hint(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "not-detected"
        assert any("git log failed" in w for w in result["warnings"])
        assert any("fetched" in w for w in result["warnings"])


class TestBranchDuringRebase:
    def test_reads_head_name_from_rebase_merge(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        (gd / "rebase-merge").mkdir(parents=True)
        (gd / "rebase-merge" / "head-name").write_text("refs/heads/feature-branch\n")
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._branch_during_rebase() == "feature-branch"

    def test_reads_head_name_from_rebase_apply(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        (gd / "rebase-apply").mkdir(parents=True)
        (gd / "rebase-apply" / "head-name").write_text("refs/heads/fix/my-fix\n")
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._branch_during_rebase() == "fix/my-fix"

    def test_returns_none_when_no_rebase_in_progress(
        self, detect_squash_residue: ModuleType, tmp_path: Path
    ) -> None:
        gd = tmp_path / "git-dir"
        gd.mkdir()
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout=str(gd))
        ):
            assert detect_squash_residue._branch_during_rebase() is None


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

    def test_in_progress_rebase_prepends_abort_to_both_remedies(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a")
        gh = _gh_payload(
            number=1, commit_oids=[c["sha"] for c in commits], merged_at="2026-05-15T12:00:00Z"
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(
                detect_squash_residue, "_in_progress_abort", return_value="git rebase --abort"
            ),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        merge = _remedy(result["remedies"], "merge")
        assert merge["commands"][0] == "git rebase --abort"
        assert "git merge origin/main" in merge["commands"]
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        assert reset["commands"][0] == "git rebase --abort"
        assert reset["commands"][1] == "git reset --hard origin/main"

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
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=None),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(
                detect_squash_residue,
                "_in_progress_abort",
                return_value="git cherry-pick --abort",
            ),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        for r in result["remedies"]:
            assert r["commands"][0] == "git cherry-pick --abort"


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
            # _base_branch_name calls `git remote` to identify registered remotes.
            if cmd[:2] == ["git", "remote"]:
                return make_completed(stdout="origin\n")
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
    def test_strips_registered_remote_prefix(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout="origin\n")
        ):
            assert detect_squash_residue._base_branch_name("origin/main") == "main"

    def test_preserves_branch_without_slash(
        self, detect_squash_residue: ModuleType
    ) -> None:
        assert detect_squash_residue._base_branch_name("main") == "main"

    def test_preserves_slash_branch_not_matching_remote(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # `release/1.0` is a local slash-named branch; "release" is not a remote.
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(stdout="origin\n")
        ):
            assert detect_squash_residue._base_branch_name("release/1.0") == "release/1.0"

    def test_strips_multi_segment_ref_with_registered_remote(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # `upstream/release/1.0` → strip "upstream/", keep "release/1.0".
        with patch.object(
            detect_squash_residue,
            "run_git",
            return_value=make_completed(stdout="origin\nupstream\n"),
        ):
            assert (
                detect_squash_residue._base_branch_name("upstream/release/1.0") == "release/1.0"
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

    def test_squash_merged_includes_pr_and_both_remedies(
        self, detect_squash_residue: ModuleType
    ) -> None:
        d = {
            "verdict": "squash-merged",
            "method": "tree-match+gh",
            "pr": {
                "number": 42,
                "url": "https://example.com/pr/42",
                "merged_at": "2026-05-15T12:00:00Z",
            },
            "squash_commit": {
                "sha": "c" * 40,
                "short": "c" * 8,
                "subject": "Squashed feature (#42)",
            },
            "warnings": [],
            "unique_commits": [
                {"sha": "a" * 40, "short": "a" * 8, "subject": "follow-up"}
            ],
            "branch_commits": [],
            "remedies": [
                {
                    "name": "merge",
                    "destructive": False,
                    "description": "Merge base into branch (non-destructive).",
                    "commands": ["git rebase --abort", "git merge origin/main"],
                },
                {
                    "name": "reset-and-cherry-pick",
                    "destructive": True,
                    "description": "Reset and replay (DESTRUCTIVE).",
                    "commands": [
                        "git rebase --abort",
                        "git reset --hard origin/main",
                        "git cherry-pick aaaaaaaa",
                    ],
                },
            ],
        }
        out = detect_squash_residue.format_terse(d)
        assert "SQUASH-MERGED" in out
        assert "PR=#42" in out
        assert "https://example.com/pr/42" in out
        assert "Squashed feature (#42)" in out
        assert "follow-up" in out
        # Both remedies labeled and ordered.
        assert "[A] merge" in out
        assert "(non-destructive)" in out
        assert "[B] reset-and-cherry-pick" in out
        assert "(DESTRUCTIVE)" in out
        assert out.index("[A] merge") < out.index("[B] reset-and-cherry-pick")
        assert "git merge origin/main" in out
        assert "git cherry-pick aaaaaaaa" in out


def _make_git_log(rows: list[tuple[str, str, str]]) -> subprocess.CompletedProcess:
    """Build a fake `git log --format=%H%x09%T%x09%s` response from rows of
    (sha, tree, subject)."""
    body = "\n".join(f"{sha}\t{tree}\t{subj}" for sha, tree, subj in rows)
    return make_completed(stdout=body)


class TestCheckViaTreeMatch:
    """The detector this fix is for. A commit on base whose tree equals the
    tree at some point on the branch is the canonical squash-merge signature.
    This catches the textbook case the old detector missed: a branch that has
    additional commits past the squash."""

    def test_finds_squash_when_base_commit_tree_matches_branch_tip(
        self, detect_squash_residue: ModuleType
    ) -> None:
        branch_rows = [
            ("sha-feat-1", "tree-1", "feat-1"),
            ("sha-feat-2", "tree-2", "feat-2"),
            ("sha-feat-3", "tree-3", "feat-3"),
        ]
        base_rows = [("sha-squash", "tree-3", "Squashed feat (#42)")]

        def fake_run_git(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["merge-base"]:
                return make_completed(stdout="sha-mb")
            if args[:1] == ["log"] and "--reverse" in args:
                return _make_git_log(branch_rows)
            if args[:1] == ["log"]:
                return _make_git_log(base_rows)
            return make_completed(returncode=1)

        with patch.object(detect_squash_residue, "run_git", side_effect=fake_run_git):
            result = detect_squash_residue._check_via_tree_match("origin/main", "HEAD")

        assert result is not None
        assert result["squash_commit"] == "sha-squash"
        assert [c["subject"] for c in result["squashed_commits"]] == [
            "feat-1",
            "feat-2",
            "feat-3",
        ]
        assert result["unique_commits"] == []

    def test_finds_squash_with_followups_past_the_squash(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # The textbook missed case: PR was squash-merged with 3 of 4 branch
        # commits; the 4th commit landed after the merge. Old local-synth
        # missed this because the full HEAD tree no longer matches the squash.
        branch_rows = [
            ("sha-1", "tree-1", "feat-1"),
            ("sha-2", "tree-2", "feat-2"),
            ("sha-3", "tree-3", "feat-3"),  # squash point
            ("sha-4", "tree-4", "follow-up after squash"),
        ]
        base_rows = [("sha-squash", "tree-3", "Squashed feat (#42)")]

        def fake_run_git(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["merge-base"]:
                return make_completed(stdout="sha-mb")
            if "--reverse" in args:
                return _make_git_log(branch_rows)
            return _make_git_log(base_rows)

        with patch.object(detect_squash_residue, "run_git", side_effect=fake_run_git):
            result = detect_squash_residue._check_via_tree_match("origin/main", "HEAD")

        assert result is not None
        assert result["squash_commit"] == "sha-squash"
        assert [c["subject"] for c in result["squashed_commits"]] == [
            "feat-1",
            "feat-2",
            "feat-3",
        ]
        assert [c["subject"] for c in result["unique_commits"]] == [
            "follow-up after squash"
        ]

    def test_returns_none_when_no_base_commit_matches(
        self, detect_squash_residue: ModuleType
    ) -> None:
        branch_rows = [("sha-1", "tree-1", "feat-1")]
        base_rows = [
            ("sha-x", "tree-x", "unrelated"),
            ("sha-y", "tree-y", "also unrelated"),
        ]

        def fake_run_git(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["merge-base"]:
                return make_completed(stdout="sha-mb")
            if "--reverse" in args:
                return _make_git_log(branch_rows)
            return _make_git_log(base_rows)

        with patch.object(detect_squash_residue, "run_git", side_effect=fake_run_git):
            assert detect_squash_residue._check_via_tree_match("origin/main", "HEAD") is None

    def test_returns_none_on_merge_base_failure(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "run_git", return_value=make_completed(returncode=128)
        ):
            assert detect_squash_residue._check_via_tree_match("origin/main", "HEAD") is None

    def test_returns_none_on_empty_branch_log(
        self, detect_squash_residue: ModuleType
    ) -> None:
        def fake_run_git(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["merge-base"]:
                return make_completed(stdout="sha-mb")
            return make_completed(stdout="")

        with patch.object(detect_squash_residue, "run_git", side_effect=fake_run_git):
            assert detect_squash_residue._check_via_tree_match("origin/main", "HEAD") is None

    def test_prefers_latest_branch_index_when_tree_repeats(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # If two branch commits share a tree (e.g. revert-then-redo), the
        # match must point at the LATER one — that gives the smallest
        # unique-commit set to replay.
        branch_rows = [
            ("sha-1", "tree-A", "first"),
            ("sha-2", "tree-B", "second"),
            ("sha-3", "tree-A", "third (same tree as first)"),
            ("sha-4", "tree-C", "fourth"),
        ]
        base_rows = [("sha-squash", "tree-A", "Squashed")]

        def fake_run_git(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["merge-base"]:
                return make_completed(stdout="sha-mb")
            if "--reverse" in args:
                return _make_git_log(branch_rows)
            return _make_git_log(base_rows)

        with patch.object(detect_squash_residue, "run_git", side_effect=fake_run_git):
            result = detect_squash_residue._check_via_tree_match("origin/main", "HEAD")

        assert result is not None
        # Latest index with tree-A is sha-3 → unique is just the trailing commit.
        assert [c["subject"] for c in result["unique_commits"]] == ["fourth"]


class TestDetectViaTreeMatch:
    """Tree-match is the new primary path through detect(). It must win over
    gh-api when both fire, and supply the unique-commit list directly."""

    def test_tree_match_alone_yields_tree_match_method(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a", "b", "c", "post")
        tree_hit = {
            "squash_commit": "s" * 40,
            "squash_short": "s" * 8,
            "squash_subject": "Squashed feature (#42)",
            "squashed_commits": commits[:3],
            "unique_commits": commits[3:],
        }
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=tree_hit),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "tree-match"
        assert result["pr"] is None
        assert result["squash_commit"]["subject"] == "Squashed feature (#42)"
        assert [c["subject"] for c in result["unique_commits"]] == ["post"]
        # Cherry-pick line in the destructive remedy must use the unique SHA.
        reset = _remedy(result["remedies"], "reset-and-cherry-pick")
        cherry = next((c for c in reset["commands"] if "cherry-pick" in c), None)
        assert cherry is not None and commits[3]["sha"] in cherry

    def test_tree_match_plus_gh_enriches_with_pr_metadata(
        self, detect_squash_residue: ModuleType
    ) -> None:
        commits = _commits("a", "b")
        tree_hit = {
            "squash_commit": "s" * 40,
            "squash_short": "s" * 8,
            "squash_subject": "Squashed",
            "squashed_commits": commits,
            "unique_commits": [],
        }
        gh = _gh_payload(
            number=42,
            commit_oids=[c["sha"] for c in commits],
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=tree_hit),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "tree-match+gh"
        assert result["pr"]["number"] == 42
        assert result["pr"]["url"] == "https://example.com/pr/42"
        assert result["squash_commit"]["short"] == "s" * 8

    def test_tree_match_takes_precedence_when_gh_disagrees(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # gh found a PR but with non-overlapping SHAs (rebased branch). Old
        # detector downgraded to inconclusive. With tree-match, the verdict
        # is squash-merged — tree equivalence is a stronger signal than
        # SHA overlap.
        commits = _commits("rebased-1", "rebased-2", "rebased-3")
        tree_hit = {
            "squash_commit": "s" * 40,
            "squash_short": "s" * 8,
            "squash_subject": "Squashed (rebased)",
            "squashed_commits": commits[:2],
            "unique_commits": commits[2:],
        }
        gh = _gh_payload(
            number=99,
            commit_oids=["a" * 40, "b" * 40],  # diverged from rebased SHAs
            merged_at="2026-05-15T12:00:00Z",
        )
        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=tree_hit),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=gh),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "tree-match+gh"
        # Unique commits come from tree-match, not gh's SHA diff.
        assert [c["subject"] for c in result["unique_commits"]] == ["rebased-3"]
        # No "inconclusive" warning — tree-match overrode the weak gh signal.
        assert not any("inconclusive" in w for w in result["warnings"])

    def test_tree_match_skips_local_synth(
        self, detect_squash_residue: ModuleType
    ) -> None:
        # When tree-match fires, local-synth must NOT run — calling it would
        # be wasteful and could produce conflicting results.
        commits = _commits("a")
        tree_hit = {
            "squash_commit": "s" * 40,
            "squash_short": "s" * 8,
            "squash_subject": "Squashed",
            "squashed_commits": commits,
            "unique_commits": [],
        }
        synth_calls = []
        def fake_synth(*a: object, **kw: object) -> bool:
            synth_calls.append((a, kw))
            return True

        with (
            patch.object(detect_squash_residue, "_resolve_head", return_value="HEAD"),
            patch.object(detect_squash_residue, "_commits_since", return_value=commits),
            patch.object(detect_squash_residue, "_check_via_tree_match", return_value=tree_hit),
            patch.object(detect_squash_residue, "_check_via_gh", return_value=None),
            patch.object(detect_squash_residue, "_check_via_synthesis", side_effect=fake_synth),
            patch.object(detect_squash_residue, "_in_progress_abort", return_value=None),
        ):
            result = detect_squash_residue.detect("feature", "origin/main")

        assert result["verdict"] == "squash-merged"
        assert result["method"] == "tree-match"
        assert synth_calls == []


class TestBuildRemedies:
    """The dual-remedy structure — both options always offered, safety order
    enforced, abort prefix applied to both when an operation is in progress."""

    def _scaffold(self, **overrides: object) -> dict:
        base = {
            "verdict": "squash-merged",
            "method": "tree-match",
            "branch_commits": [],
            "unique_commits": [],
            "squash_commit": None,
            "pr": None,
            "warnings": [],
        }
        base.update(overrides)
        return base

    def test_merge_remedy_is_non_destructive(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "_in_progress_abort", return_value=None
        ):
            remedies = detect_squash_residue._build_remedies(self._scaffold(), "origin/main")

        merge = _remedy(remedies, "merge")
        assert merge["destructive"] is False
        assert merge["commands"] == [
            "git merge origin/main",
            # The trailing `# resolve …` comment is informational only.
            next(c for c in merge["commands"] if c.startswith("#")),
        ]
        # No reset/cherry-pick commands leak into the merge option.
        assert not any("reset --hard" in c for c in merge["commands"])
        assert not any("cherry-pick" in c for c in merge["commands"] if not c.startswith("#"))

    def test_reset_remedy_is_destructive(
        self, detect_squash_residue: ModuleType
    ) -> None:
        unique = _commits("unique-1", "unique-2")
        with patch.object(
            detect_squash_residue, "_in_progress_abort", return_value=None
        ):
            remedies = detect_squash_residue._build_remedies(
                self._scaffold(unique_commits=unique), "origin/main"
            )

        reset = _remedy(remedies, "reset-and-cherry-pick")
        assert reset["destructive"] is True
        assert "git reset --hard origin/main" in reset["commands"]
        cherry = next((c for c in reset["commands"] if "cherry-pick" in c), None)
        assert cherry is not None
        for c in unique:
            assert c["sha"] in cherry

    def test_abort_prefix_applied_to_both_remedies(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "_in_progress_abort", return_value="git rebase --abort"
        ):
            remedies = detect_squash_residue._build_remedies(self._scaffold(), "origin/main")

        for r in remedies:
            assert r["commands"][0] == "git rebase --abort"

    def test_local_synth_emits_manual_review_in_destructive_remedy_only(
        self, detect_squash_residue: ModuleType
    ) -> None:
        branch = _commits("a", "b")
        scaffold = self._scaffold(
            method="local-synth",
            branch_commits=branch,
            unique_commits=[],
        )
        with patch.object(
            detect_squash_residue, "_in_progress_abort", return_value=None
        ):
            remedies = detect_squash_residue._build_remedies(scaffold, "origin/main")

        merge = _remedy(remedies, "merge")
        # Merge remedy stays clean — no per-commit review block needed.
        assert not any(c.startswith("#   ") for c in merge["commands"])
        reset = _remedy(remedies, "reset-and-cherry-pick")
        review_lines = [c for c in reset["commands"] if c.startswith("#   ")]
        assert len(review_lines) == 2
        for c in branch:
            assert any(c["short"] in line for line in review_lines)

    def test_no_unique_no_cherry_pick_in_reset_remedy(
        self, detect_squash_residue: ModuleType
    ) -> None:
        with patch.object(
            detect_squash_residue, "_in_progress_abort", return_value=None
        ):
            remedies = detect_squash_residue._build_remedies(
                self._scaffold(method="tree-match", unique_commits=[]), "origin/main"
            )

        reset = _remedy(remedies, "reset-and-cherry-pick")
        assert reset["commands"] == ["git reset --hard origin/main"]
