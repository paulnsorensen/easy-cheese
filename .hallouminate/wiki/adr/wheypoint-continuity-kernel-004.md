
# Canonical JSON persistence for Wheypoint records

<certain> Wheypoint continuity records persist as canonical UTF-8 JSON digested with SHA-256; the accepted 2026-07-27 YAML restoration is superseded for continuity records.[^spec][^research]

## ADR-004: Persist canonical JSON, not schema-bounded YAML [status: accepted]

- **Context:** <certain> The protocol reconstruction checkpoint committed to schema-bounded YAML persistence (the 2026-07-27 YAML-restoration decision, still recorded on the cross-skill work contract page). The approved Wheypoint kernel spec (2026-08-02) reversed that to canonical JSON + SHA-256 as flagged agent-introduced scope, and PR #384 implemented the spec — leaving the wiki asserting YAML while the landed kernel writes JSON, with no ADR recording why.[^checkpoint][^kernel-pr]
- **Decision:** Serialize every digested value as canonical UTF-8 JSON — sorted keys, tightest separators, literal UTF-8, non-finite refused — and take record digests, revision digests, and request fingerprints as SHA-256 over those bytes (`src/wheypoint/canonical.py`). Ratified 2026-08-11 on researched merits with packaging excluded from the analysis: document-level canonical YAML does not exist (the YAML spec's "canonical form" is per-scalar only; no RFC 8785 equivalent; no byte-stable Python emitter; surveyed YAML-native systems hash raw file bytes or decoded data, never canonical YAML), while canonical JSON has specified, production-proven prior art (RFC 8785, TUF). Record readability is delegated to Markdown projections; hand-editability of a digest-protected record is an anti-feature.
- **Dialect caveat:** <certain> The encoding is canonical JSON in the Python `json.dumps` dialect, not RFC 8785 JCS. Known divergences: key order is Unicode code-point rather than UTF-16 code-unit (differs only for non-BMP keys), and numbers keep Python's int/float distinction and `repr` conventions (`5.0` vs `5`, exponent-notation thresholds and padding, exact arbitrary-precision integers). Latent while this runtime is the sole producer and consumer — no float-typed schema fields, runtime-assigned ASCII keys — but any independent fingerprint implementation must match this dialect, not JCS.
- **Alternatives:** Restore schema-bounded YAML behind a bespoke canonical emitter (no spec, no prior art, PyYAML implements YAML 1.1 with implicit-typing ambiguity), or claim full RFC 8785 conformance (requires ECMAScript number serialization and UTF-16 key ordering).
- **Consequences:** Digest computation stays a standard-library pure function of the value. The cross-skill work contract page's YAML-persistence language no longer governs continuity records. Cross-language digest reproduction requires a dialect-conformance test before trusting fingerprints.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-continuity-kernel.md`, approved 2026-08-02 — "canonical JSON and SHA-256" declared under `agent_introduced_scope`.
[^research]: `.cheese/research/wheypoint-persistence-yaml-vs-json/wheypoint-persistence-yaml-vs-json.md` (untracked research corpus, 2026-08-11); decisive evidence inlined above.
[^checkpoint]: Reconstruction checkpoint preserved on PR #370 (`docs/root-cheese-milknado-protocol-safety`), `.cheese/notes/root-cheese-milknado-full-protocol-reconstruction.md` lines 754-756 and 773. <https://github.com/paulnsorensen/easy-cheese/pull/370>
[^kernel-pr]: Wheypoint kernel implementation. <https://github.com/paulnsorensen/easy-cheese/pull/384>