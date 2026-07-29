# Graphite publication

Use when `gt` is installed, Graphite tracks the current stack, and
`test -f "$(git rev-parse --git-dir)/.graphite_repo_config"` succeeds.

## Agent-safe discipline

Graphite is interactive by default. Pass `--no-interactive` and supply branch
names, messages, bases, and reviewers explicitly. If an operation still needs
an editor or picker, stop and ask rather than hanging or guessing.

Create branches with `gt create <name>` without all-files commit flags. Stage
named paths, then create a normal new commit. For a tracked branch update,
`gt modify -c -m "<message>"` creates a new commit and restacks descendants.
Bare `gt modify` amends; use it only when the user explicitly requests a
history rewrite. Hooks remain enabled.

Inspect with `gt log short`. Restack with `gt restack`; sync trunk and prune
merged branches with `gt sync`. Submit the whole chain with
`gt submit --stack`. Its lease-aware push is the publication path; do not push
one stack branch separately.

## Install, authenticate, and detect

- Install with `brew install withgraphite/tap/graphite` or
  `npm install -g @withgraphite/graphite-cli@stable`.
- Check `gt --version`; use `gt upgrade` on supported releases.
- Authenticate with `gt auth --token <token>`; ephemeral environments prefer
  `GRAPHITE_AUTH_TOKEN`.
- Initialize once with `gt init`; it records trunk at
  `$(git rev-parse --git-dir)/.graphite_repo_config`.
- The provider is usable only when the executable and resolved marker exist.

## Command map

| Need | Command |
| --- | --- |
| Start/extend a stack | `gt create <name>` |
| Adopt an existing branch | `gt track --parent <parent>` |
| Remove tracking | `gt untrack` |
| Inspect | `gt log short` or `gt ls` |
| Navigate | `gt up`, `gt down`, `gt top`, `gt bottom` |
| Check out | `gt checkout <branch>` |
| New commit + restack | `gt modify -c -m "<message>"` after named staging |
| Restack descendants | `gt restack` |
| Fetch trunk, prune, restack | `gt sync` |
| Submit all PRs | `gt submit --stack` |
| Update open PRs only | `gt submit --stack --update-only` |
| Preview | `gt submit --stack --dry-run` |

Submission may add `--draft`, `--publish`, or explicit reviewers. Retain the
default lease check rather than selecting true force.

## Reorganization

Use Graphite commands so lineage remains correct:

| Need | Command and rule |
| --- | --- |
| Move a branch and descendants | `gt move --onto <parent>` |
| Reorder | `gt reorder`; user-driven editor only |
| Split | `gt split -c`, `gt split -h`, or `gt split -f`; verify every resulting boundary |
| Absorb staged hunks downstack | `gt absorb` after named staging; keep confirmation enabled |
| Fold into parent | `gt fold`; explicit history-rewrite approval required |
| Squash current layer | `gt squash`; explicit history-rewrite approval required |
| Remove branch, keep changes | `gt pop`; explicit destructive approval required |
| Undo last Graphite mutation | `gt undo`; inspect before and after |
| Delete branch | `gt delete`; explicit branch-deletion approval required |

After any split, absorb, move, fold, squash, pop, or undo, inspect
`gt log short`, validate affected layers, and resubmit only after lineage and
commit paths match the approved split.

## Collaboration, frozen branches, and multiple trunks

`gt get <branch>` fetches a collaborator's submitted stack. Retrieved branches
are frozen by default; inspect them without mutation. Use `gt unfreeze` only
after the user confirms ownership/coordination, and `gt freeze` to restore the
read-only collaboration posture. `gt get -U` opts into immediate editability;
never choose it silently.

For repositories with several trunks, add one with
`gt trunk --add <branch>`. Use `gt log --all` or `gt checkout --all` for
cross-trunk inspection, but select the intended trunk explicitly before
creating lineage. Graphite refuses to mutate a branch checked out in another
worktree; report that worktree rather than bypassing the refusal. `gt undo`
history is per worktree.

## Conflict recovery

Resolve and stage each conflicted path by name, then run `gt continue` or
`gt abort`. A bare `git rebase --continue` is never the recovery path because
Graphite must advance its stack metadata. There is no documented `gt skip`;
abort and isolate the branch instead.

## Plate recipes

### Create a two-layer stack

1. From clean trunk, run `gt create <bottom>`.
2. Write bottom/common artifacts, validate, stage named paths, and commit.
3. Run `gt create <top>`; repeat the per-layer transaction for top-only work.
4. Inspect with `gt log short`.
5. Publish with `gt submit --stack` and verify every PR/base pair.

### Update a lower layer

Check out the lower branch, stage named paths, create a new commit with
`gt modify -c`, run `gt restack`, inspect, then `gt submit --stack`.

### After the bottom PR merges

Run `gt sync`, inspect `gt log short`, then submit only if local commits
remain unpublished.

Shared durable writes belong on the bottom/common branch or an explicit wiring
branch. Confirm version-specific syntax with `gt <command> --help`.
