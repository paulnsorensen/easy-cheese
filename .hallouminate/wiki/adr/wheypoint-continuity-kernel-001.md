# Wheypoint continuity authority

<certain> The minimal continuity kernel uses `WheypointRecord` as its living authority and `WheypointProjection` as generated Markdown.[^spec]

## ADR-001: Make the typed Wheypoint record authoritative [status: accepted]

- **Context:** <certain> Same-path Markdown replacement can discard earlier decisions, and legacy projections can carry unresolved lineage or inconsistent status.[^bugs]
- **Decision:** Use `WheypointRecord` as current state, `WheypointDelta` as the only update request, and `WheypointRevision` as the immutable resulting receipt. Markdown is generated as `WheypointProjection` and never owns continuity.
- **Alternatives:** Keep mutable Markdown as authority, or add only more note linting. Both leave carry-forward and concurrency correctness to writers.
- **Consequences:** The runtime, rather than the model, owns IDs, preservation, revision checks, projection generation, and derived status. The wider WorkAttempt and WorkTask protocol must build on this kernel later.

## Supersession

<certain> This decision supersedes the projection-authority, optional-parent dispatch, and new split/join portions of `wheypoint-provenance-schema-001.md` for the continuity kernel.[^legacy] Session, Git, and creation provenance remain accepted legacy evidence, but they do not select authority and declared references must resolve before dispatch.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-continuity-kernel.md`, approved 2026-08-02.
[^bugs]: GitHub issues 371-378 and 320. <https://github.com/paulnsorensen/easy-cheese/issues>
[^legacy]: [wheypoint-provenance-schema-001](./wheypoint-provenance-schema-001.md).
