# Git Town publication

Use when `git-town` is installed and `git-town.main-branch` is configured.
Lineage lives in local `git-town-branch.<name>.parent` config.

## Mandatory agent mode

Append `--non-interactive` to every state-changing Git Town command and supply
names, parents, messages, and merge choices explicitly. Use `--dry-run` first
for risky sync or reorganization when supported. If required input is missing,
stop and ask; never allow an agent-run command to wait on a prompt.

Start the bottom branch with `git town hack <name> --non-interactive` and
extend with `git town append <name> --non-interactive`. Stage named paths and
create normal new commits; avoid combined all-files or rewrite flags.

Inspect with `git town branch`. Publish the chain with
`git town propose --stack --non-interactive`. Sync/restack with
`git town sync --stack --non-interactive`; use `--no-push` only when
publication is not authorized. Never push one stack branch directly.

## Install, configure, and detect

- Install with `brew install git-town`, `choco install git-town`, or
  `scoop install git-town`; check `git town --version`.
- Configure with `git town config setup`, or set trunk directly using
  `git config --local git-town.main-branch <trunk>`.
- On GitHub, prefer `git-town.github-connector gh` to reuse authenticated CLI
  access; environment tokens are preferable in ephemeral systems.
- Usability requires the executable and a non-empty `git-town.main-branch`.
  Inspect parents with `git config --get-regexp '^git-town-branch\.'`.
- Resolve repository metadata with `git rev-parse --git-dir` when inspecting
  git-owned state; never assume a literal metadata path.

Git Town is forge-agnostic. Configure `git-town.forge-type` when forge
auto-detection is wrong.

## Branch creation, types, and configuration

| Need | Command |
| --- | --- |
| Start bottom from trunk | `git town hack <name> --non-interactive` |
| Extend current stack | `git town append <name> --non-interactive` |
| Insert below current | `git town prepend <name> --non-interactive` |
| Create local-only work | add `--prototype` to hack/append/prepend |
| Record/change parent | `git town set-parent <parent> --non-interactive` |
| Detach as perennial | `git town set-parent --none --non-interactive` |
| Inspect lineage/types | `git town branch` |
| Read a parent | `git town config get-parent [branch]` |
| Rename | `git town rename <name> --non-interactive` |
| Delete | `git town delete --non-interactive`; explicit approval required |
| Interrupted state | `git town status --pending` |

Branch types are `feature`, `prototype`, `parked`, `contribution`, and
`observed`, stored in `git-town-branch.<name>.branchtype`. Long-lived shared
branches belong in `git-town.perennial-branches`. Repository defaults may live
in `git-town.toml`; forge/auth settings use `git-town.forge-type`,
`git-town.github-connector`, and the matching token setting or environment
variable.

Prototype branches remain local until proposed. Do not silently convert a
prototype to a published feature branch.

## Sync variants

| Scope or behavior | Command |
| --- | --- |
| Current branch | `git town sync --non-interactive` |
| Current stack | `git town sync --stack --non-interactive` |
| Every branch | `git town sync --all --non-interactive` |
| Skip trunk/perennial pull-in | `git town sync --detached --non-interactive` |
| Restack locally without push | `git town sync --stack --no-push --non-interactive` |
| Prune branches that become empty | `git town sync --prune --non-interactive` |
| Open/update stack PRs | `git town propose --stack --non-interactive` |

Use `--all`, `--detached`, and `--prune` only when their wider scope or
deletion behavior is intended and verified.

## Ship

`git town ship --non-interactive` merges the current branch through the forge.
`--to-parent` ships into a non-perennial parent; an explicit message can be
provided when required. Prefer the forge UI plus
`git town sync --stack --non-interactive` for routine merges. Run `ship`
through Plate only when the user explicitly requested provider-native stack
shipping, verify the target and merge strategy, and confirm the installed
syntax with `git town ship --help`.

## Conflict recovery

When sync, propose, or ship halts, inspect `git town status --pending`.
Resolve and stage named paths, then use `git town continue`,
`git town skip`, or `git town undo` as directed by the pending operation.
A bare `git rebase --continue` is never correct because it does not advance
Git Town's branch walk.

Git Town can force-update rebased stack branches; coordinate when teammates
also write them. Shared durable writes belong on the bottom/common branch or
an explicit wiring branch before propose or sync.

## Plate recipes

### Create a two-layer stack

1. Run `git town hack <bottom> --non-interactive`.
2. Write common artifacts, validate, stage named paths, and commit.
3. Run `git town append <top> --non-interactive`; repeat for top-only work.
4. Run `git town branch` to verify parents.
5. Run `git town propose --stack --non-interactive`, then verify PR bases.

### Adopt an existing branch

Sync it, set its parent non-interactively, inspect lineage, append branches if
requested, then propose the stack.

### Update a lower branch

Switch to it, create a new commit, then sync the stack non-interactively so
descendants and remote PRs follow.

Squash merges can create phantom conflicts because child history no longer
matches the merged commit. Configure `git-town.auto-resolve` or use a
compatible merge strategy when the repository accepts it. Confirm
version-specific syntax with `git town <command> --help`.
