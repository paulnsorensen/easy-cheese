# `gt` (Graphite CLI) reference

Reference for driving the Graphite CLI on behalf of a user who already has
`gt` installed and a repo initialized. Targets `gt` v1.8.4+. Flags drift
between minor releases — when in doubt, fall back to `gt <cmd> --help`.

The shared mental model and tool-selection rules live in `../SKILL.md`. This
file is the `gt`-side detail.

## Install paths

- **Homebrew** (recommended on macOS / Linux): `brew install withgraphite/tap/graphite`
- **npm** (cross-platform, including Windows): `npm install -g @withgraphite/graphite-cli@stable`
- **Update**: from v1.7.6+ use `gt upgrade`; otherwise rerun the install
  command (`brew upgrade withgraphite/tap/graphite` or
  `npm install -g @withgraphite/graphite-cli@stable`).
- Version check: `gt --version`.
- Git-version override (rarely needed): set `GRAPHITE_IGNORE_GIT_VERSION=1`.

Source: <https://graphite.dev/docs/install-the-cli>,
<https://graphite.dev/docs/update-cli>.

## First-time setup

1. **Auth**:

   ```bash
   gt auth --token <token-from-app.graphite.com>
   ```

   The user pastes the token from <https://app.graphite.com/activate> — that
   page shows the exact `gt auth --token …` line to copy. Token is stored
   in `~/.graphite_user_config`.

   In ephemeral / CI environments, prefer the environment variable
   `GRAPHITE_AUTH_TOKEN` (v1.8.3+) instead of writing to disk.

2. **Repo init** (once per clone):

   ```bash
   gt init
   ```

   Prompts for the trunk branch (default `main`). Writes
   `.git/.graphite_repo_config`. If you skip `gt init`, any `gt` command
   auto-prompts the same flow.

Source: <https://graphite.dev/docs/cli-quick-start>.

### Detection probes

- `gt` installed: `command -v gt && gt --version` (non-zero if missing).
- Repo initialized: `test -f "$(git rev-parse --git-dir)/.graphite_repo_config"`.
  This is the on-disk marker — much more reliable than running `gt <cmd>`,
  which prompts interactively when uninitialized.

## Mental model recap

- Each branch in a stack is one PR. Parent links live in
  `.git/.graphite_repo_config`.
- `gt` calls real `git` underneath — `.gitignore`, hooks, and aliases still
  apply. `--no-verify` disables hooks for that invocation.
- "Downstack" = ancestors (toward trunk). "Upstack" = descendants (away from
  trunk). Both terms appear throughout the official docs.

## Core stack commands

### `gt create` (alias `gt c`) — new branch on top

```bash
gt create                    # interactive: prompts to stage, infers name from commit msg
gt create -am "msg"          # stage all + commit + create branch (most common)
gt create <name> -m "msg"    # explicit branch name
gt create --onto <branch>    # base the new branch on <branch> instead of current
gt create --insert           # insert mid-stack and auto-rebase upstack children
```

The canonical scripted form is `gt create --all --message "…"`.

Source: <https://graphite.dev/docs/create-stack>,
<https://graphite.dev/docs/edit-branch-order>.

### `gt modify` (alias `gt m`) — amend or add to the current branch

```bash
gt modify                    # amend staged changes to current HEAD; auto-restacks upstack
gt modify -a                 # git add -A then amend
gt modify -c                 # NEW commit (not amend); auto-restacks upstack
gt modify -cam "msg"         # stage all + new commit + restack (most common reviewer-feedback form)
gt modify --into             # amend staged hunks into a downstack branch (interactive picker)
```

Always prefer `gt modify` over `git commit --amend` in a stack — bare amend
won't fix children's parents.

Source: <https://graphite.dev/docs/update-mid-stack-branches>.

### `gt submit` (alias `gt s`; `gt ss` = `gt submit --stack`) — push + create / update PRs

```bash
gt submit --stack            # push every branch from trunk up to current, open / update PRs
gt submit --stack --draft    # new PRs as drafts
gt submit --stack --publish  # flip existing drafts to "ready for review"
gt submit --stack --dry-run  # report what would be pushed; no branches restacked, no PRs touched
gt submit --stack --reviewers alice,bob
gt submit --stack -e         # interactively edit PR metadata for ALL PRs (default: only new)
gt submit --stack -f         # true --force push instead of default --force-with-lease (use with care)
gt ss -u                     # alias for --stack --update-only (only push branches with open PRs)
gt submit --no-stack         # skip the "include upstack?" prompt — submit only the current branch + downstack
```

`gt submit` validates the stack is properly restacked first and **fails**
with a conflict message if it isn't — run `gt restack` (or fix conflicts
via `gt continue`) before retrying. Default push mode is `--force-with-lease`,
which refuses to overwrite remote commits you haven't pulled.

Source: <https://graphite.dev/docs/create-submit-prs>.

### `gt sync` — pull trunk, restack, prune

```bash
gt sync                      # fetch trunk, restack all stacks onto new trunk, prompt to delete merged/closed branches
gt sync --no-restack         # fetch + cleanup only; skip the rebase
```

