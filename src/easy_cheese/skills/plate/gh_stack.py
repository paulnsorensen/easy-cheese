"""Guard and verify Plate publication through GitHub's native gh-stack extension."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

_TIMEOUT_SECONDS = 30
_REMOTE_OPERATIONS = {"link", "push", "rebase", "submit", "sync"}
_MUTATING_OPERATIONS = _REMOTE_OPERATIONS | {"add", "init", "modify", "unstack"}
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x1b]*(?:\x1b\\|\x07))")
_WARNING = re.compile(r"(?:^|\n)\s*(?:⚠|warning\b)", re.IGNORECASE)
_HTTP_FAILURE = re.compile(
    r"\b(?:HTTP(?:/[0-9.]+)?\s+|status(?:\s+code)?\s*[:=]?\s*)[45][0-9]{2}\b",
    re.IGNORECASE,
)


class GhStackValidationError(ValueError):
    """The gh-stack publication contract was not satisfied."""


def _run(
    args: list[str], cwd: Path, timeout: float = _TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise GhStackValidationError(
            f"could not run {' '.join(args)}: {error}"
        ) from error


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
    raise GhStackValidationError(
        f"{label} failed with exit {result.returncode}: {detail}"
    )


def canonical_trunk(value: str, remote: str) -> str:
    """Return a GitHub branch name and reject remote-tracking ref spellings."""
    if value != value.strip() or not value:
        raise GhStackValidationError(
            "trunk must be a non-empty branch name without outer whitespace"
        )
    if value.startswith("refs/heads/"):
        value = value.removeprefix("refs/heads/")
    if value.startswith("refs/remotes/") or value.startswith(f"{remote}/"):
        raise GhStackValidationError(
            f"trunk {value!r} is a remote-tracking name; use a GitHub branch name such as 'main'"
        )
    if value.startswith("refs/"):
        raise GhStackValidationError(
            f"trunk {value!r} is not a heads ref; use a GitHub branch name such as 'main'"
        )
    return value


def _remote_sha(result: subprocess.CompletedProcess[str], ref: str) -> str:
    _require_success(result, f"remote branch lookup for {ref}")
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    matches = [
        columns[0] for columns in rows if len(columns) == 2 and columns[1] == ref
    ]
    if len(matches) != 1:
        raise GhStackValidationError(
            f"remote branch lookup did not return exactly {ref}"
        )
    return matches[0]


def preflight(cwd: Path, trunk: str, remote: str = "origin") -> dict[str, object]:
    """Validate the trunk and its exact branch on the publication remote."""
    if remote != "origin":
        raise GhStackValidationError(
            "Plate's gh-stack publication remote must be origin"
        )
    branch = canonical_trunk(trunk, remote)
    branch_check = _run(["git", "check-ref-format", "--branch", branch], cwd)
    _require_success(branch_check, f"trunk validation for {branch!r}")
    remote_result = _run(["git", "remote", "get-url", remote], cwd)
    _require_success(remote_result, f"remote lookup for {remote}")
    remote_url = remote_result.stdout.strip()
    if not remote_url:
        raise GhStackValidationError(f"remote {remote!r} has no URL")
    ref = f"refs/heads/{branch}"
    branch_result = _run(
        ["git", "ls-remote", "--exit-code", "--heads", remote, ref], cwd
    )
    sha = _remote_sha(branch_result, ref)
    return {
        "valid": True,
        "trunk": branch,
        "remote": remote,
        "remote_url": remote_url,
        "remote_sha": sha,
    }


def _remote_arg(args: list[str]) -> str | None:
    values: list[str] = []
    for index, value in enumerate(args):
        if value == "--remote" and index + 1 < len(args):
            values.append(args[index + 1])
        elif value.startswith("--remote="):
            values.append(value.partition("=")[2])
    return values[0] if len(values) == 1 else None


def run_guarded(args: list[str], cwd: Path) -> dict[str, object]:
    """Run one gh-stack mutation and reject warning-only false successes."""
    if len(args) < 3 or args[:2] != ["gh", "stack"]:
        raise GhStackValidationError("guarded command must start with 'gh stack'")
    operation = args[2]
    if operation not in _MUTATING_OPERATIONS:
        raise GhStackValidationError(
            f"gh stack {operation!r} is not a supported mutation"
        )
    if operation in _REMOTE_OPERATIONS and _remote_arg(args) != "origin":
        raise GhStackValidationError(
            f"gh stack {operation} must use one explicit --remote origin"
        )

    result = _run(args, cwd, timeout=300)
    output = _ANSI.sub("", "\n".join((result.stdout, result.stderr)))
    detail = output.strip() or "no diagnostic output"
    if result.returncode != 0:
        raise GhStackValidationError(
            f"gh stack {operation} failed with exit {result.returncode}: {detail}"
        )
    if _WARNING.search(output):
        raise GhStackValidationError(
            f"gh stack {operation} exited zero but emitted a warning; "
            + f"publication failed:\n{detail}"
        )
    if _HTTP_FAILURE.search(output):
        raise GhStackValidationError(
            f"gh stack {operation} exited zero but reported an HTTP failure; "
            + f"publication failed:\n{detail}"
        )
    return {
        "valid": True,
        "command": args,
        "exit_status": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _json_object(
    result: subprocess.CompletedProcess[str], label: str
) -> dict[str, object]:
    _require_success(result, label)
    try:
        value = cast(object, json.loads(result.stdout))
    except json.JSONDecodeError as error:
        raise GhStackValidationError(
            f"{label} returned invalid JSON: {error}"
        ) from error
    if not isinstance(value, dict):
        raise GhStackValidationError(f"{label} must return one JSON object")
    return cast("dict[str, object]", value)


def _json_list(result: subprocess.CompletedProcess[str], label: str) -> list[object]:
    _require_success(result, label)
    try:
        value = cast(object, json.loads(result.stdout))
    except json.JSONDecodeError as error:
        raise GhStackValidationError(
            f"{label} returned invalid JSON: {error}"
        ) from error
    if not isinstance(value, list):
        raise GhStackValidationError(f"{label} must return one JSON list")
    return cast("list[object]", value)


def _branch_sha(cwd: Path, branch: str, remote: str) -> str:
    local = _run(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], cwd)
    _require_success(local, f"local branch lookup for {branch}")
    local_sha = local.stdout.strip()
    ref = f"refs/heads/{branch}"
    remote_result = _run(
        ["git", "ls-remote", "--exit-code", "--heads", remote, ref], cwd
    )
    remote_sha = _remote_sha(remote_result, ref)
    if not local_sha or remote_sha != local_sha:
        raise GhStackValidationError(
            f"remote head for {branch!r} is {remote_sha!r}, expected local {local_sha!r}"
        )
    return local_sha


def _validated_branches(
    cwd: Path, view: dict[str, object], trunk: str, remote: str
) -> list[dict[str, object]]:
    raw_branches_value = view.get("branches")
    if not isinstance(raw_branches_value, list):
        raise GhStackValidationError("gh stack view has no branch list")
    raw_branches = cast("list[object]", raw_branches_value)
    if len(raw_branches) < 2:
        raise GhStackValidationError(
            "gh stack view must contain at least two published branches"
        )

    validated: list[dict[str, object]] = []
    expected_base = trunk
    for index, raw in enumerate(raw_branches):
        if not isinstance(raw, dict):
            raise GhStackValidationError(f"stack branch {index} is not an object")
        branch = cast("dict[str, object]", raw)
        name = branch.get("name")
        if not isinstance(name, str) or not name:
            raise GhStackValidationError(f"stack branch {index} has no name")
        if branch.get("isMerged") is not False or branch.get("isQueued") is not False:
            raise GhStackValidationError(
                f"branch {name!r} is merged or queued; it is not safe terminal publication state"
            )
        if branch.get("needsRebase") is not False:
            raise GhStackValidationError(f"branch {name!r} still needs rebase")
        raw_pr = branch.get("pr")
        if not isinstance(raw_pr, dict):
            raise GhStackValidationError(f"branch {name!r} has no pull request")
        local_pr = cast("dict[str, object]", raw_pr)
        number = local_pr.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise GhStackValidationError(
                f"branch {name!r} has no valid pull request number"
            )
        if local_pr.get("state") != "OPEN":
            raise GhStackValidationError(
                f"PR #{number} local stack state is {local_pr.get('state')!r}, expected 'OPEN'"
            )

        sha = _branch_sha(cwd, name, remote)
        pr_result = _run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--json",
                "number,url,baseRefName,headRefName,headRefOid,state,autoMergeRequest",
            ],
            cwd,
        )
        pr = _json_object(pr_result, f"PR #{number} lookup")
        returned_number = pr.get("number")
        if (
            not isinstance(returned_number, int)
            or isinstance(returned_number, bool)
            or returned_number != number
        ):
            raise GhStackValidationError(
                f"PR lookup returned the wrong number for #{number}"
            )
        if pr.get("baseRefName") != expected_base:
            raise GhStackValidationError(
                f"PR #{number} base {pr.get('baseRefName')!r}, expected {expected_base!r}"
            )
        if pr.get("headRefName") != name:
            raise GhStackValidationError(
                f"PR #{number} head {pr.get('headRefName')!r}, expected {name!r}"
            )
        if pr.get("state") != "OPEN":
            raise GhStackValidationError(
                f"PR #{number} state {pr.get('state')!r}, expected 'OPEN'"
            )
        if pr.get("headRefOid") != sha:
            raise GhStackValidationError(
                f"PR #{number} head SHA {pr.get('headRefOid')!r}, expected {sha!r}"
            )
        if pr.get("autoMergeRequest") is not None:
            raise GhStackValidationError(f"PR #{number} still has auto-merge enabled")
        validated.append(
            {
                "number": number,
                "url": pr.get("url"),
                "base": expected_base,
                "head": name,
                "state": "OPEN",
                "sha": sha,
            }
        )
        expected_base = name
    return validated


def _stack_identity_and_mapping(
    cwd: Path, prs: list[dict[str, object]], trunk: str
) -> dict[str, int]:
    expected_numbers = [cast(int, pr["number"]) for pr in prs]
    expected_heads = [cast(str, pr["head"]) for pr in prs]
    expected_shas = [cast(str, pr["sha"]) for pr in prs]
    identity: tuple[int, int] | None = None

    for number in expected_numbers:
        result = _run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/stacks?pull_request={number}"], cwd
        )
        rows = _json_list(result, f"stack mapping lookup for PR #{number}")
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise GhStackValidationError(
                f"PR #{number} must map to exactly one GitHub stack"
            )
        stack = cast("dict[str, object]", rows[0])
        stack_id = stack.get("id")
        stack_number = stack.get("number")
        if (
            not isinstance(stack_id, int)
            or isinstance(stack_id, bool)
            or not isinstance(stack_number, int)
            or isinstance(stack_number, bool)
        ):
            raise GhStackValidationError(
                f"PR #{number} stack mapping has no numeric identity"
            )
        candidate = (stack_id, stack_number)
        if identity is None:
            identity = candidate
        elif identity != candidate:
            raise GhStackValidationError("published PRs map to different GitHub stacks")
        raw_base = stack.get("base")
        if not isinstance(raw_base, dict):
            raise GhStackValidationError("GitHub stack has no base object")
        base = cast("dict[str, object]", raw_base)
        if base.get("ref") != trunk:
            raise GhStackValidationError(
                f"GitHub stack base is not the canonical trunk {trunk!r}"
            )
        if stack.get("open") is not True:
            raise GhStackValidationError("GitHub stack is not open")
        raw_remote_prs_value = stack.get("pull_requests")
        if not isinstance(raw_remote_prs_value, list):
            raise GhStackValidationError("GitHub stack has no PR mapping")
        raw_remote_prs = cast("list[object]", raw_remote_prs_value)
        if len(raw_remote_prs) != len(prs):
            raise GhStackValidationError("GitHub stack PR mapping has the wrong length")
        for index, raw_remote_pr in enumerate(raw_remote_prs):
            if not isinstance(raw_remote_pr, dict):
                raise GhStackValidationError(
                    "GitHub stack PR mapping contains a non-object"
                )
            remote_pr = cast("dict[str, object]", raw_remote_pr)
            raw_head = remote_pr.get("head")
            if not isinstance(raw_head, dict):
                raise GhStackValidationError(
                    f"GitHub stack mapping has no head for PR #{expected_numbers[index]}"
                )
            head = cast("dict[str, object]", raw_head)
            remote_number = remote_pr.get("number")
            if (
                not isinstance(remote_number, int)
                or isinstance(remote_number, bool)
                or remote_number != expected_numbers[index]
                or remote_pr.get("state") != "open"
                or remote_pr.get("merged_at") is not None
                or head.get("ref") != expected_heads[index]
                or head.get("sha") != expected_shas[index]
            ):
                raise GhStackValidationError(
                    f"GitHub stack mapping differs at PR #{expected_numbers[index]}"
                )

    if identity is None:
        raise GhStackValidationError("GitHub stack mapping is empty")
    return {"id": identity[0], "number": identity[1]}


def verify_publication(
    cwd: Path, trunk: str, remote: str = "origin"
) -> dict[str, object]:
    """Verify local, branch, PR, and GitHub stack state after publication."""
    checked = preflight(cwd, trunk, remote)
    branch = cast(str, checked["trunk"])
    view = _json_object(_run(["gh", "stack", "view", "--json"], cwd), "gh stack view")
    if view.get("trunk") != branch:
        raise GhStackValidationError(
            f"local stack trunk {view.get('trunk')!r}, expected canonical {branch!r}"
        )
    prs = _validated_branches(cwd, view, branch, remote)
    stack_identity = _stack_identity_and_mapping(cwd, prs, branch)
    return {
        "valid": True,
        "trunk": branch,
        "remote": remote,
        "prs": prs,
        "stack": stack_identity,
    }


def _common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    _ = parser.add_argument("--cwd", type=Path, default=Path.cwd())
    return parser


def preflight_main(argv: list[str] | None = None) -> int:
    parser = _common_parser("Validate gh-stack trunk and remote before mutation")
    _ = parser.add_argument("--trunk", required=True)
    _ = parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    try:
        result = preflight(
            cast(Path, args.cwd).resolve(),
            cast(str, args.trunk),
            cast(str, args.remote),
        )
    except GhStackValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_main(argv: list[str] | None = None) -> int:
    parser = _common_parser("Run one guarded gh-stack mutation")
    _ = parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = cast("list[str]", args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    try:
        result = run_guarded(command, cast(Path, args.cwd).resolve())
    except GhStackValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    stdout = cast(str, result["stdout"])
    stderr = cast(str, result["stderr"])
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"stdout", "stderr"}
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def verify_main(argv: list[str] | None = None) -> int:
    parser = _common_parser("Verify exact gh-stack publication state")
    _ = parser.add_argument("--trunk", required=True)
    _ = parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    try:
        result = verify_publication(
            cast(Path, args.cwd).resolve(),
            cast(str, args.trunk),
            cast(str, args.remote),
        )
    except GhStackValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
