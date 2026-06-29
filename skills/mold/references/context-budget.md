# Context budget — staying out of the dumb zone

A long mold dialogue can drift into the model's degraded-attention band (roughly
~120k–140k tokens), where recall and coherence soften. Mold defends the window
two ways: **offload heavy work to sub-agents by default**, and **nudge** the user
toward a checkpoint as the window fills. Both are advisory levers, not hard gates —
the reliable one is sub-agent offload (ADR-003, Risks).

## Default: offload heavy work to sub-agents

The sub-agent context gate (`SKILL.md` § Sub-agent context gate) is the **default**
for heavy work, not an exception. Spawn a read-only sub-agent — name the typed
phase-agent that fits the work, falling back to `general-purpose` where it isn't
available (e.g. a harness that installs only easy-cheese):

- **Reads / research:** deep `/briesearch` (3+ doc fetches or 2+ search angles) —
  the `researcher` phase-agent.
- **Shape check:** more than 5 symbols, wide module fan-out, large caller/dep
  traversals — the `explorer` phase-agent.
- **Prototype Cycle:** the throwaway build always runs in a sub-agent
  (`references/prototype-cycle.md`) — the `explorer` phase-agent.
- **Diagnose:** bulky logs/traces before a concise root-cause hypothesis — the
  `explorer` phase-agent.

The sub-agent returns a ≤2 KB digest; the raw evidence never enters the parent
window. The parent keeps only the dialogue, contradictions, approval state, and
the two-key handshake — those never delegate.

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
