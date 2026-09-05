# Cure round 2 — cheese area

This note records every finding from the `cheese` review, edge, and hub notes.
Each row gives the source note, the severity, the state, the commit, and the evidence.
`deferred: owned by <area>` means the fix belongs to a file outside the `cheese` area paths.
The owning area's cure node reads the same edge note.

## Findings

| # | Source note | Severity | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | review-cheese.md | blocker | applied | `c805f3ba` | `skills/cheese/SKILL.md:43-45,85-88` |
| 2 | review-cheese.md | blocker | applied | `a2688b04` | `skills/cheese/references/decomposer.md:3-12,35-37` |
| 3 | review-cheese.md | high | applied | `d3fb7e45` | `skills/cheese/references/classification.md:92-103`; `routing-receipt.md:45-47` |
| 4 | review-cheese.md | high (telemetry) | applied | `a3e94878` | `skills/cheese/SKILL.md:52-54`; `coherence-check.md:9-11`; `routing-receipt.md:49-55` |
| 5 | review-cheese.md | high | applied | `9c3e994f` | `skills/cheese/references/classification.md:28,125-139`; `SKILL.md` affinage target |
| 6 | review-cheese.md | high | partly applied | `1caa85e1`, `60b8d817` | `skills/cheese/SKILL.md` flag rules. Mold and Pasteurize prose is `deferred: owned by mold` and `deferred: owned by pasteurize` |
| 7 | review-cheese.md | high (security) | applied | `1de55ade` | `skills/cheese/SKILL.md:37-44` |
| 8 | review-cheese.md | high | applied | `c5bdd8ec` | `skills/cheese/references/agent-resolution.md:85-94`; `routing-policy.md:38` |
| 9 | review-cheese.md | high | applied | `a812a831` | `skills/cheese/references/handback-contract.md` Boundaries table |
| 10 | review-cheese.md | medium | applied | `f326eea4` | `skills/cheese/references/optional-plugins.md:14-17,22-25,45-55` |
| 11 | review-cheese.md | medium (assertions) | applied | `57cf27a4` | `tests/python/test_cheese_routing_receipt.py:60-82`; `routing-receipt.md:22-25` |
| 12 | review-cheese.md | medium | applied | `94fbdb2c` | `skills/cheese/references/handback-contract.md` carrier table |
| 13 | review-cheese.md | medium (deslop) | applied | `2100ca83`, `f7e3daf4` | every `skills/cheese/**/*.md` prose file |
| 14 | edge-cheese-affinage.md | high | applied | `bf638a56` | `skills/cheese/references/continue-resume.md` affinage branch |
| 15 | edge-cheese-affinage.md | high | deferred: owned by schemas | — | The Affinage phase transition is not registered. Row 9 narrows the Cheese claim instead |
| 16 | edge-cheese-affinage.md | medium | rejected | — | A typed `pr_ref:` preamble key would not parse. The canonical parser accepts three optional keys. Row 12 confines the overload to legacy notes |
| 17 | edge-cheese-affinage.md | medium | applied | `bf638a56` | `continue-resume.md` requires `--stake` with `--auto` |
| 18 | edge-cheese-affinage.md | medium (assertions) | applied | `bf638a56` | `tests/python/test_cheese_contracts.py::TestAffinageResumeNormalizesItsReference` |
| 19 | edge-cheese-age.md | high | deferred: owned by age | — | The Age writer clears `artifact` and omits `baseline` |
| 20 | edge-cheese-age.md | high | applied | `c9aa88e7` | `skills/cheese/references/coherence-check.md` Age source rule |
| 21 | edge-cheese-age.md | medium | deferred: owned by age | — | Age declares no `handoff_context.wiki_hits` input |
| 22 | edge-cheese-age.md | medium | deferred: owned by age | — | `--hard` is missing from both Age command forms |
| 23 | edge-cheese-briesearch.md | high | applied | `d548839e` | `skills/cheese/references/escalation.md` tier 2 |
| 24 | edge-cheese-briesearch.md | high | partly applied | `d548839e` | Cheese states the `needs_input` rule. The Briesearch half is `deferred: owned by briesearch` |
| 25 | edge-cheese-briesearch.md | medium | applied | `d548839e` | `escalation.md` sets `invocation: sidechain` |
| 26 | edge-cheese-cook.md | blocker | partly applied | `1caa85e1` | Cheese never adds `--open-pr`. Cook auto mode adding it is `deferred: owned by cook` |
| 27 | edge-cheese-cook.md | blocker | applied | `1caa85e1` | `skills/cheese/SKILL.md` ultracook redirect row |
| 28 | edge-cheese-cook.md | high | applied | `d3fb7e45` | Cook owns the one fast-path rule |
| 29 | edge-cheese-cook.md | medium | deferred: owned by cook | — | Cook declares no `handoff_context.wiki_hits` input |
| 30 | edge-cheese-cure.md | blocker | deferred: owned by cure | — | The typed `CurdPlan` path needs a normal report repair path in Cure |
| 31 | edge-cheese-cure.md | blocker | deferred: owned by cure | — | The Cure writer command omits `--body-file` |
| 32 | edge-cheese-cure.md | high | deferred: owned by cure | — | The selection packet belongs to the Cure dispatch contract |
| 33 | edge-cheese-mold.md | high | applied | `d78baf3a` | `skills/cheese/references/escalation.md:11-16` |
| 34 | edge-cheese-mold.md | high | applied | `94fbdb2c` | `handback-contract.md` carrier table; `continue-resume.md` reads `spec_ref` |
| 35 | edge-cheese-pasteurize.md | high | deferred: owned by pasteurize | — | Pasteurize drops `--open-pr` and `--hard` |
| 36 | edge-cheese-pasteurize.md | high | deferred: owned by schemas | — | The registry has no Pasteurize phase |
| 37 | edge-cheese-pasteurize.md | medium | deferred: owned by pasteurize | — | Pasteurize has no Inputs section |
| 38 | edge-cheese-plate.md | high | partly applied | `60b8d817` | Cheese names Cure as the consumer. Mold and Pasteurize are deferred, as row 6 states |
| 39 | edge-cheese-plate.md | medium | applied | `60b8d817` | `skills/cheese/SKILL.md` `--open-pr` input |
| 40 | edge-cheese-plate.md | medium | deferred: owned by plate | — | Plate does not define the hard-gate failure mode |
| 41 | edge-cheese-press.md | blocker | deferred: owned by schemas | — | The canonical handoff model needs one typed local action |
| 42 | edge-press-cheese.md | high | deferred: owned by press | — | Press defines `artifact:` as an evidence path |
| 43 | edge-cheese-wheypoint.md | blocker | deferred: owned by wheypoint | — | The record and projection drop mode, task, order, baseline, and flag fields |
| 44 | edge-cheese-wheypoint.md | blocker | deferred: owned by wheypoint | — | See Disagreements. `tests/python/test_wheypoint_skill_contract.py:173` forbids `next: cut` |
| 45 | edge-cheese-wheypoint.md | high | deferred: owned by wheypoint | — | The projection emits a bare `status: gated` |
| 46 | edge-cheese-wheypoint.md | high | applied | `d39fe989` | `continue-resume.md` disposition branch |
| 47 | edge-cheese-wheypoint.md | high | deferred: owned by wheypoint | — | The resolver gates every legacy pull request artifact |
| 48 | edge-cheese-wheypoint.md | medium | applied | `bf638a56` | `continue-resume.md` lint description |
| 49 | edge-cook-cheese.md | blocker | deferred: owned by wheypoint | — | The resolver cannot resolve an exact Cook report path |
| 50 | edge-cook-cheese.md | high | deferred: owned by cook | — | Cook documents an invalid reader command |
| 51 | edge-cook-cheese.md | high | applied | `94fbdb2c` | `handback-contract.md` states the one `artifact:` meaning |
| 52 | edge-cook-cheese.md | high | deferred: owned by cook | — | The nested `baseline:` block cannot cross the seam |
| 53 | edge-cook-cheese.md | medium | applied | `5349fffb` | `skills/cheese/references/handoff-gate.md` gate example |
| 54 | edge-cure-cheese.md | blocker | deferred: owned by wheypoint | — | The resolver rejects an exact Cure report path |
| 55 | edge-cure-cheese.md | blocker | deferred: owned by cure | — | The Cure writer removes the report body |
| 56 | edge-cure-cheese.md | blocker | applied | `d39fe989` | `continue-resume.md` routes each disposition |
| 57 | edge-cure-cheese.md | high | deferred: owned by cure | — | The writer example cannot emit `next: done` |
| 58 | edge-cure-cheese.md | high | deferred: owned by cure | — | Cure loses baseline state |
| 59 | edge-cure-cheese.md | high | deferred: owned by cure | — | Cure weakens the fresh-context failure mode |
| 60 | edge-plate-cheese.md | high | applied | `60b8d817` | `skills/cheese/SKILL.md` names both Plate triggers |
| 61 | edge-plate-cheese.md | high | deferred: owned by plate | — | Plate does not handle a normalized `other:` answer |
| 62 | hub-schemas.md | high | applied | `a812a831` | `handback-contract.md` narrows the writer claim to the registry |
| 63 | hub-shared.md | untested edge | applied | `d3fb7e45` and this note | `escalation.md:50` still calls the current `resolve_slug` signature. The tests in `tests/python/test_cheese_contracts.py` now cover the router decision branches |
| 64 | hub-build.md | — | not applicable | — | No `cheese` row exists in `hub-build.md` |

