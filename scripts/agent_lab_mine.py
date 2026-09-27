"""Mine SHA-pinned fix tasks from merged PRs for the tilth benchmark harness.

This module is pure and offline: it shells out to `gh` for PR data and to
tilth's `check_task.py` to prove each candidate task fails at its base commit
and passes at its head commit. It does not touch `src/easy_cheese`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, cast

from prompt_lab import JsonObject, SPLITS, sha256_hex


# Case-sensitive by design: only a lowercase Conventional Commit `fix:` title
# is mined; docs/prompt-lab.md documents this trust boundary.
FIX_TITLE_RE = re.compile(r"^fix(\(.+\))?!?:")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
PASS_LINE_RE = re.compile(r"^PASS (\S+):")
FAIL_LINE_RE = re.compile(r"^FAIL (\S+):")

# Only a merged PR whose author has repo write access is mined by default; an
# outside contributor's issue/PR body becomes an agent prompt with Bash
# access. Callers opt in explicitly via `allow_untrusted_authors` to mine
# untrusted-author PRs; treat mined output as untrusted, sandboxed input.
TRUSTED_AUTHOR_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})

# Split sizes are percentages of the sha256(id) bucket (0-99): the first 60
# buckets are train, the next 20 are validation, and the rest are holdout.
TRAIN_CUTOFF = 60
VALIDATION_CUTOFF = 80

# Added-line leak check: a fix line shorter than this often reappears in prose
# by coincidence (a stray brace, a blank line), so only longer lines count.
MIN_LEAK_LINE_LENGTH = 12

CheckTask = Callable[[Path], set[str]]


def _is_test_path(path: str) -> bool:
    """Return True when `path` names a test file, by directory or filename."""
    parts = Path(path).parts
    if "tests" in parts or "test" in parts:
        return True
    name = Path(path).name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test.go"):
        return True
    if re.search(r"\.(test|spec)\.(ts|js)$", name):
        return True
    return False


def _infer_test_command(test_files: list[str]) -> list[str] | None:
    """Return a test command inferred from the changed test files' languages."""
    python_files = sorted(f for f in test_files if f.endswith(".py"))
    if python_files:
        return ["python3", "-m", "pytest", *python_files, "-q"]
    go_files = sorted(f for f in test_files if f.endswith(".go"))
    if go_files:
        dirs = sorted({f"./{Path(f).parent}" for f in go_files})
        return ["go", "test", *dirs]
    rust_files = [f for f in test_files if f.endswith(".rs")]
    if rust_files:
        return ["cargo", "test"]
    return None


def _split_diff(diff_text: str, test_files: set[str]) -> tuple[str, int]:
    """Split a unified diff into (test-file patch text, non-test changed-line count)."""
    sections: list[tuple[str | None, list[str]]] = []
    header_re = re.compile(r"^diff --git a/.+ b/(.+)$")
    for line in diff_text.splitlines(keepends=True):
        match = header_re.match(line)
        if match:
            sections.append((match.group(1), [line]))
            continue
        if sections:
            sections[-1][1].append(line)
        else:
            sections.append((None, [line]))
    test_patch_parts: list[str] = []
    changed_lines = 0
    for path, lines in sections:
        text = "".join(lines)
        if path is not None and path in test_files:
            test_patch_parts.append(text)
            continue
        for line in lines:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+") or line.startswith("-"):
                changed_lines += 1
    return "".join(test_patch_parts), changed_lines


def _clean_prompt(text: str) -> str:
    """Strip fenced code blocks from an issue or PR body.

    A raw, unfenced diff can still leak an added line; `_leaks_fix` catches
    that case and drops the task instead. Stripping "+"/"-" lines here also
    deleted markdown bullets such as "- Expected: ...", which is often the
    task statement itself, so this function no longer does that.
    """
    without_fences = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    collapsed = re.sub(r"\n{3,}", "\n\n", without_fences)
    return collapsed.strip()


def _leaks_fix(prompt: str, diff_text: str, test_files: set[str]) -> bool:
    """Return True when `prompt` still contains a substantial added line from the fix."""
    header_re = re.compile(r"^diff --git a/.+ b/(.+)$")
    current_path: str | None = None
    for line in diff_text.splitlines():
        match = header_re.match(line)
        if match:
            current_path = match.group(1)
            continue
        if current_path in test_files:
            continue
        if line.startswith("+++"):
            continue
        if not line.startswith("+"):
            continue
        added = line[1:].strip()
        if len(added) >= MIN_LEAK_LINE_LENGTH and added in prompt:
            return True
    return False


def _assign_split(identifier: str) -> str:
    """Deterministically assign a train/validation/holdout split from the task id."""
    digest = sha256_hex(identifier.encode("utf-8"))
    bucket = int(digest[:8], 16) % 100
    if bucket < TRAIN_CUTOFF:
        return "train"
    if bucket < VALIDATION_CUTOFF:
        return "validation"
    return "holdout"