`gt sync` treats remote trunk as source of truth — if your local trunk
can't be fast-forwarded, `gt sync` overwrites it. v1.8.4+ skips non-trunk
branches checked out in other worktrees (trunk itself is always allowed to
update).

Source: <https://graphite.dev/docs/cli-quick-start>,
<https://graphite.dev/docs/collaborate-on-a-stack>.

### `gt track` (alias `gt tr`) — adopt a plain-git branch

```bash
gt track                     # current branch, prompts for parent
gt track <name> --parent main
gt untrack                   # stop tracking (alias `gt utr`)
```

Use when the bottom of a stack started as a plain `git checkout -b` (e.g.
bootstrap iteration before `gt` was installed) or when a teammate hands you
a plain branch you want to stack on top of.

Source: <https://graphite.dev/docs/collaborate-on-a-stack>.

### `gt log` / `gt ls` — inspect the stack

```bash
gt log                       # full per-branch detail (PR status, worktree locations)
gt log short                 # compact tree view
gt ls                        # alias for `gt log short`
gt info [branch]             # details for a single branch
```

Run `gt log short` before any restack or submit to confirm the stack looks
as you expect.

### `gt restack` — re-rebase upstack onto parent's tip

Most operations (`modify`, `sync`, `move`, `reorder`) call `gt restack`
implicitly. Run it explicitly when something feels stale after manual
history editing.

## Reorganizing the stack

| Command | Effect |
| --- | --- |
| `gt move --onto <base>` | Re-parent current branch (and its upstack) onto `<base>`. |
| `gt reorder` | Open editor to reorder branches in the current stack. |
| `gt fold` | Collapse current branch into its parent. `--keep` keeps the current name; `--stack` folds the whole stack. |
| `gt squash` (`gt sq`) | Squash all commits on current branch into one; restack upstack. |
| `gt split` (`gt sp`) | Split current branch by commit (`-c`), hunk (`-h`), or file (`-f`). |
| `gt absorb` (`gt ab`) | Auto-distribute staged hunks into the correct downstack commits. `-a` stages all; `--force` skips confirmation. |
| `gt pop` | Delete branch but keep changes in working tree. |
| `gt delete [name]` | Delete a branch. Flags: `-c/--close` (close PR), `-f/--force`, `--downstack`, `--upstack`. |

Source: <https://graphite.dev/docs/edit-branch-order>,
<https://graphite.dev/docs/squash-fold-split>.

## Navigation

```bash
gt checkout         # interactive picker
gt checkout <name>  # explicit
gt co -s            # restrict picker to ancestors/descendants of current branch
gt co -t            # jump to trunk
gt up [n]           # move n branches upstack (away from trunk); alias `gt u`
gt down [n]         # move n branches downstack; alias `gt d`
gt top              # alias `gt t`
gt bottom           # alias `gt b`
gt parent / gt children
```

## Conflict recovery — the `gt continue` / `gt abort` flow

When `gt modify`, `gt sync`, `gt move`, `gt reorder`, `gt restack`, etc.
hit a rebase conflict, `gt` halts and prints which branch is being
resolved.

```bash
# 1. Resolve the conflict in the working tree
git status                   # shows conflicted paths
# … edit files, remove <<<<<<< markers …

# 2. Mark resolved
git add .                    # or `git add path/to/resolved` for specific files

# 3. Resume the broader Graphite operation — NOT bare git rebase --continue
gt continue                  # -a stages everything before continuing (equivalent to step 2 + this)
```

Critical: **always use `gt continue` / `gt abort`**, never bare
`git rebase --continue` / `--abort`. The latter only continues the
immediate rebase step; the broader Graphite walk doesn't know to advance
and metadata stays inconsistent.

Other recovery commands:

- `gt abort` — cancel the entire halted Graphite operation. `-f` skips confirmation.
- `gt undo` — rewind the most recent Graphite mutation in **this worktree**.
  Per-worktree history; refuses to touch a branch checked out elsewhere.

Source: <https://graphite.dev/docs/update-mid-stack-branches>.

There is **no documented `gt skip`** in v1.8.4. To skip a problematic
branch during a stack-wide restack, `gt abort` and handle it in isolation.

## Pulling someone else's stack — `gt get`

```bash
gt get                       # fetch teammates' submitted stacks; branches arrive frozen by default
gt get -U                    # unfrozen (editable immediately)
gt get -d                    # downstack only
gt get --no-restack          # skip the trunk-restack step
gt get --no-checkout         # don't switch branches
gt get --delete-all          # skip cleanup prompts
gt freeze / gt unfreeze      # toggle frozen state later
```

Source: <https://graphite.dev/docs/collaborate-on-a-stack>.

## Config files

| File | Scope | Contents |
| --- | --- | --- |
| `~/.config/graphite/user_config` | user (XDG-overridable) | user preferences, telemetry opt-out |
| `~/.graphite_user_config` | user | auth token (set by `gt auth`) |
| `.git/.graphite_repo_config` | repo | trunks, remote name, GitHub owner/name |

