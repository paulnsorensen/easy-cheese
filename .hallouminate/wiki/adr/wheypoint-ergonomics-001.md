# Decision dossiers decoupled from gating

<certain> A wheypoint decision dossier may describe any active question; it is required only when an entry gates continuation.[^spec]

## ADR-001: Decouple the dossier from `blocks_continuation` [status: accepted]

- **Context:** <certain> `_dossier_rule` (`src/easy_cheese_schemas/wheypoint.py:517-522`) refused a `decision_dossier` unless some entry gated, and `ProposedEntry.blocks_continuation` defaults to false (`:353`). A parked fork therefore could not record its options, evidence, and prior leaning without turning the whole record `gated` and stopping every `/cheese --continue` auto-dispatch. The 2026-09-05 07:03 checkpoint for this very work item hit the refusal, popped the dossier, and stuffed the fork into a `working_context` prose line.
- **Decision:** Allow a dossier fork on any active question; require a covering fork only for gating entries. Keep the default of `blocks_continuation=false`. Render active non-gating questions and blockers under a projection section `## Open entries` so "ok with open questions" is visible.
- **Alternatives:** (A) Questions gate by default — honest about "unresolved" but every parked question becomes a prompt and kills auto-dispatch. (C) Do nothing — parked forks stay as prose in `working_context`, which is where the loss happened.
- **Consequences:** Derived status keeps its two values. A record can carry a weighed-but-parked fork without blocking resumption. The projection body gains a section the old renderer never had.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-ergonomics.md`, approved 2026-09-05 — fork `F1-dossier`, AC-7, AC-15.
