# New-PR topology policy

Load this reference for the **topology preflight** and **new PR** modes. It
resolves the review shape only; execution continues in `ordinary-pr.md` for a
single PR or in `stacks.md` for a stacked chain.

For a **new PR**, resolve topology before any commit or branch-layout mutation:

1. Honor an explicit user choice from the current request or verified workflow
   state. It is authoritative, so persist it and skip the topology question.
2. Otherwise inspect the finished work's review shape:
   - First classify each production change as **semantics-altering** (features,
     fixes, or externally observable contract changes) or
     **semantics-preserving** (behavior-preserving refactors, mechanical
     internal moves or renames, formatting-only changes). A diff containing
     both is never one review unit, however small: preserved behavior and
     changed behavior demand different review scrutiny. Fix-ups done "along
     the way" get their own change; they never ride along on a feature or fix.
     Treat any move or rename that changes an externally observable name, path,
     API, configuration key, serialized shape, command, or documented contract
     as semantics-altering.
   - Choose **single** and proceed without asking when the change is one
     cohesive review unit: its implementation, tests, docs, and durable
     artifacts all serve one behavior or contract, and splitting them would
     leave incomplete behavior or force reviewers to reconstruct the whole.
   - Recommend **stacked** when the change has independently reviewable ordered
     layers. Each layer needs a named purpose, its own validation, and a stable
     boundary: a lower layer can be understood on its own, and later layers
     build on it without mixing unrelated concerns. A change is also stack-sized
     when one review would combine distinct concerns that have honest ordered
     boundaries — canonically, a semantics-preserving layer below the
     semantics-altering layer that depends on the reorganization.
     Do not use line-count or file-count thresholds.
3. Ask one single-versus-stacked question when stacked is recommended or the
   review shape is genuinely ambiguous. For a stack recommendation, name the
   proposed layers and recommend **Stacked PRs**. For ambiguity, state the
   competing evidence and recommend the best-supported option rather than
   choosing silently.

This policy is unchanged under `--auto`. Transport any required question
through
[`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md).

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

Topology preflight persists the resolution, reads it back, and stops before any
commit, branch mutation, push, or PR operation.

## Repair-worktree topology

A branch created by the repair pathway
([`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md)
§ Repair pathway; branch name `worktree-agent-repair-*`) resolves topology
through that pathway's mechanical file-overlap check before this section's
policy: no shared files (or the originating run branch is already gone) plates
an ordinary independent PR against `main`; shared files at or under the
small-repair threshold harvest onto the run branch instead of publishing;
shared files over threshold restack with the repair as the base PR through the
stack machinery in `stacks.md`. Any other branch uses the policy above
unchanged.
