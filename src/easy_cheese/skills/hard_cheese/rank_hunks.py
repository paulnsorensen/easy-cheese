#!/usr/bin/env python3
"""Score `git diff <base>..<head>` hunks by risk and emit the top N as JSON.

Feeds the /hard-cheese gate a deterministic set of ranked regions so the
judge can anchor its questions to the riskiest parts of a diff instead of
picking targets itself. Scoring combines hunk churn, diff diffusion across
files and directories, and prior-change history of the file. It also weighs
whether the git author is new to the file. Pattern flags mark error paths,
authorization, concurrency, config or secret files, and deleted test lines.
Every fired feature is named in that hunk's `reasons`.

Usage:

    python3 skills/hard-cheese/scripts/hard-cheese.pyz rank-hunks \
        --base <ref> --head <ref> [--top N] [--cwd <path>]

Output is a single-line JSON list, sorted by score descending, of
`{id, path, start, end, score, reasons}`. An empty diff emits `[]`.
Deterministic: no timestamps, no randomness. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import TextIO, TypedDict, cast

from easy_cheese.shared import cli

_CHURN_WEIGHT = 1.0
_CHURN_CAP = 10
_DIFFUSION_WEIGHT = 2.0
_PRIOR_CHANGES_WEIGHT = 0.25
_PRIOR_CHANGES_CAP = 50
_AUTHOR_NEW_WEIGHT = 1.0
_PATTERN_WEIGHT = 10.0
_DELETED_TESTS_WEIGHT = 8.0

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_WORD_BOUNDARY = r"(?<![A-Za-z0-9])({})(?![A-Za-z0-9])"
_ERROR_PATH_RE = re.compile(
    _WORD_BOUNDARY.format("except|raise|catch|throw|panic|unwrap|Error"), re.IGNORECASE
)
_AUTH_RE = re.compile(
    _WORD_BOUNDARY.format("auth|permission|role|token|secret|password|acl|grant"),
    re.IGNORECASE,
)
_CONCURRENCY_RE = re.compile(
    _WORD_BOUNDARY.format("thread|lock|mutex|async|await|atomic|goroutine|channel"),
    re.IGNORECASE,
)
_CONFIG_PATH_RE = re.compile(
    r"(^|/)[^/]*\.env(\.[^/]*)?$|\.ya?ml$|\.toml$|\.json$|\.ini$|(^|/)secrets?(/|$|\.[^/]*)|(^|/)config(/|$|\.[^/]*)",
    re.IGNORECASE,
)
_TEST_PATH_RE = re.compile(
    r"(^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$", re.IGNORECASE
)


class RawHunk(TypedDict):
    path: str
    start: int
    end: int
    added: list[str]
    deleted: list[str]


class Hunk(TypedDict):
    id: str
    path: str
    start: int
    end: int
    score: float
    reasons: list[str]


def _first_stderr_line(stderr: str, *, fallback: str) -> str:
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.removeprefix("fatal: ")
    return fallback


def _run_git(args: list[str], *, cwd: Path | None) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(cwd) if cwd is not None else None,
        )
    except OSError as exc:
        raise cli.CliError(f"git invocation failed: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = cast("str | None", exc.stderr) or ""
        message = _first_stderr_line(stderr, fallback=str(exc))
        raise cli.CliError(f"git {' '.join(args)} failed: {message}") from exc
    return result.stdout


def _git_diff(base: str, head: str, *, cwd: Path | None) -> str:
    return _run_git(["diff", "--unified=0", "--end-of-options", base, head], cwd=cwd)


def _git_log_count(path: str, ref: str, *, cwd: Path | None) -> int:
    output = _run_git(
        ["log", "--oneline", "-n", "200", "--end-of-options", ref, "--", path], cwd=cwd
    )
    return len([line for line in output.splitlines() if line.strip()])


def _git_file_authors(path: str, ref: str, *, cwd: Path | None) -> set[str]:
    output = _run_git(
        ["log", "--format=%ae", "-n", "200", "--end-of-options", ref, "--", path],
        cwd=cwd,
    )
    return {line.strip() for line in output.splitlines() if line.strip()}


def _git_current_email(*, cwd: Path | None) -> str:
    try:
        return _run_git(["config", "user.email"], cwd=cwd).strip()
    except cli.CliError:
        return ""


def _resolve_repo_root(cwd: Path | None) -> Path:
    """Resolve the repo root so pathspecs stay root-relative.

    Runs even when `cwd` is `None`, so the process's own working directory
    resolves to its repo root instead of leaving later git calls to run
    against whatever directory the process happens to start in.
    """
    return Path(_run_git(["rev-parse", "--show-toplevel"], cwd=cwd).strip())


_ESCAPE_RE = re.compile(r"\\(?:([0-7]{3})|(.))")
_SINGLE_CHAR_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "t": "\t",
    "n": "\n",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "r": "\r",
}


def _unquote_git_path(token: str) -> str:
    """Decode a git-quoted path token (core.quotepath default) to plain text."""
    if len(token) < 2 or not (token.startswith('"') and token.endswith('"')):
        return token
    inner = token[1:-1]

    def _decode(match: re.Match[str]) -> str:
        octal, char = match.group(1), match.group(2)
        if octal is not None:
            return chr(int(octal, 8))
        return _SINGLE_CHAR_ESCAPES.get(char, char)

    raw = _ESCAPE_RE.sub(_decode, inner)
    return raw.encode("latin-1", errors="surrogateescape").decode(
        "utf-8", errors="surrogateescape"
    )


def _strip_prefix(token: str) -> str:
    token = _unquote_git_path(token)
    return token[2:] if token.startswith(("a/", "b/")) else token


def _parse_hunks(diff_text: str) -> list[RawHunk]:
    """Parse `git diff --unified=0` output into per-hunk path/start/end/lines.

    `start`/`end` come from the `+` side of the hunk header; pure deletions
    (new-side count 0) fall back to the old-side line number for both.
    """
    hunks: list[RawHunk] = []
    current: RawHunk | None = None
    current_path: str | None = None
    old_token: str | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            hunks.append(current)
            current = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            current_path = None
            old_token = None
        elif current is None and line.startswith("--- "):
            old_token = line[4:].strip()
        elif current is None and line.startswith("+++ "):
            flush()
            new_token = line[4:].strip()
            if new_token != "/dev/null":
                current_path = _strip_prefix(new_token)
            elif old_token and old_token != "/dev/null":
                current_path = _strip_prefix(old_token)
            else:
                current_path = None
        elif line.startswith("@@ "):
            flush()
            match = _HUNK_HEADER_RE.match(line)
            if match is None or current_path is None:
                continue
            old_start = int(match.group(1))
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            if new_count > 0:
                start, end = new_start, new_start + new_count - 1
            else:
                start = end = old_start
            current = {
                "path": current_path,
                "start": start,
                "end": end,
                "added": [],
                "deleted": [],
            }
        elif current is not None and line.startswith("+"):
            current["added"].append(line[1:])
        elif current is not None and line.startswith("-"):
            current["deleted"].append(line[1:])
    flush()
    return hunks


def _diffusion(raw_hunks: list[RawHunk]) -> int:
    paths = {h["path"] for h in raw_hunks}
    dirs = {p.split("/", 1)[0] for p in paths if "/" in p}
    return len(paths) + len(dirs)


def _score_hunk(
    raw: RawHunk,
    *,
    diffusion: int,
    num_paths: int,
    prior_count: int,
    is_new_author: bool,
    deleted_tests: bool,
) -> tuple[float, list[str]]:
    text = "\n".join(raw["added"] + raw["deleted"])
    reasons: list[str] = []
    churn = len(raw["added"]) + len(raw["deleted"])
    score = min(churn, _CHURN_CAP) * _CHURN_WEIGHT
    reasons.append(f"churn:{churn}")
    if num_paths > 1:
        score += diffusion * _DIFFUSION_WEIGHT
        reasons.append("diffusion")
    if prior_count > 0:
        score += min(prior_count, _PRIOR_CHANGES_CAP) * _PRIOR_CHANGES_WEIGHT
        reasons.append("prior-changes")
    if is_new_author:
        score += _AUTHOR_NEW_WEIGHT
        reasons.append("author-new-to-file")
    if _ERROR_PATH_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("error-path")
    if _AUTH_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("auth")
    if _CONCURRENCY_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("concurrency")
    if _CONFIG_PATH_RE.search(raw["path"]):
        score += _PATTERN_WEIGHT
        reasons.append("config-or-secret-file")
    if deleted_tests:
        score += _DELETED_TESTS_WEIGHT
        reasons.append("deleted-tests")
    return score, reasons


def rank_hunks(base: str, head: str, *, cwd: Path | None = None) -> list[Hunk]:
    """Score every hunk of `git diff <base>..<head>`, sorted by score descending."""
    repo_root = _resolve_repo_root(cwd)
    raw_hunks = _parse_hunks(_git_diff(base, head, cwd=repo_root))
    if not raw_hunks:
        return []
    diffusion = _diffusion(raw_hunks)
    num_paths = len({h["path"] for h in raw_hunks})
    current_email = _git_current_email(cwd=repo_root)
    prior_counts: dict[str, int] = {}
    authors: dict[str, set[str]] = {}
    results: list[Hunk] = []
    for raw in raw_hunks:
        path = raw["path"]
        if path not in prior_counts:
            prior_counts[path] = _git_log_count(path, base, cwd=repo_root)
        if path not in authors:
            authors[path] = _git_file_authors(path, base, cwd=repo_root)
        is_new_author = bool(current_email) and current_email not in authors[path]
        deleted_tests = bool(raw["deleted"]) and bool(_TEST_PATH_RE.search(path))
        score, reasons = _score_hunk(
            raw,
            diffusion=diffusion,
            num_paths=num_paths,
            prior_count=prior_counts[path],
            is_new_author=is_new_author,
            deleted_tests=deleted_tests,
        )
        results.append(
            {
                "id": f"{path}:{raw['start']}-{raw['end']}",
                "path": path,
                "start": raw["start"],
                "end": raw["end"],
                "score": score,
                "reasons": reasons,
            }
        )
    results.sort(key=lambda h: (-h["score"], h["path"], h["start"]))
    return results


def _git_ref(value: str) -> str:
    if value.startswith("-"):
        raise argparse.ArgumentTypeError("ref must not start with '-'")
    return value


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--top must be an integer >= 1") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("--top must be an integer >= 1")
    return parsed


def _cmd_rank(args: argparse.Namespace) -> int:
    base = cast(str, args.base)
    head = cast(str, args.head)
    top = cast(int, args.top)
    cwd_arg = cast("str | None", args.cwd)
    cwd = Path(cwd_arg) if cwd_arg else None
    if cwd is not None and not cwd.is_dir():
        raise cli.CliError(f"--cwd {cwd} is not a directory")
    stdout = cast(TextIO, args.stdout)
    hunks = rank_hunks(base, head, cwd=cwd)
    print(json.dumps(hunks[:top], indent=None, sort_keys=True), file=stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Rank git diff hunks between two refs by risk score."
    _ = parser.add_argument("--base", required=True, type=_git_ref, help="base git ref")
    _ = parser.add_argument("--head", required=True, type=_git_ref, help="head git ref")
    _ = parser.add_argument(
        "--top", type=_positive_int, default=3, help="max hunks to emit (default: 3)"
    )
    _ = parser.add_argument(
        "--cwd", default=None, help="git working directory (default: cwd). Test hook."
    )
    parser.set_defaults(func=_cmd_rank)


def main(argv: list[str] | None = None) -> int:
    def setup(parser: argparse.ArgumentParser) -> None:
        parser.prog = "rank-hunks"  # noqa: V101
        _setup(parser)

    return cli.run(setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
