#!/usr/bin/env python3
"""Detect squash-merge residue before running the conflict cascade.

When a PR is squash-merged into the base branch, the local branch retains the
pre-squash commits. Rebasing then re-applies commits whose content is already
in base, producing useless conflicts that mergiraf cannot resolve — the right
answer is to merge base in (non-destructive) or reset and re-cherry-pick the
unique commits (destructive).

Detection cascade (strongest first; later signals run only when needed):
  1. Tree-match — walk recent commits on base looking for one whose tree
     equals the tree at some point on the branch. That commit is a squash
     of branch commits up to that point. Works offline, through fork PRs,
     and when the branch has additional commits past the squash (the case
     `local-synth` misses). Always runs first.
  2. gh API — `gh pr list --state merged --head <branch>` provides PR
     metadata (number, URL) and an independent SHA-overlap signal. Always
     runs alongside tree-match so it can enrich a tree-match verdict, and
     supplies the verdict on its own when tree-match found nothing.
  3. Local synthesis — synthesize a would-be squash commit from HEAD's
     tree and ask `git cherry` whether base contains an equivalent. Only
     runs when neither tree-match nor gh produced a verdict. Last resort;
     cannot enumerate squashed vs unique commits, and misses the case
     where the branch has commits past the squash.

No auto-fix. Prints two remedies (merge first, then reset+cherry-pick) as
copy-paste blocks; the user picks and runs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Safe git ref name characters: alphanumeric, slash, dot, dash, underscore.
# Used to prevent shell metacharacters from being interpolated into the printed
# remedy block (which the user copy-pastes).
_SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")

from git_utils import run_git  # noqa: E402


def _current_branch() -> str | None:
    r = run_git(["branch", "--show-current"])
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _merge_base(base: str, head: str = "HEAD") -> str | None:
    r = run_git(["merge-base", base, head])
    return r.stdout.strip() if r.returncode == 0 else None


def _commits_since(base: str, head: str = "HEAD") -> list[dict] | None:
    """Returns commits on success (possibly empty), None on git failure."""
    r = run_git(["log", "--reverse", "--format=%H%x09%s", f"{base}..{head}"])
    if r.returncode != 0:
        return None
    commits = []
    for line in r.stdout.strip().split("\n"):
        if "\t" in line:
            sha, subject = line.split("\t", 1)
            commits.append({"sha": sha, "short": sha[:8], "subject": subject})
    return commits



def _base_branch_name(base_ref: str) -> str:
    """Strip the remote prefix from a base ref so it matches gh's --base flag.

    Only strips the leading segment when it matches a registered remote, so
    slash-named local branches like `release/1.0` are preserved as-is.
    `origin/main` → `main`. `upstream/release/1.0` → `release/1.0`. `main` → `main`.
    """
    if "/" not in base_ref:
        return base_ref
    prefix, _, rest = base_ref.partition("/")
    r = run_git(["remote"])
    if r.returncode == 0 and prefix in r.stdout.splitlines():
        return rest
    return base_ref


def _check_via_gh(branch: str, base_ref: str) -> dict | None:
    if shutil.which("gh") is None:
        return None
    cmd = [
        "gh", "pr", "list",
        "--state", "merged",
        "--head", branch,
        "--base", _base_branch_name(base_ref),
        "--json", "number,url,mergeCommit,commits,mergedAt",
        "-L", "5",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        prs = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    if not prs:
        return None
    prs.sort(key=lambda p: p.get("mergedAt", ""), reverse=True)
    pr = prs[0]
    return {
        "number": pr["number"],
        "url": pr["url"],
        "merge_commit": (pr.get("mergeCommit") or {}).get("oid"),
        "merged_at": pr["mergedAt"],
        "pr_commits": [c["oid"] for c in pr.get("commits", [])],
        "multiple_prs": len(prs) > 1,
    }


def _log_with_trees(
    range_ref: str, *, reverse: bool = False, limit: int | None = None
) -> list[tuple[str, str, str]] | None:
    """git log --format='%H<tab>%T<tab>%s' <range> → [(sha, tree, subject)].
    Returns None on git failure, [] when the range is empty.
    """
    args = ["log"]
    if limit is not None:
        args.append(f"-{limit}")
    if reverse:
        args.append("--reverse")
    args += ["--format=%H%x09%T%x09%s", range_ref]
    r = run_git(args)
    if r.returncode != 0:
        return None
    rows: list[tuple[str, str, str]] = []
    if not r.stdout.strip():
        return rows
    for line in r.stdout.strip().split("\n"):
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def _format_commit_list(rows: list[tuple[str, str, str]]) -> list[dict]:
    return [{"sha": sha, "short": sha[:8], "subject": subj} for sha, _, subj in rows]


def _build_tree_match_result(
    base_sha: str,
    base_subject: str,
    branch_commits: list[tuple[str, str, str]],
    squash_index: int,
) -> dict:
    """Format a tree-match hit into the result dict shape."""
    return {
        "squash_commit": base_sha,
        "squash_short": base_sha[:8],
        "squash_subject": base_subject,
        "squashed_commits": _format_commit_list(branch_commits[: squash_index + 1]),
        "unique_commits": _format_commit_list(branch_commits[squash_index + 1 :]),
    }


def _check_via_tree_match(base_ref: str, head: str = "HEAD") -> dict | None:
    """Strongest of the three detection methods: works offline, through forks
    and renames, and (unlike `_check_via_synthesis`) handles the case where
    the user has committed additional work on top of the squashed commits.
    """
    mb = _merge_base(base_ref, head)
    if not mb:
        return None

    branch_commits = _log_with_trees(f"{mb}..{head}", reverse=True)
    if not branch_commits:
        return None

    # Map tree SHA -> latest branch index with that tree. Revert-then-redo
    # collisions prefer the latest so the unique-commit replay set stays small.
    branch_tree_to_index = {tree: i for i, (_, tree, _) in enumerate(branch_commits)}

    # Cap base log at 500 commits to stay fast on long-running base branches.
    base_commits = _log_with_trees(f"{mb}..{base_ref}", limit=500)
    if base_commits is None:
        return None

    for base_sha, base_tree, base_subject in base_commits:
        if base_tree in branch_tree_to_index:
            return _build_tree_match_result(
                base_sha, base_subject, branch_commits, branch_tree_to_index[base_tree]
            )
    return None


def _check_via_synthesis(base_ref: str, head: str = "HEAD") -> bool | None:
    """Build a would-be squash commit from head's tree, then ask `git cherry`
    whether base_ref already contains an equivalent. Returns True if yes.
    """
    mb = _merge_base(base_ref, head)
    if not mb:
        return None
    tree = run_git(["rev-parse", f"{head}^{{tree}}"])
    if tree.returncode != 0:
        return None
    synth = run_git(
        ["commit-tree", tree.stdout.strip(), "-p", mb, "-m", "_squash-probe"]
    )
    if synth.returncode != 0:
        return None
    cherry = run_git(["cherry", base_ref, synth.stdout.strip()])
    if cherry.returncode != 0:
        return None
    first = cherry.stdout.strip().split("\n")[0] if cherry.stdout.strip() else ""
    return first.startswith("-")


def _branch_during_rebase() -> str | None:
    """Read the pre-rebase branch name from git rebase metadata.

    During a rebase HEAD is detached, so `git branch --show-current` returns
    empty. The rebase state directory records the original branch in head-name.
    """
    r = run_git(["rev-parse", "--git-dir"])
    if r.returncode != 0:
        return None
    gd = Path(r.stdout.strip())
    for head_name_path in (gd / "rebase-merge" / "head-name", gd / "rebase-apply" / "head-name"):
        if head_name_path.exists():
            return head_name_path.read_text().strip().removeprefix("refs/heads/")
    return None


def _in_progress_abort() -> str | None:
    r = run_git(["rev-parse", "--git-dir"])
    if r.returncode != 0:
        return None
    gd = Path(r.stdout.strip())
    if (gd / "rebase-merge").exists() or (gd / "rebase-apply").exists():
        return "git rebase --abort"
    if (gd / "MERGE_HEAD").exists():
        return "git merge --abort"
    if (gd / "CHERRY_PICK_HEAD").exists():
        return "git cherry-pick --abort"
    return None


def _resolve_head(branch: str) -> str:
    """Return a ref usable as HEAD for diff/log: prefer local branch tip, fall
    back to remote-tracking ref, else literal 'HEAD'."""
    for candidate in (branch, f"refs/heads/{branch}", f"origin/{branch}"):
        r = run_git(["rev-parse", "--verify", "--quiet", candidate])
        if r.returncode == 0 and r.stdout.strip():
            return candidate
    return "HEAD"


def _build_merge_remedy(base_ref: str, abort: str | None) -> dict:
    commands: list[str] = []
    if abort:
        commands.append(abort)
    commands.append(f"git merge {base_ref}")
    commands.append(
        "# resolve any remaining conflicts with /melt — squashed commits "
        "collapse to no-ops, so only real edits should remain"
    )
    return {
        "name": "merge",
        "destructive": False,
        "description": (
            "Merge base into branch. Non-destructive: preserves all "
            "branch history and refs. Squashed commits collapse to a "
            "no-op merge, so only real conflicts surface. Prefer this "
            "when the branch has unique work or you are not sure the "
            "unique-commit list below is complete."
        ),
        "commands": commands,
    }


def _build_reset_remedy(result: dict, base_ref: str, abort: str | None) -> dict:
    commands: list[str] = []
    if abort:
        commands.append(abort)
    commands.append(f"git reset --hard {base_ref}")
    if result["unique_commits"]:
        shas = " ".join(c["sha"] for c in result["unique_commits"])
        commands.append(f"git cherry-pick {shas}")
    elif result["method"] == "local-synth":
        commands.append("# review and cherry-pick unique commits manually:")
        for c in result["branch_commits"]:
            commands.append(f"#   {c['short']} {c['subject']}")
    return {
        "name": "reset-and-cherry-pick",
        "destructive": True,
        "description": (
            "Reset to base and replay only the unique commits. "
            "DESTRUCTIVE: rewrites the branch and requires force-push. "
            "Use when you want a clean linear history and the "
            "unique-commit list looks complete."
        ),
        "commands": commands,
    }


def _gh_correlates_with_tree(gh: dict, tree: dict) -> bool:
    """True iff the gh PR is the same squash that tree-match found.

    Branch names get reused across PRs, so the gh PR currently advertising
    this branch is not always the one whose squash sits on base. Confirm
    via merge-commit equality (strongest) or SHA overlap between the PR's
    source commits and the tree-match squashed set before attaching gh
    metadata — otherwise we'd point the user at an unrelated PR.
    """
    if gh.get("merge_commit") and gh["merge_commit"] == tree["squash_commit"]:
        return True
    pr_shas = set(gh.get("pr_commits", []))
    squashed_shas = {c["sha"] for c in tree.get("squashed_commits", [])}
    return bool(pr_shas & squashed_shas)


def _gh_merge_commit_disagrees(gh: dict, tree: dict) -> bool:
    """True iff gh recorded a merge_commit that differs from the tree-match
    squash commit. Soft signal — correlation may still hold via SHA overlap,
    but the recorded merge points elsewhere, so warn the user.
    """
    mc = gh.get("merge_commit")
    return bool(mc and mc != tree["squash_commit"])


def _init_result(branch: str, base_ref: str, head_ref: str) -> dict:
    return {
        "verdict": "not-detected",
        "method": None,
        "branch": branch,
        "base": base_ref,
        "head_ref": head_ref,
        "pr": None,
        "squash_commit": None,
        "branch_commits": [],
        "squashed_shas": [],
        "unique_commits": [],
        "remedies": [],
        "warnings": [],
    }


def _apply_synth_fallback(result: dict, base_ref: str, head_ref: str) -> None:
    """Last-resort detection when tree-match and gh both came up empty.
    `git cherry`-based equivalence check — cannot enumerate squashed vs
    unique commits, so the user has to review the branch list by hand."""
    synth = _check_via_synthesis(base_ref, head_ref)
    if synth:
        result["verdict"] = "squash-merged"
        result["method"] = "local-synth"
        result["warnings"].append(
            "detected via local synthesis; cannot enumerate which commits "
            "were squashed vs unique — review branch commits manually"
        )


def _apply_tree_match_to_result(result: dict, tree: dict, gh: dict | None) -> None:
    result["verdict"] = "squash-merged"
    result["squash_commit"] = {
        "sha": tree["squash_commit"],
        "short": tree["squash_short"],
        "subject": tree["squash_subject"],
    }
    result["unique_commits"] = tree["unique_commits"]
    if gh and _gh_correlates_with_tree(gh, tree):
        result["method"] = "tree-match+gh"
        result["pr"] = {k: gh[k] for k in ("number", "url", "merged_at", "merge_commit")}
        result["squashed_shas"] = gh["pr_commits"]
        if _gh_merge_commit_disagrees(gh, tree):
            result["warnings"].append(
                f"gh PR #{gh['number']} merge-commit {gh['merge_commit'][:8]} "
                f"differs from tree-match squash {tree['squash_commit'][:8]} — "
                "PR commits overlap but the recorded squash may be a different one"
            )
        if gh["multiple_prs"]:
            result["warnings"].append("multiple merged PRs from this branch — using most recent")
        return
    result["method"] = "tree-match"
    if gh:
        result["warnings"].append(
            f"gh found PR #{gh['number']} ({gh['url']}) but its "
            "commits do not correlate with the tree-match squash — "
            "branch name may have been reused; not attaching PR metadata"
        )


def _apply_gh_only_to_result(result: dict, gh: dict) -> None:
    """Zero SHA overlap is treated as inconclusive (reused branch name or full rebase)."""
    squashed = set(gh["pr_commits"])
    unique = [c for c in result["branch_commits"] if c["sha"] not in squashed]
    matched = len(result["branch_commits"]) - len(unique)
    if matched == 0:
        result["warnings"].append(
            f"gh found PR #{gh['number']} ({gh['url']}) but no local "
            "commits matched its SHAs and tree-match found no equivalent "
            "commit on base — treating as inconclusive"
        )
        return
    result["verdict"] = "squash-merged"
    result["method"] = "gh-api"
    result["pr"] = {k: gh[k] for k in ("number", "url", "merged_at", "merge_commit")}
    result["squashed_shas"] = gh["pr_commits"]
    result["unique_commits"] = unique
    if gh["multiple_prs"]:
        result["warnings"].append("multiple merged PRs from this branch — using most recent")


def detect(branch: str, base_ref: str) -> dict:
    head_ref = _resolve_head(branch)
    result = _init_result(branch, base_ref, head_ref)

    branch_commits = _commits_since(base_ref, head_ref)
    if branch_commits is None:
        result["warnings"].append(
            f"git log failed for {base_ref}..{head_ref} — is {base_ref} fetched?"
        )
        return result
    result["branch_commits"] = branch_commits

    if not result["branch_commits"]:
        result["warnings"].append(f"no commits between {base_ref} and {head_ref}")
        return result

    # Run tree-match first — strongest signal, works offline, and unlike
    # gh-api or local-synth it handles the case where the branch has commits
    # past the squash. gh runs in parallel to enrich tree-match or to
    # supply the verdict on its own.
    tree = _check_via_tree_match(base_ref, head_ref)
    gh = _check_via_gh(branch, base_ref)

    if tree:
        _apply_tree_match_to_result(result, tree, gh)
    elif gh:
        _apply_gh_only_to_result(result, gh)

    if result["verdict"] == "not-detected":
        _apply_synth_fallback(result, base_ref, head_ref)

    if result["verdict"] == "squash-merged":
        abort = _in_progress_abort()
        result["remedies"] = [
            _build_merge_remedy(base_ref, abort),
            _build_reset_remedy(result, base_ref, abort),
        ]

    return result


def format_terse(d: dict) -> str:
    if d["verdict"] == "not-detected":
        lines = [f"verdict: not-detected branch={d['branch']} base={d['base']}"]
        for w in d["warnings"]:
            lines.append(f"warn: {w}")
        return "\n".join(lines)

    lines = []
    pr = d["pr"]
    sc = d.get("squash_commit")
    header = f"verdict: SQUASH-MERGED method={d['method']}"
    if pr:
        header += f" PR=#{pr['number']}"
    lines.append(header)
    if pr:
        lines.append(f"  pr-url: {pr['url']}")
        lines.append(f"  merged-at: {pr['merged_at']}")
    if sc:
        lines.append(f"  squash-commit: {sc['short']} {sc['subject']}")

    for w in d["warnings"]:
        lines.append(f"warn: {w}")

    if d["unique_commits"]:
        lines.append(f"unique commits ({len(d['unique_commits'])}):")
        for c in d["unique_commits"]:
            lines.append(f"  {c['short']} {c['subject']}")
    elif d["method"] == "local-synth":
        lines.append(f"branch commits ({len(d['branch_commits'])}):")
        for c in d["branch_commits"]:
            lines.append(f"  {c['short']} {c['subject']}")
    else:
        lines.append("unique commits: 0 (branch is fully contained in base)")

    lines.append("")
    lines.append("remedies — pick one, copy-paste, review before running:")
    for i, r in enumerate(d.get("remedies", [])):
        label = chr(ord("A") + i)
        marker = "DESTRUCTIVE" if r["destructive"] else "non-destructive"
        lines.append("")
        lines.append(f"  [{label}] {r['name']} ({marker})")
        lines.append(f"      {r['description']}")
        for cmd in r["commands"]:
            lines.append(f"      {cmd}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Detect squash-merge residue and emit the remedy."
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref to compare against (default: origin/main).",
    )
    parser.add_argument("--branch", help="Branch to check (default: current).")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    args = parser.parse_args()

    if not _SAFE_REF.match(args.base):
        msg = f"error: --base {args.base!r} contains unsafe characters"
        if args.json:
            print(json.dumps({"verdict": "error", "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 1

    branch = args.branch or _current_branch() or _branch_during_rebase()
    if not branch:
        msg = "error: cannot determine current branch — pass --branch <name>"
        if args.json:
            print(json.dumps({"verdict": "error", "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 1

    if not _SAFE_REF.match(branch):
        msg = f"error: branch {branch!r} contains unsafe characters"
        if args.json:
            print(json.dumps({"verdict": "error", "error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 1

    base_short = args.base.split("/")[-1]
    if branch == base_short or branch in ("main", "master", "develop"):
        msg = f"not-applicable: on base branch {branch}"
        if args.json:
            print(json.dumps({"verdict": "not-applicable", "reason": msg}))
        else:
            print(msg)
        return 0

    result = detect(branch, args.base)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_terse(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
