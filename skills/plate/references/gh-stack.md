# `gh stack` publication

Use when the `github/gh-stack` extension is installed and the repository
accepts its remote operations. Exit code 4 means the GitHub API or preview is
unavailable; halt and report the enablement requirement.

## Initialize and inspect

Initialize or adopt with:

```bash
gh stack init --base <trunk>
gh stack init --adopt --base <trunk>
gh stack init --prefix <prefix> --numbered --base <trunk>
```

`--numbered` requires `--prefix`. Add branches with `gh stack add <branch>`
without combined staging/commit flags, stage named paths, and create normal new
commits. Inspect with `gh stack view --short` or `gh stack view --json`.

Resolve local tracking paths from `GIT_DIR="$(git rev-parse --git-dir)"`.
Tracking lives at `$GIT_DIR/gh-stack`; rebase recovery state lives at
`$GIT_DIR/gh-stack-rebase-state`. Neither is committed.

## Remote selection and publication

Select the intended remote explicitly when it is not unambiguously `origin`.
Use the same `--remote <name>` on push, submit, sync, and link operations.

Publish all branches and PRs with
`gh stack submit --auto --open --remote <name>` after Plate has resolved
stacked topology and every title/body is known. Here `--auto` skips only
provider metadata prompts; it never overrides Plate's explicit-choice and
review-shape policy. Omit `--open` for drafts.

Use `gh stack push --remote <name>` only to update an already-created stack
without changing PR metadata. Both operations are stack-aware and lease-safe;
never use a bare single-branch push.

## Install, authenticate, and detect

- Install with `gh extension install github/gh-stack`; upgrade using
  `gh extension upgrade gh-stack`.
- Use full `gh stack` commands; do not assume the optional `gs` alias.
- Authenticate through `gh auth login`; the extension uses OAuth, not personal
  access tokens.
- Detect via `gh extension list`. Repository enablement has no documented
  preflight; translate remote exit code 4 into the API/preview failure.
- Resolve all local metadata with `git rev-parse --git-dir`.

## Command map

| Need | Command |
| --- | --- |
| Initialize/adopt | `gh stack init [--adopt] [--base <branch>] [--prefix <text> --numbered]` |
| Add top branch | `gh stack add <branch>` |
| Inspect | `gh stack view --short` or `gh stack view --json` |
| Pull collaborator stack | `gh stack checkout <PR-or-branch>` |
| Push branches only | `gh stack push --remote <name>` |
| Create/update PRs | `gh stack submit [--auto] [--open] --remote <name>` |
| Sync remote/local state | `gh stack sync --remote <name>` |
| Cascade local rebase | `gh stack rebase` |
| Reorder/drop/rename/fold | `gh stack modify` |
| Link existing branches/PRs | `gh stack link --base <base> --remote <name> <items...>` |
| Remove stack tracking | `gh stack unstack` |
| Navigate | `gh stack up`, `down`, `top`, `bottom`, or `switch` |

`submit` defaults new PRs to draft; `--open` marks them ready for review.
`push` updates branches without PR metadata. `link` creates the server
relationship without adopting local tracking.

## Exit handling

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | Success | Verify stack and PRs |
| 1 | Generic error | Preserve stderr and halt; do not reinterpret |
| 2 | Not in a stack | Re-detect or adopt; do not emulate |
| 3 | Rebase conflict | Use provider recovery |
| 4 | API/preview unavailable | Report enablement or auth |
| 5 | Invalid arguments or flags | Read installed-command help, correct input, retry once |
| 6 | Ambiguous membership | Ask which stack |
| 7 | Rebase active | Resume or abort provider operation |
| 8 | Stack locked | Wait; do not mutate concurrently |

Unknown non-zero exits are failures: preserve the command, code, and stderr,
then halt rather than treating them as success.

## Conflict recovery

On a rebase conflict, resolve and stage named paths, then use
`gh stack rebase --continue` or `gh stack rebase --abort`. A bare
`git rebase --continue` is never correct because `gh stack` must update its
rebase state. For modify conflicts, use
`gh stack modify --continue` or `gh stack modify --abort`.

## Plate recipes

### Create a two-layer stack

1. Initialize the bottom with `gh stack init --base <trunk>`.
2. Write common artifacts, validate, stage named paths, and commit.
3. Add the top branch, then repeat the transaction for top-specific work.
4. Inspect with `gh stack view --json`.
5. Submit with explicit remote and verify the stack map and every PR/base pair.

### Update a lower layer

Navigate down, create a new commit, run `gh stack rebase`, inspect, then use
`push` or `submit` according to whether PR metadata changed.

### Link externally managed branches

Use `gh stack link --base <base> --remote <name> <branches-or-PRs>`. This does
not adopt local tracking.

### After a bottom PR merges

Run `gh stack sync --remote <name>`, inspect the stack, and submit again only
when local commits remain unpublished. GitHub enforces bottom-up merges and
cascades the remaining branches server-side.

Shared durable writes belong on the bottom/common branch or explicit wiring
branch before submission. Confirm uncertain syntax with
`gh stack <command> --help`.
