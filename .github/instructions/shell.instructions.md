---
applyTo: "scripts/**/*.sh,tests/bash/**/*.bats"
---

# Shell review checklist (install script and bats tests)

`scripts/install.sh` is the only entry point most users see. `tests/bash/`
exercises it under bats. ShellCheck runs in CI (`just lint-sh`), so don't
spend review budget on lint nits — focus on behavior.

## Hard rules

- `set -euo pipefail` at the top of any new shell script. Missing it is a
  blocker, not a nit.
- Quote every expansion: `"$var"`, `"${arr[@]}"`. Unquoted `$var` in a
  filename or path is a security finding, not a style one.
- `[[ ... ]]` over `[ ... ]`. Bash-only repo, no POSIX-sh constraint.
- Use `printf` for any output that contains user-supplied data or escape
  sequences. Reserve `echo` for literal static strings.
- New external commands (`curl`, `jq`, `bats`, `brew`, etc.) need a preflight
  check with a clear error message — don't let the script die three lines
  later on `command not found`.

## What to flag

- Functions over ~30 lines or scripts over ~500 lines without decomposition.
- Network calls without timeout flags (`curl --max-time`, `--connect-timeout`).
- `eval` or `bash -c "$var"` — almost always avoidable, almost always a
  vulnerability when `$var` touches user input.
- `rm -rf "$var"` without guarding against empty `$var`. Use
  `rm -rf -- "${var:?}"` or check first.
- Silent failures in `install.sh` — every failed step should print what
  failed and exit non-zero. This is the user's first impression of the
  repo; a half-installed state is worse than a clean abort.
- bats tests that exercise the happy path only. Each new flag or branch in
  `install.sh` should have a failure-mode test in `test_install.bats`.

## What not to flag

- Anything ShellCheck already catches (SC2086, SC2046, etc.) — CI runs it.
- `local` placement, alignment, double-vs-single quote on static strings.
- Cheese / Dune / Mad Max / LOTR / Princess Bride flavor in user-facing
  `echo` lines. Intentional repo voice.
- Bashism vs POSIX-sh portability — this is a Bash repo.

## bats specifics

- Each `@test` does one thing. Name the test after the behavior, not the
  function: `@test "install fails fast when curl missing"`, not
  `@test "test_check_deps"`.
- Use `run` for the command under test, then assert on `$status` and
  `$output` — don't assert before `run` returns.
- Stub external commands (`curl`, `brew`, `claude`, `gh`) via `PATH`
  injection or helper wrappers. A bats test that actually hits the network
  or shells out to real `brew` is a flake waiting to happen.
- The real-install smoke test in `validate.yml` (the `--skip-mcp` job)
  intentionally bypasses stubs to catch breakage in upstream package
  resolution. Don't add stubbing there; do add it to `test_install.bats`.
