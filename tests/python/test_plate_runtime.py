from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.plate import publication, stack_tools


def valid_publication() -> dict[str, object]:
    return {
        "mode": "new-pr",
        "topology": "single",
        "provider": "ordinary",
        "artifacts": [
            {"target": "docs/adr/example.md", "backend": "tilth", "verified": True}
        ],
        "gate": {"command": "just check", "result": "pass"},
        "commits": ["0022ccafb9568b5ddf04f6d3b86592885184427a"],
        "prs": [
            {
                "url": "https://github.com/example/repo/pull/42",
                "base": "main",
                "head": "feature",
                "verified": True,
            }
        ],
        "risk": "none",
    }


def test_validate_publication_normalizes_valid_evidence() -> None:
    result = publication.validate_publication(valid_publication())

    assert result["valid"] is True
    assert result["mode"] == "new-pr"
    assert result["topology"] == "single"
    assert result["provider"] == "ordinary"
    assert cast(dict[str, object], cast(list[object], result["artifacts"])[0])["verified"] is True


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"provider": "graphite"}, "single topology requires provider ordinary"),
        ({"topology": "stacked"}, "stacked topology requires a stack provider"),
        ({"gate": {"command": "just check", "result": "fail"}}, "publication requires a passing gate"),
        ({"commits": ["not-a-sha"]}, "commits[0] must be a 7-40 character hexadecimal SHA"),
        ({"prs": []}, "new-pr requires at least one verified PR"),
    ],
)
def test_validate_publication_rejects_impossible_states(
    updates: dict[str, object], message: str
) -> None:
    state = valid_publication() | updates

    with pytest.raises(publication.PublicationValidationError) as error:
        _ = publication.validate_publication(state)

    assert message in error.value.errors


def test_validate_publication_rejects_unverified_artifacts_and_pr_plan_drift() -> None:
    state = valid_publication()
    cast(dict[str, object], cast(list[object], state["artifacts"])[0])["verified"] = False
    state["pr_plan"] = {"plate_layout": "stacked"}

    with pytest.raises(publication.PublicationValidationError) as error:
        _ = publication.validate_publication(state)

    assert error.value.errors == (
        "artifacts[0].verified must be true",
        "pr_plan.plate_layout must match topology",
    )


def test_topology_preflight_requires_empty_publication_evidence() -> None:
    overrides: dict[str, object] = {
        "mode": "topology-preflight",
        "provider": "n/a",
        "gate": {"command": "n/a", "result": "n/a"},
        "commits": [],
        "prs": [],
    }
    state = valid_publication() | overrides

    result = publication.validate_publication(state)

    assert result["valid"] is True
    assert result["gate"] == {"command": "n/a", "result": "n/a"}


def test_validate_publication_cli_reports_every_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = valid_publication()
    cast(dict[str, object], cast(list[object], state["artifacts"])[0])["verified"] = False
    state["commits"] = ["bad"]
    path = tmp_path / "state.json"
    _ = path.write_text(json.dumps(state))

    assert publication.main([str(path)]) == 1

    stderr = capsys.readouterr().err
    assert "artifacts[0].verified must be true" in stderr
    assert "commits[0] must be a 7-40 character hexadecimal SHA" in stderr


def completed(
    args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


PREFLIGHT = ["gh", "api", "--include", "repos/{owner}/{repo}/stacks"]
ALL_TOOLS = frozenset({"git", "gt", "git-town", "gh"})
GH_ONLY = frozenset({"git", "gh"})


def response(status_line: str) -> str:
    return f"{status_line}\r\nContent-Type: application/json\r\n\r\n[]\n"


def install_stack_tool_stubs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    preflight: subprocess.CompletedProcess[str] | None,
    tools: frozenset[str] = ALL_TOOLS,
) -> None:
    """Stub every process `detect_stack_tools` shells out to.

    `preflight` is what the `gh api` enablement probe returns; `None` models a
    probe that never completed (timeout or spawn failure).
    """
    git_dir = tmp_path / ".git"
    git_dir.mkdir(exist_ok=True)
    if "gt" in tools:
        _ = (git_dir / ".graphite_repo_config").write_text("{}")

    def which(name: str) -> str | None:
        return f"/bin/{name}" if name in tools else None

    monkeypatch.setattr(shutil, "which", which)

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if args == ["git", "rev-parse", "--git-dir"]:
            return completed(args, stdout=".git\n")
        if args == ["git", "config", "--get", "git-town.main-branch"]:
            return completed(args, stdout="main\n")
        if args == ["gh", "extension", "list"]:
            return completed(args, stdout="github/gh-stack\tgh stack\n")
        if args == PREFLIGHT:
            if preflight is None:
                raise subprocess.TimeoutExpired(args, 10)
            return preflight
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", run)


