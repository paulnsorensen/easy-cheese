"""Detect supported stacked-PR providers without mutating repository state."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

_TIMEOUT_SECONDS = 5
_REMOTE_TIMEOUT_SECONDS = 10
_STATUS_LINE = re.compile(r"^HTTP/[\d.]+\s+(\d{3})\b")


def _run(
    args: list[str], cwd: Path, timeout: float = _TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _git_dir(cwd: Path) -> Path | None:
    if shutil.which("git") is None:
        return None
    result = _run(["git", "rev-parse", "--git-dir"], cwd)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else cwd / path


def _configured_status(installed: bool, configured: bool) -> str:
    if not installed:
        return "not-installed"
    return "available" if configured else "not-configured"


def _http_status(stdout: str) -> int | None:
    """The final HTTP status code in a `gh api --include` response, if any."""
    codes = [
        int(match.group(1))
        for line in stdout.splitlines()
        if (match := _STATUS_LINE.match(line)) is not None
    ]
    return codes[-1] if codes else None


def _gh_stack_enablement(cwd: Path) -> tuple[str, bool | None]:
    """Classify the documented read-only `gh stack` enablement preflight.

    `GET /repos/{owner}/{repo}/stacks` answers 200 when Stacked PRs is enabled
    and 404 when it is not. Every other outcome — authentication, service, or
    an unresolvable repository — stays indeterminate so the caller keeps the
    exit-code-4 fallback instead of reporting a false enablement verdict.
    """
    result = _run(
        ["gh", "api", "--include", "repos/{owner}/{repo}/stacks"],
        cwd,
        timeout=_REMOTE_TIMEOUT_SECONDS,
    )
    status = _http_status(result.stdout) if result is not None else None
    if status is None:
        return "remote-check-required", None
    if 200 <= status < 300:
        return "available", True
    if status == 404:
        return "not-enabled", False
    if status in {401, 403}:
        return "auth-required", None
    return "service-error", None


def detect_stack_tools(cwd: Path) -> dict[str, object]:
    """Return deterministic installation and repository signals for stack tools."""
    git_dir = _git_dir(cwd)
    graphite_installed = shutil.which("gt") is not None
    graphite_signal = bool(git_dir and (git_dir / ".graphite_repo_config").is_file())

    git_town_installed = shutil.which("git-town") is not None
    git_town_result = (
        _run(["git", "config", "--get", "git-town.main-branch"], cwd)
        if git_town_installed and shutil.which("git") is not None
        else None
    )
    git_town_signal = bool(
        git_town_result
        and git_town_result.returncode == 0
        and git_town_result.stdout.strip()
    )

    gh_installed = shutil.which("gh") is not None
    extension_result = _run(["gh", "extension", "list"], cwd) if gh_installed else None
    gh_stack_installed = bool(
        extension_result
        and extension_result.returncode == 0
        and any(
            columns[1] == "github/gh-stack"
            for line in extension_result.stdout.splitlines()
            if len(columns := line.split()) > 1
        )
    )

    gh_stack_status, gh_stack_signal = (
        _gh_stack_enablement(cwd) if gh_stack_installed else ("not-installed", None)
    )

    providers: dict[str, dict[str, object]] = {
        "graphite": {
            "installed": graphite_installed,
            "repository_signal": graphite_signal,
            "status": _configured_status(graphite_installed, graphite_signal),
        },
        "git-town": {
            "installed": git_town_installed,
            "repository_signal": git_town_signal,
            "status": _configured_status(git_town_installed, git_town_signal),
        },
        "gh-stack": {
            "installed": gh_stack_installed,
            "repository_signal": gh_stack_signal,
            "status": gh_stack_status,
        },
    }
    recommended = next(
        (
            name
            for name in ("graphite", "git-town")
            if providers[name]["status"] == "available"
        ),
        "gh-stack" if gh_stack_installed and gh_stack_status != "not-enabled" else None,
    )
    return {"providers": providers, "recommended": recommended}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    cwd = cast(Path, args.cwd)
    if not cwd.is_dir():
        print(f"ERROR: not a directory: {cwd}", file=sys.stderr)
        return 1
    print(json.dumps(detect_stack_tools(cwd.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
