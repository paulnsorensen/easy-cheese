# Spawn-primitive reference

`/ultracook` resolves each fresh phase through the shared [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md) contract. Host syntax is transport; role, power, permissions, isolation, and topology are the contract.

## Invariants

Every phase dispatch must:

1. start in fresh context;
2. meet the phase's tool, permission, isolation, and minimum-power floor;
3. run only its named phase and never chain forward;
4. return control synchronously;
5. write the phase handoff with the shared `agent_resolution` block.

Missing required tools, write capability, fresh context, or worktree isolation halts. Known underpowered candidates are rejected. Unknown power is final fallback only and records `degraded: true`.

## Role policy

| Work | Preferred type | Permission/isolation | Minimum power | Effort |
| --- | --- | --- | --- | --- |
| Decompose | planner, then general | write (manifest only); fresh context | powerful | high |
| Cook, press, cure, seed, wiring | coder | write; isolated worktree | default | high |
| Every age pass | reviewer | read-only; fresh context | powerful | high |
| Harvest and plate | parent | parent repository state | powerful | high |

Harvest and plate are never delegated. A general worker can fill a read-only role only through prompt-only no-write enforcement with `degraded: true`; a general worker cannot substitute for missing write capability.

## Same-worktree phase handoff

For each parallel curd, the parent creates one worktree and performs five top-level sequential spawns into that same path:

```text
coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)
```

After each return, the parent reads the phase handoff, records its `agent_resolution`, and passes the artifact path plus worktree path to the next fresh spawn. Before each age dispatch, the parent records and passes explicit review context: base commit SHA, reviewed tree object ID, normalized diff hash, and scope. The final age must return `next: done`; `next: cure` or a missing value halts and is not publishable. The parent then runs `/plate` in commit-only mode.

## Host examples

On Claude Code, render the resolved type in `Agent(subagent_type: <resolved-type>, prompt: ...)`. On Codex, use the host spawn capability with `fork_turns: "none"` so no conversation turns are inherited. On OMP, render the same record through `task(...)`. Do not add a call-site model override that contradicts the resolved power.

The phase prompt includes: phase name, slug, worktree path, prior handoff path, no-chain directive, required artifact path, and the resolved agent record. Wait for completion before dispatching the next phase.

If no host primitive satisfies a required invariant, halt `/ultracook` and recommend `/cook --auto`; do not silently collapse the fresh-context topology.
