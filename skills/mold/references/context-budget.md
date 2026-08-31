# Context budget — staying out of the dumb zone

A long mold dialogue can drift into the model's degraded-attention band (roughly
~120k–140k tokens), where recall and coherence soften. Mold defends the window
three ways: **offload heavy work to sub-agents by default**, **bound the active
orchestration** so a phase cannot grind unnoticed, and **nudge** the user toward a
checkpoint as the window fills. None is a hard gate — the reliable one is sub-agent
offload (ADR-003, Risks).

## Default: offload heavy work to sub-agents

The sub-agent context gate (`SKILL.md` § Sub-agent context gate) is the **default** for heavy work, not an exception. Resolve the typed read-only role through `../../cheese/references/agent-resolution.md`: exact specialist, compatible specialist, then a prompt-constrained general worker with `degraded: true`. Use inline work only when dispatch is unavailable:

- **Research:** deep `/briesearch` (3+ doc fetches or 2+ search angles) —
  the `researcher` phase-agent.
- **Shape check:** more than 5 symbols, wide module fan-out, large caller/dep
  traversals — the `explorer` phase-agent.
- **Prototype Cycle:** the throwaway build always runs in a sub-agent
  (`prototype-cycle.md`) — the `explorer` phase-agent.
- **Diagnose:** bulky logs/traces before a concise root-cause hypothesis — the
  `explorer` phase-agent.

The sub-agent returns a ≤2 KB digest; the raw evidence never enters the parent
window. The parent keeps only the dialogue, contradictions, approval state, and
the two-key handshake — those never delegate.

## Orchestration budgets — bound the active work, not only the window

Token pressure is the late signal. What actually runs long is *active orchestration*: one mold episode owns bounds, grounding, research, shape, taste testing, planning, approval, and publication, and the cost shows up as tool calls and spawns long before the window fills. Measured over 16 top-level invocations (the 2026-08 workflow-skill analytics sample): median 35.6 active minutes, heavy sessions at 100–276 tool calls and up to 11 sub-agent spawns.

So each phase carries a bound, and every bound has the same exhaustion move — stop adding work, record what is settled, and take the checkpoint:

| Budget | Bound | On exhaustion |
| --- | --- | --- |
| Ground per topic | 1 wiki probe + 1 delegated digest | mark the remainder `[?]` and move on; a third probe is re-reading, not grounding |
| Shape / Sketch per option set | 1 explorer digest | a second dispatch needs a *new* question, never a rerun of the same one |
| Fork rounds | 3 consecutive rounds that add no new evidence | render the decision map and stop asking (`SKILL.md` § Rules) |
| Parent-context tool calls | ~40 in the parent window | `/wheypoint` before the next heavy step |
| Sub-agent spawns | 6 per episode | `/wheypoint`; resume with the digests, not the dispatches |
| Repeated failures | 2 consecutive failures of the same tool or agent | record the degrade in the ledger and route around it — the third attempt is the one that burns the window |

Count only the *parent* window's calls and spawns. A sub-agent's internal tool calls are exactly what offload is for, and charging them here would penalise the lever that works.

These are budgets, not walls: exhaustion forces a checkpoint or a recorded degrade, never a truncated design. What it forbids is the silent third try.

## The nudge — heuristic, not a hard count

There is no precise live token count, so the budget is a **heuristic estimate**,
designed as a nudge:

| Estimate | Action |
| --- | --- |
| ~120k tokens | **Advisory:** note the window is filling; prefer sub-agent offload for the next heavy step; tighten questions. |
| ~140k tokens | **Suggest a re-up:** recommend `/wheypoint` to compact the session into a durable handoff slug, then resume in a fresh context. |

Estimate from the visible signals — turn count, sub-agent digests folded in,
large pastes — not a false-precision number. When in doubt, offload before you
nudge: the sub-agent split is the lever that actually moves the needle.

## The wheypoint re-up

At the ~140k nudge, recommend (do not auto-run):

```text
The dialogue is large enough to risk the model's dumb zone. /wheypoint will
compact what we've decided into .cheese/notes/<slug>.md so a fresh session can
resume without losing the handshake state. Resume with /cheese --continue <slug>.
```

`/wheypoint` preserves the dialogue, contradictions, approval state, and any open
Validate/Prototype cycles, so the fresh agent picks up mid-handshake rather than
re-deriving the design. See `skills/wheypoint/SKILL.md`.

## Why a nudge, not a gate

A hard token gate would cut confidence-gathering short — the exact failure
ADR-003 rejects for cycle caps. The window pressure is real but approximate, so
mold treats it as a prompt to act (offload or checkpoint), never as a wall that
ends the dialogue.
