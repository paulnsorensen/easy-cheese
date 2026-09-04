# Schemas to Mold Edge Review

## State

broken

Schemas define the canonical Mold document and Grounding records.
The mini-spec path accepts documents that do not satisfy that contract.

## Evidence

### Schemas producer

- `src/easy_cheese_schemas/contracts.py:2307-2417` defines the frontmatter fields and enum values.
- `MoldSpecFrontmatter` requires `slug`, `status`, `source`, `created`, `confidence`, and `gate_applicability`.
- `src/easy_cheese_schemas/contracts.py:2338-2356` defines the `wiki` and `explorer` probes.
- The same lines define the `hit`, `miss`, and `unavailable` outcomes.
- `src/easy_cheese_schemas/contracts.py:2449-2465` requires a non-empty evidence value in each `GroundingRow`.
- `src/easy_cheese_schemas/contracts.py:2487-2515` declares Grounding as a required section.
- `src/easy_cheese_schemas/contracts.py:2548-2617` requires exactly one row for each probe.
- `src/easy_cheese_schemas/spec_format.py:24-35` recognizes both Mold sources.
- The mini-spec section set at lines 33-35 omits Grounding.
- `src/easy_cheese_schemas/spec_format.py:56-65` applies that smaller section set to `agent-mini-spec`.

### Mold consumer

- `src/easy_cheese/skills/mold/validate_spec.py:40-142` imports the schema policy and loads the contract module.
- `src/easy_cheese/skills/mold/validate_spec.py:167-185` reads generated sections, columns, and enums by their canonical names.
- `src/easy_cheese/skills/mold/validate_spec.py:447-514` supplies defaults for missing required frontmatter fields.
- Those defaults are `legacy-spec`, `draft`, `legacy`, `unknown`, and `medium`.
- `src/easy_cheese/skills/mold/validate_spec.py:550-592` converts present Grounding rows to the schema types.
- `src/easy_cheese/skills/mold/validate_spec.py:595-634` creates two `unavailable` rows when policy permits no Grounding section.
- `src/easy_cheese/shared/taste_test.py:20-33` imports the same document and Grounding types.
- `src/easy_cheese/shared/taste_test.py:662-689` also creates two `unavailable` rows when the document has none.
- `src/easy_cheese/shared/taste_test.py:700-802` also supplies the missing frontmatter defaults.
- `skills/mold/references/mini-spec-mode.md:14-51` omits Grounding, `status`, `created`, and `confidence`.
- `skills/mold/references/curdle.md:35-77` includes those fields and both Grounding rows for full specs.
- `skills/mold/SKILL.md:76-105` describes provenance and applicability but does not require the persisted Grounding table.

### Generated files and commands

- `src/easy_cheese_schemas/_document_rules_compiler.py:39-91` projects `MoldSpecDocument` into runtime rules.
- `scripts/build_pyz.py:106-154` checks `src/easy_cheese/shared/document_rules.py` against that projection.
- `scripts/render_generated_regions.py:188-194` projects the model into the Curdle reference.
- `src/easy_cheese/shared/document_rules.py:6-53` contains the checked-in runtime projection.
- `skills/mold/references/curdle.md:156-220` contains the generated prose projection.
- `src/easy_cheese/skills/mold/commands.py:52-63` exposes `taste-test` and `validate-spec`.
- `skills/mold/scripts/mold.pyz` packages those consumers and the schema runtime.
- Schemas do not import Mold or call a Mold command.
- This edge defines no handoff field.
- Mold materializes a Markdown file and an in-memory `MoldSpecDocument`.

### Contract agreement

- The full Curdle path agrees on field names, enum values, table columns, and row types.
- The full path also agrees on the required Grounding rows and non-empty evidence.
- The mini-spec path disagrees on required sections and required frontmatter fields.
- The schema model raises `ValueError` when either Grounding probe is absent.
- The Mold command maps model failures to `ERROR:` lines and exit status 1.
- The strict mini-spec path bypasses that error with invented values and returns status 0.

### Tests and probes

- `tests/python/test_document_rules_compiler.py:50-93` checks full-template sections, columns, and rules.
- `tests/python/test_document_rules_compiler.py:171-199` checks missing probes, duplicate probes, and blank evidence.
- `tests/python/test_document_rules_compiler.py:239-280` checks the generated runtime projection.
- `tests/python/test_validate_spec.py:748-829` checks the same Grounding failures through the Mold command.
- `tests/python/test_mold_taste_test.py:438-453` checks duplicate Grounding rows through the typed taste path.
- No validator test uses `source: agent-mini-spec`.
- `tests/python/test_mold_taste_test.py:207-216` checks only missing applicability for that source.
- The schema and Mold test files report 115 passed tests.
- The Mold taste file reports 33 passed tests.
- A strict command probe used the documented mini-spec shape.
- The command returned status 0 without Grounding, `status`, `created`, or `confidence`.
- A typed probe showed two invented `unavailable` rows.
- The typed probe also showed `draft`, `unknown`, and `medium` defaults.

## Findings

### Blocker

none

### High

- **The strict mini-spec path invents canonical evidence.** The schema requires one real record for each Grounding probe. The mini-spec template omits both rows. Both Mold consumers create `unavailable` rows that describe no attempted action. They also create missing required frontmatter values. This behavior violates the Grounding decision in `disagreements.md:70-73`. **Fix:** Add the required frontmatter and Grounding table to the mini-spec template. Require Grounding for strict mini-spec validation. Remove both synthetic Grounding paths and strict frontmatter defaults.

### Medium

- **Tests do not exercise the documented mini-spec against the schema contract.** Producer tests use full Curdle documents. Consumer tests do not run `agent-mini-spec` through `validate-spec --strict`. **Fix:** Run the documented mini-spec through strict validation. Reject each missing required field and each missing probe. Assert that present values reach `MoldSpecDocument` unchanged.

### Low

none

## STE100 status

noncompliant

- No `skills/schemas/SKILL.md` file exists.
- `skills/mold/SKILL.md:94-95` uses passive voice in `is never inferred`.
- `skills/mold/SKILL.md:98-100` ends with a noun list instead of a complete clause.
- `skills/mold/references/mini-spec-mode.md:31` uses `behaviour` instead of the established term `behavior`.
- This note uses active voice, short sentences, and one term for each meaning.

## Follow-ups

- Make strict mini-spec documents satisfy the canonical Mold document contract.
- Add producer and consumer tests for the strict mini-spec seam.
