# `gh stack` reference

GitHub's first-party stacked-PR workflow, delivered as a `gh` extension
(`github/gh-stack`). The CLI drives the local branch / PR machinery; the
GitHub PR UI renders the stack map, enforces bottom-up merging, and runs
cascading rebases server-side.

The shared mental model and tool-selection rules live in `../SKILL.md`.
This file is the `gh stack`-side detail.

**Status (2026-05-12):** Private preview. The CLI installs anywhere, but
remote operations fail against any repo not allow-listed via the waitlist
at [gh.io/stacksbeta](https://gh.io/stacksbeta).

Primary sources:

- Landing: <https://github.github.com/gh-stack/>
- Quick start: <https://github.github.com/gh-stack/getting-started/quick-start/>
- Overview: <https://github.github.com/gh-stack/introduction/overview/>
- CLI reference: <https://github.github.com/gh-stack/reference/cli/>
- Working with stacked PRs: <https://github.github.com/gh-stack/guides/stacked-prs/>
- Repo + README + exit codes: <https://github.com/github/gh-stack>

## Install / enable

```bash
gh extension install github/gh-stack          # install
gh extension upgrade gh-stack                 # upgrade
gh stack alias                                # optional: install `gs` alias
```

The `gh stack alias` step writes a `gs` shell alias so users can type
`gs init` instead of `gh stack init`. **Skills should NOT assume the alias
is installed** — always emit `gh stack …`.

Requires `gh` v2.0+. Uses standard OAuth via `gh auth login`. **Personal
access tokens (PATs) are explicitly unsupported.**

Source: <https://github.com/github/gh-stack>,
<https://github.github.com/gh-stack/getting-started/quick-start/>.

## Detection

Run these in order:

1. Extension installed locally:

   ```bash
   gh extension list 2>/dev/null | awk -F '\t' '$2 == "github/gh-stack"' | grep -q .
   ```

   (or `gh stack --help` exits 0 — same signal, slower.)

2. `gh` version OK: `gh --version` reports `>= 2.0`.

3. **Repo enablement** has no documented preflight command. The only
   reliable signal is exit code `4` from a remote op (`submit`, `sync`,
   `link`) when the repo isn't allow-listed. Don't preflight — just run
   the user's command and translate the failure.

## Mental model

A stack is an ordered chain of branches rooted on trunk (default `main`).
Each branch's PR base is the branch below it.

```
frontend       → PR #3 (base: api-endpoints)   ← top
api-endpoints  → PR #2 (base: auth-layer)
auth-layer     → PR #1 (base: main)            ← bottom
main (trunk)
```

Local metadata lives in `.git/gh-stack` (stack tracking) and
`.git/gh-stack-rebase-state` (rebase recovery). Neither is committed.

What `gh stack` does that third-party stackers don't:

- The **stack map** renders inside the GitHub PR UI itself.
- Merges are **server-enforced bottom-up** — mid-stack merges are rejected
  by the API.
- A **Rebase Stack** button in the UI triggers server-side cascading
  rebase + force-push of every unmerged branch.

All three merge methods (squash, merge commit, rebase) are supported, and
stacks are merge-queue compatible.

Source: <https://github.github.com/gh-stack/introduction/overview/>,
<https://github.github.com/gh-stack/guides/stacked-prs/>.

## Command surface

All flags below come from the official CLI reference page unless tagged.

### Stack management (local)

| Command | Purpose |
| --- | --- |
| `gh stack init [flags] [branches...]` | Create a stack and its first branch. Flags: `-b/--base <branch>`, `-a/--adopt`, `-p/--prefix <str>`, `-n/--numbered` (requires `--prefix`). |
| `gh stack add [flags] [branch]` | Add a new branch on top of the current stack. Must be run from the topmost branch. `-Am "msg"` folds add + stage + commit. |
| `gh stack view [flags]` | List branches, PR links, statuses, last commit. Flags: `-s/--short`, `--json`. Output paged. |
| `gh stack checkout [<pr-number> \| <branch>]` | Pull a stack down from GitHub by PR number or branch. |
| `gh stack modify [flags]` | TUI to rename / drop / reorder / fold branches. Flags: `--continue`, `--abort`. Run `gh stack submit` after to push the restructure. |

### Remote operations

| Command | Purpose |
| --- | --- |
| `gh stack push [--remote <name>]` | Push every branch with `--force-with-lease --atomic`. Does NOT touch PRs. |
| `gh stack submit [--auto] [--open] [--remote <name>]` | Push branches AND create / update PRs and the GitHub Stack object. `--auto` skips title prompts; `--open` creates non-draft PRs (default is **draft**). |
| `gh stack rebase [flags] [branch]` | Fetch from `origin` and cascade-rebase from trunk upward. Auto-switches to `--onto` mode for merged PRs (handles squash-merges safely). Flags: `--continue`, `--abort`. |
| `gh stack sync [--remote <name>]` | All-in-one: fetch → fast-forward trunk → cascade rebase (only if trunk moved) → push with `--force-with-lease` → sync PR state. On conflict, restores all branches and tells you to run `gh stack rebase` interactively. |
| `gh stack unstack` | Remove the stack from GitHub and local tracking (for restructuring). |
| `gh stack link [flags] <branches\|PR#s...>` | Open a stack of PRs from existing branches / PRs without touching local `gh-stack` tracking state. Designed for users driving local branches with `jj`, Sapling, or git-town. Flags: `--base <branch>`, `--open`, `--remote <name>`. |

### Navigation

| Command | Purpose |
| --- | --- |
| `gh stack up [n]` | Move `n` branches up (away from trunk). Default 1. From trunk, jumps to the first stack branch. |
| `gh stack down [n]` | Move `n` branches down (toward trunk). Default 1. |
| `gh stack top` | Check out the topmost branch. |
| `gh stack bottom` | Check out the bottommost branch. |
| `gh stack switch` | Interactive TUI picker. Requires a TTY. |

All navigation clamps at the bounds (no-op + message).

### Utilities

| Command | Purpose |
| --- | --- |
| `gh stack alias` | Install the `gs` alias for `gh stack`. |
| `gh stack feedback` | Submit feedback to GitHub. |

## Exit codes

From the README — critical for skill error handling:

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Generic error |
| 2 | Not in a stack / stack not found |
| 3 | Rebase conflict |
| 4 | GitHub API failure (use this to detect "feature not enabled for repo") |
| 5 | Invalid arguments or flags |
| 6 | Disambiguation required (branch belongs to multiple stacks) |
| 7 | Rebase already in progress |
| 8 | Stack is locked by another process |

Source: <https://github.com/github/gh-stack> (exit codes table).

## Conflict recovery

On exit code `3`, `gh stack` halts the cascading rebase. Resolve and resume
using the tool's own continue / abort flags, **not** bare `git rebase
--continue`:

```bash
# 1. Resolve conflicts in the working tree
git status                    # shows conflicted paths
# … edit files, remove <<<<<<< markers …

# 2. Stage resolved files
git add path/to/resolved

# 3. Resume the broader stack operation
gh stack rebase --continue    # or `gh stack rebase --abort` to back out
```

If the halted operation was `gh stack modify` (mid-restructure), use
`gh stack modify --continue` / `--abort` instead.

For `sync` specifically: on conflict, `sync` restores all branches to
their pre-sync state and instructs the user to run `gh stack rebase`
interactively to resolve.

## How it represents a stack on GitHub

- One PR per branch, each with `base` set to the branch below it (each
  PR's diff is just that layer).
- A first-party **Stack** object linking the PRs, surfaced as a stack map
  in the PR UI.
- A **Rebase Stack** button in the UI triggers server-side cascading
  rebase + force-push of every unmerged branch.
- Merges enforced bottom-up: a contiguous group starting from the lowest
  unmerged PR. Mid-stack merges are rejected by the server.
- After a merge, GitHub auto-rebases the remaining PRs so the next-lowest
  PR targets the updated base.
- Merge methods: squash, merge commit, rebase — all supported. Merge-queue
  compatible.

Source: <https://github.github.com/gh-stack/introduction/overview/>,
<https://github.github.com/gh-stack/guides/stacked-prs/>.

## Known limitations

- **Private preview** — does not work on non-allow-listed repos. Join the
  waitlist at <https://gh.io/stacksbeta>.
- **Forks** — community reports indicate stacked PRs still can't be opened
  from a fork; contributors must work from branches inside the main repo.
  Not contradicted by official docs but not explicitly confirmed either.
- **GitHub Enterprise Server** — no GHES support documented during
  preview. Assume GitHub.com only until confirmed.
- **Auth** — OAuth only via `gh auth login`. PATs are explicitly
  unsupported.
- **Concurrency** — exit code `8` means the stack is locked by another
  `gh stack` process. Don't run two ops in parallel against the same
  stack.

## Recipes

### Open a new 2-PR stack from clean trunk

```bash
gh stack init -p feat/payments -n auth payments
# ↑ creates feat/payments-1-auth and feat/payments-2-payments
# … edit files in branch 1 …
gh stack submit --open
```

Or, building one branch at a time:

```bash
gh stack init -b main feat/auth
# … edit, commit normally …
gh stack add -Am "feat: payments"   # adds a new top branch with that commit
gh stack submit --open
```

### Sync trunk into your stack (also: after a sibling PR merged)

This is the canonical post-merge command. When the bottom (or any) PR in
the stack lands, GitHub has already cascaded the rebase server-side —
`gh stack sync` pulls that state down. You only need a follow-up
`gh stack submit` if you have local commits not yet pushed.

```bash
gh stack sync
# if conflicts: it restores branches and tells you to run rebase manually
gh stack rebase                     # resolve, git add, `gh stack rebase --continue`
gh stack submit                     # re-submit after rebase
```

### Address review feedback on a non-top branch

```bash
gh stack down                       # move to the branch under review
# … edit files, commit normally …
git commit -am "address review"
gh stack rebase                     # cascade the new commit up the stack
gh stack push                       # push without re-prompting PR metadata
```

### Pull down a teammate's stack

```bash
gh stack checkout <pr-number>       # by PR number
gh stack checkout feat/their-top    # by branch name
gh stack view                       # confirm the chain
```

### Open a stack from branches you built with other tooling (jj / Sapling / git-town)

```bash
gh stack link --base main feat/auth feat/payments feat/ui
# or by existing PR numbers:
gh stack link 412 413 414
```

`gh stack link` does NOT take ownership of the branches in local
`gh-stack` tracking — it just stacks the PRs on GitHub.

### Remove the stack from GitHub (for restructuring)

```bash
gh stack unstack
# … restructure locally, then …
gh stack submit                     # re-creates the Stack object
```

## Agent gotchas

- **Preflight**: check `gh extension list` for `github/gh-stack` and bail
  with the install + waitlist message if missing.
- **Detect repo enablement lazily**: don't preflight it — just run the
  user's command and translate exit code `4` into a helpful "the Stacked
  PRs feature isn't enabled for this repo" message.
- **Never assume `gs`** — always emit `gh stack …`.
- **Don't mix with `git push`**: `gh stack push` uses `--force-with-lease
  --atomic` and knows every branch. Bare `git push` on a single stack
  branch leaves the rest stale.
- **Submit defaults to drafts** — pass `--open` when the user wants
  reviewable PRs immediately.
- **Conflict path**: on exit 3, resolve files, `git add`, then `gh stack
  rebase --continue` (or `--abort`). For `gh stack modify`, the `--continue
  / --abort` flags belong to `modify`, not `rebase`.
- **Prefer `sync` for normal day-to-day**; reserve `rebase` for interactive
  conflict resolution.

## Divergence from `gt`

Quick contrast for users coming from Graphite:

| Concept | `gt` | `gh stack` |
| --- | --- | --- |
| Mental model | trunk + chain | trunk + chain (identical) |
| Stack creation | `gt create` | `gh stack init` + `gh stack add` |
| Submit | `gt submit` | `gh stack submit` (with PRs) / `gh stack push` (no PRs) |
| Cascade rebase | `gt restack` / `gt sync` | `gh stack rebase` / `gh stack sync` |
| Stack visualization | client-side | server-side stack map in PR UI |
| Merge enforcement | client validates | GitHub server enforces bottom-up |
| Backend account | Graphite SaaS | none — pure GitHub OAuth |
| BYO local tooling (jj, Sapling) | partial | first-class via `gh stack link` |
| GHES support | Enterprise plan only | not yet (preview is github.com only) |
| Public availability | GA | private preview (waitlist) |
