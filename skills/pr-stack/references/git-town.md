# `git town` (Git Town) reference

Reference for driving Git Town on behalf of a user who already has
`git-town` installed and the repo configured. Targets `git-town` v23+.
Flags drift between majors (v23 reworked the `up` / `down` navigation
commands) — when in doubt, fall back to `git town <cmd> --help`.

The shared mental model and tool-selection rules live in `../SKILL.md`. This
file is the `git town`-side detail.

## What makes it different

- **No account, offline-first.** Unlike Graphite (`gt`), Git Town needs no
  SaaS sign-up. All branch lineage lives in local git config — nothing is
  stored server-side.
- **Forge-agnostic.** Works against GitHub, GitLab, Gitea, Forgejo,
  Bitbucket (cloud + Data Center), and Azure DevOps. Override
  auto-detection with `git config git-town.forge-type <forge>`.
- **Stacked changes are first-class and stable** — the docs ship a dedicated
  "Stacked Changes" page, and `propose --stack` has been stable since the
  v14 series (mid-2024).

Source: <https://www.git-town.com/stacked-changes>,
<https://www.git-town.com/preferences/forge-type>.

## Install paths

- **Homebrew** (recommended on macOS / Linux): `brew install git-town`
- **Windows**: `choco install git-town` or `scoop install git-town`
- **Binary**: `curl https://www.git-town.com/install.sh | sh` — review the script first (or use a package-manager path above); don't pipe an unreviewed remote script straight to `sh`.
- **From source**: `go install github.com/git-town/git-town/v23@latest`
  (bump the major suffix to match the installed release).
- Version check: `git town --version`.

Source: <https://www.git-town.com/install>.

## First-time setup

1. **Configure the repo** (once):

   ```bash
   git town config setup                  # interactive wizard (recent builds; older ones used `git town init` — confirm with `git town --help`)
   git config --local git-town.main-branch main   # or set the trunk directly, no wizard
   ```

   The direct `git config` form is the one the detection probe below reads,
   and works with no prompts — prefer it when driving from an agent.

2. **Forge auth** — pick one:

   ```bash
   git config --local git-town.github-connector gh   # reuse the gh CLI's existing auth (cleanest if gh is set up)
   git config --local git-town.github-token ghp_xxx  # or a PAT, stored in local git config
   export GIT_TOWN_GITHUB_TOKEN=ghp_xxx      # or an env var (CI / ephemeral homes)
   ```

   For other forges, set `git-town.forge-type` (`gitlab` / `gitea` /
   `bitbucket` / `forgejo` / `azuredevops`) and the matching `*-token` key
   (e.g. `git-town.gitlab-token`).

Source: <https://www.git-town.com/preferences/github-connector>,
<https://www.git-town.com/preferences/main-branch>.

### Detection probes

- `git-town` installed: `command -v git-town && git town --version`
  (non-zero if missing).
- Repo configured: `git config --local --get git-town.main-branch` — a non-empty
  result means Git Town knows this repo's trunk. This is the on-disk marker;
  prefer it over running a `git town` command, which prompts when
  unconfigured.
- Any stack tracked: `git config --get-regexp '^git-town-branch\.'` — each
  `git-town-branch.<name>.parent` row is one tracked branch.

## Mental model recap

- **Trunk** is the `git-town.main-branch` (usually `main`). Long-lived
  shared branches are **perennial** (`git-town.perennial-branches`).
- Each feature branch records its **parent** in git config
  (`git-town-branch.<name>.parent`). A stack is just a parent chain — there
  is no separate metadata file and no remote service.
- `git town` calls real `git` underneath, so hooks, `.gitignore`, and
  aliases still apply.

## Core stack commands

### Create a branch — `git town hack` / `append` / `prepend`

```bash
git town hack <name>      # new branch off MAIN/trunk — use to start a stack's root
git town append <name>    # new branch off the CURRENT branch — extends the stack
git town prepend <name>   # insert a new branch BETWEEN current and its parent
```

