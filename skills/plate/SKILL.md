---
name: plate
description: >
  Turn finished local work into a commit, an ordinary pull request, or a
  stacked pull-request chain. Use when asked to commit, save changes, open or
  update a PR, publish a branch, create/sync/restack/submit a PR stack, or run
  /plate. Owns all staging, committing, pushing, PR creation, and stack-aware
  mutation. GitHub inspection, review, comments, CI, issues, releases, and
  repository administration remain /gh.
license: MIT
---

# /plate

Plate is the final local-to-review transaction: finish required artifacts,
validate, commit safely, then publish through the repository's ordinary or
stack-aware path.

## Inputs and modes

- **Commit-only** — save local work without publishing it.
- **Topology preflight** — answer and persist the new-PR layout before another
  workflow creates commits or branches.
- **New PR** — no PR exists for the branch and publication is requested.
- **Existing PR** — update a PR while preserving its current topology.
- **Stack maintenance** — create, inspect, sync, restack, submit, recover, or
  explicitly ship a stack through its provider.

Accept `--hard` to run `/hard-cheese` immediately before the first
share-for-review operation. Give that gate the final artifact inventory and
verification rows, not an earlier implementation-only snapshot.

## New-PR topology policy

For a **new PR**, resolve topology before any commit or branch-layout mutation:

1. Honor an explicit user choice from the current request or verified workflow
   state. It is authoritative, so persist it and skip the topology question.
2. Otherwise inspect the finished work's review shape:
   - Choose **single** and proceed without asking when the change is one
     cohesive review unit: its implementation, tests, docs, and durable
     artifacts all serve one behavior or contract, and splitting them would
     leave incomplete behavior or force reviewers to reconstruct the whole.
   - Recommend **stacked** when the change has independently reviewable ordered
     layers. Each layer needs a named purpose, its own validation, and a stable
     boundary: a lower layer can be understood on its own, and later layers
     build on it without mixing unrelated concerns. A change is also stack-sized
     when one review would combine distinct concerns that have honest ordered
     boundaries. Do not use line-count or file-count thresholds.
3. Ask one single-versus-stacked question when stacked is recommended or the
   review shape is genuinely ambiguous. For a stack recommendation, name the
   proposed layers and recommend **Stacked PRs**. For ambiguity, state the
   competing evidence and recommend the best-supported option rather than
   choosing silently.

This policy is unchanged under `--auto`. Transport any required question
through
[`../cheese/references/ask-user-question.md`](../cheese/references/ask-user-question.md).

```yaml
question:
  id: plate-layout
  prompt: How should this work be plated for review?
  recommended: <single | stacked>
  multi: false
  options:
    - id: single
      label: Single PR
      description: Keep the cohesive change as one branch and one review unit.
    - id: stacked
      label: Stacked PRs
      description: Split the named layers into ordered branches and dependent PRs.
```

A supplied `pr_plan` is evidence for a stack recommendation and may provide
explicit commit/file boundaries. It cannot override an explicit user choice or
another verified topology resolution. If stacked is selected but neither the
user nor the plan supplies clear boundaries, ask for the split rather than
inventing it.

A prior `/plate` **topology preflight** for the same run is the resolution,
whether it was explicit, inferred as cohesive, or confirmed after a question.
Persist it as `plate_layout: single | stacked` in workflow state and copy it
into any later `pr_plan`. At terminal publication, verify both values agree
and reuse the resolution; do not ask twice. A missing, conflicting, or
unverified record re-runs this policy rather than automatically asking.

For an **Existing PR**, detect its ordinary or stacked topology and do not ask
the layout question. Preserve that topology and use its matching update path.
Commit-only isolated workers also do not ask because publication is out of
scope.

### Repair-worktree topology

A branch created by the repair pathway ([`../cook/references/quality-gates.md`](../cook/references/quality-gates.md) § Repair pathway; branch name `worktree-agent-repair-*`) resolves topology through that pathway's mechanical file-overlap check before this section's policy: no shared files (or the originating run branch is already gone) plates an ordinary independent PR against `main`; shared files at or under the small-repair threshold harvest onto the run branch instead of publishing; shared files over threshold restack with the repair as the base PR through the stack machinery below. Any other branch uses the policy above unchanged.

## Flow

1. **Classify** — commit-only, topology preflight, new PR, existing PR, or
   stack maintenance.
2. **Resolve topology** — honor an explicit choice, infer an obviously cohesive
   single PR, ask when stacked is recommended or shape is ambiguous, or detect
   existing topology from PR and stack metadata.
