#!/usr/bin/env python3
"""Post a reply to a GitHub PR thread or PR conversation with the mandatory
"agent on behalf of <handle>" attribution suffix appended.

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

Operational errors (gh failure, unresolved handle) exit 1; usage errors (bad
flags, missing required fields) exit 2.
"""

from __future__ import annotations

import os
import subprocess
import sys

import fromargs

# IMPORTANT: This is the attribution suffix's verbatim fixed text. Do not
# paraphrase, do not change capitalization, do not change punctuation. The
# handle is appended to the prefix with no terminal punctuation — see
# skills/affinage/SKILL.md,
# section "Rules".
ATTRIBUTION_PREFIX = "agent on behalf of"

# Horizontal-rule line that separates the reply from the attribution.
ATTRIBUTION_SEPARATOR = "---"


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
    raise fromargs.CliError(
        "could not resolve a GitHub handle (set RESPOND_GH_HANDLE, sign in "
        + "with gh, or set git config user.name)",
        exit_code=1,
    )


def resolve_repo() -> str:
    """Resolve <owner>/<repo> from the current git remote via gh."""
    repo = _capture(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not repo:
        raise fromargs.CliError("could not resolve <owner>/<repo> from the current git remote", exit_code=1)
    return repo


def compose_body(body: str, handle: str) -> str:
    """Compose the final reply body: original body + blank line + separator +
    attribution line. Idempotent — if the body already ends with the exact
    suffix block (separator + attribution line for this handle, optionally
    followed by a trailing newline), return it unchanged. An exact-suffix match
    (not a substring match) ensures a body that merely quotes the attribution
    elsewhere still gets a real attribution appended."""
    attribution_line = f"{ATTRIBUTION_PREFIX} {handle}"
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
    except FileNotFoundError as exc:
        raise fromargs.CliError("gh CLI not found in PATH", exit_code=1) from exc
    if result.returncode != 0:
        raise fromargs.CliError(
            f"gh api POST {api_path} failed (exit {result.returncode}): {result.stderr.strip()}",
            exit_code=1,
        )
    _ = sys.stdout.write(result.stdout)


def post_thread_reply(pr: str, comment_id: str, full_body: str) -> None:
    repo = resolve_repo()
    _post(f"repos/{repo}/pulls/{pr}/comments/{comment_id}/replies", full_body)


def post_issue_comment(pr: str, full_body: str) -> None:
    repo = resolve_repo()
    _post(f"repos/{repo}/issues/{pr}/comments", full_body)


def post_reply(
    *,
    thread: bool = False,
    issue: bool = False,
    pr: str = "",
    comment_id: str = "",
    body: str = "",
) -> None:
    """Post a reply to a GitHub PR thread or PR conversation with the mandatory attribution suffix.

    Parameters
    ----------
    thread
        Reply to a specific inline review-thread comment.
    issue
        Post a top-level PR conversation comment (used for review-body summary
        replies that have no anchored comment).
    pr
        PR number.
    comment_id
        Review-thread comment id (required for --thread).
    body
        Reply body text.
    """
    if thread and issue:
        raise fromargs.CliError("cannot combine --thread and --issue")
    if not thread and not issue:
        raise fromargs.CliError("post-reply requires --thread or --issue")
    if not pr:
        raise fromargs.CliError("missing --pr")
    if not body:
        raise fromargs.CliError("missing --body")
    if thread and not comment_id:
        raise fromargs.CliError("missing --comment-id (required for --thread)")
    if issue and comment_id:
        raise fromargs.CliError("--comment-id is not valid for --issue mode")
    handle = resolve_handle()
    full_body = compose_body(body, handle)
    if thread:
        post_thread_reply(pr, comment_id, full_body)
    else:
        post_issue_comment(pr, full_body)


def build_app() -> fromargs.App:
    return fromargs.App(
        "post-reply",
        help="Post a reply to a GitHub PR thread or PR conversation with the mandatory attribution suffix.",
        help_formatter="plain",
        default_command=post_reply,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
