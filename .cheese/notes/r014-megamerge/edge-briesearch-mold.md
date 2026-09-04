# Edge Review: Briesearch to Mold

## State

`broken`

The design authority contract agrees at HEAD.
The artifact path, slug, and validation contracts do not agree.
No test exercises the complete edge.

## Evidence

### Briesearch producer

- `skills/briesearch/SKILL.md:13` returns one provenance line and writes `research/<slug>/<slug>.md`.
- The same rule derives the research slug from the parent mini-spec slug.
- `skills/briesearch/SKILL.md:28,72-73` forbids design choices and keeps alternatives as open questions.
- `skills/briesearch/references/synthesis.md:26-38` assigns each design choice to Mold and the user.
- `skills/briesearch/references/synthesis.md:84-102` defines five required short-report sections.
- `Next step` is free text and can name `/mold`.
- `skills/briesearch/references/context-isolation.md:19-20` requires a four-to-six-word slug and unchanged layout paths.
- `skills/briesearch/references/synthesis.md:114-116` repeats that limit and returns the layout report path.
- `src/easy_cheese/skills/briesearch/research_layout.py:26-50` returns six absolute path strings and the slug.
- The fields are `corpus_root`, `dir`, `report`, `raw_dir`, `manifest`, and `slug`.
- `src/easy_cheese/skills/briesearch/research_layout.py:54-63` returns status one for an invalid generic slug.
- `src/easy_cheese/skills/briesearch/commands.py:14-55` lists every Briesearch command.
- That command surface has no Mold command, import, file, or direct call.
- A complete source search also found no Mold import or call.
- This edge uses host dispatch and Markdown artifacts only.

### Mold consumer

- `skills/mold/references/mini-spec-mode.md:5` allows a parent slug with no more than four words.
- `skills/mold/references/mini-spec-mode.md:48-50` requires a `briesearch` provenance bullet and a corpus-relative artifact path.
- `skills/mold/references/mini-spec-mode.md:62` permits no artifact only for local code research without a durable file.
- `skills/mold/SKILL.md:49,117,138,143-144` prevents silent design choices.
- `skills/mold/references/grounding.md:48-56` requires cited, fresh, and decisive prior evidence.
- The same rule cannot skip a consequential user fork or an approval gate.
- `src/easy_cheese/skills/mold/validate_spec.py:637-735` validates registered sections but does not validate provenance.
- `src/easy_cheese/skills/mold/commands.py:10-93` lists every Mold command.
- That command surface has no Briesearch command, import, file, or direct call.

### Runtime probes

- `research-layout fix-auth` returned status zero and an absolute `report` path.
- The same command accepted a two-word slug despite the documented four-to-six-word rule.
- `research-layout Bad_Slug` returned status one with the generic kebab-case error.
- Strict Mold validation accepted an absolute private path in a malformed `briesearch` provenance bullet.
- The same probe also accepted a provenance sentence that selected Redis without user approval.

### Tests

- `tests/python/test_artifact_path.py:103-149` tests only the Briesearch layout and shared resolver.
- That test expects absolute paths and accepts two-word and three-word research slugs.
- `tests/python/test_mold_orchestration_budget.py:218-237` tests generic prior-evidence rules only.
- The checked `tests/python/test_mold*.py` files contain no `briesearch` reference.
- The checked `tests/python/test_briesearch*.py` files contain no `mold` reference.
- No test sends a Briesearch result into Mold.

## Findings by severity

### Blocker

none

### High

- **[spec:high] The artifact path representations conflict.**
  Briesearch returns the absolute `report` path.
  Mold requires `research/<slug>/<slug>.md` as a corpus-relative path.
  The handoff defines no conversion or relative field.
  Evidence: `src/easy_cheese/skills/briesearch/research_layout.py:26-50`; `skills/briesearch/references/synthesis.md:114-116`; `skills/mold/references/mini-spec-mode.md:48-50,62`.
  **Fix:** Add a corpus-relative `artifact` field to `ResearchLayout`.
  Use `report` only for file writes.
  Put `artifact` in Mold provenance.

- **[spec:high] The slug limits conflict.**
  Briesearch requires four to six words.
  Mold permits one to four words and requires the parent slug.
  Only a four-word slug satisfies both prose contracts.
  Evidence: `skills/briesearch/SKILL.md:13`; `skills/briesearch/references/context-isolation.md:19-20`; `skills/briesearch/references/synthesis.md:114`; `skills/mold/references/mini-spec-mode.md:5,50`.
  **Fix:** Define the tier-2 slug as the Mold parent slug.
  Keep the longer limit only for standalone reports, if needed.
  Add cross-edge tests for parent slugs with one through four words.

- **[correctness:high] Strict Mold validation ignores tier-2 provenance.**
  The validator accepts a missing or malformed `briesearch` bullet.
  It also accepts an absolute private path and an unauthorized design choice.
  Evidence: `skills/mold/references/mini-spec-mode.md:48-50,62`; `src/easy_cheese/skills/mold/validate_spec.py:637-735`.
  **Fix:** Add tier-2 provenance to the canonical Mold document rules.
  Require the source name, one-line synthesis, and relative artifact path.
  Reject missing, absolute, and malformed artifact paths.

- **[assertions:high] Tests do not exercise this seam from either side.**
  Producer tests stop at path creation.
  Consumer tests start with generic prior evidence.
  Evidence: `tests/python/test_artifact_path.py:103-149`; `tests/python/test_mold_orchestration_budget.py:218-237`.
  **Fix:** Add one producer contract test and one consumer contract test.
  Cover route selection, path mapping, slug limits, omission, and design authority.

### Medium

- **[spec:medium] The artifact omission rules use different predicates.**
  Briesearch skips the file when it fetches no source.
  Mold omits the field for local code research without a file.
  The contract does not classify a local code read as a fetched source.
  Evidence: `skills/briesearch/SKILL.md:13`; `skills/mold/references/mini-spec-mode.md:62`.
  **Fix:** Make artifact presence depend only on whether Briesearch wrote the report.
  Use one Boolean or one nullable artifact field.

### Low

none

## Contract drift

- PR #582 added the absolute `research-layout` result.
- Mold still requires a corpus-relative artifact field.
- Mold's short parent slug did not update Briesearch's longer report slug rule.
- Mold's strict validator did not adopt the tier-2 provenance fields.
- Both skills still assign design choices to Mold and the user.

## STE100 status

noncompliant

- `skills/briesearch/SKILL.md:19` combines two actions in one instruction.
- `skills/mold/SKILL.md:12,19,24,131` contains long instructions and multiple actions.
- This note uses active voice, short sentences, and one term for each meaning.

## Follow-ups

- Add a corpus-relative Briesearch artifact field.
- Reconcile tier-2 slug limits.
- Validate Mold provenance fields and errors.
- Add producer and consumer seam tests.