3. **Choose the transaction**:
   - Commit-only and ordinary PR work use the generic transaction below.
   - Stacked work uses the per-layer stack transaction below.
   - Topology preflight persists the resolution, reads it back, and stops before
     any commit, branch mutation, push, or PR operation.

### Generic transaction

1. **Final writing gate** — inventory, write, and read back every promised or
   required artifact using
   [`references/durable-writes.md`](references/durable-writes.md). Halt if
   any required write is missing or unverified.
2. **Validate** — run the repository's shippability gate. In easy-cheese and
   any repo that defines it, this is `just check`. Never commit or publish on
   red.
3. **Inspect** — read status, diff, and recent log; verify the intended file
   set.
4. **Stage** — add named files only. Never stage the whole tree. Keep transient
   `.cheese/` reports unstaged; include tracked wiki/docs writes.
5. **Commit** — use a Conventional Commit message focused on why. Do not amend
   unless explicitly requested and do not bypass hooks.
6. **Verify** — inspect status and the committed file set.
7. **Publish when requested** — use
   [`references/ordinary-pr.md`](references/ordinary-pr.md), then read the PR
   back and verify it.

Commit-only mode stops after verification. It never pushes or opens a PR.

### Per-layer stack transaction

1. Select the configured provider and read its reference.
2. Require explicit split boundaries. Partition paths and commits by layer;
   place shared durable writes on the bottom/common layer or an explicit
   wiring layer.
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

## Commit contract

Before staging, inspect `git status`, the complete diff, and recent commits.
Reject credentials, `.env` files, and unexplained large binaries. Stage every
intended path explicitly. Use:

```text
type(scope): short description

Optional body when the rationale needs it.
```

Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`,
`style`. If a hook fails, fix it, re-run the writing and quality gates when
artifacts changed, re-stage named files, and create a new commit.

Use a single-quoted heredoc delimiter for multi-line commit messages so shell
interpolation cannot alter backticks or dollar signs. An optional
`Co-Authored-By: <name> <email>` trailer may use the harness identity when the
project accepts it; otherwise omit it. After staging, inspect the cached diff.
If the working diff is empty, distinguish "nothing to commit" from "everything
is staged" by checking the cached diff.

## Ordinary PR publication

Read [`references/ordinary-pr.md`](references/ordinary-pr.md). Draft the title
and body from the validated diff and commits. Write the PR body to a file and
use `gh pr create --body-file`; never embed a markdown heredoc in `--body`.
Push the named branch, create the PR with explicit base/head, then read it back
with `gh pr view` to verify number, URL, base, head, and state.

## Stack provider detection

Resolve metadata through `GIT_DIR="$(git rev-parse --git-dir)"`; never assume
the repository metadata directory is the literal `.git` path.

| Provider | Installed | Repository signal | Reference |
| --- | --- | --- | --- |
| Graphite | `gt --version` | `$GIT_DIR/.graphite_repo_config` | [`gt.md`](references/gt.md) |
| Git Town | `git town --version` | `git-town.main-branch` config | [`git-town.md`](references/git-town.md) |
| `gh stack` | `gh extension list` contains `github/gh-stack` | remote enablement is detected on operation | [`gh-stack.md`](references/gh-stack.md) |

Run probes on every invocation. If several providers are usable, preserve the
one already tracking the branch. When none tracks it, prefer Graphite, then Git
Town, then `gh stack`, and state the choice. If no provider is usable after
stacked was selected, stop with setup instructions; do not emulate stacking
with plain pushes.

## Existing PR updates

Use `gh pr view --json number,baseRefName,headRefName,url` to detect the PR,
then inspect provider metadata. Ordinary PR: use the generic transaction and
push its named head branch. Stack: use the per-layer transaction and provider
submission; never use a bare single-branch push inside the stack.

## Boundaries

- `/plate` owns staging, commits, pushes, ordinary PR creation/update, and
  stack creation/update/sync/recovery. Provider-native stack shipping runs here
  only when the user explicitly requests the merge.
- `/gh` owns GitHub inspection, review, comments, CI, ordinary merge, issues,
  workflows, releases, search, and administration when no local publication
  transaction is required.
- `/plate` never performs code-quality review; use `/age`.
- Destructive deletion, history rewrites, force-push outside a provider's
  lease-safe stack flow, and protected-branch mutation require explicit user
  authorization.

## Completion

Report mode, topology/provider, artifact completion rows, quality-gate result,
commit SHA(s), PR URL(s) when published, and any remaining risk.