## Simplifications applied

- Cook owns one fast-path contract. Two Cheese copies became links (`d3fb7e45`).
- The legacy curd block is scoped to explicit migration (`a2688b04`).
- The planner and the integrator are separate jobs in one row (`c5bdd8ec`).
- Each reference kind has one carrier (`94fbdb2c`).
- Optional-plugin detection uses one capability rule for every host (`f326eea4`).
- The router body lost duplicated escalation and scan mechanics (`f7e3daf4`).

## Disagreements

- **Cut route.** `src/easy_cheese_schemas/wheypoint.py` defines `NextMove.CUT`, and
  `skills/wheypoint/references/delta-contract.md:47-49` accepts Cut.
  `tests/python/test_wheypoint_skill_contract.py:173-186` asserts `"next: cut" not in corpus`
  across the Wheypoint skill, the Cheese skill, and the resume reference.
  The typed schema contract wins by rule 3, so the Cheese resume flow must gain a Cut branch.
  That branch cannot land while the absence test stands, and that test belongs to `wheypoint`.
  This node therefore records the finding as deferred and keeps the Cheese side unchanged.
- **Typed `pr_ref:` field.** `edge-cheese-affinage.md` asks for a typed `pr_ref` preamble field.
  `src/easy_cheese/shared/handoff.py:83-160` accepts only three optional keys.
  A new preamble key would parse as the orientation line, which repeats the Press `action:` defect.
  This node normalizes the reference at dispatch instead and confines the overload to legacy notes.

