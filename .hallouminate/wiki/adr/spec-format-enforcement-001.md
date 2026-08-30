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
- **Vendoring attrs into mold.pyz** — rejected in favor of the dependency-free generated rules module, mirroring `_schema_catalog.py`. Superseded in part — see the amendment below.

## Amendment (2026-08-30): schemas-package seam for the spec-format policy

**Status:** superseded in part (2026-08-30). The Decision above stands; the
fourth Alternative — "Vendoring attrs into mold.pyz — rejected" — no longer
governs where the *acceptance policy* lives.

v0.13-era specs must stay readable forever, so `validate-spec` gained a
read-side legacy acceptance path with a mint-side `--strict` posture. That
policy now lives in `src/easy_cheese_schemas/spec_format.py`, and
`src/easy_cheese/skills/mold/validate_spec.py` imports it — which drags the
attrs-backed model stack into the validator's import graph.

Rationale for accepting that cost:

- **The bundle-size argument is moot.** attrs already ships in every bundle:
  `easy_cheese.shared.manifest_io` imports `easy_cheese_schemas.io`, and that
  import executes the `easy_cheese_schemas` package `__init__`, which pulls the
  attrs-backed models. The validator adds no new dependency to any archive.
- **Channel portability is the point.** The read-side legacy grace has to hold
  identically for every release channel that reads a spec, not just for
  `mold.pyz`. Putting the policy in the published schemas package makes every
  channel inherit one definition of "what a legacy spec is" instead of
  re-deriving it.
- **Measured cost:** ~124 ms of import time on a `validate-spec` invocation.
  Acceptable for a one-shot CLI gate.

The generated dependency-free `_document_rules` projection is unchanged: the
*rule data* still reaches the validator without the model stack. Only the
acceptance-policy seam moved.
