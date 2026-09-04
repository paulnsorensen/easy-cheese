# Edge review: Cheese to Cook

## State

broken

Cheese and Cook disagree on publication permission and retired-route flags.
Their fast-path rules also differ.

## Evidence

- Cheese selects `/cook --auto` for Cook at `skills/cheese/SKILL.md:179-189`.
  Cook accepts `--auto`, `--hard`, `--open-pr`, and `--resume <slug>` at `skills/cook/SKILL.md:30-45`.
- Cheese lists `--open-pr` as optional publication permission at `skills/cheese/SKILL.md:23-30`.
  Cook auto mode adds that flag at `skills/cook/references/auto-mode.md:23-28`.
- Cheese redirects Ultracook and forwards three named flags at `skills/cheese/SKILL.md:189`.
  Cook accepts the omitted `--hard` flag at `skills/cook/SKILL.md:38-43`.
  The retired stub promises the same `[flags]` at `skills/ultracook/SKILL.md:12-15`.
- Cheese accepts a file or behavior without a design question at `skills/cheese/references/routing-receipt.md:39-49`.
  Its classifier uses another rule at `skills/cheese/references/classification.md:88-101`.
  Cook requires a bug or call site in one or two files at `skills/cook/SKILL.md:47-54`.
  Cook also requires a proving check.
- Cheese emits optional `handoff_context.wiki_hits` at `skills/cheese/SKILL.md:50-60`.
  The shared payload defines `{page, line, why}` at `skills/cheese/references/handoff-gate.md:113-139`.
  Cook's complete input list does not name this payload at `skills/cook/SKILL.md:30-45`.
  A scoped search found no `handoff_context` or `wiki_hits` in the nine Cook Markdown files.
- Cheese forwards a validated Mold artifact unchanged at `skills/cheese/references/continue-resume.md:109-120`.
  Cook accepts a route-bound `HandoffPointer` at `skills/cook/SKILL.md:32-36`.
  Its handler verifies the Cook destination and `CurdPlan` schema at `src/easy_cheese/skills/cook/contract_handlers.py:119-143`.
  Cheese stops on invalid lineage at `skills/cheese/references/continue-resume.md:38-59`.
  Cook returns an error for invalid pointer data at `src/easy_cheese/skills/cook/contract_handlers.py:125-136`.
- Cook writes `.cheese/cook/<slug>.md` with its preamble at `skills/cook/SKILL.md:131-184`.
  Cheese reads `status`, `next`, and optional `mode` at `skills/cheese/references/continue-resume.md:67-80`.
  Cheese gives a missing `mode` the `single` value.
  Cheese stops on halt, gated, or malformed state at `skills/cheese/references/continue-resume.md:98-129,166-180`.
- Cheese makes no direct Python import or Cook bundle call.
  Its router rule permits only host dispatch at `skills/cheese/SKILL.md:64-66`.
- The redirect test checks Cheese text at `tests/python/test_ultracook_skills.py:73-98`.
  Its flag check covers only `--open-pr`, `--resume <slug>`, and `--auto`.
  The Cook resume test reads the Ultracook file at `tests/python/test_ultracook_skills.py:1418-1432`.
  The receipt tests check text order at `tests/python/test_cheese_routing_receipt.py:123-145`.
  The focused text tests report 19 passes.
  The two Cook pointer tests report two skips.
  Their dependency gate appears at `tests/python/test_cook_contract_accept.py:19-29`.

## Findings by severity

### Blocker

- Cook grants publication permission that Cheese did not send.
  Cheese omits `--open-pr` from its default `/cook --auto` command.
  Cook then adds `--open-pr` without user permission.
  This behavior can publish a new pull request without the required input.
  **Fix:** Forward `--open-pr` only when Cheese received it.
  Add a negative contract test for the default route.
- The Ultracook redirect can drop the requested `--hard` gate.
  Cheese accepts `--hard`, and Cook accepts `--hard`.
  The redirect forwards only three other flags.
  **Fix:** Forward `--hard` through the retired route.
  Add `--hard` to the redirect contract test.

### High

- Cheese and Cook use different fast-path rules.
  Cheese can dispatch work that Cook must return to Mold.
  This mismatch can create a routing loop or an unnecessary specification.
  **Fix:** Make Cook own one eligibility rule.
  Replace every Cheese copy with a direct reference.
- Tests do not exercise the dispatch contract from producer to consumer.
  One test checks a Cheese sentence, and another checks only the retired stub.
  The named Cook resume test reads the wrong skill file.
  **Fix:** Compare each Cheese command with Cook's declared inputs in one table-driven test.
  Change the resume test to read `skills/cook/SKILL.md`.
  Test defaults and all forwarded flags.

### Medium

- Cheese sends `handoff_context.wiki_hits`, but Cook does not declare that input.
  Cook can ignore repository decisions that Cheese supplied.
  **Fix:** Add the optional payload to Cook's input contract.
  Define its type, default, validation, and use.
- Cheese does not list `--auto` in its optional input flags.
  Cheese uses the flag by default and allows explicit continuation opt-in.
  Cook defines the flag at `skills/cook/SKILL.md:38-43`.
  **Fix:** Add `--auto` to Cheese inputs.
  State its default for direct routes and continuation routes.

### Low

none

## STE100 status

not compliant

- `skills/cheese/SKILL.md:41` combines several instructions in one sentence.
- `skills/cheese/SKILL.md:61` combines three instructions in one sentence.
- `skills/cook/SKILL.md:63` combines two instructions in one sentence.
- `skills/cook/SKILL.md:241` uses passive voice.
- `skills/cook/SKILL.md:250` combines two instructions in one sentence.

## Follow-ups

- Align `--open-pr` and `--hard` propagation before merge.
- Make Cook own the fast-path rule.
- Define Cook intake for `handoff_context.wiki_hits`.
- Add producer-to-consumer seam tests.
- Correct the listed STE100 violations.
