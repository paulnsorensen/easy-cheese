# Stack maintenance

Load this reference for the **stack maintenance** mode, and for any new or
existing PR whose resolved topology is stacked. Ordinary single-PR work never
reads this file.

## Per-layer stack transaction

1. Select the configured provider and read its reference.
2. Require explicit split boundaries. Partition paths and commits by layer.
   Place shared durable writes on the bottom/common layer or an explicit wiring layer.
   Classify the production implementation decision. Tests, docs, and durable artifacts inherit its layer.
   They inherit the layer when they directly verify or describe the decision.
   Each layer's implementation preserves semantics or alters them, never both.
   Put semantics-preserving layers below the semantic changes that depend on their reorganization.
3. Create or adopt provider lineage in the approved bottom-to-top order.
4. For **each layer**, bottom to top:
   1. Check out its provider-tracked branch.
   2. Run the final writing gate for that layer and read every write back.
   3. Run the repository quality gate.
   4. Inspect the layer diff and stage only its named paths.
   5. Create a new Conventional Commit without skipping hooks.
   6. Verify the commit's paths and the layer's parent.
5. Inspect or restack the complete chain through the provider.
6. Submit the complete chain after you verify all layers.
7. Read back every PR, base and head pair, and provider stack map.

Never manufacture split boundaries. Never move a shared artifact to a convenient upper layer.
Never submit a partially verified chain.

## Stack provider detection

Resolve metadata through `GIT_DIR="$(git rev-parse --git-dir)"`; never assume
the repository metadata directory is the literal `.git` path.

| Provider | Installed | Repository signal | Reference |
| --- | --- | --- | --- |
| Graphite | `gt --version` | `$GIT_DIR/.graphite_repo_config` | [`gt.md`](gt.md) |
| Git Town | `git town --version` | `git-town.main-branch` config | [`git-town.md`](git-town.md) |
| `gh stack` | `gh extension list` contains `github/gh-stack` | `gh api --include "repos/{owner}/{repo}/stacks"` preflight | [`gh-stack.md`](gh-stack.md) |

Use the `stack-tools` report on every invocation. Preserve the provider that already tracks the branch.
When no provider tracks it, use the report's `recommended` provider. State the choice.
Only a `gh-stack` status of `not-enabled` (preflight `404`) is a repository enablement requirement.
Other non-`available` statuses are environment failures. Exit code 4 remains the fallback.
If no provider is usable after stacked was selected, stop with setup instructions.
Do not emulate stacking with plain pushes.

## Existing stacked PR updates

Use `gh pr view --json number,baseRefName,headRefName,url` to detect the PR.
Then inspect the provider metadata. Use the per-layer transaction when the topology is a stack.
Use the provider submission process. Never use a bare single-branch push inside the stack.
An ordinary PR uses the generic transaction and `ordinary-pr.md` instead.

Run provider-native stack shipping in `/plate` only when the user explicitly requests the merge.
Require explicit user authorization for a force-push outside a provider's lease-safe stack flow.
