# Ultracook agent topology

Ultracook assigns a fresh typed agent to each reasoning phase instead of
running a whole curd through one write-capable worker.

## Phase ownership

- Decomposition uses a planner or compatible general worker.
- Seed, cook, press, cure, and wiring use a coder.
- Every age pass uses an independent reviewer.
- Harvest and plate remain parent-orchestrator responsibilities.[^1]

A parallel curd always runs
`coder(cook) → coder(press) → reviewer(age) → coder(cure) →
reviewer(final age)` in the same isolated worktree. The post-merge chain is
`coder(press) → reviewer(age) → coder(cure) → reviewer(final age)`.
A non-terminal age cannot skip cure and final review; only the terminal age's
`next: done` authorizes publication.[^2]

## Reproducible review identity

Before each age dispatch, the orchestrator records and passes the base commit,
reviewed tree object ID, SHA-256 diff hash, and file scope. Completed curds and
post-review publication phases cannot validate without this identity.[^3]
Post-merge identity is written atomically to both `current_review` and
`post_review.review_context` before the manifest advances.[^4]

This uses a tree object ID rather than claiming the uncommitted review head is
a commit. The explicit identity lets later review runs distinguish a changed
diff from differences in reviewer type, model power, effort, or topology.

## Why

The previous parallel worker performed cook, press, age, and cure in one
context, so review was not independent and cure could modify code after the
last review. Post-merge review also lacked a reproducible diff identity. Typed
top-level phases and a mandatory final age close both publication paths.

Related decision: [progressive agent resolution](../adr/agent-resolution.md).

[^1]: skills/ultracook/SKILL.md:93-96,224-227
[^2]: skills/ultracook/SKILL.md:152-170; src/fanout/phase_decision.py:45-48,84-132
[^3]: skills/ultracook/SKILL.md:177-180; src/fanout/validate_manifest.py:64-80,380-390
[^4]: src/fanout/manifest_update.py:239-267,336-368
