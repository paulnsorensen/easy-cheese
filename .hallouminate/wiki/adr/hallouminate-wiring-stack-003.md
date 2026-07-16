# ADR: liberal wiki grounding in mold/culture is prose guidance, not a coherence gate

**Status:** accepted (2026-07-16)

- **Context:** Issue #201 wants /mold probing the wiki at every decision point and /culture probing during evidence-gathering. Enforcement could be prose trigger-list guidance or a new lockstep-tested `COHERENCE_GATES` item ("wiki probed before curdle") like deb89a2's durable-writes gate.
- **Decision:** Prose guidance: extend `skills/mold/references/grounding.md`'s probe-trigger list to decision/question/rationale points across Dialogue modes, and add a light probe to `skills/culture/SKILL.md:30`. No new gate node.
- **Alternatives:** Coherence gate — enforced and drift-proof, but touches the gate graph plus lockstep test and fires even when the wiki has nothing relevant, adding ceremony to every mold session.
- **Consequences:** Matches the issue's `triage/clear-fix` weight and keeps mold sessions light; costs the possibility of prose drift, which the wiki-probe habit in review can catch later. A gate can be added in a follow-up if drift is observed.
