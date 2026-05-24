#!/usr/bin/env bats
#
# Tests for src/cheese-factory/pr_plan_to_branches.py.
#
# Each shape (single, orthogonal_flat, stacked_linear, diamond_stack) gets
# at least one test verifying:
#   - exit 0 on valid input
#   - emitted command shape matches the PR layout
#   - branch / base / commit / PR-create commands all appear
#
# Both YAML and JSON inputs are exercised — the script accepts either via
# manifest_io.read_mapping_arg_or_stdin.

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../.." && pwd)"
    SCRIPT="$REPO_ROOT/src/cheese-factory/pr_plan_to_branches.py"
    # Bundles run self-contained; raw-source tests shim shared/ + sibling scripts.
    export PYTHONPATH="$REPO_ROOT/shared/scripts:$REPO_ROOT/src/cheese-factory${PYTHONPATH:+:$PYTHONPATH}"
    PLAN_FILE="$BATS_TEST_TMPDIR/plan.yaml"
}

# Helper: write a plan with one group. YAML is the canonical format.
write_single_plan() {
    cat > "$PLAN_FILE" <<'YAML'
shape: single
groups:
  - branch: cheese-factory/foo/pr-1
    title: "feat(foo): everything in one"
    body: Ships the whole feature in one PR.
    base: main
    commits:
      - aaa1111
      - bbb2222
YAML
}

write_orthogonal_flat_plan() {
    cat > "$PLAN_FILE" <<'YAML'
shape: orthogonal_flat
groups:
  - branch: cheese-factory/foo/pr-curd-1
    title: "feat(foo): curd one"
    body: ""
    base: main
    commits: [c1c1c1d]
  - branch: cheese-factory/foo/pr-curd-2
    title: "feat(foo): curd two"
    body: ""
    base: main
    commits: [c2c2c2d]
  - branch: cheese-factory/foo/pr-curd-3
    title: "feat(foo): curd three"
    body: ""
    base: main
    commits: [c3c3c3d]
YAML
}

write_stacked_linear_plan() {
    cat > "$PLAN_FILE" <<'YAML'
shape: stacked_linear
groups:
  - branch: cheese-factory/foo/pr-1-seed
    title: "feat(foo): seed"
    body: ""
    base: main
    commits: [5eed011]
  - branch: cheese-factory/foo/pr-2-curd
    title: "feat(foo): curd"
    body: ""
    base: cheese-factory/foo/pr-1-seed
    commits: [a701a11]
  - branch: cheese-factory/foo/pr-3-wire
    title: "feat(foo): wire"
    body: ""
    base: cheese-factory/foo/pr-2-curd
    commits: [aaee011]
YAML
}

write_diamond_stack_plan() {
    cat > "$PLAN_FILE" <<'YAML'
shape: diamond_stack
groups:
  - branch: cheese-factory/foo/pr-seed
    title: "feat(foo): seed"
    body: ""
    base: main
    commits: [5eed022]
  - branch: cheese-factory/foo/pr-curd-1
    title: "feat(foo): curd one"
    body: ""
    base: cheese-factory/foo/pr-seed
    commits: [a1a1a11]
  - branch: cheese-factory/foo/pr-curd-2
    title: "feat(foo): curd two"
    body: ""
    base: cheese-factory/foo/pr-seed
    commits: [a2a2a22]
  - branch: cheese-factory/foo/pr-wire
    title: "feat(foo): wire"
    body: ""
    base: cheese-factory/foo/pr-curd-2
    commits: [aaee022]
YAML
}

# -- preflight ---------------------------------------------------------------

@test "script is executable" {
    [ -x "$SCRIPT" ]
}

@test "script accepts --help with exit 0" {
    run "$SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "script -h prints usage and exits 0" {
    run "$SCRIPT" -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape"* ]]
}

@test "script rejects missing file with exit 1" {
    run "$SCRIPT" /nope/nope/nope.yaml
    [ "$status" -eq 1 ]
    [[ "$output" == *"not found"* ]]
}

# -- single shape ------------------------------------------------------------

@test "single shape emits one branch, two cherry-picks, one PR" {
    write_single_plan
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: single"* ]]
    [[ "$output" == *"set -euo pipefail"* ]]
    # gh pr create is guarded by gh pr view so a partial re-publish doesn't
    # hard-stop the plan on the first already-created PR.
    [[ "$output" == *"gh pr view 'cheese-factory/foo/pr-1' --json number"* ]]
    [[ "$output" == *">/dev/null 2>&1 || gh pr create"* ]]
    [[ "$output" == *"git checkout -b 'cheese-factory/foo/pr-1' 'main'"* ]]
    [[ "$output" == *"git cherry-pick 'aaa1111'"* ]]
    [[ "$output" == *"git cherry-pick 'bbb2222'"* ]]
    [[ "$output" == *"git push -u origin 'cheese-factory/foo/pr-1'"* ]]
    [[ "$output" == *"gh pr create --base 'main' --head 'cheese-factory/foo/pr-1'"* ]]
    # Exactly one PR-create line.
    [ "$(printf '%s\n' "$output" | grep -c '|| gh pr create ')" -eq 1 ]
}

