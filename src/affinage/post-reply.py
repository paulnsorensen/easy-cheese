#!/usr/bin/env python3
"""Post a reply to a GitHub PR thread or PR conversation with the mandatory
"agent on behalf of <handle>;" attribution suffix appended.

Used by /affinage. Single source of truth for the attribution suffix — never
duplicate the literal phrase into callers.

Usage:
    post-reply --thread --pr <pr> --comment-id <id> --body <body>
    post-reply --issue  --pr <pr>                    --body <body>

Mode selection:
    --thread  Reply to a specific inline review-thread comment.
    --issue   Post a top-level PR conversation comment (used for review-body
              summary replies that have no anchored comment).

Resolves <handle> for both idempotence detection and the footer in this order:
    1. RESPOND_GH_HANDLE env var.
    2. gh api user --jq .login (the authenticated gh user).
    3. git config user.name (final fallback).

Exits non-zero on any failure (missing args, gh failure, no handle).
"""

from __future__ import annotations

import os
import subprocess
import sys

# IMPORTANT: This is the attribution suffix's verbatim fixed text. Do not
# paraphrase, do not change capitalization, do not change punctuation. The
# handle is inserted before the final semicolon — see skills/affinage/SKILL.md,
# section "Rules".
ATTRIBUTION_PREFIX = "agent on behalf of"

# Horizontal-rule line that separates the reply from the attribution.
ATTRIBUTION_SEPARATOR = "---"

_USAGE = (
    "Usage:\n"
    "  post-reply --thread --pr <pr> --comment-id <id> --body <body>\n"
    "  post-reply --issue  --pr <pr>                    --body <body>\n"
)


def _die(message: str) -> SystemExit:
    """Build a fatal error exiting 1 (operational failure). Caller `raise`s it."""
    sys.stderr.write(f"post-reply: {message}\n")
    return SystemExit(1)


def _usage_error() -> SystemExit:
    """Build a usage error exiting 2. Caller `raise`s it."""
    sys.stderr.write(_USAGE)
    return SystemExit(2)


def _capture(args: list[str]) -> str:
    """Run a command and return stripped stdout, or "" on any failure
    (non-zero exit, missing binary). Mirrors the bash `cmd 2>/dev/null` idiom."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def resolve_handle() -> str:
    """Resolve the GitHub handle: env var -> gh user -> git config -> fail."""
    env = os.environ.get("RESPOND_GH_HANDLE")
    if env:
        return env
    login = _capture(["gh", "api", "user", "--jq", ".login"])
    if login:
        return login
    name = _capture(["git", "config", "user.name"])
    if name:
        return name
    raise _die(
        "could not resolve a GitHub handle (set RESPOND_GH_HANDLE, sign in "
        "with gh, or set git config user.name)"
    )


def resolve_repo() -> str:
    """Resolve <owner>/<repo> from the current git remote via gh."""
    repo = _capture(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not repo:
        raise _die("could not resolve <owner>/<repo> from the current git remote")
    return repo


def compose_body(body: str, handle: str) -> str:
    """Compose the final reply body: original body + blank line + separator +
    attribution line. Idempotent — if the body already ends with the exact
    suffix block (separator + attribution line for this handle, optionally
    followed by a trailing newline), return it unchanged. An exact-suffix match
    (not a substring match) ensures a body that merely quotes the attribution
    elsewhere still gets a real attribution appended."""
    attribution_line = f"{ATTRIBUTION_PREFIX} {handle};"
    suffix = f"\n\n{ATTRIBUTION_SEPARATOR}\n{attribution_line}"
    # Strip a single trailing newline (the form compose_body itself emits)
    # before comparing, so the check accepts both "...handle" and "...handle\n".
    body_trimmed = body[:-1] if body.endswith("\n") else body
    if body_trimmed.endswith(suffix):
        return body
    return f"{body}\n\n{ATTRIBUTION_SEPARATOR}\n{attribution_line}\n"


def _post(api_path: str, full_body: str) -> None:
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "POST", api_path, "-f", f"body={full_body}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise _die("gh CLI not found in PATH")
    if result.returncode != 0:
        raise _die(f"gh api POST {api_path} failed (exit {result.returncode}): {result.stderr.strip()}")
    sys.stdout.write(result.stdout)


def post_thread_reply(pr: str, comment_id: str, full_body: str) -> None:
    repo = resolve_repo()
    _post(f"repos/{repo}/pulls/{pr}/comments/{comment_id}/replies", full_body)


def post_issue_comment(pr: str, full_body: str) -> None:
    repo = resolve_repo()
    _post(f"repos/{repo}/issues/{pr}/comments", full_body)


def _scan_flags(argv: list[str]) -> tuple[str, str, str, str]:
    """Scan argv into (mode, pr, comment_id, body) without post-parse validation.
    Raises SystemExit on mode conflicts or unknown flags."""
    mode = ""
    pr = ""
    comment_id = ""
    body = ""

    def set_mode(new_mode: str) -> None:
        nonlocal mode
        if mode and mode != new_mode:
            raise _die(f"cannot combine --thread and --issue (mode already set to '{mode}')")
        if mode and mode == new_mode:
            raise _die(f"--{new_mode} passed more than once")
        mode = new_mode

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--thread":
            set_mode("thread")
            i += 1
        elif arg == "--issue":
            set_mode("issue")
            i += 1
        elif arg == "--pr":
            pr = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        elif arg == "--comment-id":
            comment_id = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        elif arg == "--body":
            body = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        elif arg in ("-h", "--help"):
            raise _usage_error()
        else:
            raise _die(f"unknown argument: {arg}")

    return mode, pr, comment_id, body


def _validate(mode: str, pr: str, comment_id: str, body: str) -> None:
    """Enforce the cross-flag rules. Raises SystemExit with the bash-compatible
    exit codes (2 for usage, 1 for operational) on any violation."""
    if not mode:
        raise _usage_error()
    if not pr:
        raise _die("missing --pr")
    if not body:
        raise _die("missing --body")
    if mode == "thread" and not comment_id:
        raise _die("missing --comment-id (required for --thread)")
    if mode == "issue" and comment_id:
        raise _die("--comment-id is not valid for --issue mode")


def _parse_args(argv: list[str]) -> tuple[str, str, str, str]:
    """Parse argv into (mode, pr, comment_id, body) via scan + validate. Raises
    SystemExit with the bash-compatible exit codes on any validation failure."""
    mode, pr, comment_id, body = _scan_flags(argv)
    _validate(mode, pr, comment_id, body)
    return mode, pr, comment_id, body


def main(argv: list[str] | None = None) -> int:
    mode, pr, comment_id, body = _parse_args(list(sys.argv[1:] if argv is None else argv))
    handle = resolve_handle()
    full_body = compose_body(body, handle)
    if mode == "thread":
        post_thread_reply(pr, comment_id, full_body)
    else:
        post_issue_comment(pr, full_body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
