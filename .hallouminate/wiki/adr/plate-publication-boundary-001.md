# ADR: plate owns the commit-to-PR publication boundary

**Status:** accepted (2026-07-14)

The publishing boundary previously spanned an external `/commit` skill, an external
`/pr-stack` skill, and raw `/gh` handoffs. That split left no single phase responsible
for making required artifacts durable before code was shared for review.

## Decision

`/plate` owns the complete local-to-review transaction: final artifact writes, project
validation, named-file staging, Conventional Commits, ordinary PR publication, and
stack-aware publication or maintenance.[^1] Raw GitHub inspection, review, CI, merge,
issue, release, and administration work remains outside `/plate`.

New-PR topology follows review shape before any commit or branch-layout mutation.[^2]
An explicit user choice is authoritative. Without one, `/plate` selects a single PR
without asking only when the work is one cohesive review unit; it recommends stacked PRs
and asks when there are independently reviewable ordered layers, and asks when the shape
is genuinely ambiguous. The criteria are cohesion and stable review boundaries, never
line or file counts. Parallel `/ultracook --open-pr` runs the same policy in topology
preflight before seed or worker commits, persists `plate_layout`, and reuses that
resolution at terminal publication rather than asking twice.[^4] A later `pr_plan` may
support a stack recommendation but cannot override an explicit or verified choice.
Updating an existing PR preserves its detected topology without asking again. A branch created by the baseline-repair pathway (name convention `worktree-agent-repair-*`) resolves through a mechanical file-overlap check ahead of this policy: no overlap plates an ordinary independent PR against main, small overlap (≤2 files, ≤50 lines) harvests onto the run branch instead of publishing, and larger overlap restacks with the repair as the base PR — falling back to the policy above for any other branch.[^6]

Before validation or publication, `/plate` inventories promised artifacts and durable
implementation learnings. It routes durable knowledge through the consumer repo's
hallouminate writer when available, otherwise uses the tracked ADR/domain-model fallback,
then reads every required output back and records `{target, backend, verified}`.[^3]
An unverified required write halts the transaction. For a stack, `/plate` selects and
creates or adopts provider lineage, then runs the write, validation, named-stage, commit,
and verification transaction separately for each layer before submitting the chain.[^5]
Shared durable writes live on the bottom/common branch or an explicit wiring branch.

## Alternatives

- **Keep commit, stacked PRs, and ordinary PR opening separate.** Rejected because the
  final write, validation, commit, and publication steps would still have split ownership.
- **Put everything in `/gh`.** Rejected because GitHub review, CI, issues, releases, and
  administration are unrelated to the local publication transaction.
- **Always ask single versus stacked.** Rejected because an explicit choice already
  resolves the decision, and asking about obviously cohesive work adds interruption
  without improving review structure.
- **Always infer topology.** Rejected because independently reviewable layers require
  user confirmation before branch mutation, and genuinely ambiguous work must not be
  classified silently.

## Consequences

The pipeline now ends at an explicit `/plate` phase, and every PR-opening caller shares
one durable-write and publication contract. Autonomous pipelines proceed directly for an
explicit choice or obviously cohesive single PR, but pause before mutation for a stack
recommendation or ambiguous shape. Commit-only calls and existing-PR updates avoid that
question.

Related: [[architecture]], [[workflow-invariants]].

[^1]: skills/plate/SKILL.md:93-147,172-202
[^2]: skills/plate/SKILL.md:33-104
[^3]: skills/plate/references/durable-writes.md:1-40
[^4]: skills/ultracook/SKILL.md:34-45,149-176
[^5]: skills/plate/SKILL.md:128-147
[^6]: skills/plate/SKILL.md § Repair-worktree topology; skills/cook/references/quality-gates.md § Repair pathway, Merge-time topology.
