#!/usr/bin/env python3
"""Score `git diff <base>...<head>` hunks by risk and emit the top N as JSON.

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

from cyclopts import App
import json
import os
import re
import subprocess
from pathlib import Path
from typing import TypedDict, cast

from easy_cheese.shared import cli

_CHURN_WEIGHT = 1.0
_CHURN_CAP = 10
_DIFFUSION_WEIGHT = 2.0
_PRIOR_CHANGES_WEIGHT = 0.25
_PRIOR_CHANGES_CAP = 50
_AUTHOR_NEW_WEIGHT = 1.0
_PATTERN_WEIGHT = 10.0
_DELETED_TESTS_WEIGHT = 8.0
_GIT_TIMEOUT_SECONDS = 30

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
    history_path: str
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
    env = os.environ.copy()
    _ = env.pop("GIT_EXTERNAL_DIFF", None)
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=off", "--literal-pathspecs", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        raise cli.CliError(f"git invocation failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise cli.CliError(
            f"git {' '.join(args)} timed out after {_GIT_TIMEOUT_SECONDS} seconds"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = cast("str | None", exc.stderr) or ""
        message = _first_stderr_line(stderr, fallback=str(exc))
        raise cli.CliError(f"git {' '.join(args)} failed: {message}") from exc
    return result.stdout


def _git_diff(base: str, head: str, *, cwd: Path | None) -> str:
    return _run_git(
        [
            "diff",
            "--unified=0",
            "--find-renames=20%",
            "--no-ext-diff",
            "--no-textconv",
            "--end-of-options",
            f"{base}...{head}",
        ],
        cwd=cwd,
    )


def _git_head_author(ref: str, *, cwd: Path | None) -> str:
    return _run_git(
        ["show", "-s", "--format=%ae", "--end-of-options", ref], cwd=cwd
    ).strip()


def _git_file_history(
    paths: list[str], ref: str, *, cwd: Path | None
) -> dict[str, list[str]]:
    history: dict[str, list[str]] = {path: [] for path in paths}
    output = _run_git(
        [
            "log",
            "--format=%x00%ae%x00",
            "--name-only",
            "--no-renames",
            "--end-of-options",
            ref,
            "--",
            *paths,
        ],
        cwd=cwd,
    )
    fields = output.split("\x00")
    for email, names in zip(fields[1::2], fields[2::2], strict=True):
        for token in names.splitlines():
            if not token:
                continue
            path = _unquote_git_path(token)
            if path in history:
                history[path].append(email.strip())
    return history


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
    history_path: str | None = None
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
            history_path = None
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
            if old_token and old_token != "/dev/null":
                history_path = _strip_prefix(old_token)
            else:
                history_path = current_path
        elif line.startswith("@@ "):
            flush()
            match = _HUNK_HEADER_RE.match(line)
            if match is None or current_path is None or history_path is None:
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
                "history_path": history_path,
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
    behavior_path = not _TEST_PATH_RE.search(raw["path"]) and not raw["path"].startswith(
        ".hallouminate/wiki/"
    )
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
    if behavior_path and _ERROR_PATH_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("error-path")
    if behavior_path and _AUTH_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("auth")
    if behavior_path and _CONCURRENCY_RE.search(text):
        score += _PATTERN_WEIGHT
        reasons.append("concurrency")
    if behavior_path and _CONFIG_PATH_RE.search(raw["path"]):
        score += _PATTERN_WEIGHT
        reasons.append("config-or-secret-file")
    if deleted_tests:
        score += _DELETED_TESTS_WEIGHT
        reasons.append("deleted-tests")
    return score, reasons


def rank_hunks(base: str, head: str, *, cwd: Path | None = None) -> list[Hunk]:
    """Score every hunk of `git diff <base>...<head>`, sorted by score descending."""
    repo_root = _resolve_repo_root(cwd)
    raw_hunks = _parse_hunks(_git_diff(base, head, cwd=repo_root))
    if not raw_hunks:
        return []
    diffusion = _diffusion(raw_hunks)
    paths = sorted({h["path"] for h in raw_hunks})
    history_paths = sorted({h["history_path"] for h in raw_hunks})
    num_paths = len(paths)
    head_author = _git_head_author(head, cwd=repo_root)
    history = _git_file_history(history_paths, base, cwd=repo_root)
    results: list[Hunk] = []
    for raw in raw_hunks:
        path = raw["path"]
        path_history = history[raw["history_path"]]
        is_new_author = bool(head_author) and head_author not in path_history
        deleted_tests = bool(raw["deleted"]) and bool(_TEST_PATH_RE.search(path))
        score, reasons = _score_hunk(
            raw,
            diffusion=diffusion,
            num_paths=num_paths,
            prior_count=len(path_history),
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
    if value.startswith("-") or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise cli.CliError("ref must not start with '-' or contain control characters")
    return value


def _positive_int(value: int) -> int:
    if value < 1:
        raise cli.CliError("--top must be an integer >= 1")
    return value


def _cmd_rank(base: str, head: str, top: int = 3, cwd: str | None = None) -> int:
    base = _git_ref(base)
    head = _git_ref(head)
    top = _positive_int(top)
    path = Path(cwd) if cwd else None
    if path is not None and not path.is_dir():
        raise cli.CliError(f"--cwd {path} is not a directory")
    hunks = rank_hunks(base, head, cwd=path)
    print(json.dumps(hunks[:top], indent=None, sort_keys=True))
    return 0


app = App(name="rank-hunks")
_ = app.default(_cmd_rank)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
