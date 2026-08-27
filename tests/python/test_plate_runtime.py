from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from easy_cheese.skills.plate import publication, stack_tools


def valid_publication() -> dict:
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
    assert result["artifacts"][0]["verified"] is True


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
    updates: dict, message: str
) -> None:
    state = valid_publication() | updates

    with pytest.raises(publication.PublicationValidationError) as error:
        publication.validate_publication(state)

    assert message in error.value.errors


def test_validate_publication_rejects_unverified_artifacts_and_pr_plan_drift() -> None:
    state = valid_publication()
    state["artifacts"][0]["verified"] = False
    state["pr_plan"] = {"plate_layout": "stacked"}

    with pytest.raises(publication.PublicationValidationError) as error:
        publication.validate_publication(state)

    assert error.value.errors == (
        "artifacts[0].verified must be true",
        "pr_plan.plate_layout must match topology",
    )


def test_topology_preflight_requires_empty_publication_evidence() -> None:
    state = valid_publication() | {
        "mode": "topology-preflight",
        "provider": "n/a",
        "gate": {"command": "n/a", "result": "n/a"},
        "commits": [],
        "prs": [],
    }

    result = publication.validate_publication(state)

    assert result["valid"] is True
    assert result["gate"] == {"command": "n/a", "result": "n/a"}


def test_validate_publication_cli_reports_every_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = valid_publication()
    state["artifacts"][0]["verified"] = False
    state["commits"] = ["bad"]
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))

    assert publication.main([str(path)]) == 1

    stderr = capsys.readouterr().err
    assert "artifacts[0].verified must be true" in stderr
    assert "commits[0] must be a 7-40 character hexadecimal SHA" in stderr


def completed(
    args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def test_stack_tools_reports_available_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / ".graphite_repo_config").write_text("{}")

    monkeypatch.setattr(
        stack_tools.shutil,
        "which",
        lambda name: f"/bin/{name}" if name in {"git", "gt", "git-town", "gh"} else None,
    )

    def run(args: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if args == ["git", "rev-parse", "--git-dir"]:
            return completed(args, stdout=".git\n")
        if args == ["git", "config", "--get", "git-town.main-branch"]:
            return completed(args, stdout="main\n")
        if args == ["gh", "extension", "list"]:
            return completed(args, stdout="github/gh-stack\tgh stack\n")
        raise AssertionError(args)

    monkeypatch.setattr(stack_tools.subprocess, "run", run)

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
            "repository_signal": None,
            "status": "remote-check-required",
        },
    }


def test_stack_tools_reports_missing_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stack_tools.shutil, "which", lambda _name: None)

    result = stack_tools.detect_stack_tools(tmp_path)

    assert result["recommended"] is None
    assert {provider["status"] for provider in result["providers"].values()} == {
        "not-installed"
    }
