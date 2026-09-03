# ADR: Preserve H2 and H3 identity during semantic chunking

Status: superseded (2026-08-30) by [[skill-overlap-ratchet-005]] — the ratchet is retired and `tools/skill-overlap/` is deleted.

Meaningful H2 and H3 sections remain independent semantic units at any length; only oversized embedding payloads are subdivided, and generated parts retain their original section identity.

## Decision record

### ADR-002: Section identity over fixed-size chunks [status: accepted]

- **Context:** The corpus contains 719 H2/H3 sections. A fixed merge below 50 whitespace tokens would collapse 144 sections, including complete invariants, commands, and examples. Thirteen sections exceed 512 whitespace tokens and would risk model truncation. H4-only splitting protects none of those current long sections.[^1]
- **Decision:** Treat every real H2/H3 outside fences as a section. Skip embeddings only for empty containers and deterministic pointer-only sections. Preserve meaningful short sections with breadcrumb context only. Subdivide oversized payloads at structural boundaries toward 384 model tokens with a 480-token ceiling and no body overlap.
- **Alternatives:** Embed whole files; merge short sections upward; preserve all sections and accept truncation; fail on oversized sections; use fixed token windows.
- **Consequences:** Reports retain actionable source spans and terse atomic concepts. The Markdown parser and splitter require broader fixtures, and one logical section can own multiple embedding parts. Parts from the same section must never be compared.

### ADR-002a: pulldown-cmark owns block structure [status: accepted, amends ADR-002]

- **Context:** ADR-002's section identity rested on a hand-rolled CommonMark reader in `tools/skill-overlap/src/main.rs` — a fence state machine, a `list_indent` heuristic, and an `is_table_row` regex recompiled per call. Chunk identities and `source_hash` fingerprints are built on that layer, so every parser divergence silently re-fingerprints findings.
- **Decision:** Delegate block structure — heading detection and level, fence awareness, list items, tables — to `pulldown-cmark` 0.13.4. `parse_document` runs a two-pass design: an event scan builds a heading map keyed by start line, then the original line loop drives body accumulation. Heading titles are re-sliced from raw source lines, never rebuilt from inline events, so markup in a title stays byte-identical. Spans stay line-based; byte offsets convert at the boundary via `line_offsets` / `byte_to_line`.
- **Alternatives:** Keep the hand-rolled reader; adopt `comrak`; move spans to byte offsets across all call sites.
- **Consequences:** Two byte-length-preserving input shims are required and must stay byte-length-preserving, or every span shifts. `normalize_fence_closer_tabs` works around an upstream bug where `scan_closing_code_fence` accepts only ASCII space after the fence run, so a trailing tab leaves the fence open and swallows the rest of the file. `neutralize_front_matter` covers the absence of a frontmatter extension. Heading indent tolerance is now uniform: CommonMark's 0-3-leading-space rule applies at every level, where the old reader demanded H1 at column 0 while tolerating any indent for H2/H3. `extract_relative_refs` is deliberately not subsumed — its inline code spans arrive as `Event::Code`, never `Tag::Link`. Verified at 0 parity divergences across 161 files / 988 sections against the pre-swap parser.

Related: [[skill-overlap-ratchet-001]], [[skill-overlap-ratchet-003]].

[^1]: `skills/cheez-read/SKILL.md:22-34`; `skills/mold/references/handshake.md:5-11`; `skills/cheese/SKILL.md:89-114`
