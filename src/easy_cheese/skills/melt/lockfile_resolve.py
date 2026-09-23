#!/usr/bin/env python3
"""
Lockfile conflict resolution.
Takes one side and regenerates the lockfile from the manifest.
"""

from __future__ import annotations

import subprocess

from cyclopts import App
from pathlib import Path
from typing import TypedDict

from easy_cheese.shared import cli

from easy_cheese.shared.git_utils import (
    detect_lockfile_type,
    get_conflicted_files,
    run_git,
)


class _LockfileConfig(TypedDict):
    manifest: str
    lockfile: str
    regen_cmd: list[str]


class _LockfileResult(TypedDict):
    path: str
    resolved: bool
    message: str


# Map lockfile types to regeneration commands and manifest files
LOCKFILE_CONFIG: dict[str, _LockfileConfig] = {
    "cargo": {
        "manifest": "Cargo.toml",
        "lockfile": "Cargo.lock",
        "regen_cmd": ["cargo", "generate-lockfile"],
    },
    "npm": {
        "manifest": "package.json",
        "lockfile": "package-lock.json",
        "regen_cmd": ["npm", "install", "--package-lock-only"],
    },
    "yarn": {
        "manifest": "package.json",
        "lockfile": "yarn.lock",
        "regen_cmd": ["yarn", "install", "--mode", "update-lockfile"],
    },
    "pnpm": {
        "manifest": "package.json",
        "lockfile": "pnpm-lock.yaml",
        "regen_cmd": ["pnpm", "install", "--lockfile-only"],
    },
    "poetry": {
        "manifest": "pyproject.toml",
        "lockfile": "poetry.lock",
        "regen_cmd": ["poetry", "lock", "--no-update"],
    },
    "pipenv": {
        "manifest": "Pipfile",
        "lockfile": "Pipfile.lock",
        "regen_cmd": ["pipenv", "lock"],
    },
    "uv": {
        "manifest": "pyproject.toml",
        "lockfile": "uv.lock",
        "regen_cmd": ["uv", "lock"],
    },
    "bundler": {
        "manifest": "Gemfile",
        "lockfile": "Gemfile.lock",
        "regen_cmd": ["bundle", "lock"],
    },
    "go": {
        "manifest": "go.mod",
        "lockfile": "go.sum",
        "regen_cmd": ["go", "mod", "tidy"],
    },
}


def resolve_lockfile(
    lockfile_path: str,
    strategy: str = "theirs",
    dry_run: bool = False,
) -> _LockfileResult:
    result: _LockfileResult = {
        "path": lockfile_path,
        "resolved": False,
        "message": "",
    }

    lockfile_type = detect_lockfile_type(lockfile_path)
    if not lockfile_type:
        result["message"] = "Unknown lockfile type"
        return result

    config = LOCKFILE_CONFIG.get(lockfile_type)
    if not config:
        result["message"] = f"No config for lockfile type: {lockfile_type}"
        return result

    manifest_path = Path(lockfile_path).parent / config["manifest"]
    if not manifest_path.exists():
        result["message"] = f"Manifest not found: {manifest_path}"
        return result

    if "<<<<<<<" in manifest_path.read_text():
        result["message"] = (
            f"Manifest {manifest_path} has conflict markers — resolve it before regenerating"
        )
        return result

    if dry_run:
        result["resolved"] = True
        result["message"] = f"would take {strategy} and run: {' '.join(config['regen_cmd'])}"
        return result

    if strategy in ("ours", "theirs"):
        stage = ":2:" if strategy == "ours" else ":3:"
        git_result: subprocess.CompletedProcess[str] = run_git(["show", f"{stage}{lockfile_path}"])

        if git_result.returncode != 0:
            result["message"] = f"could not extract {strategy} version"
            return result

        _ = Path(lockfile_path).write_text(git_result.stdout)

    regen_result = subprocess.run(
        config["regen_cmd"],
        capture_output=True,
        text=True,
        cwd=Path(lockfile_path).parent,
    )

    if regen_result.returncode != 0:
        result["message"] = f"regen failed: {regen_result.stderr.strip()}"
        return result

    add_result: subprocess.CompletedProcess[str] = run_git(["add", lockfile_path])
    if add_result.returncode != 0:
        result["message"] = f"regenerated but staging failed: {add_result.stderr.strip()}"
        return result
    if lockfile_type == "go":
        go_mod = Path(lockfile_path).parent / "go.mod"
        if go_mod.exists():
            add_mod_result: subprocess.CompletedProcess[str] = run_git(["add", str(go_mod)])
            if add_mod_result.returncode != 0:
                result["message"] = (
                    f"regenerated but staging go.mod failed: {add_mod_result.stderr.strip()}"
                )
                return result

    result["resolved"] = True
    if strategy == "regen":
        result["message"] = "regenerated and staged"
    else:
        result["message"] = f"took {strategy}, regenerated, staged"
    return result


def _collect_lockfiles(files: list[str]) -> list[str]:
    if files:
        return files
    return [f for f in get_conflicted_files() if detect_lockfile_type(f)]


def _command(strategy: str = "theirs", dry_run: bool = False, files: list[str] | None = None) -> int:
    files = files or []
    lockfiles = _collect_lockfiles(files)

    if not lockfiles:
        print("no conflicted lockfiles")
        return 0

    results: list[_LockfileResult] = []
    for path in lockfiles:
        result = resolve_lockfile(path, strategy, dry_run)
        results.append(result)
        status = "ok" if result["resolved"] else "--"
        print(f"{status} {result['path']}: {result['message']}")

    resolved = sum(1 for r in results if r["resolved"])
    mode = "dry-run" if dry_run else "apply"
    print(f"{resolved}/{len(results)} resolved ({mode})")

    return 0 if resolved == len(results) else 1


app = App(name="lockfile-resolve")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
