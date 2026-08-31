# #553 — suggestions into gates: what landed, what remains

Branch: `fix/r014-gates-conversion` (base `bab83ce4`).

## The pattern this issue names

An instruction written as a numbered step with a degrade clause is resolved
in favour of getting on with the work. An instruction written as a
precondition on the next artifact cannot be. The fix is therefore never
more prose — it is moving the requirement into a schema/validator that the
artifact must satisfy before it exists.

## Landed (commit `8676654a`)

Proposals 1 (grounding gate) and 2 (delegation gate), implemented as one
mechanism rather than two, because both are "a probe mold's prose mandated
and runs skipped":

- `src/easy_cheese_schemas/contracts.py` — `GroundingProbe` (`wiki`,
  `explorer`), `GroundingOutcome` (`hit`, `miss`, `unavailable`),
  `GroundingRow`, a required `## Grounding` section carrying a
  three-column table rule, cross-field rules `grounding-probe-recorded`
  and `delegation-digest-recorded`, and a `MoldSpecDocument` validator
  requiring each probe exactly once.
- `src/easy_cheese/skills/mold/validate_spec.py` — the Test Contracts
  table parser is now a shared declared-table reader (`_declared_table_rows`)
  used by both tables; `_grounding_errors` enforces coverage, closed sets,
  and non-empty evidence. Per-probe rule ids so a skipped wiki probe and a
  skipped explorer delegation fail under distinct identifiers.
- `src/easy_cheese/shared/document_rules.py` regenerated; all 13 `.pyz`
  bundles rebuilt (`just bundle`).
- `skills/mold/references/curdle.md` spec template gains the section —
  `test_mold_spec_document_declares_full_curdle_template_section_set`
  binds the declared section list to that template in order, so the
  reference edit is test-enforced, not decorative.
- Tests: 14 new cases across `tests/python/test_validate_spec.py` (both
  seams: direct script and `mold.pyz`) and
  `tests/python/test_document_rules_compiler.py`.

Key design call: `unavailable` stays a valid outcome — the degrade path
must keep working when a backend is genuinely absent — but `Evidence` is
non-empty for every outcome. A probe may be skipped; it may not be assumed.

Second design call: the gate lives on the **spec artifact**, not on the
span. A span-level check ("has this run called `ground` yet?") would need
harness telemetry mold does not have; a spec that cannot be written without
the row gets the same adherence with tooling that already exists.

## Remaining

### Proposal 3 — receipt gate (cook preflight, blocked on #546)

Cook's preflight must return a receipt or an explicit N/A, or not return.
Not started here: `#546` owns the preflight itself, and main is cut-free by
design (`681820f0`, `#560`), so the old "absent receipt invokes `/cut`"
wording in `cook/SKILL.md:14` needs replacing with whatever #546 lands, not
resurrecting. Do not reintroduce cut/RED-gate machinery.

### Proposal 4 — review/repair gate (age, #552)

Age's handoff artifact should refuse to write when the span has spawned a
`coder` or written production files. This one genuinely needs span state —
the cheapest honest version is a precondition field on the age report
schema (e.g. `production_writes: none | <list>`) validated the way the
Grounding table now is, plus the report writer refusing a non-empty list.
Worth confirming with the release owner whether a self-declared field is
enough or whether real span telemetry is required.

### Proposal 5 — authoring audit rule

Add to the skill-authoring reference: any instruction whose skip has a
measured cost is written as a precondition on the next artifact, not as a
step. Cheap, prose-only, and the thing that stops the pattern coming back.
Deliberately left out of this branch to keep SKILL.md churn off it —
sibling branches are touching the same files.

### Proposal 6 — telemetry

One span metric per gate. Out of scope for a validator branch; needs the
harness-side counter design first.

## Notes for whoever picks this up

- Regenerating `document_rules.py` has no CLI. `just bundle` only *detects*
  staleness. Regenerate with:
  `python3 -c "import sys,pathlib; sys.path.insert(0,'scripts'); import build_pyz as b; b.DOCUMENT_RULES_SOURCE.write_text(b._compiled_document_rules_source())"`
  A first-class `just regen` recipe would be a kindness.
- Mini-spec mode (`skills/mold/references/mini-spec-mode.md`) is a distinct
  format that `validate_spec.py` does not gate, so it was left alone. If
  mini specs should also carry grounding, that is a separate decision.
- `not-applicable` specs still require the Grounding table. That is
  deliberate — grounding is orthogonal to whether a RED gate applies — and
  is covered by `test_not_applicable_spec_still_requires_grounding`.
