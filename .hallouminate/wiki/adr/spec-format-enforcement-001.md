# ADR: Mold spec format enforced by decorator-declared document contracts

**Status:** accepted (2026-08-23)
Spec: skills-only-spec-format-enforcement (durable specs corpus).

## Context

The mold spec format was prose-template-only; nothing mechanically checked frontmatter, sections, or the Test Contracts table before curdle. Research (three-part briesearch + BAML part 4) found no maintained Python declarative markdown-schema tool in the bounded search, OpenSpec `validate --strict` as the only spec-tool precedent, and BAML's schema-aligned parsing (verified at `jsonish` source level) as the lenient-syntax/strict-semantics model.

## Decision

Declare the spec format as decorator-marked models (`@document_contract`, extending the existing `@contract` pattern at `contracts.py:40-86`). A build-only compiler projects them into a generated dependency-free `_document_rules.py` staged into `mold.pyz`, consumed by a hand-rolled `validate-spec` subcommand with SAP posture: lenient syntax repair (heading case/punctuation, table whitespace, fence dialects), strict semantic rejection (AC coverage exactly-once, tracer/matrix cell rules, gate-applicability coherence) with accumulated `ERROR:` lines. The validator blocks curdle via a new handshake checklist item derived by `COHERENCE_GATES`/`gate_id()` into the `spec-format-valid` gate node. Applying SAP to file artifacts has no external precedent — it is this repo's deliberate extrapolation.

## Alternatives

- **mdschema (Go)** — rejected: declarative shape only, cannot express conditional cross-field contract rules or fenced-block content schemas; adds a Go toolchain dependency.
- **PyMarkdown custom rules** — rejected: same effort as hand-rolling behind a plugin API, plus a dependency.
- **Vendoring BAML's jsonish** — rejected: not exposed as a standalone library (BoundaryML/baml issue #998).
- **Vendoring attrs into mold.pyz** — rejected in favor of the dependency-free generated rules module, mirroring `_schema_catalog.py`.