def test_stack_tools_reports_available_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stack_tool_stubs(
        monkeypatch,
        tmp_path,
        preflight=completed(PREFLIGHT, stdout=response("HTTP/2.0 200 OK")),
    )

    result = stack_tools.detect_stack_tools(tmp_path)

    assert result["recommended"] == "graphite"
    assert result["providers"] == {
        "graphite": {
            "installed": True,
            "repository_signal": True,
            "status": "available",
        },
        "git-town": {
            "installed": True,
            "repository_signal": True,
            "status": "available",
        },
        "gh-stack": {
            "installed": True,
            "repository_signal": True,
            "status": "available",
        },
    }


@pytest.mark.parametrize(
    ("preflight", "status", "signal"),
    [
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 404 Not Found")),
            "not-enabled",
            False,
        ),
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 401 Unauthorized")),
            "auth-required",
            None,
        ),
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 403 Forbidden")),
            "auth-required",
            None,
        ),
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 503 Service Unavailable")),
            "service-error",
            None,
        ),
        (
            completed(
                PREFLIGHT,
                returncode=1,
                stderr="none of the git remotes point to a known GitHub host\n",
            ),
            "remote-check-required",
            None,
        ),
        (None, "remote-check-required", None),
    ],
)
def test_gh_stack_preflight_classifies_every_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preflight: subprocess.CompletedProcess[str] | None,
    status: str,
    signal: bool | None,
) -> None:
    install_stack_tool_stubs(
        monkeypatch, tmp_path, preflight=preflight, tools=GH_ONLY
    )

    providers = cast(
        dict[str, dict[str, object]], stack_tools.detect_stack_tools(tmp_path)["providers"]
    )

    assert providers["gh-stack"]["status"] == status
    assert providers["gh-stack"]["repository_signal"] is signal


@pytest.mark.parametrize(
    ("preflight", "recommended"),
    [
        (completed(PREFLIGHT, stdout=response("HTTP/2.0 200 OK")), "gh-stack"),
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 404 Not Found")),
            None,
        ),
        (
            completed(PREFLIGHT, returncode=1, stdout=response("HTTP/2.0 503 Service Unavailable")),
            "gh-stack",
        ),
        (None, "gh-stack"),
    ],
)
def test_only_a_404_preflight_withdraws_the_gh_stack_recommendation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preflight: subprocess.CompletedProcess[str] | None,
    recommended: str | None,
) -> None:
    install_stack_tool_stubs(
        monkeypatch, tmp_path, preflight=preflight, tools=GH_ONLY
    )

    assert stack_tools.detect_stack_tools(tmp_path)["recommended"] == recommended


def test_gh_stack_preflight_is_skipped_when_the_extension_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def which(name: str) -> str | None:
        return f"/bin/{name}" if name in {"git", "gh"} else None

    monkeypatch.setattr(shutil, "which", which)

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if args == ["git", "rev-parse", "--git-dir"]:
            return completed(args, stdout=".git\n")
        if args == ["gh", "extension", "list"]:
            return completed(args, stdout="github/gh-dash\tgh dash\n")
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", run)

    providers = cast(
        dict[str, dict[str, object]], stack_tools.detect_stack_tools(tmp_path)["providers"]
    )

    assert providers["gh-stack"] == {
        "installed": False,
        "repository_signal": None,
        "status": "not-installed",
    }


def test_stack_tools_reports_missing_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def which(_name: str) -> None:
        return None

    monkeypatch.setattr(shutil, "which", which)

    result = stack_tools.detect_stack_tools(tmp_path)

    providers = cast(dict[str, dict[str, object]], result["providers"])
    assert result["recommended"] is None
    assert {provider["status"] for provider in providers.values()} == {
        "not-installed"
    }
