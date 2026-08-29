---
status: accepted
owner: easy-cheese
last_verified: 2026-08-29
confidence: high
---
# ADR: Preserve diamonds canonically and lower them privately for publication

PrPlan retains diamond topology. Plate absorbs provider limitations by lowering safe arms into staged linear sets and deferring the join.

## Context

The canonical plan needs to express a fork, independent arms, and a later join. The supported stack tools expose one-parent linear stack models rather than native multi-parent joins: gh-stack publishes an ordered stack, Graphite tracks one parent branch, and Git Town configures one parent branch.[^1][^2][^3]

Flattening every diamond would make provider execution simple but erase the logical dependency graph. Putting provider state into PrPlan would preserve more execution detail at the cost of coupling a stable input contract to mutable local and remote tool state.

## Decision

- Keep diamond topology in provider-neutral PrPlan.
- For a new stack, prefer gh-stack, then Graphite, then Git Town, then manual git and GitHub CLI.
- When a branch is already tracked, preserve that provider even when it is lower in the new-stack preference order.
- Halt if an existing tracked provider is unavailable; do not silently migrate provider metadata.
- Lower a diamond privately in Plate.
- Resolve each fork base once to a SHA and compute rename-aware changed paths over the exact base-to-arm range.
- Fan out only when planned scopes and actual changed paths are pairwise disjoint and all footprints resolve; serialize overlaps and fail closed on unknown footprints.
- Emit no join operation in the initial projection.
- Emit manual join commands only after GitHub reports every prerequisite merged into the target branch with the expected head SHA.

## Alternatives

- **Flatten diamonds permanently:** rejected because it loses canonical intent.
- **Require one provider and halt otherwise:** rejected because a manual path remains feasible for new stacks.
- **Embed provider and landing state in PrPlan:** rejected because those are private execution concerns.
- **Treat file disjointness as proof of semantic independence:** rejected; it is only a conservative conflict-avoidance gate, and full checks still run on every set and the join.

## Consequences

Plate gains a private staged execution path and a resume boundary. Provider limitations no longer distort the public topology, but diamond publication may span multiple landing rounds and manual join work.

[^1]: https://github.com/github/gh-stack
[^2]: https://graphite.com/docs/track-branches
[^3]: https://www.git-town.com/preferences/parent.html