## Outward dependencies

- `cook` — `skills/cook/SKILL.md` section Standalone fast-path now owns the one fast-path contract that
  `classification.md` and `routing-receipt.md` link. The Cook text did not change.
- `mold` — `mold artifact-path specs <slug>` owns the specification write target that `escalation.md` names.
  `skills/mold/references/curdle.md` owns the typed planner dispatch that `agent-resolution.md` and
  `decomposer.md` link. Neither Mold file changed.
- `affinage` — `/affinage <pr-ref>` and its `pr-status` command accept a number or a URL.
  `continue-resume.md` now normalizes to that shape. The Affinage side did not change.
- `schemas` — `easy_cheese_schemas.phase_contracts` and the compiled phase registry gate the artifact
  writer. `handback-contract.md` now states that gate. The registry did not change.
- `shared` — `resolve_slug(candidate_slug, phase_hint="specs")` in `src/easy_cheese/shared/paths.py`
  stays the hallouminate-absent fallback in `escalation.md`. That signature did not change.
- `wheypoint` — `/wheypoint resolve --ref` and `/wheypoint lint <projection-path>` keep their current
  split. `continue-resume.md` now describes `lint` as a projection-only check.
- `build` — `skills/cheese/references/schema-intertwine.md` is generated by
  `scripts/render_generated_regions.py`. This node did not edit it.

## STE100 status

compliant, with two exceptions:

- `skills/cheese/references/schema-intertwine.md:3` still has one long descriptive sentence.
  The file is generated. `deferred: owned by build`.
- `skills/cheese/references/formatting.md:95,97` keeps two long quoted bad-example lines.
  The STE100 rule keeps quoted material unchanged.

## Follow-ups

- `tests/python/test_shared_migrate.py::test_accept_rejects_two_legacy_source_identities` fails at HEAD.
  The failure predates this node and comes from the `schemas` and `shared` reconcile commits.
  The adapter now raises `artifact schema mismatch` before the two-identity check.
  This test is outside the `cheese` area.
- Replace `tests/python/test_wheypoint_skill_contract.py::test_pipeline_omits_cut_and_resume_preserves_flags`
  with a Cut behavior test, then add the Cut branch to `continue-resume.md`.
- Register the Affinage and Pasteurize phase transitions, or keep the narrowed writer claim.
- Add a typed local Press continuation action to the canonical handoff model.
- Let the Wheypoint resolver accept an exact registered phase report path.
