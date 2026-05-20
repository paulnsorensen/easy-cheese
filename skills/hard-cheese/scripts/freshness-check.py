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

    python3 skills/hard-cheese/scripts/freshness-check.py --slug <slug> [--json]

Output is the state string by default, or `{"state": ..., "diff_head": ...}`
when `--json` is passed. Stdlib-only.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Seed: cli helper at repo-root/shared/scripts/cli.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "scripts"))
import cli  # noqa: E402  (path-insert seed pattern)

STATES = ("previously_passed", "stale", "new")
EXIT_FOR_STATE = {"previously_passed": 0, "stale": 2, "new": 3}

# Match "## Attempt N (PASS — ...)" headings followed (eventually) by a
# `git: <sha>` line. The SKILL.md documents this shape.
_ATTEMPT_HEAD_RE = re.compile(
    r"^##\s+Attempt\s+\d+\s*\(\s*(?P<status>[A-Za-z]+)\b[^)]*\)\s*$",
    re.MULTILINE,
)
_GIT_LINE_RE = re.compile(r"^git:\s*(?P<sha>\S+)\s*$", re.MULTILINE)

# Fallback shape: a markdown table row like `| pass | 4 | <sha> | ... |`.
# The seed names this as the if-undocumented shape; we honour both so the
# script is robust to log-format drift.
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
        stderr = (exc.stderr or "").strip()
        raise cli.CliError(f"git rev-parse HEAD failed: {stderr or exc}") from exc
    sha = result.stdout.strip()
    if not sha:
        raise cli.CliError("git rev-parse HEAD returned empty output")
    return sha


def _is_pass_status(token: str) -> bool:
    """Match a status cell that starts with 'pass' (covers PASS, passed, Pass)."""
    return token.strip().lower().startswith("pass")


def _last_pass_sha_from_headings(body: str) -> str | None:
    """Walk `## Attempt N (STATUS ...)` blocks; return the last PASS block's sha."""
    matches = list(_ATTEMPT_HEAD_RE.finditer(body))
    last_sha: str | None = None
    for i, match in enumerate(matches):
        if not _is_pass_status(match.group("status")):
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        git_match = _GIT_LINE_RE.search(body, start, end)
        if git_match is not None:
            last_sha = git_match.group("sha")
    return last_sha


def _last_pass_sha_from_table(body: str) -> str | None:
    """Walk `| status | score | head_sha | ...` rows; return last PASS row's sha."""
    last_sha: str | None = None
    for row in _TABLE_ROW_RE.finditer(body):
        cells = [c.strip() for c in row.group("cells").split("|")]
        if len(cells) < 3:
            continue
        # Skip the header separator row (`| --- | --- | --- |`).
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue
        if not _is_pass_status(cells[0]):
            continue
        # head_sha is the third cell per the seed's documented column order.
        sha = cells[2]
        if sha and sha != "head_sha":  # ignore header row that happens to start with "pass" — defensive
            last_sha = sha
    return last_sha


def last_pass_sha(log_path: Path) -> str | None:
    """Return the SHA recorded against the most recent passing attempt, or None.

    Tries the SKILL.md heading shape first, then the markdown-table fallback.
    Returns None when the log is missing, unreadable, or has no pass row.
    """
    try:
        body = log_path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError, OSError):
        return None
    sha = _last_pass_sha_from_headings(body)
    if sha is not None:
        return sha
    return _last_pass_sha_from_table(body)


def decide(slug: str, *, cheese_root: Path, repo_root: Path | None = None) -> dict:
    """Compute {state, diff_head} for `slug`. Pure modulo git + filesystem."""
    diff_head = git_head(cwd=repo_root)
    log_path = cheese_root / "hard-cheese" / f"{slug}.md"
    recorded = last_pass_sha(log_path)
    if recorded is None:
        state = "new"
    elif recorded == diff_head:
        state = "previously_passed"
    else:
        state = "stale"
    return {"state": state, "diff_head": diff_head}


def _cmd_check(args: argparse.Namespace) -> None:
    slug = (args.slug or "").strip()
    if not slug:
        raise cli.CliError("--slug must not be empty")
    cheese_root = Path(args.cheese_root) if args.cheese_root else Path(".cheese")
    repo_root = Path(args.repo_root) if args.repo_root else None
    result = decide(slug, cheese_root=cheese_root, repo_root=repo_root)
    if args.json_mode:
        cli.emit(result, json_mode=True)
    else:
        cli.emit(result["state"])
    sys.exit(EXIT_FOR_STATE[result["state"]])


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Decide /hard-cheese freshness for <slug>."
    parser.add_argument("--slug", required=True, help="hard-cheese slug to check")
    parser.add_argument(
        "--cheese-root",
        default=None,
        help="override .cheese directory (default: ./.cheese). Test hook.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="override git cwd for rev-parse (default: cwd). Test hook.",
    )
    parser.set_defaults(func=_cmd_check)


if __name__ == "__main__":
    cli.run(_setup)
