#!/usr/bin/env bash
# pr_plan_to_branches.sh — convert a cheese-factory pr-plan.json to branch
# creation / push / PR-create commands.
#
# Reads pr-plan.json on stdin (or as $1) and prints one shell command per line.
# The orchestrator reviews the commands, then pipes them to `bash -s` to
# execute. Dry-run friendly — the script itself never invokes git or gh.
#
# Per .github/instructions/shell.instructions.md:
# - set -euo pipefail at the top.
# - quote every expansion.
# - [[ over [.
# - printf for any user-supplied output.
# - preflight external commands.

set -euo pipefail

PROG="$(basename "$0")"

# sq <value> — single-quote a value safely for a POSIX shell command line.
# We always wrap in single quotes (even for simple words) so the emitted
# commands are visually consistent and grep-able by callers. Internal
# apostrophes are escaped as the canonical four-character sequence: close
# quote, backslash-escaped quote, open quote — '\''.
#
# Bash parameter-expansion replacement strings can't reliably embed the
# literal sequence '\'' via backslash escapes inside a double-quoted
# replacement, so we build it once via $'...' (ANSI-C quoting) and pass it
# as a variable to the //pat/repl substitution.
sq() {
    local value="$1"
    local esc=$'\047\134\047\047'  # the four chars: ' \ ' '
    printf "'%s'" "${value//\'/${esc}}"
}

usage() {
    cat <<USAGE
Usage: ${PROG} [<pr-plan.json>]

Reads a cheese-factory pr-plan.json (from \$1 or stdin) and prints the shell
commands needed to create the planned branches and PRs.

The script emits commands only; it never invokes git or gh itself. Pipe its
output to \`bash -s\` to execute, or eyeball it first.

Supported shapes (from pr-plan.json "shape" field):
  - single            One PR, one branch from main.
  - orthogonal_flat   N PRs each branching from main, no inter-dep.
  - stacked_linear    Linear stack; each PR bases on the previous branch.
  - diamond_stack     Seed PR at base, N curd PRs from seed, wiring PR last.
USAGE
}

# Preflight: jq is required to parse the plan.
if ! command -v jq >/dev/null 2>&1; then
    printf 'ERROR: jq not found — install jq (https://stedolan.github.io/jq) before running %s\n' "${PROG}" >&2
    exit 2
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Read plan from $1 or stdin.
if [[ -n "${1:-}" ]]; then
    if [[ ! -f "$1" ]]; then
        printf 'ERROR: file not found: %s\n' "$1" >&2
        exit 1
    fi
    plan="$(cat -- "$1")"
else
    plan="$(cat)"
fi

# Sanity check: shape must be one of the four known values.
shape="$(printf '%s' "${plan}" | jq -r '.shape // empty')"
case "${shape}" in
    single|orthogonal_flat|stacked_linear|diamond_stack) ;;
    "")
        printf 'ERROR: pr-plan.json missing required "shape" field\n' >&2
        exit 1
        ;;
    *)
        printf 'ERROR: unknown shape %q (expected single|orthogonal_flat|stacked_linear|diamond_stack)\n' "${shape}" >&2
        exit 1
        ;;
esac

# Sanity check: groups must be a non-empty array.
group_count="$(printf '%s' "${plan}" | jq '.groups | length')"
if [[ "${group_count}" -lt 1 ]]; then
    printf 'ERROR: pr-plan.json has no groups\n' >&2
    exit 1
fi

# Emit a header comment so the user knows what they're about to run.
printf '# pr-plan shape: %s (%d groups)\n' "${shape}" "${group_count}"

# Walk each group and emit branch + commit + push + PR commands.
i=0
while [[ "${i}" -lt "${group_count}" ]]; do
    branch="$(printf '%s' "${plan}" | jq -r ".groups[${i}].branch")"
    title="$(printf '%s' "${plan}" | jq -r ".groups[${i}].title")"
    body="$(printf '%s' "${plan}" | jq -r ".groups[${i}].body // \"\"")"
    base="$(printf '%s' "${plan}" | jq -r ".groups[${i}].base")"
    commit_count="$(printf '%s' "${plan}" | jq ".groups[${i}].commits | length")"

    printf '\n# Group %d: %s (base: %s)\n' "$((i + 1))" "${branch}" "${base}"
    printf 'git checkout -b %s %s\n' "$(sq "${branch}")" "$(sq "${base}")"

    # Emit one cherry-pick per commit.
    j=0
    while [[ "${j}" -lt "${commit_count}" ]]; do
        sha="$(printf '%s' "${plan}" | jq -r ".groups[${i}].commits[${j}]")"
        printf 'git cherry-pick %s\n' "$(sq "${sha}")"
        j=$((j + 1))
    done

    printf 'git push -u origin %s\n' "$(sq "${branch}")"
    # gh pr create uses --base for the target.
    printf 'gh pr create --base %s --head %s --title %s --body %s\n' \
        "$(sq "${base}")" "$(sq "${branch}")" "$(sq "${title}")" "$(sq "${body}")"

    i=$((i + 1))
done