The hack-vs-append distinction is the whole stacking story: `hack` starts a
fresh chain from trunk; `append` grows the chain you're standing on. Shared
flags:

```bash
--prototype       # keep the branch local until you propose it
--propose         # create and immediately open a PR
--commit -m "…"   # commit the staged changes into the new branch
```

Source: <https://www.git-town.com/commands/hack>,
<https://www.git-town.com/commands/append>.

### Inspect the stack

```bash
git town branch                       # full branch lineage with branch types
git town switch                       # interactive picker showing the hierarchy
git town config get-parent [branch]   # parent of current (or named) branch
```

### `git town sync` — pull trunk, restack, push

```bash
git town sync                # current branch only
git town sync --stack        # every branch in the current stack (-s)
git town sync --all          # every branch in the repo
git town sync --detached     # don't pull trunk/perennial into the stack (-d; busy monorepos)
git town sync --no-push      # restack locally, skip the push (offline)
git town sync --prune        # drop branches that became empty (-p)
```

`git town sync` is the workhorse: it pulls trunk, rebases each branch onto
its parent's new tip, and force-pushes the updated branches.

Source: <https://www.git-town.com/commands/sync>.

### `git town propose` — open / update PRs for the stack

```bash
git town propose             # PR for the current branch; base auto-set to its parent
git town propose --stack     # one PR per branch in the stack (-s) — the stacking command
git town propose --title "…" --body "…"
git town propose --body-file pr-body.md
git town propose --no-browser
```

`propose --stack` opens (or updates) one PR per branch and sets each PR's
base to its **immediate parent**, so the chain reviews bottom-up — the same
shape `gt submit --stack` produces.

Source: <https://www.git-town.com/stacked-changes>.

### `git town set-parent` — adopt / re-parent a branch

```bash
git town set-parent              # interactive: prompts for the new parent
git town set-parent main         # non-interactive: positional arg is the new parent
git town set-parent --none       # detach (branch becomes perennial)
```

Use to pull a plain `git checkout -b` branch into a stack, or to move a
branch onto a new base. Run `git town sync` afterward to pull the new
parent's changes in.

Source: <https://www.git-town.com/commands/set-parent>.

### `git town ship` — merge a branch

```bash
git town ship                # ship the current branch via the forge API
git town ship --message "…"  # custom merge-commit message
git town ship --to-parent    # ship into a non-perennial parent
```

The **recommended** flow is to merge via the web UI and then run
`git town sync --stack` — that keeps the forge as the source of truth and
lets `sync` cascade the survivors. Reach for `git town ship` only when you
want the CLI to drive the merge. Confirm available merge strategies with
`git town ship --help` before passing one.

Source: <https://www.git-town.com/commands/ship>.

## Conflict recovery — `continue` / `skip` / `undo`

When `sync`, `propose`, `ship`, etc. hit a rebase conflict, `git town`
halts and records the pending step.

```bash
git town status                # show the halted state and what's available
git town status --pending      # machine-readable: prints the pending command name (or nothing)

# 1. resolve the conflict in the working tree, then:
git add <resolved paths>       # stage resolved paths by name, not the whole tree
# 2. resume — NOT bare git rebase --continue
git town continue              # re-run the halted command from where it stopped
git town skip                  # abandon the conflicting branch, continue with the rest
git town skip --park           # skip and permanently "park" that branch
git town undo                  # revert the last completed git-town command
```

Always use `git town continue` / `skip` / `undo`, never bare
`git rebase --continue` / `--abort` — only Git Town knows to advance the
rest of the branch walk and keep the parent metadata consistent.

Source: <https://www.git-town.com/commands/skip>,
<https://www.git-town.com/commands/status>.

## Other branch ops

```bash
git town rename <new-name>   # rename current branch, updating lineage
git town delete              # delete current branch and clean up its lineage
```

