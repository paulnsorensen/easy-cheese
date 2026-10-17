# ADR — question-transport-policy-002

### ADR-002: Policy lives in ask-user-question.md  [status: accepted]

- **Context:** The #287 audit adds transport pointers across every dialogue-heavy skill. The "when to structure" policy needs a home those pointers reach.
- **Decision:** Extend `skills/cheese/references/ask-user-question.md` with a § When to structure section — one chokepoint; every pointer inherits *how* + *when* together.
- **Alternatives:** Sibling `question-policy.md` (rejected: extra reference hop per skill); inline per-skill clauses (rejected: divergent copies).
- **Consequences:** The transport doc becomes transport + policy — slightly mixed concerns, accepted for the single-chokepoint win.