@test "single shape also accepts a JSON plan file" {
    # Backward-compatibility: JSON is a subset of YAML and read_mapping_arg_or_stdin
    # tries JSON first, so a .json file should still work cleanly.
    JSON_PLAN="$BATS_TEST_TMPDIR/plan.json"
    cat > "$JSON_PLAN" <<'JSON'
{
  "shape": "single",
  "groups": [
    {
      "branch": "cheese-factory/foo/pr-1",
      "title": "feat(foo): everything in one",
      "body": "Ships the whole feature in one PR.",
      "base": "main",
      "commits": ["aaa1111", "bbb2222"]
    }
  ]
}
JSON
    run "$SCRIPT" "$JSON_PLAN"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: single"* ]]
    [[ "$output" == *"git cherry-pick 'aaa1111'"* ]]
    [[ "$output" == *"git cherry-pick 'bbb2222'"* ]]
}

# -- orthogonal_flat shape ---------------------------------------------------

@test "orthogonal_flat emits N PRs each with base main" {
    write_orthogonal_flat_plan
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: orthogonal_flat"* ]]
    # Three PR-create lines, all targeting main.
    [ "$(printf '%s\n' "$output" | grep -c '|| gh pr create ')" -eq 3 ]
    [ "$(printf '%s\n' "$output" | grep -c "|| gh pr create --base 'main'")" -eq 3 ]
}

@test "orthogonal_flat emits exactly one cherry-pick per curd" {
    write_orthogonal_flat_plan
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 0 ]
    [ "$(printf '%s\n' "$output" | grep -c '^git cherry-pick ')" -eq 3 ]
}

# -- stacked_linear shape ----------------------------------------------------

@test "stacked_linear emits each PR with previous branch as base" {
    write_stacked_linear_plan
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: stacked_linear"* ]]
    [ "$(printf '%s\n' "$output" | grep -c '|| gh pr create ')" -eq 3 ]
    # Only the first PR targets main; the next two target the previous branch.
    [ "$(printf '%s\n' "$output" | grep -c "|| gh pr create --base 'main'")" -eq 1 ]
    [[ "$output" == *"--base 'cheese-factory/foo/pr-1-seed'"* ]]
    [[ "$output" == *"--base 'cheese-factory/foo/pr-2-curd'"* ]]
}

# -- diamond_stack shape -----------------------------------------------------

@test "diamond_stack emits seed-rooted parallel curd PRs and a wiring tip" {
    write_diamond_stack_plan
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: diamond_stack"* ]]
    [ "$(printf '%s\n' "$output" | grep -c '|| gh pr create ')" -eq 4 ]
    # Two curd PRs share the seed branch as base.
    [ "$(printf '%s\n' "$output" | grep -c "|| gh pr create --base 'cheese-factory/foo/pr-seed'")" -eq 2 ]
}

# -- error handling ----------------------------------------------------------

@test "script rejects unknown shape" {
    cat > "$PLAN_FILE" <<'YAML'
shape: marbled
groups:
  - branch: x
    title: y
    body: ""
    base: main
    commits: [c]
YAML
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 1 ]
    [[ "$output" == *"shape must be one of"* ]]
}

@test "script rejects empty groups" {
    cat > "$PLAN_FILE" <<'YAML'
shape: single
groups: []
YAML
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 1 ]
    [[ "$output" == *"groups must be a non-empty list"* ]]
}

@test "script rejects missing shape field" {
    cat > "$PLAN_FILE" <<'YAML'
groups:
  - branch: x
    title: y
    body: ""
    base: main
    commits: [c]
YAML
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 1 ]
    [[ "$output" == *"shape"* ]]
}

@test "script rejects option-shaped commit token at integration layer" {
    # `--abort` would reach `git cherry-pick` as a flag even after single
    # quoting, since shell quoting does not stop git from interpreting
    # option-shaped tokens. The validator must reject this before commands
    # are emitted.
    cat > "$PLAN_FILE" <<'YAML'
shape: single
groups:
  - branch: cheese-factory/foo/pr-1
    title: t
    body: ""
    base: main
    commits: [--abort]
YAML
    run "$SCRIPT" "$PLAN_FILE"
    [ "$status" -eq 1 ]
    [[ "$output" == *"must be a hex SHA"* ]]
    # No git command should have leaked into stdout.
    [[ "$output" != *"git cherry-pick"* ]]
}

