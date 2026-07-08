# ADR: owner-homed cross-skill content stays with its owner

### ADR-002: content with a natural owner is not centralized  [status: accepted]

- **Context:** Several files are owned by one skill but cited by many (age's voice.md ×10, sub-agent-gate.md ×4, dimensions.md ×2; cure's selection.md ×2; hard-cheese's composition.md ×3). With `skills/cheese/references/` established as the shared home (ADR-001), the question was whether ≥2-consumer files should relocate there.
- **Decision:** They stay with their owning skill. Only the reference *form* changes — repo-anchored prose (`skills/age/references/voice.md`) becomes sibling-relative (`../age/references/voice.md`), the same rule as the cheese-kernel refs, so it resolves in installed trees too.
- **Alternatives:** Centralize everything referenced by ≥2 skills under cheese — cleaner "one home for shared things", but re-litigates ownership decisions (age owns the review voice kernel), causes larger churn, and buys nothing: the sibling-relative form gives the identical single-path/context-dedup property either way.
- **Consequences:** One uniform reference rule across the tree ("cite any sibling skill's file via `../<skill>/…`"); no content moves beyond the six ownerless shared docs. Cross-skill refs still require the owning skill to be installed — same partial-install caveat as ADR-001, same mitigation (install `--skill "*"`).
