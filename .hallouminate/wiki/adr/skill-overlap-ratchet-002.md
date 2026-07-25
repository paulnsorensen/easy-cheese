
# ADR: Preserve H2 and H3 identity during semantic chunking

Meaningful H2 and H3 sections remain independent semantic units at any length; only oversized embedding payloads are subdivided, and generated parts retain their original section identity.

## Decision record

### ADR-002: Section identity over fixed-size chunks [status: accepted]

- **Context:** The corpus contains 719 H2/H3 sections. A fixed merge below 50 whitespace tokens would collapse 144 sections, including complete invariants, commands, and examples. Thirteen sections exceed 512 whitespace tokens and would risk model truncation. H4-only splitting protects none of those current long sections.[^1]
- **Decision:** Treat every real H2/H3 outside fences as a section. Skip embeddings only for empty containers and deterministic pointer-only sections. Preserve meaningful short sections with breadcrumb context only. Subdivide oversized payloads at structural boundaries toward 384 model tokens with a 480-token ceiling and no body overlap.
- **Alternatives:** Embed whole files; merge short sections upward; preserve all sections and accept truncation; fail on oversized sections; use fixed token windows.
- **Consequences:** Reports retain actionable source spans and terse atomic concepts. The Markdown parser and splitter require broader fixtures, and one logical section can own multiple embedding parts. Parts from the same section must never be compared.

Related: [[skill-overlap-ratchet-001]], [[skill-overlap-ratchet-003]].

[^1]: `skills/cheez-read/SKILL.md:22-34`; `skills/mold/references/handshake.md:5-11`; `skills/cheese/SKILL.md:89-114`