`gt config` is an interactive menu — there's no `gt config --key value`
form. Trunk, submit defaults, branch naming live behind those prompts.

Environment overrides:

- `GRAPHITE_AUTH_TOKEN` — auth without writing to disk (v1.8.3+).
- `GRAPHITE_IGNORE_GIT_VERSION=1` — bypass git-version check.

## Monorepo / multi-trunk / worktrees / GHES

- **Multiple trunks**: add with `gt trunk --add <branch>` or via the
  `gt config` menu. Many commands accept `--all` to operate across all
  trunks (`gt checkout --all`, `gt log --all`).
- **Worktrees** (v1.8.4+): `gt` refuses to mutate a branch checked out in
  another worktree. `gt sync` and `gt get` can still update trunk across
  worktrees. `gt undo` history is per-worktree.
- **GitHub Enterprise Cloud**: works out of the box.
- **GitHub Enterprise Server (self-hosted)**: requires Graphite Enterprise
  plus IP allowlist coordination with Graphite support. No self-serve path.

Source: <https://graphite.dev/docs/multiple-trunks>,
<https://graphite.dev/docs/multiple-worktrees>,
<https://graphite.dev/docs/github-enterprise-server>.

## Global flags (every command)

- `--cwd <dir>` — run as if from `<dir>`.
- `--no-interactive` — disable prompts / pagers / editors. **Essential when
  driving `gt` from an agent.**
- `--no-verify` — bypass git hooks for that invocation.
- `--quiet` — minimize output (implies `--no-interactive`).
- `--debug` — verbose debug output.
- `--help` / `--help --all` — list every command (the latter includes hidden ones).

## Recipes

### Open a new 2-PR stack from a clean trunk

```bash
gt sync                              # ensure trunk fresh
gt create -am "feat: part 1"
gt create -am "feat: part 2"
gt submit --stack --reviewers alice
```

### Address review feedback on the bottom PR

```bash
gt checkout part_1
# … edit files …
gt modify -cam "address review"      # new commit, auto-restacks part_2
gt submit --stack
```

### Sync trunk into your stack and resubmit

```bash
gt sync
# if conflicts: resolve files, `gt add .`, `gt continue`
gt submit --stack
```

### Split a sprawling branch into a stack

```bash
gt checkout big_branch
gt split --by-commit                 # or --by-hunk / --by-file
gt submit --stack
```

### Adopt a teammate's plain-git branch as your base

```bash
git pull
gt track                             # prompts for parent
gt create -am "build on top"
gt submit --stack
```

### Bootstrap retrofit: iter 1 plain-git → adopt later

When a workflow has to start before `gt` is available, use plain git for
iteration 1 and adopt it later:

```bash
# Iteration 1 — gt not present yet
git checkout -b feat/skill-first main
# … work, commit …

# Iteration 2+ — gt now available; bring iter 1 into the stack
git checkout feat/skill-first
gt track --parent main
gt create feat/skill-second -m "feat: second slice"
# … and so on …
```

`gt track` only edits Graphite metadata, not commits — the retrofit is
free.

### Recover from a botched operation

```bash
gt undo                              # rewind the last gt mutation
# or, mid-conflict:
gt abort                             # cancel the whole halted gt command
```

## Agent gotchas

- `gt` is **interactive by default**. Pass `--no-interactive` and supply
  `-m`, `-a`, branch names, etc. explicitly, or commands will hang waiting
  on a TTY.
- `gt submit` does a force push (default `--force-with-lease`). Only pass
  `-f/--force` after verifying no concurrent updates.
- After a conflict, **always** `gt continue` / `gt abort` — never bare
  `git rebase --continue` / `--abort`.
- `gt submit` refuses to push when branches aren't properly restacked.
  `gt restack` (or fix conflicts via `gt continue`) before retrying.
- In CI / ephemeral environments, set `GRAPHITE_AUTH_TOKEN` rather than
  running `gt auth` — the latter writes to `~/.graphite_user_config` and
  may fail when home is non-persistent.

## Primary sources

- Install: <https://graphite.dev/docs/install-the-cli>
- Quick start: <https://graphite.dev/docs/cli-quick-start>
- Create a stack: <https://graphite.dev/docs/create-stack>
- Update mid-stack branches: <https://graphite.dev/docs/update-mid-stack-branches>
- Submit PRs: <https://graphite.dev/docs/create-submit-prs>
- Collaborate on a stack: <https://graphite.dev/docs/collaborate-on-a-stack>
- Edit branch order: <https://graphite.dev/docs/edit-branch-order>
- Squash, fold, split: <https://graphite.dev/docs/squash-fold-split>
- Multiple trunks: <https://graphite.dev/docs/multiple-trunks>
- Worktrees: <https://graphite.dev/docs/multiple-worktrees>
- GHES: <https://graphite.dev/docs/github-enterprise-server>
- Configure CLI: <https://graphite.dev/docs/configure-cli>
