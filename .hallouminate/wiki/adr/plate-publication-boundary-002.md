# ADR: Plate decides PR topology without asking

**Status:** accepted (2026-10-15). Supersedes the new-PR topology paragraph of [[plate-publication-boundary-001]].

`/plate` resolves the review shape of every new PR by itself and records the reason. It never asks the user single versus stacked.[^1] PR #779 (squash `594b7b38`) landed this decision.

## Decision

- An explicit choice is authoritative. Sources are the current request, verified workflow state, or the spec's `landing` block.[^1]
- Without one, Plate partitions the work into parts on existing commit or whole-file boundaries. It picks the first matching row of the shape table: `single`, `orthogonal_flat`, `stacked_linear`, or a mixed chain plus independent PRs. Any other case is `single`.[^1]
- `diamond_stack` is allowed only when an explicit choice names it.
- Plate never stacks parts that do not depend on each other. Independent parts publish as separate PRs against the trunk (`orthogonal_flat`) and merge and revert alone.[^2]
- Size never decides the shape. Past roughly 400 semantics-altering lines, Plate looks again for clean boundaries. With none, it publishes `single` and states the size risk and a reading order in the PR body.[^1]
- A `landing` block the diff cannot meet does not stop publication. Plate re-layers on clean boundaries or collapses to `single`, and states the deviation.
- Plate records `Plated as <shape>: <reason>` in the completion report and the PR body.
- The `/cook` fan pathway persists both `plate_layout` and `shape` at preflight and passes both to the PR planner. Publication reuses them.[^3]
- `validate-publication` accepts `plate_layout: stacked` with provider `ordinary` only for an `orthogonal_flat` plan.[^4]

## Alternatives

- **Ask before stacking (the 001 policy).** Rejected. In 22 past sessions Plate asked single versus stacked, and every clear answer took the recommended option. The question added an interruption at the last step and no information.
- **Gate the question on diff size.** Rejected. Size does not create review boundaries; dependency and cohesion do.
- **Always stack multi-part work.** Rejected. A chain of independent parts serializes review and merge for no gain.

## Consequences

- Autonomous pipelines no longer pause before publication for a topology question.
- Callers that want a stack must state it explicitly or supply a dependent `pr_plan`.
- A caller that requests a stack of independent parts makes an explicit choice. Plate honors it, so caller prompts must not request stacks by default.
- Issue #789 tracks the open validator gap. `validate-publication` compares `landing` with the plan by layout, not by exact shape, and has no `deviation` field.

Related: [[plate-publication-boundary-001]], [[workflow-invariants]], [[plate-runtime-contract]].

[^1]: skills/plate/references/topology.md § Decide the shape
[^2]: skills/plate/references/ordinary-pr.md § Independent PRs
[^3]: skills/cook/references/fan-pathway.md; skills/ultracook/references/pr-planner-prompt.md
[^4]: src/easy_cheese/skills/plate/publication.py
