# #553 — suggestions into gates: current state and open work

Branch: `fix/r014-gates-conversion` (base `bab83ce4`).

## The pattern this issue names

A numbered step with a fallback lets an agent continue without the required work.
A precondition blocks the next artifact until the requirement passes.
Therefore, move the requirement from prose into a schema or validator.
The artifact must satisfy the requirement before its creation.

## Complete (commit `8676654a`)

Proposals 1 and 2 use one mechanism.
Both proposals address required probes that agents skip.

- `src/easy_cheese_schemas/contracts.py` defines `GroundingProbe` with `wiki` and `explorer` values.
  It defines `GroundingOutcome` with `hit`, `miss`, and `unavailable` values.
  It also defines `GroundingRow` and a required `## Grounding` section with a three-column table.
  Cross-field rules include `grounding-probe-recorded` and `delegation-digest-recorded`.
  A `MoldSpecDocument` validator requires each probe exactly once.
- `src/easy_cheese/skills/mold/validate_spec.py` uses `_declared_table_rows` to read both declared tables.
  `_grounding_errors` enforces probe coverage, closed value sets, and nonempty evidence.
  Each probe has a separate rule identifier.
  Thus, skipped wiki and explorer probes fail under different identifiers.
- `src/easy_cheese/shared/document_rules.py` contains regenerated rules.
  All 13 `.pyz` bundles contain the rebuilt code from `just bundle`.
- `skills/mold/references/curdle.md` includes the new section in its specification template.
  `test_mold_spec_document_declares_full_curdle_template_section_set` checks the declared section order against that template.
  Thus, the test enforces the reference change.
- Fourteen new tests cover `tests/python/test_validate_spec.py` and `tests/python/test_document_rules_compiler.py`.
  The validator tests cover the direct script and `mold.pyz` seams.

The `unavailable` outcome remains valid because a backend can be absent.
Every outcome requires nonempty `Evidence`.
An agent can skip a probe only when it records the reason.

The gate applies to the **spec artifact**, not the span.
A span check needs harness telemetry that mold does not have.
The artifact gate provides the same control with existing tools.

## Remaining

### Proposal 3 — receipt gate (cook preflight, blocked on #546)

Cook preflight must produce a receipt, produce an explicit N/A result, or stop.
This branch does not implement that gate because `#546` owns the preflight.
Main intentionally has no cut flow (`681820f0`, `#560`).
Replace the old absent-receipt text in `cook/SKILL.md:14` with the result from #546.
Do not restore the cut or RED-gate mechanism.

### Proposal 4 — review and repair gate (age, #552)

The Age handoff writer must refuse output after a span starts a `coder` or writes production files.
This requirement needs span state.
Add a precondition field to the Age report schema, such as `production_writes: none | <list>`.
Validate this field like the Grounding table.
The report writer must refuse a nonempty list.
Ask the release owner whether a self-declared field is sufficient.
Otherwise, require real span telemetry.

### Proposal 5 — authoring audit rule

Add this rule to the skill-authoring reference.
Write a requirement as a precondition when omission has a measured cost.
Do not write that requirement as a step.
This branch excludes the rule because sibling branches change the same files.

### Proposal 6 — telemetry

Add one span metric for each gate.
This validator branch excludes telemetry because telemetry first needs a harness counter design.

## Notes for the next contributor

- `document_rules.py` has no regeneration CLI.
  `just bundle` only detects stale output.
  Regenerate the file with this command:
  `python3 -c "import sys,pathlib; sys.path.insert(0,'scripts'); import build_pyz as b; b.DOCUMENT_RULES_SOURCE.write_text(b._compiled_document_rules_source())"`
  Consider a dedicated `just regen` recipe.
- Mini-spec mode uses a separate format in `skills/mold/references/mini-spec-mode.md`.
  `validate_spec.py` does not gate that format.
  Decide separately whether mini specs must include grounding.
- `not-applicable` specs still require the Grounding table.
  Grounding does not depend on whether a RED gate applies.
  `test_not_applicable_spec_still_requires_grounding` checks this requirement.