def _run_gh(args: list[str], *, gh_bin: str) -> str:
    completed = subprocess.run([gh_bin, *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _list_merged_prs(
    repo: str, *, gh_bin: str, since: str | None, limit: int | None
) -> list[JsonObject]:
    """List merged PRs for `repo` with the fields `_build_candidate` needs."""
    fields = (
        "number,title,body,mergeCommit,baseRefOid,headRefOid,"
        "closingIssuesReferences,files,mergedAt,authorAssociation"
    )
    args = ["pr", "list", "--repo", repo, "--state", "merged", "--json", fields]
    if since is not None:
        args += ["--search", f"merged:>={since}"]
    args += ["--limit", str(limit if limit is not None else 100)]
    output = _run_gh(args, gh_bin=gh_bin)
    return cast(list[JsonObject], json.loads(output))


def _parent_sha(repo: str, sha: str, *, gh_bin: str) -> str:
    """Return the first parent of `sha`, which is the pre-merge base commit."""
    output = _run_gh(["api", f"repos/{repo}/commits/{sha}"], gh_bin=gh_bin)
    data = cast(JsonObject, json.loads(output))
    parents = cast(list[JsonObject], data.get("parents") or [])
    if not parents:
        raise RuntimeError(f"commit {sha} in {repo} has no parent commit")
    return str(parents[0]["sha"])


def _pr_diff(repo: str, number: int, *, gh_bin: str) -> str:
    return _run_gh(["pr", "diff", str(number), "--repo", repo], gh_bin=gh_bin)


def _issue_in_repo(issue: JsonObject, repo: str) -> bool:
    """Return True when `issue`'s repository is `repo`, not a cross-repo link."""
    repository = cast(JsonObject, issue.get("repository") or {})
    owner_field = cast(JsonObject, repository.get("owner") or {})
    owner = owner_field.get("login")
    name = repository.get("name")
    if not owner or not name:
        return False
    return f"{owner}/{name}" == repo


def _linked_issue_body(issue: JsonObject, *, gh_bin: str) -> str:
    """Return the linked issue's body, or \"\" when it cannot be resolved.

    `closingIssuesReferences` carries only id, number, repository, and url;
    it never carries the issue body, so a separate `gh issue view` call reads it.
    """
    number = issue.get("number")
    repository = cast(JsonObject, issue.get("repository") or {})
    owner_field = cast(JsonObject, repository.get("owner") or {})
    owner = owner_field.get("login")
    name = repository.get("name")
    if not number or not owner or not name:
        return ""
    output = _run_gh(
        ["issue", "view", str(number), "--repo", f"{owner}/{name}", "--json", "body"],
        gh_bin=gh_bin,
    )
    return str(cast(JsonObject, json.loads(output)).get("body") or "")


def _build_candidate(
    repo: str, pr: JsonObject, *, gh_bin: str, allow_untrusted_authors: bool = False
) -> tuple[JsonObject | None, str]:
    """Build one mined task from a merged PR, or return (None, reason) to drop it."""
    title = str(pr.get("title", ""))
    if not FIX_TITLE_RE.match(title):
        return None, "title does not match the fix: pattern"

    if not allow_untrusted_authors:
        association = pr.get("authorAssociation")
        if association not in TRUSTED_AUTHOR_ASSOCIATIONS:
            return None, "author is not OWNER, MEMBER, or COLLABORATOR"

    files = [str(f["path"]) for f in cast(list[JsonObject], pr.get("files", []))]
    test_files = {f for f in files if _is_test_path(f)}
    if not test_files:
        return None, "no test file changes"

    number = int(cast(int, pr["number"]))
    merge_commit = cast(JsonObject, pr.get("mergeCommit") or {})
    head_sha = str(merge_commit.get("oid", ""))
    if not HEX40_RE.match(head_sha):
        return None, "merge commit sha is not 40 lowercase hex characters"
    base_sha = _parent_sha(repo, head_sha, gh_bin=gh_bin)

    diff_text = _pr_diff(repo, number, gh_bin=gh_bin)
    test_patch, reference_changed_lines = _split_diff(diff_text, test_files)
    if not test_patch:
        return None, "no diff hunks touch a test file"

    test_command = _infer_test_command(sorted(test_files))
    if test_command is None:
        return None, "no inferable test command for the changed test files"

    issues = cast(list[JsonObject], pr.get("closingIssuesReferences") or [])
    same_repo_issues = [issue for issue in issues if _issue_in_repo(issue, repo)]
    source_text = ""
    if same_repo_issues:
        try:
            source_text = _linked_issue_body(same_repo_issues[0], gh_bin=gh_bin)
        except RuntimeError:
            source_text = ""
    if not source_text:
        source_text = str(pr.get("body", ""))
    prompt = _clean_prompt(source_text)
    if not prompt:
        return None, "prompt is empty after removing diff and code content"
    if _leaks_fix(prompt, diff_text, test_files):
        return None, "prompt leaks an added line from the fix"

    identifier = f"{repo.replace('/', '-')}-{number}"
    task: JsonObject = {
        "id": identifier,
        "family": identifier,
        "split": _assign_split(identifier),
        "capability": "fix",
        "prompt": prompt,
        "test_command": test_command,
        "repo_url": f"https://github.com/{repo}",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "test_patch": test_patch,
        "reference_changed_lines": reference_changed_lines,
    }
    validate_mined_task(task)
    return task, ""


def mine_tasks(
    repo: str,
    *,
    gh_bin: str = "gh",
    check_task: CheckTask,
    since: str | None = None,
    limit: int | None = None,
    allow_untrusted_authors: bool = False,
    drops: list[tuple[int, str]] | None = None,
) -> list[JsonObject]:
    """Mine SHA-pinned fix tasks from `repo`'s merged PRs, gated by `check_task`.

    `check_task` receives the path to a candidate tasks JSON file and returns
    the set of task ids that printed a `PASS <id>:` line; only those ids are
    kept in the result. A PR that fails to build for any reason is dropped
    without aborting the run; when `drops` is given, each dropped PR's
    number and reason is appended to it.
    """
    prs = _list_merged_prs(repo, gh_bin=gh_bin, since=since, limit=limit)
    candidates: list[JsonObject] = []
    for pr in prs:
        number = int(cast(int, pr.get("number", 0)))
        try:
            task, reason = _build_candidate(
                repo, pr, gh_bin=gh_bin, allow_untrusted_authors=allow_untrusted_authors
            )
        except RuntimeError as exc:
            task, reason = None, str(exc)
        if task is not None:
            candidates.append(task)
        elif drops is not None:
            drops.append((number, reason))
    if not candidates:
        return []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tasks_path = Path(tmp_dir) / "mined_candidates.json"
        _ = tasks_path.write_text(
            json.dumps({"version": 1, "tasks": candidates}), encoding="utf-8"
        )
        passed_ids = check_task(tasks_path)
    return [task for task in candidates if task["id"] in passed_ids]


def make_check_task(tilth_root: Path, *, python_bin: str | None = None) -> CheckTask:
    """Return a `check_task` callable that runs tilth's `check_task.py` gate."""
    binary = python_bin or sys.executable
    script = Path(tilth_root) / "benchmark" / "check_task.py"
    if not script.is_file():
        raise RuntimeError(f"tilth check_task.py not found at {script}")

    def check_task(tasks_path: Path) -> set[str]:
        completed = subprocess.run(
            [binary, str(script), "--tasks-json", str(tasks_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        passed: set[str] = set()
        parsed_any = False
        for line in completed.stdout.splitlines():
            pass_match = PASS_LINE_RE.match(line)
            if pass_match:
                passed.add(pass_match.group(1))
                parsed_any = True
            elif FAIL_LINE_RE.match(line):
                parsed_any = True
        if completed.returncode != 0 and not parsed_any:
            stderr_tail = "\n".join(completed.stderr.splitlines()[-20:])
            message = (
                f"check_task.py exited {completed.returncode} with no PASS/FAIL lines parsed; "
                + f"stderr: {stderr_tail}"
            )
            raise RuntimeError(message)
        return passed

    return check_task


def validate_mined_task(task: JsonObject) -> None:
    """Raise ValueError when `task` does not match the mined task shape."""
    for field in ("id", "family", "capability", "prompt", "repo_url", "base_sha", "head_sha"):
        value = task.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a nonempty string")

    split = task.get("split")
    if split not in SPLITS:
        raise ValueError("split must be train, validation, or holdout")

    for field in ("base_sha", "head_sha"):
        value = str(task[field])
        if not HEX40_RE.match(value):
            raise ValueError(f"{field} must be 40 lowercase hex characters")

    test_command = task.get("test_command")
    if (
        not isinstance(test_command, list)
        or not test_command
        or not all(isinstance(item, str) for item in cast(list[object], test_command))
    ):
        raise ValueError("test_command must be a non-empty list of strings")

    test_patch = task.get("test_patch")
    if not isinstance(test_patch, str) or not test_patch:
        raise ValueError("test_patch must be a nonempty string")

    reference_changed_lines = task.get("reference_changed_lines")
    if (
        not isinstance(reference_changed_lines, int)
        or isinstance(reference_changed_lines, bool)
        or reference_changed_lines < 0
    ):
        raise ValueError("reference_changed_lines must be a non-negative integer")

    lint_command = task.get("lint_command")
    if lint_command is not None and (
        not isinstance(lint_command, list)
        or not all(isinstance(item, str) for item in cast(list[object], lint_command))
    ):
        raise ValueError("lint_command must be a list of strings when present")
