# `gh stack` publication

Use this provider when the `github/gh-stack` extension is installed. Also require the enablement preflight below to report the repository as enabled.
Exit code 4 remains the fallback for races and later remote failures.
It means that the GitHub API or preview is unavailable. Halt at `publish`. Then report the enablement requirement.

## Initialize and inspect

Initialize or adopt with:

```bash
gh stack init --base <trunk>
gh stack init --adopt --base <trunk>
gh stack init --prefix <prefix> --numbered --base <trunk>
```

`--numbered` requires `--prefix`. Add branches with `gh stack add <branch>`.
Do not use combined staging or commit flags. Stage named paths. Create normal new commits.
Inspect with `gh stack view --short` or `gh stack view --json`.

Resolve local tracking paths from `GIT_DIR="$(git rev-parse --git-dir)"`.
Tracking lives at `$GIT_DIR/gh-stack`. Rebase recovery state lives at
`$GIT_DIR/gh-stack-rebase-state`. Git does not track either path.

## Remote selection and publication

Select the intended remote explicitly when it is not unambiguously `origin`.
Use the same `--remote <name>` on push, submit, sync, and link operations.

Resolve the stacked topology first. Know every title and body.
Then publish all branches and pull requests with `gh stack submit --auto --open --remote <name>`.
Here `--auto` skips only provider metadata prompts. It never overrides Plate's explicit-choice policy.
It never overrides Plate's review-shape policy. Omit `--open` for drafts.

Use `gh stack push --remote <name>` only to update an existing stack without changing pull request metadata.
Both operations are stack-aware and lease-safe. Never use a bare single-branch push.

## Install, authenticate, and detect

- Install with `gh extension install github/gh-stack`. Upgrade with
  `gh extension upgrade gh-stack`.
- Use full `gh stack` commands. Do not assume the optional `gs` alias.
- Authenticate through `gh auth login`. The extension uses OAuth, not personal
  access tokens.
- Detect installation via `gh extension list`.
- Resolve all local metadata with `git rev-parse --git-dir`.

## Enablement preflight

`GET /repos/{owner}/{repo}/stacks` is a read-only preflight: run it before the
first stack mutation instead of discovering enablement from a failed write.

```bash
gh api --include "repos/{owner}/{repo}/stacks"
```

`--include` prints the status line for success and failure. Classify the response by status, not by exit code:

| Status | Meaning | Response |
| --- | --- | --- |
| `2xx` | Stacked PRs enabled | Proceed with the provider |
| `404` | Repository enablement requirement | Halt; report that Stacked PRs must be enabled |
| `401`, `403` | Authentication or authorization failure | Halt; report auth, not enablement |
| other | Service failure | Halt. Preserve the status and stderr |
| none | Indeterminate — no resolvable repository, network failure, or timeout | Proceed. Here exit code 4 stays the fallback |

`python3 skills/plate/scripts/plate.pyz stack-tools` runs this preflight.
It reports one `gh-stack` status. The status is `available`, `not-enabled`, `auth-required`, `service-error`, `remote-check-required`, or `not-installed`.
`repository_signal` is `true` only for a 2xx response. It is `false` only for a 404 response.
It is `null` when the probe cannot decide. The report never recommends a `not-enabled` repository.

The report also preserves the service-failure evidence that this table requires:

| Field | Value |
| --- | --- |
| `http_status` | The final HTTP status code, or `null` when the probe reports none |
| `exit_status` | The `gh` exit status, or `null` when the probe did not complete |
| `stderr` | The trailing 2000 characters of `gh` stderr, or `null` when it is empty |

Report `http_status`, `exit_status`, and `stderr` for a `service-error` status. Do not discard them.

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
| 1 | Generic error | Preserve stderr. Halt. Do not reinterpret |
| 2 | Not in a stack | Re-detect or adopt; do not emulate |
| 3 | Rebase conflict | Use provider recovery |
| 4 | API/preview unavailable | Report enablement or auth |
| 5 | Invalid arguments or flags | Read installed-command help, correct input, retry once |
| 6 | Ambiguous membership | Ask which stack |
| 7 | Rebase active | Resume or abort provider operation |
| 8 | Stack locked | Wait; do not mutate concurrently |

Unknown non-zero exits are failures. Preserve the command, code, and stderr. Then halt.

## Conflict recovery

Resolve each named path after a rebase conflict. Stage each resolved path.
Then run `gh stack rebase --continue` or `gh stack rebase --abort`.
Do not run `git rebase --continue`. The `gh stack` command must update its rebase state.
For modify conflicts, run `gh stack modify --continue` or `gh stack modify --abort`.

## Plate recipes

### Create a two-layer stack

1. Initialize the bottom with `gh stack init --base <trunk>`.
2. Write the common artifacts. Validate the work. Stage named paths. Commit the changes.
3. Add the top branch. Repeat the transaction for top-specific work.
4. Inspect with `gh stack view --json`.
5. Submit with an explicit remote. Verify the stack map and every PR/base pair.

### Update a lower layer

Navigate to the lower layer. Create a new commit. Run `gh stack rebase`. Inspect the stack.
Use `push` or `submit` according to the PR metadata change.

### Link externally managed branches

Run `gh stack link --base <base> --remote <name> <branches-or-PRs>`.
This command does not adopt local tracking.

### After a bottom PR merges

Run `gh stack sync --remote <name>`. Inspect the stack.
Submit again only when local commits remain unpublished. GitHub enforces bottom-up merges.
GitHub also updates the remaining branches on the server.

Put shared durable writes on the bottom branch, common branch, or explicit wiring branch before submission.
Confirm uncertain syntax with `gh stack <command> --help`.
