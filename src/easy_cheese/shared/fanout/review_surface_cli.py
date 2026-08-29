"""CLI entry point for review_surface.score -- runs git, prints JSON.

Split from review_surface.py so that module stays a pure function with zero
I/O imports (see review_surface.py's module docstring); all git I/O and the
optional [review_surface] TOML override live here instead. Mirrors
baseline.py's argparse + cli.run + cli.CliError pattern (cli is co-staged in
the bundled .pyz alongside this module).
"""
from __future__ import annotations

import argparse
import math
import sys
import tomllib
from typing import TextIO, cast

from easy_cheese.shared import cli, git_utils

from .review_surface import ReviewScore, score


def _numstat_rows(repo: str, diff_args: list[str]) -> list[tuple[str, int, int]]:
    for arg in diff_args:
        if arg.startswith("-"):
            raise cli.CliError(f"diff argument must not start with '-': {arg!r}")
    # -z: NUL-delimited records with raw (unescaped, unquoted) paths --
    # eliminates core.quotePath escaping of non-ASCII paths.
    # --no-renames: a renamed file becomes a plain delete + add row instead
    # of a brace-compressed "{old => new}/path" synthetic string.
    # "--" separates diff_args from git flags so a leading-"-" element
    # (rejected above as defense in depth) can never be read as a flag.
    result = git_utils.run_git(
        ["-C", repo, "diff", "--numstat", "-z", "--no-renames", *diff_args, "--"]
    )
    if result.returncode != 0:
        raise cli.CliError(
            f"git diff --numstat {' '.join(diff_args)} failed: {result.stderr.strip()}"
        )
    rows: list[tuple[str, int, int]] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        insertions, deletions, path = record.split("\t", 2)
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
    ship unmodified). Every entry is validated: exactly two elements, a
    non-empty string glob, and a finite weight in [0.0, 1.0] -- an
    out-of-range or malformed weight must not be able to silently drive a
    repo's own sizing negative or off the scale."""
    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise cli.CliError(f"cannot read config {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise cli.CliError(f"malformed TOML in {config_path}: {exc}") from exc
    table = data.get("review_surface")
    if not isinstance(table, dict):
        return None
    table_items = cast(dict[str, object], table)
    if "weights" not in table_items:
        return None
    raw = table_items["weights"]
    if not isinstance(raw, list):
        raise cli.CliError(f"[review_surface].weights must be a list, got {type(raw).__name__}")
    raw_items = cast(list[object], raw)
    weights: list[tuple[str, float]] = []
    for index, entry in enumerate(raw_items):
        if not isinstance(entry, list):
            raise cli.CliError(
                f"[review_surface].weights[{index}] must be a [glob, weight] pair: {entry!r}"
            )
        entry_items = cast(list[object], entry)
        if len(entry_items) != 2:
            raise cli.CliError(
                f"[review_surface].weights[{index}] must be a [glob, weight] pair: {entry!r}"
            )
        glob, weight_raw = entry_items
        if not isinstance(glob, str) or not glob:
            raise cli.CliError(
                f"[review_surface].weights[{index}] glob must be a non-empty string: {glob!r}"
            )
        if isinstance(weight_raw, bool) or not isinstance(weight_raw, (int, float)):
            raise cli.CliError(
                f"[review_surface].weights[{index}] weight must be a number: {weight_raw!r}"
            )
        weight = float(weight_raw)
        if not math.isfinite(weight) or not (0.0 <= weight <= 1.0):
            raise cli.CliError(
                f"[review_surface].weights[{index}] weight must be finite in [0.0, 1.0]: {weight!r}"
            )
        weights.append((glob, weight))
    return tuple(weights)


class _Args(argparse.Namespace):
    config: str | None = None
    repo: str = "."
    diff_args: list[str] = ["HEAD"]
    stdout: TextIO = sys.stdout


def _cmd_score(args: _Args) -> None:
    weights = None
    weights_source = "defaults"
    if args.config:
        weights = _load_weight_override(args.config)
        if weights is not None:
            weights_source = args.config
    rows = _numstat_rows(args.repo, args.diff_args)
    result: ReviewScore = score(rows, weights=weights, weights_source=weights_source)
    cli.emit(result, json_mode=True, stdout=args.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Score a git diff's review surface via review_surface.score()."
    _ = parser.add_argument("--repo", default=".", help="path to the git repository")
    _ = parser.add_argument(
        "--config",
        help="optional TOML file with a [review_surface] weights override",
    )
    _ = parser.add_argument(
        "diff_args",
        nargs="*",
        default=["HEAD"],
        help="git diff --numstat arguments (e.g. HEAD~1 HEAD, or HEAD~1..HEAD); defaults to HEAD",
    )
    parser.set_defaults(func=_cmd_score)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
