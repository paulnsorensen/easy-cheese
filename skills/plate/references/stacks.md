# Stack maintenance

Load this reference for the **stack maintenance** mode, and for any new or
existing PR whose resolved topology is stacked. Ordinary single-PR work never
reads this file.

## Per-layer stack transaction

1. Select the configured provider and read its reference.
2. Require explicit split boundaries. Partition paths and commits by layer;
   place shared durable writes on the bottom/common layer or an explicit
   wiring layer. Classify the production implementation decision; tests, docs,
   and durable artifacts inherit its layer when they directly verify or
   describe it. Every layer's implementation either preserves semantics or
   alters them, never both, and semantics-preserving layers sit below the
   semantic changes that depend on their reorganization.
3. Create or adopt provider lineage in the approved bottom-to-top order.
4. For **each layer**, bottom to top:
   1. Check out its provider-tracked branch.
   2. Run the final writing gate for that layer and read every write back.
   3. Run the repository quality gate.
   4. Inspect the layer diff and stage only its named paths.
   5. Create a new Conventional Commit without skipping hooks.
   6. Verify the commit's paths and the layer's parent.
5. Inspect or restack the complete chain through the provider.
6. Submit the complete chain once all layers are verified. Read back every PR,
   base/head pair, and provider stack map.

Never manufacture split boundaries, move a shared artifact to a convenient
upper layer, or submit a partially verified chain.

## Stack provider detection

Resolve metadata through `GIT_DIR="$(git rev-parse --git-dir)"`; never assume
the repository metadata directory is the literal `.git` path.

| Provider | Installed | Repository signal | Reference |
| --- | --- | --- | --- |
| Graphite | `gt --version` | `$GIT_DIR/.graphite_repo_config` | [`gt.md`](gt.md) |
| Git Town | `git town --version` | `git-town.main-branch` config | [`git-town.md`](git-town.md) |
| `gh stack` | `gh extension list` contains `github/gh-stack` | `gh api --include "repos/{owner}/{repo}/stacks"` preflight | [`gh-stack.md`](gh-stack.md) |

Use the `stack-tools` report on every invocation. If several providers are
usable, preserve the one already tracking the branch. When none tracks it,
use the report's `recommended` provider and state the choice. Only a `gh-stack`
status of `not-enabled` (preflight `404`) is the repository-enablement
requirement; other non-`available` statuses are environment failures that leave
exit code 4 as the fallback. If no provider is usable after stacked was
selected, stop with setup instructions; do not emulate stacking with plain
pushes.

## Existing stacked PR updates

Use `gh pr view --json number,baseRefName,headRefName,url` to detect the PR,
then inspect provider metadata. When the topology is a stack, use the per-layer
transaction above and provider submission; never use a bare single-branch push
inside the stack. An ordinary PR uses the generic transaction and
`ordinary-pr.md` instead.

Provider-native stack shipping runs in `/plate` only when the user explicitly
requests the merge. Force-push outside a provider's lease-safe stack flow
requires explicit user authorization.
