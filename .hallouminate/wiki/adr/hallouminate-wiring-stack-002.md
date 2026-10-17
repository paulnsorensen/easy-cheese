# ADR: cook and age record durable-change flags; only the publication boundary writes the wiki

**Status:** accepted (2026-07-16)

- **Context:** Issue #202 reads literally as "post-land write-back hooks in /cook, /cure, and /age". Cure's write-back already landed (deb89a2, `skills/cure/SKILL.md:141-150`). Mirroring it into cook and age would create up to three writers for one change when the phases chain, and /age is otherwise a read-only reviewer. The `[TBD]` at `cure/SKILL.md:150` already leans toward consolidating the write trigger at one publication seam (/plate).
- **Decision:** Cook and age get a conservative flag-only gate — a `durable_flags:` key in their handoff slugs recording durable-knowledge candidates (architecture/protocol/convention/rationale deltas only, default `none`). The single wiki write stays at the publication boundary (cure/plate/affinage), which consumes upstream flags as its candidate list.
- **Alternatives:** Literal mirror (each phase writes independently) — rejected for duplicate writes and breaking /age's read-only contract. Cook-writes/age-flags middle ground — rejected as two writers where one suffices; standalone cooks still reach a publication boundary via /plate.
- **Consequences:** One writer, no duplicate wiki entries, /age stays read-only, and the existing `[TBD]`'s plate-consolidation direction is preserved. Costs: a standalone cook whose session never publishes leaves flags unconsumed in its slug — acceptable, the slug is durable and the next publish reads it.
