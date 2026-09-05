# Context budget

A long Mold dialogue can reduce model recall and coherence. This risk increases near 120,000 to 140,000 tokens. Mold controls this risk in three ways. It delegates heavy work, limits active orchestration, and recommends a checkpoint when the context grows. Delegation is the most reliable control. See ADR-003.

## Delegate heavy work by default

Use the sub-agent context gate for heavy work. Resolve the read-only role through `../../cheese/references/agent-resolution.md`. Select the exact specialist first. Then select a compatible specialist. Use a constrained general worker with `degraded: true` only when no specialist is available. Work in the parent context only when dispatch is unavailable.

- **Research:** Delegate deep `/briesearch` work to a `researcher`. Deep work uses at least three document fetches or two search angles.
- **Shape check:** Delegate wide analysis to an `explorer`. Wide analysis includes more than five symbols or a large caller graph.
- **Prototype Cycle:** Always run the temporary build in an `explorer`. See `prototype-cycle.md`.
- **Diagnose:** Delegate large logs and traces to an `explorer`. Keep only the concise root-cause hypothesis in the parent context.

The sub-agent returns a digest of 2 KB or less. Do not copy raw evidence into the parent context. The parent keeps the dialogue, contradictions, approval state, and two-key handshake. Never delegate these items.

## Orchestration budgets

Token pressure gives a late warning. Active orchestration consumes the context before this warning occurs. One Mold episode can include bounds, grounding, research, Shape, taste tests, planning, approval, and publication.

The 2026-08 workflow sample contains 16 top-level invocations. The median active time is 35.6 minutes. Large sessions use 100 to 276 tool calls and up to 11 sub-agent spawns.

Each phase has a bound and an exhaustion action. When a phase reaches its bound, stop new work. Record the settled work and take the checkpoint.

| Budget | Bound | On exhaustion |
| --- | --- | --- |
| Ground per topic | 1 wiki probe and 1 delegated digest | Mark the remainder `[?]`. Treat a third probe as repeated work. |
| Shape or Sketch per option set | 1 explorer digest | require a new question before a second dispatch |
| Fork rounds | 3 consecutive rounds that add no new evidence | show the decision map and stop questions |
| Fork altitude | 3 consecutive forks that move no acceptance criterion, seam, or non-goal | show the decision map; demote the pending fork to `[AGENT-DECIDED]` or a follow-up candidate |
| Parent-context tool calls | approximately 40 calls | run `/wheypoint` before the next heavy step |
| Sub-agent spawns | 6 spawns per episode | Run `/wheypoint`. Resume from the digests. |
| Repeated failures | 2 consecutive failures from the same tool or agent | record the degraded path and use a different route |

Count only calls and spawns from the parent context. Do not count internal sub-agent tool calls. Delegation exists to move those calls out of the parent context.

These budgets are not terminal limits. Exhaustion requires a checkpoint or a recorded degraded path. It does not permit a truncated design. Do not make a silent third attempt.

## Context estimate

No precise live token count is available. Use the visible signals to estimate context use.

| Estimate | Action |
| --- | --- |
| approximately 120,000 tokens | Advise the user that the context is filling. Delegate the next heavy step. Keep each question concise. |
| approximately 140,000 tokens | Recommend `/wheypoint`. Resume in a fresh context. |

Estimate from the turn count, sub-agent digests, and large pasted inputs. Do not report false precision. Delegate before you recommend a checkpoint. Delegation directly reduces parent-context use.

## Wheypoint checkpoint

At approximately 140,000 tokens, recommend this action. Do not run it automatically.

```text
The dialogue can now reduce model recall. Run /wheypoint to save the settled decisions in .cheese/notes/<slug>.md.
Resume in a fresh session with /cheese --continue <slug>.
```

`/wheypoint` preserves the dialogue, contradictions, approval state, and open Validate or Prototype cycles. The fresh agent resumes at the current handshake state. It does not derive the design again. See `skills/wheypoint/SKILL.md`.

## Why Mold recommends a checkpoint

A hard token gate can stop confidence work too early. ADR-003 rejects this behavior for cycle caps. Context pressure is approximate. Therefore, Mold recommends delegation or a checkpoint instead of ending the dialogue.
