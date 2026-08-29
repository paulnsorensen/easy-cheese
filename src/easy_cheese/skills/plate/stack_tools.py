"""Detect supported stacked-PR providers without mutating repository state."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

_TIMEOUT_SECONDS = 5


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
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
            line.split(maxsplit=1)[0] == "github/gh-stack"
            for line in extension_result.stdout.splitlines()
            if line.split()
        )
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
            "repository_signal": None,
            "status": "remote-check-required" if gh_stack_installed else "not-installed",
        },
    }
    recommended = next(
        (
            name
            for name in ("graphite", "git-town")
            if providers[name]["status"] == "available"
        ),
        "gh-stack" if gh_stack_installed else None,
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
