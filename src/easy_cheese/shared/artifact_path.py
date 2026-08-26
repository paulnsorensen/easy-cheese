"""Resolve durable and transient artifact paths for packaged skills."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PHASES = frozenset({
    "cook", "press", "age", "cure", "specs", "notes", "hard",
    "research", "ultracook", "pasteurize",
})
XDG_PHASES = frozenset({"specs", "research"})
PHASE_DIRS = {"hard": "hard-cheese"}
KEBAB_SLUG = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")


def _project_key() -> str:
    override = os.environ.get("EASY_CHEESE_PROJECT", "").strip()
    if override:
        return re.sub(r"[^a-z0-9._-]+", "-", override.lower()).strip("-._") or "default"
    try:
        remote = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if remote.returncode == 0 and remote.stdout.strip():
            value = remote.stdout.strip().removesuffix(".git")
            value = value.rsplit(":", 1)[-1].rsplit("/", 2)[-2:]
            return re.sub(r"[^a-z0-9._-]+", "-", "-".join(value).lower()).strip("-._") or "default"
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().name


def _corpus_home() -> Path:
    override = os.environ.get("EASY_CHEESE_HOME", "").strip()
    if override and Path(override).is_absolute():
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    return (Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "share") / "cheese"


def project_corpus_root() -> Path:
    return _corpus_home() / _project_key()


def artifact_path(phase: str, slug: str) -> Path:
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; expected one of {sorted(PHASES)}")
    if not isinstance(slug, str) or not KEBAB_SLUG.match(slug):
        raise ValueError(
            f"slug {slug!r} must be kebab-case, 1-64 chars, [a-z0-9-], "
            "no leading/trailing hyphen, no double hyphens"
        )
    root = project_corpus_root() if phase in XDG_PHASES else Path(".cheese")
    return root / PHASE_DIRS.get(phase, phase) / f"{slug}.md"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase")
    parser.add_argument("slug")
    args = parser.parse_args(argv)
    try:
        resolved = project_corpus_root() if args.phase == "research" else artifact_path(args.phase, args.slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0
