#!/usr/bin/env bash
# shared/post-reply.sh — post a reply to a GitHub PR thread or PR conversation
# with the mandatory "agent on behalf of;" attribution suffix appended.
#
# Used by /affinage (this repo) and modelled after the contract in the global
# /respond skill's scripts/post-reply.sh. Single source of truth for the
# attribution suffix — never duplicate the literal phrase into callers.
#
# Usage:
#   post-reply.sh --thread --pr <pr> --comment-id <id> --body <body>
#   post-reply.sh --issue  --pr <pr>                   --body <body>
#
# Mode selection:
#   --thread  Reply to a specific inline review-thread comment.
#   --issue   Post a top-level PR conversation comment (used for review-body
#             summary replies that have no anchored comment).
#
# Resolves <handle> in this order:
#   1. RESPOND_GH_HANDLE env var.
#   2. gh api user --jq .login (the authenticated gh user).
#   3. git config user.name (final fallback).
#
# Exits non-zero on any failure (missing args, gh failure, no handle).

set -euo pipefail

# --- Constants ------------------------------------------------------------

# IMPORTANT: This is the attribution suffix's verbatim prefix. Do not
# paraphrase, do not change capitalization, do not change punctuation. The
# single space between the semicolon and the handle is part of the spec —
# see skills/affinage/SKILL.md, section "Rules".
readonly ATTRIBUTION_PREFIX="agent on behalf of;"

# Horizontal-rule line that separates the reply from the attribution.
readonly ATTRIBUTION_SEPARATOR="---"

# --- Helpers --------------------------------------------------------------

die() {
  printf 'post-reply.sh: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF' >&2
Usage:
  post-reply.sh --thread --pr <pr> --comment-id <id> --body <body>
  post-reply.sh --issue  --pr <pr>                   --body <body>
EOF
  exit 2
}

resolve_handle() {
  if [ -n "${RESPOND_GH_HANDLE:-}" ]; then
    printf '%s' "$RESPOND_GH_HANDLE"
    return 0
  fi
  local login
  if login=$(gh api user --jq .login 2>/dev/null) && [ -n "$login" ]; then
    printf '%s' "$login"
    return 0
  fi
  local name
  if name=$(git config user.name 2>/dev/null) && [ -n "$name" ]; then
    printf '%s' "$name"
    return 0
  fi
  die "could not resolve a GitHub handle (set RESPOND_GH_HANDLE, sign in with gh, or set git config user.name)"
}

# Compose the final reply body: original body + blank line + separator +
# attribution line. Idempotent — if the body already ends with the exact
# suffix block (separator + attribution line for this handle, optionally
# followed by a trailing newline), return it unchanged. A substring match
# would skip the append when the body merely quotes the attribution
# elsewhere (e.g. citing the spec), which would post unattributed replies.
compose_body() {
  local body="$1"
  local handle="$2"
  local attribution_line="${ATTRIBUTION_PREFIX} ${handle}"
  local suffix
  printf -v suffix '\n\n%s\n%s' "$ATTRIBUTION_SEPARATOR" "$attribution_line"
  # Strip a single trailing newline (the form compose_body itself emits)
  # before comparing, so the check accepts both "...handle" and "...handle\n".
  local body_trimmed="${body%$'\n'}"
  if [ "${body_trimmed: -${#suffix}}" = "$suffix" ]; then
    printf '%s' "$body"
    return 0
  fi
  printf '%s\n\n%s\n%s\n' "$body" "$ATTRIBUTION_SEPARATOR" "$attribution_line"
}

resolve_repo() {
  gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null \
    || die "could not resolve <owner>/<repo> from the current git remote"
}

post_thread_reply() {
  local pr="$1" comment_id="$2" full_body="$3"
  local repo
  repo=$(resolve_repo)
  gh api \
    --method POST \
    "repos/${repo}/pulls/${pr}/comments/${comment_id}/replies" \
    -f body="$full_body"
}

post_issue_comment() {
  local pr="$1" full_body="$2"
  local repo
  repo=$(resolve_repo)
  gh api \
    --method POST \
    "repos/${repo}/issues/${pr}/comments" \
    -f body="$full_body"
}

# --- Argument parsing -----------------------------------------------------

mode=""
pr=""
comment_id=""
body=""

set_mode() {
  local new_mode="$1"
  if [ -n "$mode" ] && [ "$mode" != "$new_mode" ]; then
    die "cannot combine --thread and --issue (mode already set to '$mode')"
  fi
  if [ -n "$mode" ] && [ "$mode" = "$new_mode" ]; then
    die "--${new_mode} passed more than once"
  fi
  mode="$new_mode"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --thread)     set_mode "thread"; shift ;;
    --issue)      set_mode "issue"; shift ;;
    --pr)         pr="${2:-}"; shift 2 ;;
    --comment-id) comment_id="${2:-}"; shift 2 ;;
    --body)       body="${2:-}"; shift 2 ;;
    -h|--help)    usage ;;
    *)            die "unknown argument: $1" ;;
  esac
done

[ -n "$mode" ] || usage
[ -n "$pr" ]   || die "missing --pr"
[ -n "$body" ] || die "missing --body"
case "$mode" in
  thread) [ -n "$comment_id" ] || die "missing --comment-id (required for --thread)" ;;
  issue)  [ -z "$comment_id" ] || die "--comment-id is not valid for --issue mode" ;;
esac

# --- Compose + post -------------------------------------------------------

handle=$(resolve_handle)
full_body=$(compose_body "$body" "$handle")

case "$mode" in
  thread) post_thread_reply "$pr" "$comment_id" "$full_body" ;;
  issue)  post_issue_comment "$pr" "$full_body" ;;
esac
