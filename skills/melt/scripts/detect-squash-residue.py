#!/usr/bin/env python3
"""Detect squash-merge residue before running the conflict cascade.

When a PR is squash-merged into the base branch, the local branch retains the
pre-squash commits. Rebasing then re-applies commits whose content is already
in base, producing useless conflicts that mergiraf cannot resolve — the right
answer is to abort and re-cherry-pick the commits that postdate the squash.

Detection path:
  1. gh API — `gh pr list --state merged --head <branch>` returns both the
     verdict (PR exists) and the cherry-pick list (PR commit SHAs).
  2. Local fallback — synthesize a would-be squash commit via `commit-tree`,
     then ask `git cherry` whether base already contains an equivalent. Works
     offline but cannot enumerate which commits were squashed.

No auto-fix. Prints the remedy as a copy-paste block; the user runs it.
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

sys.path.insert(0, str(Path(__file__).parent))

from git_utils import run_git


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


def _gh_available() -> bool:
    return shutil.which("gh") is not None


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
    if not _gh_available():
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


def detect(branch: str, base_ref: str) -> dict:
    head_ref = _resolve_head(branch)
    result = {
        "verdict": "not-detected",
        "method": None,
        "branch": branch,
        "base": base_ref,
        "head_ref": head_ref,
        "pr": None,
        "branch_commits": [],
        "squashed_shas": [],
        "unique_commits": [],
        "remedy": [],
        "warnings": [],
    }

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

    gh = _check_via_gh(branch, base_ref)
    if gh:
        result["verdict"] = "squash-merged"
        result["method"] = "gh-api"
        result["pr"] = {
            "number": gh["number"],
            "url": gh["url"],
            "merged_at": gh["merged_at"],
            "merge_commit": gh["merge_commit"],
        }
        result["squashed_shas"] = gh["pr_commits"]
        if gh["multiple_prs"]:
            result["warnings"].append(
                "multiple merged PRs from this branch — using most recent"
            )
        squashed = set(gh["pr_commits"])
        result["unique_commits"] = [
            c for c in result["branch_commits"] if c["sha"] not in squashed
        ]
        matched = len(result["branch_commits"]) - len(result["unique_commits"])
        if matched == 0:
            result["warnings"].append(
                "no local commits matched PR commits by SHA — "
                "branch may have been rebased after the squash merge; "
                "verify the cherry-pick list manually before running the remedy"
            )

    if result["verdict"] == "not-detected":
        synth = _check_via_synthesis(base_ref, head_ref)
        if synth:
            result["verdict"] = "squash-merged"
            result["method"] = "local-synth"
            result["warnings"].append(
                "detected via local synthesis; cannot enumerate which commits "
                "were squashed vs unique — review branch commits manually"
            )

    if result["verdict"] == "squash-merged":
        remedy = []
        abort = _in_progress_abort()
        if abort:
            remedy.append(abort)
        remedy.append(f"git reset --hard {base_ref}")
        if result["unique_commits"]:
            shas = " ".join(c["sha"] for c in result["unique_commits"])
            remedy.append(f"git cherry-pick {shas}")
        elif result["method"] == "local-synth":
            # No PR data available — list branch commits so the user has a
            # recovery path before running `reset --hard`.
            remedy.append("# review and cherry-pick unique commits manually:")
            for c in result["branch_commits"]:
                remedy.append(f"#   {c['short']} {c['subject']}")
        result["remedy"] = remedy

    return result


def format_terse(d: dict) -> str:
    if d["verdict"] == "not-detected":
        lines = [f"verdict: not-detected branch={d['branch']} base={d['base']}"]
        for w in d["warnings"]:
            lines.append(f"warn: {w}")
        return "\n".join(lines)

    lines = []
    pr = d["pr"]
    if pr:
        lines.append(
            f"verdict: SQUASH-MERGED via PR #{pr['number']} "
            f"merged={pr['merged_at']} method={d['method']}"
        )
        lines.append(f"  url: {pr['url']}")
    else:
        lines.append(f"verdict: SQUASH-MERGED method={d['method']}")

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

    lines.append("remedy (copy-paste — destructive, review first):")
    for r in d["remedy"]:
        lines.append(f"  {r}")
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
