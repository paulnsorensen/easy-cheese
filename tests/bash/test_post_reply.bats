#!/usr/bin/env bats
#
# Tests for shared/post-reply.sh.
#
# Stubs `gh` in PATH so the script's invocations are logged to a temp file.
# Verifies endpoint routing, attribution, handle resolution, idempotency,
# and argument validation.

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    SCRIPT="$REPO_ROOT/shared/post-reply.sh"
    FAKE_BIN="$BATS_TEST_TMPDIR/bin"
    GH_LOG="$BATS_TEST_TMPDIR/gh.log"
    export GH_LOG
    : > "$GH_LOG"
    ORIG_PATH="$PATH"

    mkdir -p "$FAKE_BIN"

    # Stub gh: log every invocation arg-by-arg, return canned responses for
    # the read-only sub-commands.
    cat > "$FAKE_BIN/gh" <<'EOF'
#!/usr/bin/env bash
{
  printf '=== GH_INVOKE ===\n'
  for arg in "$@"; do
    printf 'ARG: %s\n' "$arg"
  done
  printf '=== END ===\n'
} >> "$GH_LOG"
case "$1 $2" in
  "api user")   printf 'stub-user\n' ;;
  "repo view")  printf 'owner/repo\n' ;;
  *)            : ;;
esac
exit 0
EOF
    chmod +x "$FAKE_BIN/gh"

    export PATH="$FAKE_BIN:$PATH"
    unset RESPOND_GH_HANDLE
}

teardown() {
    export PATH="${ORIG_PATH:-$PATH}"
    unset ORIG_PATH
}

@test "--thread mode hits the pulls comments replies endpoint" {
    run "$SCRIPT" --thread --pr 42 --comment-id 999 --body "Fixed."
    [ "$status" -eq 0 ]
    grep -F "ARG: repos/owner/repo/pulls/42/comments/999/replies" "$GH_LOG"
}

@test "--issue mode hits the issues comments endpoint" {
    run "$SCRIPT" --issue --pr 42 --body "Re: @alice — fixed."
    [ "$status" -eq 0 ]
    grep -F "ARG: repos/owner/repo/issues/42/comments" "$GH_LOG"
}

@test "attribution suffix is appended with the resolved handle" {
    run "$SCRIPT" --issue --pr 42 --body "Hello world."
    [ "$status" -eq 0 ]
    # The body arg passed to gh should contain the attribution line.
    grep -F "agent on behalf of; stub-user" "$GH_LOG"
}

@test "RESPOND_GH_HANDLE overrides handle resolution" {
    export RESPOND_GH_HANDLE="override-handle"
    run "$SCRIPT" --issue --pr 42 --body "Hello."
    [ "$status" -eq 0 ]
    grep -F "agent on behalf of; override-handle" "$GH_LOG"
    # And gh api user was never called (env var short-circuits).
    ! grep -F "ARG: user" "$GH_LOG"
}

@test "idempotent: body already ending with attribution is not double-appended" {
    body=$'Hello.\n\n---\nagent on behalf of; stub-user'
    run "$SCRIPT" --issue --pr 42 --body "$body"
    [ "$status" -eq 0 ]
    # Exactly one attribution line in the gh body arg.
    count=$(grep -cF "agent on behalf of; stub-user" "$GH_LOG")
    [ "$count" -eq 1 ]
}

@test "missing --pr fails with usage error" {
    run "$SCRIPT" --thread --comment-id 999 --body "x"
    [ "$status" -ne 0 ]
    [[ "$output" == *"missing --pr"* ]]
}

@test "--thread without --comment-id fails" {
    run "$SCRIPT" --thread --pr 42 --body "x"
    [ "$status" -ne 0 ]
    [[ "$output" == *"missing --comment-id"* ]]
}

@test "--issue with --comment-id fails" {
    run "$SCRIPT" --issue --pr 42 --comment-id 999 --body "x"
    [ "$status" -ne 0 ]
    [[ "$output" == *"--comment-id is not valid for --issue"* ]]
}

@test "unknown flag fails" {
    run "$SCRIPT" --issue --pr 42 --body "x" --bogus value
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown argument"* ]]
}

@test "--thread and --issue together fails" {
    run "$SCRIPT" --thread --issue --pr 42 --comment-id 1 --body "x"
    [ "$status" -ne 0 ]
    [[ "$output" == *"cannot combine"* ]]
}

@test "handle resolution falls through gh failure to git config" {
    # Override gh to fail on `api user` but still respond to repo view.
    cat > "$FAKE_BIN/gh" <<'EOF'
#!/usr/bin/env bash
{
  printf '=== GH_INVOKE ===\n'
  for arg in "$@"; do
    printf 'ARG: %s\n' "$arg"
  done
  printf '=== END ===\n'
} >> "$GH_LOG"
case "$1 $2" in
  "api user")   exit 1 ;;
  "repo view")  printf 'owner/repo\n' ;;
  *)            : ;;
esac
exit 0
EOF
    chmod +x "$FAKE_BIN/gh"

    # Stub git so `git config user.name` returns a known value.
    cat > "$FAKE_BIN/git" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "config" ] && [ "$2" = "user.name" ]; then
  printf 'fallback-user\n'
  exit 0
fi
exit 1
EOF
    chmod +x "$FAKE_BIN/git"

    run "$SCRIPT" --issue --pr 42 --body "Hello."
    [ "$status" -eq 0 ]
    grep -F "agent on behalf of; fallback-user" "$GH_LOG"
}

@test "handle resolution failure when all sources exhausted exits with clear error" {
    # gh api user fails; git config user.name also fails.
    cat > "$FAKE_BIN/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
  "api user")   exit 1 ;;
  "repo view")  printf 'owner/repo\n' ;;
esac
exit 0
EOF
    chmod +x "$FAKE_BIN/gh"

    cat > "$FAKE_BIN/git" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
    chmod +x "$FAKE_BIN/git"

    run "$SCRIPT" --issue --pr 42 --body "Hello."
    [ "$status" -ne 0 ]
    [[ "$output" == *"could not resolve a GitHub handle"* ]]
}

@test "resolve_repo failure surfaces a clear error" {
    # gh repo view fails; gh api user still works.
    cat > "$FAKE_BIN/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
  "api user")   printf 'stub-user\n' ;;
  "repo view")  exit 1 ;;
esac
exit 0
EOF
    chmod +x "$FAKE_BIN/gh"

    run "$SCRIPT" --issue --pr 42 --body "Hello."
    [ "$status" -ne 0 ]
    [[ "$output" == *"could not resolve <owner>/<repo>"* ]]
}

@test "body with shell metacharacters is preserved verbatim" {
    body='Backticks `code` and $vars and "quotes" and newlines
still survive.'
    run "$SCRIPT" --issue --pr 42 --body "$body"
    [ "$status" -eq 0 ]
    # The literal backtick-code segment must appear in the gh body arg.
    grep -F 'Backticks `code` and $vars' "$GH_LOG"
}