## Config keys (for scripting / detection)

| Key | Meaning |
| --- | --- |
| `git-town.main-branch` | trunk branch name |
| `git-town.perennial-branches` | space-separated long-lived branches |
| `git-town.forge-type` | `github` / `gitlab` / `gitea` / `bitbucket` / `forgejo` / `azuredevops` |
| `git-town.github-connector` | `gh` to reuse the gh CLI's auth |
| `git-town.github-token` | forge PAT (per-forge key: `gitlab-token`, …) |
| `git-town-branch.<name>.parent` | immediate parent of `<name>` |
| `git-town-branch.<name>.branchtype` | `feature` / `prototype` / `parked` / `contribution` / `observed` |

Repo defaults can also live in a committed `git-town.toml`. Environment
overrides use the `GIT_TOWN_*` prefix (e.g. `GIT_TOWN_GITHUB_TOKEN`).

## Global / agent flags (every command)

- `--non-interactive` — suppress all prompts. **Essential when driving
  `git town` from an agent**, or commands hang waiting on a TTY.
- `--dry-run` — print what would happen without changing anything.
- `--verbose` / `-v` — echo every underlying `git` command.

## Squash-merge gotcha

If the forge squash-merges PRs, Git Town can hit **phantom conflicts** when
rebasing survivors after the bottom branch ships — the squashed commit no
longer matches the child's history. Mitigate by enabling
`git config git-town.auto-resolve true` or by shipping with a fast-forward
strategy. Plain merge / rebase merges don't have this problem.

Source: <https://www.git-town.com/stacked-changes>.

## Recipes

### Open a new 2-PR stack from clean trunk

```bash
git town hack feat-part-1            # branch off trunk
# … edit, git add, git commit …
git town append feat-part-2          # branch off part-1
# … edit, git add, git commit …
git town propose --stack             # one PR per branch, bases auto-wired
```

### Address review feedback on a lower branch

```bash
git town switch feat-part-1          # or: git checkout feat-part-1
# … edit, git add, git commit …
git town sync --stack                # restack feat-part-2 onto the updated feat-part-1 and push
```

### After the bottom PR merges (via web UI)

```bash
git town sync --stack                # pulls trunk, drops the merged branch, rebases + pushes survivors
git town branch                      # confirm the chain looks right
```

### Adopt a plain-git branch as a stack base

```bash
git town sync                        # get the branch in sync first
git town set-parent main             # record its parent
git town append feat-next            # build on top
git town propose --stack
```

## Agent gotchas

- `git town` is **interactive by default**. Pass `--non-interactive` and
  supply names / messages explicitly, or commands hang waiting on a TTY.
- After a conflict, **always** `git town continue` / `skip` — never bare
  `git rebase --continue` / `--abort`; the broader walk won't advance.
- `git town sync` force-pushes the branches it rebases. Expected for a
  stack, but don't run it on a branch a teammate is also pushing to without
  coordinating.
- Prefer reusing `gh` auth (`git-town.github-connector gh`) over a stored
  PAT in shared / ephemeral environments.
- `git town status --pending` is the scriptable way to tell whether a halted
  command is waiting on you.

## Primary sources

- Install: <https://www.git-town.com/install>
- Stacked changes: <https://www.git-town.com/stacked-changes>
- Commands index: <https://www.git-town.com/commands>
- hack / append / prepend: <https://www.git-town.com/commands/hack>
- sync: <https://www.git-town.com/commands/sync>
- propose: <https://www.git-town.com/commands/propose>
- ship: <https://www.git-town.com/commands/ship>
- set-parent: <https://www.git-town.com/commands/set-parent>
- skip / continue / undo: <https://www.git-town.com/commands/skip>
- status: <https://www.git-town.com/commands/status>
- forge type: <https://www.git-town.com/preferences/forge-type>
- github connector: <https://www.git-town.com/preferences/github-connector>
