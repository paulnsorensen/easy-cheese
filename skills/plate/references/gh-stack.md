# `gh stack` publication

Use this provider only when `github/gh-stack` is installed and the enablement
preflight reports `available`. Run every command from the repository root.

## Contents

- [Inspect the installed command](#inspect-the-installed-command)
- [Validate the trunk before mutation](#validate-the-trunk-before-mutation)
- [Initialize and inspect](#initialize-and-inspect)
- [Guard every mutation](#guard-every-mutation)
- [Publish and verify](#publish-and-verify)
- [Install, authenticate, and detect](#install-authenticate-and-detect)
- [Enablement preflight](#enablement-preflight)
- [Command map](#command-map)
- [Exit handling](#exit-handling)
- [Conflict recovery](#conflict-recovery)
- [Wrong-trunk recovery](#wrong-trunk-recovery)
- [Plate recipes](#plate-recipes)

## Inspect the installed command

Run `gh stack --version` and `gh stack <command> --help` before the first
mutation. The verified command surface adopts existing branches through
positional arguments. Do not use the deprecated hidden `init --adopt` flag.
The installed `init` command has no `--prefix` or `--numbered` flags.

## Validate the trunk before mutation

Resolve the intended GitHub branch name. The default branch query
`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'` returns a
name such as `main`. Do not pass a remote-tracking value such as `origin/main`
or `refs/remotes/origin/main` to `--base`.

Run the executable preflight before `init`, `link`, or any recovery mutation:

```bash
python3 skills/plate/scripts/plate.pyz gh-stack-preflight \
  --trunk <github-branch-name> --remote origin
```

The preflight canonicalizes `refs/heads/<name>` to `<name>`, validates the Git
branch name, requires the `origin` remote, and confirms the exact
`refs/heads/<name>` branch on that remote. Halt at `publish` when it fails.

## Initialize and inspect

Initialize one or more new or existing branches in bottom-to-top order:

```bash
gh stack init --base <trunk> <bottom> [<next> ...]
```

Existing branches are adopted automatically. Add a new top branch with
`gh stack add <branch>`. Do not use combined staging or commit flags. Stage
named paths and create normal commits before branch operations.

Inspect with `gh stack view --short` or `gh stack view --json`.
Resolve local tracking paths from `GIT_DIR="$(git rev-parse --git-dir)"`.
Tracking lives at `$GIT_DIR/gh-stack`. Rebase recovery state lives at
`$GIT_DIR/gh-stack-rebase-state`. Git does not track either path.

## Guard every mutation

The extension can print `⚠` warnings for failed PR or stack API calls and still
exit zero. A zero exit is therefore provisional. Run mutations through Plate's
guard so a warning, HTTP failure, or non-zero exit fails publication:

```bash
python3 skills/plate/scripts/plate.pyz gh-stack-run -- \
  gh stack <operation> <arguments>
```

The guard requires explicit `--remote origin` for `submit`, `push`, `sync`,
`rebase`, and `link`. The installed `init`, `add`, `modify`, and `unstack`
commands do not support `--remote`; do not add it to those commands.

## Publish and verify

Resolve every title and body before publication. Submit the complete chain:

```bash
python3 skills/plate/scripts/plate.pyz gh-stack-run -- \
  gh stack submit --auto --open --remote origin
```

Here `--auto` skips only the provider editor. It does not override Plate's
explicit topology or review-shape policy. Omit `--open` when the requested PRs
must remain drafts.

Use guarded `gh stack push --remote origin` only to update existing branches
without PR metadata changes. Never use a bare single-branch push.

After `submit`, `push`, or `link`, run terminal validation:

```bash
python3 skills/plate/scripts/plate.pyz gh-stack-verify \
  --trunk <github-branch-name> --remote origin
```

The verifier fails unless all of these facts match exactly:

- The local stack trunk equals the canonical GitHub branch name.
- Every branch exists at the same local, remote, and PR head SHA.
- Every PR is open, has auto-merge disabled, and has the expected base and head.
- Every PR maps to the same open GitHub stack.
- The remote stack base, ordered PR numbers, head refs, states, and SHAs match.

Treat any failed check as a failed publication even when `gh stack` exited zero.

## Install, authenticate, and detect

- Install with `gh extension install github/gh-stack`.
- Upgrade with `gh extension upgrade gh-stack`.
- Use full `gh stack` commands. Do not assume the optional `gs` alias.
- Authenticate through `gh auth login`. The extension uses OAuth.
- Detect installation via `gh extension list`.
- Resolve all local metadata with `git rev-parse --git-dir`.

## Enablement preflight

`GET /repos/{owner}/{repo}/stacks` is a read-only preflight; run it before the
first stack mutation instead of discovering enablement from a failed write.

```bash
gh api --include "repos/{owner}/{repo}/stacks"
```

Classify the response by HTTP status, not by process exit:

| Status | Meaning | Response |
| --- | --- | --- |
| `2xx` | Stacked PRs enabled | Proceed with the provider |
| `404` | Repository enablement requirement | Halt and report that Stacked PRs must be enabled |
| `401`, `403` | Authentication or authorization failure | Halt and report authentication or authorization |
| other | Service failure | Halt and preserve the status and stderr |
| none | Indeterminate repository or network failure | Halt and report the unresolved remote check |

`python3 skills/plate/scripts/plate.pyz stack-tools` runs this preflight. It
reports `available`, `not-enabled`, `auth-required`, `service-error`,
`remote-check-required`, or `not-installed`. Proceed only with `available`.
The report preserves `http_status`, `exit_status`, and `stderr`.

## Command map

| Need | Installed command |
| --- | --- |
| Initialize or adopt | `gh stack init --base <branch> <branches...>` |
| Add top branch | `gh stack add <branch>` |
| Inspect | `gh stack view --short` or `gh stack view --json` |
| Pull collaborator stack | `gh stack checkout <PR-or-branch>` |
| Push branches only | `gh stack push --remote origin` |
| Create or update PRs | `gh stack submit [--auto] [--open] --remote origin` |
| Sync remote and local state | `gh stack sync --remote origin` |
| Cascade local rebase | `gh stack rebase --remote origin` |
| Reorder, drop, rename, or fold | `gh stack modify` |
| Link existing branches or PRs | `gh stack link --base <base> --remote origin <items...>` |
| Remove stack tracking | `gh stack unstack [<stack-number>] [--local]` |
| Navigate | `gh stack up`, `down`, `top`, `bottom`, `trunk`, or `switch` |

`submit --auto` defaults new PRs to draft. `--open` marks new and existing PRs
ready for review. `push` changes branches without PR metadata. `link` creates
the server relationship without adopting local tracking.

## Exit handling

The installed extension defines these codes. Warning-free exit zero still
requires terminal validation.

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | Command returned without a typed error | Reject warnings, then verify exact state |
| 1 | Generic or already-reported error | Preserve stderr and halt |
| 2 | Branch or stack not found | Re-detect or adopt; do not emulate |
| 3 | Rebase conflict | Use provider recovery |
| 4 | GitHub API failure | Preserve the API error and halt |
| 5 | Invalid arguments or flags | Read installed help, correct input, and retry once |
| 6 | Disambiguation required | Select the intended stack or remote |
| 7 | Rebase already active | Continue or abort the provider operation |
| 8 | Stack lock acquisition failed | Wait; do not mutate concurrently |
| 9 | Stacked PRs unavailable | Halt and report repository enablement |
| 10 | Interrupted modify requires recovery | Continue or abort `gh stack modify` |

Unknown non-zero exits fail publication. Preserve the command, code, stdout,
and stderr. Then halt.

## Conflict recovery

Resolve each named path after a rebase conflict. Stage each resolved path.
Run `gh stack rebase --continue` or `gh stack rebase --abort`.
Do not run `git rebase --continue`. The provider must update its recovery state.
For modify conflicts, run `gh stack modify --continue` or
`gh stack modify --abort`.

## Wrong-trunk recovery

Use this transaction when local tracking or published PRs use the wrong trunk.
Preserve PR identity when the stack is safe to rebuild.

1. Stop publication. Save `gh stack view --json`, the remote stack response,
   every branch SHA, and every PR's number, base, head, state, draft state,
   `autoMergeRequest`, and merge-queue state.
2. Halt for a user decision when any PR is merged, queued, has auto-merge
   enabled, or is not open. Do not unstack or rewrite those PRs.
3. Run `gh-stack-preflight` with the corrected trunk. Halt if it fails.
4. Run guarded `gh stack unstack <stack-number>`. Verify each PR remains open
   with the same number and head. Verify each PR-to-stack query returns empty.
5. Run guarded `gh stack unstack --local` only if local tracking remains.
6. Re-adopt the same branches, bottom to top, with guarded
   `gh stack init --base <correct-trunk> <branches...>`. Do not recreate or
   rename an existing PR.
7. Submit with guarded `gh stack submit --auto --remote origin`. Preserve draft
   state; add `--open` only when every recovered PR was ready before recovery.
8. Run `gh-stack-verify`. Compare every PR number with the saved snapshot.

If unstacking, re-adoption, PR identity, or final mapping differs from the
snapshot, halt at `publish`. Do not create replacement PRs automatically.

## Plate recipes

### Create a two-layer stack

1. Run the trunk and enablement preflights.
2. Run guarded `gh stack init --base <trunk> <bottom>`.
3. Write, validate, stage, and commit the bottom layer.
4. Run guarded `gh stack add <top>`. Repeat the transaction for the top layer.
5. Inspect with `gh stack view --json`.
6. Submit through the guard with `--remote origin`.
7. Run `gh-stack-verify` and record every verified PR/base/head pair.

### Update a lower layer

Navigate to the lower layer and create a new commit. Run guarded
`gh stack rebase --remote origin`. Inspect the stack. Use guarded `push` or
`submit` according to whether PR metadata changes. Then verify publication.

### Link externally managed branches

Run guarded
`gh stack link --base <base> --remote origin <branches-or-PRs>`.
This command does not adopt local tracking. Verify the remote stack mapping.

### After a bottom PR merges

Run guarded `gh stack sync --remote origin`. Inspect the stack. Submit again
only when local commits remain unpublished. Do not run `gh-stack-verify` until
the remaining stack is fully open and publishable; merged or queued branches
require lifecycle inspection instead.
