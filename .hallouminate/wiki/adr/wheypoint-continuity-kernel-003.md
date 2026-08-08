# Immutable Wheypoint updates and resolution

<certain> Continuity updates use immutable revision receipts, record-last promotion, and deterministic resolution.[^spec]

### ADR-003: Put preservation and continuation invariants in the runtime [status: accepted]

- **Context:** <certain> Same-slug replacement, stale writers, lost responses, compaction, and cross-worktree lookup all fail when a Markdown filename or session is treated as current authority.[^bugs]
- **Decision:** Commit revision-checked semantic deltas under a per-record lock. Omission carries protected state forward. Exact replay returns the existing revision. Changed stale input promotes nothing. Immutable revision and projection files are written before atomically replacing the living record. Resolution uses explicit path, work ID, unique XDG slug, then deterministic legacy fallback, never recency.
- **Alternatives:** Require each model to rewrite complete state, choose the newest note, or trust optional parent and artifact references without verification.
- **Consequences:** The runtime can detect tampering, unresolved lineage, stale artifact coverage, and missing compaction rehydration before automatic dispatch. Slug ambiguity becomes an explicit result.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-continuity-kernel.md`, approved 2026-08-02.
[^bugs]: GitHub issues 320 and 371-378. https://github.com/paulnsorensen/easy-cheese/issues
