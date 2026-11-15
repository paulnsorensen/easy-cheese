# BAML generous input acceptance

**Decision supported:** whether easy-cheese's dual-read, canonical-write cutover should accept legacy artifacts generously while retaining strict canonical boundary schemas.

**Scope:** BAML's current `canary` source at `a50430fba33012bea9a740ab0466c10697050678`, inspected 2026-08-24, plus BoundaryML documentation. These sources describe LLM-output parsing, not durable workflow-artifact migration.

## Synthesis

BAML deliberately accepts and repairs LLM-shaped output, then coerces candidate values toward its declared BAML type and applies required-field and assertion checks. Its parser preserves repair/coercion provenance as flags and ranks alternatives; it does not establish a general rule that durable records should tolerate arbitrary malformed input.

For easy-cheese, the transferable shape is a bounded compatibility reader: recognize an explicitly listed legacy format, normalize it once, record that migration, then validate and write only the canonical artifact. The BAML-specific syntax repair and heuristic semantic coercion remain inappropriate for persisted inter-skill artifacts.

## Evidence

| Claim | Source | Confidence |
|---|---|---|
| BAML first tries strict JSON; on failure it tries markdown blocks and then extracts JSON-like candidates from surrounding text. The parser retains multiple alternatives as `AnyOf` values and marks extracted candidates as fixed JSON. | [parser entry](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/jsonish/parser/entry.rs#L15-L173) | certain |
| The documented SAP behavior explicitly repairs missing quotes, trailing commas, comments/yapping, fractions, escaping, and incomplete JSON sequences. | [BoundaryML "Why BAML?"](https://docs.boundaryml.com/guide/why-baml) | certain |
| Repository tests cover trailing commas, incomplete arrays and strings, markdown fences, unquoted keys, unquoted string values with spaces, comments, single quotes, and markdown-like unquoted values. | [jsonish basics tests](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/tests/test_basics.rs#L256-L326), [more syntax cases](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/tests/test_basics.rs#L540-L647) | certain |
| Numeric coercion accepts numeric strings, floats for integers (rounding), fractions, comma-separated numbers, and trailing commas; boolean coercion accepts string booleans and invokes fuzzy string matching otherwise. | [primitive coercion](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/coerce_primitive.rs#L185-L402) | certain |
| Candidate choice is deterministic but heuristic: successful candidates are scored from repair/coercion flags, with special preferences for non-default values and better structured/list parses; score ties use original index. | [candidate selection](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/array_helper.rs#L29-L285), [flag scores](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/score.rs#L10-L95) | certain |
| BAML rejects ambiguous fuzzy string matches: substring candidates that tie are flagged, and `try_match_only_once` returns a `Too many matches` error. | [string matching](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/match_string.rs#L39-L182), [tie handling](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/match_string.rs#L213-L327) | certain |
| Required missing or unparseable fields generate a structured parsing error. Assertions are evaluated after coercion and failures reject the value; ordinary `@check` results are retained as flags rather than rejection. | [required-field errors](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/mod.rs#L205-L252), [constraint handling](https://github.com/BoundaryML/baml/blob/canary/engine/baml-lib/jsonish/src/deserializer/coercer/field_type.rs#L1-L11) | certain |
| BAML's acceptance is not strict JSON-schema validation: it deliberately performs syntax repair and semantic coercion before checking the declared type/constraints. | Sources above | certain |

## Principles transferable to dual-read, canonical-write

1. **Separate acceptance from publication.** <speculative> Read compatibility input permissively only in an adapter; write the validated canonical representation only.
2. **Make normalization observable.** <speculative> BAML records repairs/coercions as flags. Easy-cheese should record legacy-schema/version, adapter identity, and migration result rather than silently accepting the legacy input.
3. **Reject ambiguity.** <speculative> Do not choose among multiple plausible legacy interpretations; require an explicitly deterministic adapter or reject with diagnostics.
4. **Validate after normalization and before domain execution.** <speculative> BAML's required-field/assertion pass illustrates the order, while easy-cheese should apply its canonical schema without BAML's broad coercion.
5. **Keep the compatibility set finite.** <speculative> Accept enumerated legacy schema IDs/versions and precise structural changes, not arbitrary JSON-ish syntax or heuristic field-name/value correction.

## Do not copy into durable artifact migration

- <certain> Do not accept syntax-repaired JSON, comments, markdown fences, incomplete documents, or extracted snippets as persisted handoff artifacts; those are BAML's response-to-LLM conveniences, not a durable protocol.
- <certain> Do not round numeric values, convert fractions, remove punctuation, use substring matching, or infer booleans/fields during artifact migration. BAML documents and implements these as coercions, and they can change meaning.
- <certain> Do not select among multiple candidates by a repair-score heuristic. Require one known legacy discriminator and one deterministic normalizer; reject collisions/ambiguity.
- <speculative> Preserve raw legacy input only in diagnostic/migration evidence subject to existing privacy and retention rules; it should not become a second current artifact authority.

## Open questions

- Whether the first Mold → Cook cutover needs any legacy reader at all, or can use a canonical-only hard cut, depends on the actual persisted/resumable artifact inventory.
- Which explicit observability mechanism fits the existing `.cheese` artifact model (metadata, event/log, or migration receipt) requires local design evidence.

## Confidence

**High.** Syntax acceptance, coercion, candidate choice, ambiguity rejection, and post-coercion constraints are directly verified in BoundaryML documentation and current BAML source; the easy-cheese transfer principles are explicitly marked inference.
