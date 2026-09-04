# Edge Review: Mold to Briesearch

## State

`broken`

Mold can select Briesearch, but the sidechain request contract is incomplete.
The result, slug, artifact, and error contracts do not agree.
No automated test crosses this edge.

## Evidence

### Mold producer

- `skills/mold/SKILL.md:19,61-68` selects Briesearch for external validation.
- The same lines keep the Mold dialogue and approval state in the parent.
- `skills/mold/references/validate-cycle.md:7-16` sends one hypothesis through `/briesearch`.
- `skills/mold/references/validate-cycle.md:18-24` expects `SUPPORTED`, `CONTRADICTED`, or `REFINED`.
- `skills/mold/references/validate-cycle.md:48-64` records the outcome and blocks Curdle for an open hypothesis.
- `skills/mold/references/context-budget.md:7-14` delegates deep research to a `researcher`.
- `skills/mold/references/mini-spec-mode.md:48-62` emits a `briesearch` provenance line and an optional artifact path.
- That artifact path is `research/<slug>/<slug>.md`.
- `skills/mold/references/handoff-menus.md:22-27` can dispatch `/briesearch` after Curdle.
- `src/easy_cheese/skills/mold/commands.py:10-94` has no Briesearch command or import.
- Host skill dispatch and Markdown files carry this edge.

### Briesearch consumer

- `skills/briesearch/SKILL.md:10-15` defines only user and Cheese tier-2 contexts.
- `skills/briesearch/SKILL.md:17-19` accepts the complete prompt and can ask one question.
- `skills/briesearch/references/context-isolation.md:41-67` requires `invocation: sidechain` when another skill asks.
- `src/easy_cheese/skills/briesearch/ledger.py:51-54,329-348` accepts `top-level` or `sidechain`.
- The parser defaults a missing invocation to `top-level`.
- It raises `LedgerError` for any other value.
- `skills/briesearch/references/synthesis.md:51-63` defines `certain`, `speculating`, and `don't know`.
- `skills/briesearch/references/synthesis.md:80-110` defines the returned report sections.
- `skills/briesearch/references/synthesis.md:112-116` requires a four-to-six-word slug for a deep report.
- `src/easy_cheese/skills/briesearch/research_layout.py:26-50` returns six absolute path strings and the slug.
- The path fields are `corpus_root`, `dir`, `report`, `raw_dir`, and `manifest`.
- `src/easy_cheese/skills/briesearch/research_layout.py:54-64` returns status one for an invalid generic slug.
- `skills/briesearch/references/budgets.md:47-53` defines the deep report budget errors.
- `skills/briesearch/references/synthesis.md:73-78` defines the deep report grounding errors.
- `src/easy_cheese/skills/briesearch/commands.py:14-55` has no Mold command or import.

### Tests and probe

- `tests/python/test_briesearch_ledger.py:124-126` rejects an unknown invocation value.
- `tests/python/test_briesearch_budget.py:251-274` reports `sidechain` metrics without a Mold caller.
- `tests/python/test_artifact_path.py:103-149` tests only the Briesearch layout and shared resolver.
- The checked `tests/python/test_mold*.py` files contain no `/briesearch` reference.
- The checked `tests/python/test_briesearch*.py` files contain no `mold` reference.
- No test sends a Mold request into Briesearch.
- `research-layout fix-auth` returned status zero and absolute paths.
- The two-word slug violates the documented four-to-six-word rule.

## Findings by severity

### Blocker

none

### High

- **[spec:high] The Mold sidechain request has no defined packet.**
  Mold sends a hypothesis and keeps dialogue ownership.
  Briesearch defines no Mold context, input fields, or silent-question rule.
  A nested run can ask the user or use the wrong output form.
  Evidence: `skills/mold/SKILL.md:19,66-68`; `skills/mold/references/validate-cycle.md:7-16`; `skills/briesearch/SKILL.md:10-19,60-62`.
  **Fix:** Define `question`, `invocation`, `slug`, and `allow_question` for a sidechain request.
  Require `invocation: sidechain` and `allow_question: false` for Mold.

- **[spec:high] A Mold sidechain can silently become a top-level run.**
  Briesearch requires `sidechain` when another skill asks.
  Mold does not emit that field.
  The parser defaults the missing field to `top-level`.
  Evidence: `skills/briesearch/references/context-isolation.md:63-67`; `src/easy_cheese/skills/briesearch/ledger.py:329-348`; `skills/mold/references/validate-cycle.md:7-16`.
  **Fix:** Put `invocation: sidechain` in the Mold request.
  Reject a missing value for every internal run.

- **[correctness:high] Mold does not map an inconclusive Briesearch result.**
  Briesearch returns `don't know` for uncovered or conflicting critical evidence.
  Mold defines only three settled outcomes.
  The flow does not map `don't know` to the open-hypothesis state.
  Evidence: `skills/briesearch/references/synthesis.md:51-63`; `skills/mold/references/validate-cycle.md:18-24,48-64`.
  **Fix:** Map `don't know` to an open hypothesis without an `outcome`.
  Keep Curdle blocked until new evidence or an explicit `[TBD]` decision settles it.

- **[spec:high] The slug and artifact path contracts conflict.**
  Mold permits a parent slug with one to four words.
  Briesearch requires four to six words for a deep report.
  Mold stores a corpus-relative artifact path.
  Briesearch returns only an absolute `report` path.
  Evidence: `skills/mold/references/mini-spec-mode.md:5,48-62`; `skills/briesearch/references/context-isolation.md:19-20`; `src/easy_cheese/skills/briesearch/research_layout.py:26-50`.
  **Fix:** Let every sidechain reuse the caller slug.
  Add a corpus-relative `artifact` field to `ResearchLayout`.
  Keep `report` for file writes.

- **[assertions:high] Tests do not exercise the seam from both sides.**
  Briesearch tests stop at invocation parsing and layout creation.
  Mold tests do not send a research request or consume its result.
  Evidence: `tests/python/test_briesearch_ledger.py:124-126`; `tests/python/test_artifact_path.py:103-149`.
  **Fix:** Add one producer test and one consumer test.
  Cover request fields, question ownership, confidence mapping, slug reuse, artifact mapping, and command errors.

### Medium

- **[spec:medium] Briesearch defines two incompatible sidechain outputs.**
  Internal tier-2 mode returns one provenance line.
  The synthesis contract says every caller receives the complete short form.
  Mold needs claims and citations before it judges the hypothesis.
  Evidence: `skills/briesearch/SKILL.md:10-13,60-62`; `skills/briesearch/references/synthesis.md:80-110`; `skills/mold/references/grounding.md:46-56`.
  **Fix:** Define one sidechain result with `summary`, `claims`, `confidence`, `artifact`, and `needs_input`.
  Let each caller render only the fields it needs.

### Low

none

## Contract drift

- PR #582 added the sidechain marker and the absolute research layout.
- Mold did not add the marker or a path conversion.
- Mold's parent slug rule did not update Briesearch's report slug rule.
- Both skills still assign every design choice to Mold and the user.

## STE100 status

noncompliant

- `skills/mold/SKILL.md:12,19,24,131` contains long instructions or multiple actions.
- `skills/briesearch/SKILL.md:19` puts two instructions in one sentence.
- This note uses active voice, short sentences, and one term for each meaning.

## Follow-ups

- Define the Mold-to-Briesearch sidechain request and result.
- Map `don't know` to an open Mold hypothesis.
- Reconcile the slug and artifact fields.
- Add producer and consumer seam tests.
