"""CLI entry point for review_surface.score -- runs git, prints JSON.

Split from review_surface.py so that module stays a pure function with zero
I/O imports (see review_surface.py's module docstring); all git I/O and the
optional [review_surface] TOML override live here instead. Mirrors
baseline.py's argparse + cli.run + cli.CliError pattern (cli is co-staged in
the bundled .pyz alongside this module).
"""
from __future__ import annotations

# Cyclopts exposes a dynamically typed invocation surface.
# pyright: reportAny=false, reportUnusedCallResult=false, reportUnusedFunction=false

import math
import sys
import tomllib
from typing import Annotated, Protocol, TextIO, cast

from cyclopts import App, Parameter

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


class _Args(Protocol):
    config: str | None
    repo: str
    diff_args: list[str]
    stdout: TextIO


def _score(repo: str, config: str | None, diff_args: list[str], stdout: TextIO) -> None:
    weights = None
    weights_source = "defaults"
    if config:
        weights = _load_weight_override(config)
        if weights is not None:
            weights_source = config
    rows = _numstat_rows(repo, diff_args)
    result: ReviewScore = score(rows, weights=weights, weights_source=weights_source)
    cli.emit(result, json_mode=True, stdout=stdout)


def _cmd_score(args: _Args) -> None:
    diff_args = args.diff_args
    named_range = getattr(args, "range", None)
    if named_range is not None:
        if diff_args != ["HEAD"]:
            raise cli.CliError("--range cannot be combined with positional diff arguments")
        diff_args = [named_range]
    _score(args.repo, args.config, diff_args, args.stdout)


def _command(*, repo: str = ".", config: str | None = None, diff_args: list[str] | None = None, named_range: Annotated[str | None, Parameter(name="--range")] = None) -> None:
    args = diff_args or ["HEAD"]
    if named_range is not None:
        if args != ["HEAD"]:
            raise cli.CliError("--range cannot be combined with positional diff arguments")
        args = [named_range]
    _score(repo, config, args, sys.stdout)


app = App(name="review-surface")
app.default(_command)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
