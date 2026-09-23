#!/usr/bin/env python3
"""Decide whether a /hard-cheese attempt for <slug> is fresh, stale, or new.

Replaces the LLM-judged "did this already pass?" confirmation-bias step at the
top of the /hard-cheese gate. Reads the attempt log at
`.cheese/hard-cheese/<slug>.md` (which the gate writes after each attempt),
compares the last recorded passing-attempt HEAD against the current
`git rev-parse HEAD`, and exits with a state + exit code the calling skill
can branch on without re-reading the log itself.

States and exit codes:

    previously_passed  exit 0   — last pass matches current HEAD; gate may skip.
    stale              exit 2   — last pass exists but HEAD has moved; re-run gate.
    new                exit 3   — no prior attempt (or log is unreadable / malformed).

Usage:

    python3 skills/hard-cheese/scripts/hard-cheese.pyz freshness-check --slug <slug> [--json]

Output is the state string by default, or `{"state": ..., "diff_head": ...}`
when `--json` is passed. Stdlib-only.
"""
from __future__ import annotations

import re
import sys
import subprocess

from cyclopts import App, Parameter
from pathlib import Path
from typing import Annotated, TypedDict, cast

from easy_cheese.shared import cli

EXIT_FOR_STATE = {"previously_passed": 0, "stale": 2, "new": 3}
MIN_PASSING_SCORE = 1
MAX_PASSING_SCORE = 5


class PassAttempt(TypedDict):
    sha: str
    score: int | None


class FreshnessResult(TypedDict):
    state: str
    diff_head: str


# Match a markdown table row like `| timestamp | head_sha | status | ... |`.
_TABLE_ROW_RE = re.compile(r"^\s*\|(?P<cells>[^\n]+)\|\s*$", re.MULTILINE)


def git_head(cwd: Path | None = None) -> str:
    """Return `git rev-parse HEAD`, full SHA. Raises CliError on git failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(cwd) if cwd is not None else None,
        )
    except FileNotFoundError as exc:
        raise cli.CliError("git not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (cast("str | None", exc.stderr) or "").strip()
        raise cli.CliError(f"git rev-parse HEAD failed: {stderr or exc}") from exc
    sha = result.stdout.strip()
    if not sha:
        raise cli.CliError("git rev-parse HEAD returned empty output")
    return sha


def _is_pass_status(token: str) -> bool:
    """Match a status cell that starts with 'pass' (covers PASS, passed, Pass)."""
    return token.strip().lower().startswith("pass")


def _parse_score(token: str) -> int | None:
    try:
        return int(token.strip())
    except ValueError:
        return None


def _last_pass_attempt_from_table(body: str) -> PassAttempt | None:
    """Walk attempt-log table rows; return the last PASS row's sha and score.

    The writer in `append-attempt.py` produces the canonical schema
    `| timestamp | head_sha | status | score | feedback | explanation |`,
    so the row's status cell is index 2, the head_sha cell is index 1, and
    the score cell is index 3. The parser reads the header row to locate
    the `status`, `head_sha`, and `score`
    columns by name, so callers who later reorder the schema do not silently
    break the freshness check.
    """
    rows = list(_TABLE_ROW_RE.finditer(body))
    status_col: int | None = None
    sha_col: int | None = None
    score_col: int | None = None
    last_attempt: PassAttempt | None = None
    for row in rows:
        cells = [c.strip() for c in row.group("cells").split("|")]
        # Strip the empty edge cells produced by leading/trailing pipes.
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) < 2:
            continue
        # Header row: locate the columns we care about by name.
        if status_col is None and "status" in (c.lower() for c in cells):
            lowered = [c.lower() for c in cells]
            status_col = lowered.index("status")
            sha_col = lowered.index("head_sha") if "head_sha" in lowered else None
            score_col = lowered.index("score") if "score" in lowered else None
            continue
        # Separator row (`| --- | --- | --- |`).
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue
        # Data row — fall back to the legacy column order (head_sha at index 2)
        # when no header was seen, otherwise honour the discovered indices.
        s_col = status_col if status_col is not None else 0
        h_col = sha_col if sha_col is not None else 2
        sc_col = score_col if score_col is not None else 1
        if s_col >= len(cells) or h_col >= len(cells):
            continue
        if not _is_pass_status(cells[s_col]):
            continue
        sha = cells[h_col]
        if sha and sha.lower() != "head_sha":
            score = _parse_score(cells[sc_col]) if sc_col < len(cells) else None
            last_attempt = {"sha": sha, "score": score}
    return last_attempt


def last_pass_attempt(log_path: Path) -> PassAttempt | None:
    """Return the most recent passing attempt, or None when no parseable pass exists."""
    try:
        body = log_path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError, OSError):
        return None
    return _last_pass_attempt_from_table(body)


def decide(
    slug: str,
    *,
    cheese_root: Path,
    repo_root: Path | None = None,
    passing_score: int = 3,
) -> FreshnessResult:
    """Compute {state, diff_head} for `slug`. Pure modulo git + filesystem.

    `append-attempt.py` writes the short (abbreviated) HEAD sha; `git rev-parse
    HEAD` returns the full sha. Treat the recorded sha as a match when it's a
    prefix of `diff_head` (or vice versa) so the writer/reader pair round-trips.
    """
    diff_head = git_head(cwd=repo_root)
    log_path = cheese_root / "hard-cheese" / f"{slug}.md"
    attempt = last_pass_attempt(log_path)
    if attempt is None:
        state = "new"
    elif attempt["score"] is None or attempt["score"] < passing_score:
        state = "stale"
    elif _sha_matches(attempt["sha"], diff_head):
        state = "previously_passed"
    else:
        state = "stale"
    return {"state": state, "diff_head": diff_head}


def _sha_matches(recorded: str, diff_head: str) -> bool:
    """True when `recorded` is the same sha as `diff_head`, allowing either to
    be the abbreviated form (`git rev-parse --short`). Empty / 'unknown' never
    matches — the writer falls back to 'unknown' when git fails, and that
    sentinel must not silently mark every diff `previously_passed`."""
    if not recorded or not diff_head:
        return False
    if recorded.lower() == "unknown":
        return False
    return diff_head.startswith(recorded) or recorded.startswith(diff_head)


def _command(slug: str, passing_score: int = 3, cheese_root: str | None = None, repo_root: str | None = None, json_mode: Annotated[bool, Parameter(name="--json")] = False) -> int:
    slug = slug.strip()
    if not MIN_PASSING_SCORE <= passing_score <= MAX_PASSING_SCORE:
        raise cli.CliError("--passing-score must be between 1 and 5")
    if not slug:
        raise cli.CliError("--slug must not be empty")
    stdout = sys.stdout

    cheese_root_path = Path(cheese_root) if cheese_root else Path(".cheese")
    repo_root_path = Path(repo_root) if repo_root else None
    result = decide(
        slug,
        cheese_root=cheese_root_path,
        repo_root=repo_root_path,
        passing_score=passing_score,
    )
    if json_mode:
        cli.emit(result, json_mode=True, stdout=stdout)
    else:
        cli.emit(result["state"], stdout=stdout)
    return EXIT_FOR_STATE[result["state"]]


app = App(name="freshness-check")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