@test "script reads from stdin when no argument given" {
    write_single_plan
    run bash -c "'$SCRIPT' < '$PLAN_FILE'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"shape: single"* ]]
}

# -- quoting safety ----------------------------------------------------------

# Helper: write a fake gh/git pair that records args one-per-line so we can
# verify the emitted commands round-trip cleanly through bash.
write_fake_bin() {
    FAKE_BIN="$BATS_TEST_TMPDIR/fakebin"
    mkdir -p "$FAKE_BIN"
    cat > "$FAKE_BIN/gh" <<'SH'
#!/usr/bin/env bash
# Print each arg on its own line wrapped in <>. Exit 1 for `pr view` so the
# emitted idempotency guard falls through to `pr create` — the round-trip
# tests want to verify what `pr create` actually receives.
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
    exit 1
fi
printf '<%s>\n' "$@"
SH
    cat > "$FAKE_BIN/git" <<'SH'
#!/usr/bin/env bash
printf '<%s>\n' "$@"
SH
    chmod +x "$FAKE_BIN/gh" "$FAKE_BIN/git"
}

@test "emitted commands round-trip through bash when title contains an apostrophe" {
    # PR titles routinely contain apostrophes ("don't", "it's"). The sq()
    # escape must produce output that bash can evaluate without syntax error.
    cat > "$PLAN_FILE" <<'YAML'
shape: single
groups:
  - branch: cheese-factory/foo/pr-1
    title: "feat(foo): don't break the cart"
    body: "It's a fix."
    base: main
    commits: [abc1234]
YAML
    write_fake_bin
    out="$("$SCRIPT" "$PLAN_FILE")"
    # Evaluate the emitted command stream with the fakes on PATH and capture
    # what gh saw. If sq() is broken, bash itself errors out before gh runs.
    run env PATH="$FAKE_BIN:$PATH" bash -c "$out"
    [ "$status" -eq 0 ]
    [[ "$output" == *"<feat(foo): don't break the cart>"* ]]
    [[ "$output" == *"<It's a fix.>"* ]]
}

@test "idempotency guard skips gh pr create when gh pr view succeeds" {
    # If the PR already exists for the branch, `gh pr view` exits 0 and the
    # guard short-circuits — `gh pr create` is never invoked. This is the
    # property that lets a partially shipped plan be re-run safely.
    write_single_plan
    FAKE_BIN="$BATS_TEST_TMPDIR/fakebin"
    mkdir -p "$FAKE_BIN"
    cat > "$FAKE_BIN/gh" <<'SH'
#!/usr/bin/env bash
# Fake gh that always reports the PR exists; record any pr create attempt.
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
    exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "create" ]; then
    echo "FAIL: gh pr create should have been skipped" >&2
    exit 1
fi
SH
    cat > "$FAKE_BIN/git" <<'SH'
#!/usr/bin/env bash
# Fake git is a no-op so push / cherry-pick succeed under set -e.
exit 0
SH
    chmod +x "$FAKE_BIN/gh" "$FAKE_BIN/git"
    out="$("$SCRIPT" "$PLAN_FILE")"
    run env PATH="$FAKE_BIN:$PATH" bash -c "$out"
    [ "$status" -eq 0 ]
    [[ "$output" != *"FAIL: gh pr create"* ]]
}

@test "emitted commands round-trip through bash when body contains quotes and newlines" {
    # Use JSON here so the literal \n escapes decode to real newlines without
    # YAML scalar style fuss — the quoting helper is what we want to exercise,
    # not YAML's block-vs-flow handling.
    JSON_PLAN="$BATS_TEST_TMPDIR/plan.json"
    cat > "$JSON_PLAN" <<'JSON'
{
  "shape": "single",
  "groups": [
    {
      "branch": "cheese-factory/foo/pr-1",
      "title": "feat(foo): ship",
      "body": "Line one with 'quoted' word.\nLine two.\nLine three with \"double\" too.",
      "base": "main",
      "commits": ["c1c1c1d"]
    }
  ]
}
JSON
    write_fake_bin
    out="$("$SCRIPT" "$JSON_PLAN")"
    run env PATH="$FAKE_BIN:$PATH" bash -c "$out"
    [ "$status" -eq 0 ]
    # Body must survive verbatim — single quotes, newlines, and double quotes.
    [[ "$output" == *"'quoted'"* ]]
    [[ "$output" == *"Line two."* ]]
    [[ "$output" == *"\"double\""* ]]
}
