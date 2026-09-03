# New-PR topology policy

Load this reference for the **topology preflight** and **new PR** modes. It resolves only the review shape.
Execution continues in `ordinary-pr.md` for a single PR or in `stacks.md` for a stacked chain.

For a **new PR**, resolve topology before any commit or branch-layout mutation:

1. Honor an explicit user choice from the current request or verified workflow state. It is authoritative.
   Persist the choice. Skip the topology question.
2. Otherwise inspect the finished work's review shape:
   - First classify each production change.
     Use **semantics-altering** for features, fixes, or externally observable contract changes.
     Use **semantics-preserving** for behavior-preserving refactors, internal moves, internal renames, or formatting-only changes.
     A diff containing both is never one review unit. Preserved behavior and changed behavior require different review scrutiny.
     Put incidental fixes in a separate change. Never put them in a feature or fix.
     A move or rename is semantics-altering if it changes an externally observable name, path, API, or configuration key.
     Use the same classification for a changed serialized shape, command, or documented contract.
   - Choose **single** and proceed without asking when the change is one cohesive review unit.
     Its implementation, tests, docs, and durable artifacts must serve one behavior or contract.
     A split must not leave incomplete behavior. It must not force reviewers to reconstruct the whole.
   - Recommend **stacked** when the change has independently reviewable ordered layers.
     Give each layer a named purpose, its own validation, and a stable boundary.
     A lower layer must stand alone. Later layers must build on it without unrelated concerns.
     A change is also stack-sized when one review would combine distinct concerns with clear ordered boundaries.
     Put a semantics-preserving layer below a semantic change that depends on the reorganization.
     Do not use line-count or file-count thresholds.
3. Ask one single-versus-stacked question when you recommend a stack.
   Ask the same question when the review shape is genuinely ambiguous.
   For a stack recommendation, name the proposed layers. Recommend **Stacked PRs**.
   For ambiguity, state the competing evidence. Recommend the best-supported option.
   Do not choose silently.

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

A supplied `pr_plan` is evidence for a stack recommendation. It can provide explicit commit and file boundaries.
It cannot override an explicit user choice or another verified topology resolution.
If stacked is selected without clear user or plan boundaries, ask for the split.
Do not invent the boundaries.

A prior `/plate` **topology preflight** for the same run is the resolution.
The resolution can be explicit, inferred as cohesive, or confirmed after a question.
Persist it as `plate_layout: single | stacked` in workflow state. Copy it into any later `pr_plan`.
At terminal publication, verify that both values agree. Reuse the resolution. Do not ask twice.
Apply this policy again when the record is missing, conflicting, or unverified. Do not ask automatically.

For an **Existing PR**, detect its ordinary or stacked topology. Do not ask the layout question.
Preserve that topology. Use its matching update path.
Commit-only isolated workers also do not ask because publication is out of scope.

Topology preflight persists the resolution. It reads the resolution back.
It stops before any commit, branch mutation, push, or PR operation.

## Repair-worktree topology

First, run the repair pathway's mechanical file-overlap check.
See [`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md) § Repair pathway.
The branch name is `worktree-agent-repair-*`.
If there are no shared files, publish an ordinary independent PR against `main`.
Use the same path if the original run branch no longer exists.
At or below the small-repair threshold, move shared files onto the run branch.
Do not publish these files independently.
Above the threshold, restack with the repair as the base PR. Use the stack process in `stacks.md`.
Apply the policy above to any other branch.
