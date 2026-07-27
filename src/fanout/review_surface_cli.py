"""CLI entry point for review_surface.score -- runs git, prints JSON.

Split from review_surface.py so that module stays a pure function with zero
I/O imports (see review_surface.py's module docstring); all git I/O and the
optional [review_surface] TOML override live here instead. Mirrors
age_route_cli.py's split-CLI pattern.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib

from review_surface import score


def _numstat_rows(repo: str, diff_args: list[str]) -> list[tuple[str, int, int]]:
    result = subprocess.run(
        ["git", "-C", repo, "diff", "--numstat", *diff_args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff --numstat {' '.join(diff_args)} failed: {result.stderr.strip()}"
        )
    rows: list[tuple[str, int, int]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        insertions, deletions, path = line.split("\t", 2)
        rows.append(
            (
                path,
                0 if insertions == "-" else int(insertions),
                0 if deletions == "-" else int(deletions),
            )
        )
    return rows


def _load_weight_override(config_path: str) -> tuple[tuple[str, float], ...] | None:
    """Read an optional [review_surface] TOML table's `weights` key -- a list
    of [glob, weight] pairs that REPLACES review_surface.DEFAULT_WEIGHTS
    wholesale. Returns None when the table or key is absent (module defaults
    ship unmodified)."""
    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise RuntimeError(f"cannot read config {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"malformed TOML in {config_path}: {exc}") from exc
    table = data.get("review_surface")
    if not table or "weights" not in table:
        return None
    return tuple((str(glob), float(weight)) for glob, weight in table["weights"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Score a git diff's review surface via review_surface.score()."
    )
    parser.add_argument("--repo", default=".", help="path to the git repository")
    parser.add_argument(
        "--config",
        help="optional TOML file with a [review_surface] weights override",
    )
    parser.add_argument(
        "diff_args",
        nargs="*",
        default=["HEAD"],
        help="git diff --numstat arguments (e.g. HEAD~1 HEAD, or HEAD~1..HEAD); defaults to HEAD",
    )
    args = parser.parse_args(argv[1:])

    weights = None
    if args.config:
        try:
            weights = _load_weight_override(args.config)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    try:
        rows = _numstat_rows(args.repo, args.diff_args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    result = score(rows, weights=weights)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
