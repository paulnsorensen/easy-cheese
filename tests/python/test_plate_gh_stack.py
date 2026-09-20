from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.plate import gh_stack


def completed(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def test_canonical_trunk_accepts_heads_ref_and_rejects_remote_tracking_names() -> None:
    assert gh_stack.canonical_trunk("main", "origin") == "main"
    assert gh_stack.canonical_trunk("refs/heads/main", "origin") == "main"

    for value in ("origin/main", "refs/remotes/origin/main"):
        with pytest.raises(gh_stack.GhStackValidationError, match="remote-tracking"):
            _ = gh_stack.canonical_trunk(value, "origin")


def test_preflight_requires_the_canonical_trunk_on_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(
        args: list[str], _cwd: Path, _timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {
            ("git", "check-ref-format", "--branch", "main"): completed(args),
            ("git", "remote", "get-url", "origin"): completed(
                args, stdout="git@github.com:example/repo.git\n"
            ),
            (
                "git",
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "refs/heads/main",
            ): completed(args, stdout="abc123\trefs/heads/main\n"),
        }
        return responses[tuple(args)]

    monkeypatch.setattr(gh_stack, "_run", run)

    assert gh_stack.preflight(tmp_path, "refs/heads/main", "origin") == {
        "valid": True,
        "trunk": "main",
        "remote": "origin",
        "remote_url": "git@github.com:example/repo.git",
        "remote_sha": "abc123",
    }
    assert calls[-1][-1] == "refs/heads/main"


def test_guarded_run_rejects_zero_exit_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["gh", "stack", "submit", "--auto", "--open", "--remote", "origin"]

    def run(
        _args: list[str], _cwd: Path, timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        return completed(
            args,
            stderr="⚠ Failed to update stack on GitHub: Validation Failed\n",
        )

    monkeypatch.setattr(gh_stack, "_run", run)

    with pytest.raises(gh_stack.GhStackValidationError, match="warning"):
        _ = gh_stack.run_guarded(args, tmp_path)


@pytest.mark.parametrize(
    "stderr",
    [
        "! Warning: could not update PR #3\n",
        "gh: ⚠ Failed to update stack\n",
        "[warn] stack not updated\n",
        "pushed\nstack sync warning: mapping skipped\n",
    ],
)
def test_guarded_run_rejects_decorated_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str
) -> None:
    args = ["gh", "stack", "sync", "--remote", "origin"]

    def run(
        _args: list[str], _cwd: Path, timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        return completed(args, stderr=stderr)

    monkeypatch.setattr(gh_stack, "_run", run)

    with pytest.raises(gh_stack.GhStackValidationError, match="warning"):
        _ = gh_stack.run_guarded(args, tmp_path)


def test_guarded_run_returns_the_result_for_a_clean_zero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["gh", "stack", "push", "--remote", "origin"]

    def run(
        _args: list[str], _cwd: Path, timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        return completed(args, stdout="Pushed fix-warning-banner to origin\n")

    monkeypatch.setattr(gh_stack, "_run", run)

    assert gh_stack.run_guarded(args, tmp_path) == {
        "valid": True,
        "command": args,
        "exit_status": 0,
        "stdout": "Pushed fix-warning-banner to origin\n",
        "stderr": "",
    }


def test_guarded_run_rejects_zero_exit_http_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["gh", "stack", "sync", "--remote", "origin"]

    def run(
        _args: list[str], _cwd: Path, timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        _ = timeout
        return completed(
            args,
            stderr="request ended with HTTP 503\n",
        )

    monkeypatch.setattr(gh_stack, "_run", run)

    with pytest.raises(gh_stack.GhStackValidationError, match="HTTP failure"):
        _ = gh_stack.run_guarded(args, tmp_path)


def test_guarded_run_requires_explicit_origin_when_supported(tmp_path: Path) -> None:
    with pytest.raises(gh_stack.GhStackValidationError, match="--remote origin"):
        _ = gh_stack.run_guarded(["gh", "stack", "submit", "--auto"], tmp_path)


def test_verify_publication_checks_prs_and_remote_stack_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack_view = {
        "trunk": "main",
        "currentBranch": "feature-two",
        "branches": [
            {
                "name": "feature-one",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {
                    "number": 11,
                    "url": "https://example.test/pull/11",
                    "state": "OPEN",
                },
            },
            {
                "name": "feature-two",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {
                    "number": 12,
                    "url": "https://example.test/pull/12",
                    "state": "OPEN",
                },
            },
        ],
    }
    remote_stack = [
        {
            "id": 99,
            "number": 7,
            "open": True,
            "base": {"ref": "main"},
            "pull_requests": [
                {
                    "number": 11,
                    "state": "open",
                    "merged_at": None,
                    "head": {"ref": "feature-one", "sha": "sha-one"},
                },
                {
                    "number": 12,
                    "state": "open",
                    "merged_at": None,
                    "head": {"ref": "feature-two", "sha": "sha-two"},
                },
            ],
        }
    ]

    def run(
        args: list[str], _cwd: Path, _timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(args)
        if key == ("git", "check-ref-format", "--branch", "main"):
            return completed(args)
        if key == ("git", "remote", "get-url", "origin"):
            return completed(args, stdout="git@github.com:example/repo.git\n")
        if key == (
            "git",
            "ls-remote",
            "--exit-code",
            "--heads",
            "origin",
            "refs/heads/main",
        ):
            return completed(args, stdout="trunk-sha\trefs/heads/main\n")
        if key == ("gh", "stack", "view", "--json"):
            return completed(args, stdout=json.dumps(stack_view))
        if key[:3] == ("git", "rev-parse", "--verify"):
            branch = key[3].removeprefix("refs/heads/")
            return completed(args, stdout=f"sha-{branch.removeprefix('feature-')}\n")
        if key[:5] == ("git", "ls-remote", "--exit-code", "--heads", "origin"):
            branch = key[5].removeprefix("refs/heads/")
            sha = f"sha-{branch.removeprefix('feature-')}"
            return completed(args, stdout=f"{sha}\trefs/heads/{branch}\n")
        if key[:3] == ("gh", "pr", "view"):
            number = int(key[3])
            branch = "feature-one" if number == 11 else "feature-two"
            base = "main" if number == 11 else "feature-one"
            return completed(
                args,
                stdout=json.dumps(
                    {
                        "number": number,
                        "url": f"https://example.test/pull/{number}",
                        "baseRefName": base,
                        "headRefName": branch,
                        "headRefOid": f"sha-{branch.removeprefix('feature-')}",
                        "state": "OPEN",
                        "autoMergeRequest": None,
                    }
                ),
            )
        if key[:2] == ("gh", "api"):
            return completed(args, stdout=json.dumps(remote_stack))
        raise AssertionError(args)

    monkeypatch.setattr(gh_stack, "_run", run)

    result = gh_stack.verify_publication(tmp_path, "main", "origin")

    assert result["valid"] is True
    assert result["stack"] == {"id": 99, "number": 7}
    prs = cast("list[dict[str, object]]", result["prs"])
    assert [pr["number"] for pr in prs] == [11, 12]


def test_verify_publication_rejects_wrong_pr_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack_view = {
        "trunk": "main",
        "currentBranch": "feature-one",
        "branches": [
            {
                "name": "feature-one",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {"number": 11, "state": "OPEN"},
            },
            {
                "name": "feature-two",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {"number": 12, "state": "OPEN"},
            },
        ],
    }

    def run(
        args: list[str], _cwd: Path, _timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(args)
        if key == ("git", "check-ref-format", "--branch", "main"):
            return completed(args)
        if key == ("git", "remote", "get-url", "origin"):
            return completed(args, stdout="origin-url\n")
        if key[-1:] == ("refs/heads/main",):
            return completed(args, stdout="trunk-sha\trefs/heads/main\n")
        if key == ("gh", "stack", "view", "--json"):
            return completed(args, stdout=json.dumps(stack_view))
        if key == ("git", "rev-parse", "--verify", "refs/heads/feature-one"):
            return completed(args, stdout="sha-one\n")
        if key[-1:] == ("refs/heads/feature-one",):
            return completed(args, stdout="sha-one\trefs/heads/feature-one\n")
        if key[:3] == ("gh", "pr", "view"):
            return completed(
                args,
                stdout=json.dumps(
                    {
                        "number": 11,
                        "url": "https://example.test/pull/11",
                        "baseRefName": "origin/main",
                        "headRefName": "feature-one",
                        "headRefOid": "sha-one",
                        "state": "OPEN",
                        "autoMergeRequest": None,
                    }
                ),
            )
        raise AssertionError(args)

    monkeypatch.setattr(gh_stack, "_run", run)

    with pytest.raises(gh_stack.GhStackValidationError, match="base 'origin/main'"):
        _ = gh_stack.verify_publication(tmp_path, "main", "origin")


@pytest.mark.parametrize(
    ("boolean_source", "message"),
    (("pr", "wrong number"), ("stack", "mapping differs")),
)
def test_verify_publication_rejects_boolean_pr_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boolean_source: str,
    message: str,
) -> None:
    stack_view: dict[str, object] = {
        "trunk": "main",
        "currentBranch": "feature-two",
        "branches": [
            {
                "name": "feature-one",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {"number": 1, "state": "OPEN"},
            },
            {
                "name": "feature-two",
                "isMerged": False,
                "isQueued": False,
                "needsRebase": False,
                "pr": {"number": 2, "state": "OPEN"},
            },
        ],
    }
    remote_stack = [
        {
            "id": 99,
            "number": 7,
            "open": True,
            "base": {"ref": "main"},
            "pull_requests": [
                {
                    "number": True if boolean_source == "stack" else 1,
                    "state": "open",
                    "merged_at": None,
                    "head": {"ref": "feature-one", "sha": "sha-one"},
                },
                {
                    "number": 2,
                    "state": "open",
                    "merged_at": None,
                    "head": {"ref": "feature-two", "sha": "sha-two"},
                },
            ],
        }
    ]

    def run(
        args: list[str], _cwd: Path, _timeout: float = 10
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(args)
        if key == ("git", "check-ref-format", "--branch", "main"):
            return completed(args)
        if key == ("git", "remote", "get-url", "origin"):
            return completed(args, stdout="git@github.com:example/repo.git\n")
        if key == (
            "git",
            "ls-remote",
            "--exit-code",
            "--heads",
            "origin",
            "refs/heads/main",
        ):
            return completed(args, stdout="trunk-sha\trefs/heads/main\n")
        if key == ("gh", "stack", "view", "--json"):
            return completed(args, stdout=json.dumps(stack_view))
        if key[:3] == ("git", "rev-parse", "--verify"):
            branch = key[3].removeprefix("refs/heads/")
            return completed(args, stdout=f"sha-{branch.removeprefix('feature-')}\n")
        if key[:5] == ("git", "ls-remote", "--exit-code", "--heads", "origin"):
            branch = key[5].removeprefix("refs/heads/")
            sha = f"sha-{branch.removeprefix('feature-')}"
            return completed(args, stdout=f"{sha}\trefs/heads/{branch}\n")
        if key[:3] == ("gh", "pr", "view"):
            number = int(key[3])
            branch = "feature-one" if number == 1 else "feature-two"
            base = "main" if number == 1 else "feature-one"
            returned_number = True if boolean_source == "pr" and number == 1 else number
            return completed(
                args,
                stdout=json.dumps(
                    {
                        "number": returned_number,
                        "url": f"https://example.test/pull/{number}",
                        "baseRefName": base,
                        "headRefName": branch,
                        "headRefOid": f"sha-{branch.removeprefix('feature-')}",
                        "state": "OPEN",
                        "autoMergeRequest": None,
                    }
                ),
            )
        if key[:2] == ("gh", "api"):
            return completed(args, stdout=json.dumps(remote_stack))
        raise AssertionError(args)

    monkeypatch.setattr(gh_stack, "_run", run)

    with pytest.raises(gh_stack.GhStackValidationError, match=message):
        _ = gh_stack.verify_publication(tmp_path, "main", "origin")
