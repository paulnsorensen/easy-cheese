# cure2 — cook

This note records every finding that the Cook review notes raised.
It gives the state, the commit, and the evidence for each finding.

## Findings

| # | Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | review-cook.md | blocker | Cook fetches a network artifact from an untrusted pointer | applied by `shared` | (none) | `src/easy_cheese/shared/publication.py:494-497` rejects a non-`file` scheme. A probe returned `artifact 'payload-op-unsafe' is not a file:// uri`. |
| 2 | review-cook.md, hub-schemas.md | blocker | Cook ignores plan dependencies during execution | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1252-1277` runs declaration order. `skills/cook/references/fan-pathway.md:75-77` already requires topological waves. |
| 3 | review-cook.md, edge-cheese-cook.md, edge-cook-cure.md, edge-cook-plate.md, edge-cook-press.md | blocker | Auto mode grants publication permission without `--open-pr` | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:27-30`; `skills/cook/SKILL.md:42`; `tests/python/test_cook_prose_contract.py:26` |
| 4 | review-cook.md | blocker | Fan mode has two conflicting recovery records | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:8-13,90-95,101`; `tests/python/test_cook_prose_contract.py:47` |
| 5 | review-cook.md, edge-cook-age.md, edge-cook-cure.md | blocker | Cook, Age, and Cure assign the Cure cap to different owners | rejected | (none) | Age has no pass-count input (`skills/age/SKILL.md:17-22`). `skills/age/references/handoff-detail.md:90-107` says Age does not count passes. Age starts in a fresh context for each pass. Cook keeps orchestrator ownership at `skills/cook/references/auto-mode.md:67-89`. See Disagreements. |
| 6 | review-cook.md | high | Happy acceptance tests do not verify the emitted plan | applied | c90d9311 | `tests/python/test_cook_contract_accept.py:115-159` asserts the complete wrapper. |
| 7 | review-cook.md, edge-mold-cook.md | medium/high | Three rejection tests assert obsolete messages | applied | c90d9311 | `tests/python/test_cook_contract_accept.py:162-179,192-199,215-224` |
| 8 | review-cook.md, all edge notes | medium | Six Cook prose files violate the STE100 rules | applied | cb2b03b2, d5d47da7 | `skills/cook/SKILL.md:70-72`; `skills/cook/references/auto-mode.md:94-98`; `fan-pathway.md:186,285`; `package-report.md:70`; `tdd-loop.md:117,140-143,152`; `cook-discipline.md:38` |
| 9 | review-cook.md | low | Cook serializes each accepted value twice | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:36-38,82,127` |
| 10 | review-cook.md | low | Two reference labels do not exist | applied | cb2b03b2 | `skills/cook/references/tdd-loop.md:64-66` links `age/references/fan-out.md#router-call`. `auto-mode.md:142-144` names each phase file. `tests/python/test_cook_prose_contract.py:178` checks every link. |
| 11 | review-cook.md | simplification | Inline the three single-caller argument parsers | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:47-50,89-92,113-116` |
| 12 | review-cook.md | simplification | Remove the manifest command wrappers | deferred: owned by build | (none) | `src/easy_cheese/skills/cook/commands.py:63-95` feeds the generated rows in `skills/cook/references/commands.md:15,26-29`. Removal needs the generated-region rebuild and the bundle-closure tests that `build` owns. |
| 13 | hub-schemas.md | medium | Cook bypasses the schema error path for invalid UTF-8 | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:56-70,98`; `tests/python/test_cook_contract_handlers.py:98,113,126` |
| 14 | hub-shared.md | high | Cook removes its report body during handoff writing | applied | cb2b03b2 | `skills/cook/SKILL.md:179-183`; `tests/python/test_cook_prose_contract.py:115` |
| 15 | hub-shared.md | high | Cook reads an unbounded pointer before validation | applied by `shared` | (none) | `src/easy_cheese/shared/publication.py:456-469` reads at most `MAX_CONTRACT_BYTES`. |
| 16 | edge-briesearch-cook.md | high | No test protects implementation authorization | deferred: owned by briesearch | (none) | The producer side owns the stop rule at `skills/briesearch/SKILL.md:23-30`. Cook's entry list at `skills/cook/SKILL.md:32-36` accepts no Briesearch report. |
| 17 | edge-cheese-cook.md | blocker | The Ultracook redirect drops `--hard` | deferred: owned by cheese | (none) | `skills/cheese/SKILL.md:189` forwards three flags. Cook accepts `--hard` at `skills/cook/SKILL.md:41`. |
| 18 | edge-cheese-cook.md | high | Cheese and Cook use different fast-path rules | deferred: owned by cheese | (none) | Cook owns the rule at `skills/cook/SKILL.md:49-54`. Cheese must reference it, not copy it. |
| 19 | edge-cheese-cook.md | medium | Cook does not declare `handoff_context.wiki_hits` | applied | a2b7ccd4 | `skills/cook/SKILL.md:47-54`; `tests/python/test_cook_prose_contract.py:160` |
| 20 | edge-cheese-cook.md | medium | Cheese does not list `--auto` in its inputs | deferred: owned by cheese | (none) | Cook defines the flag at `skills/cook/SKILL.md:40`. |
| 21 | edge-cook-age.md | blocker | The typed curd review has no Age adapter | deferred: owned by age | (none) | `skills/age/phase-contract.yaml:5-10` declares `CurdResult` input, but `src/easy_cheese/skills/age/commands.py:11-106` has no adapter. |
| 22 | edge-cook-age.md | high | The direct Cook-to-Age review drops `artifact` and `baseline` | deferred: owned by age | (none) | `skills/age/SKILL.md:112-115` passes an empty artifact and omits `--baseline`. |
| 23 | edge-cook-age.md | high | The scoped Age command loses the pipeline slug | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:47-51`; `tests/python/test_cook_prose_contract.py:36` |
| 24 | edge-cook-age.md | high | Cook does not transfer `--hard` into Age | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:30,42,51` |
| 25 | edge-cook-age.md | high | Tests do not exercise the seam from both sides | deferred: owned by age | (none) | The adapter in finding 21 must land before a seam test can run. |
| 26 | edge-cook-age.md | medium | Cook does not document the exact `age-route` input | applied | cb2b03b2 | `skills/cook/references/tdd-loop.md:64-66` |
| 27 | edge-cook-cheese.md | blocker | `/cheese --continue <slug>` cannot resolve a Cook report | deferred: owned by wheypoint | (none) | `src/easy_cheese/skills/wheypoint/legacy.py:350-366` searches only `.cheese/notes/<slug>.md`. |
| 28 | edge-cook-cheese.md | high | Cook documents an invalid handoff reader command | applied | cb2b03b2 | `skills/cook/references/fan-pathway.md:48-53`; `tests/python/test_cook_prose_contract.py:95` |
| 29 | edge-cook-cheese.md, edge-press-cook.md, edge-wheypoint-cook.md | high | The nested `baseline:` block cannot cross the seam | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:44-74` defines a one-line artifact reference. `skills/cook/SKILL.md:153` and `:203-206` agree. `tests/python/test_cook_prose_contract.py:58` |
| 30 | edge-cook-cheese.md | high | Cook and Cheese give `artifact:` different meanings | applied | cb2b03b2 | `skills/cook/SKILL.md:150,164-169`; `tests/python/test_cook_prose_contract.py:122` |
| 31 | edge-cook-cheese.md | medium | The Cheese gate example does not match the Cook menu | deferred: owned by cheese | (none) | `skills/cheese/references/handoff-gate.md:27-54` holds the example. |
| 32 | edge-cook-cheese.md | medium | Tests do not run Cook output through Cheese resume | deferred: owned by cheese | (none) | The resolver in finding 27 must land first. |
| 33 | edge-cook-cure.md | blocker | Cook omits the Review to Diagnosis transition | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1043-1119` diagnoses only failed writer output. |
| 34 | edge-cook-cure.md | blocker | Cure does not give the diagnosis to the repair writer | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:331-376` has no diagnosis field. |
| 35 | edge-cook-cure.md | blocker | Cure requires bindings for clean curds | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1192-1198` requires every plan curd. |
| 36 | edge-cook-cure.md | blocker | The file handoff cannot transport diagnosis bindings | deferred: owned by schemas | (none) | `CureDiagnosisBinding` has no registered schema. |
| 37 | edge-cook-cure.md | high | Tests do not exercise the successful Cure seam | deferred: owned by schemas | (none) | Findings 33 to 36 must land first. |
| 38 | edge-cook-mold.md | blocker | The declared payload never crosses a validated boundary | deferred: owned by mold | (none) | `src/easy_cheese/skills/mold/commands.py:10-94` has no intake command. Cook now publishes and names the validated request at `skills/cook/references/fan-pathway.md:113-129`. |
| 39 | edge-cook-mold.md | high | Cook and Mold assign different owners to the planner request | applied | a2b7ccd4 | `skills/cook/references/fan-pathway.md:113-116`; `tests/python/test_cook_prose_contract.py:140` |
| 40 | edge-cook-mold.md | high | Failure semantics do not select a valid request kind | applied | a2b7ccd4 | `skills/cook/references/fan-pathway.md:119-125` |
| 41 | edge-cook-mold.md | high | The status rules can stop the Mold route | applied | a2b7ccd4 | `skills/cook/SKILL.md:20,22` admits `next: mold`. `fan-pathway.md:129` fixes `status: ok`. `tests/python/test_cook_prose_contract.py:153` |
| 42 | edge-cook-mold.md | medium | Tests do not exercise the complete Cook-to-Mold edge | deferred: owned by mold | (none) | Finding 38 must land first. |
| 43 | edge-cook-pasteurize.md | high | Cook cannot consume the documented Pasteurize slug | applied | a2b7ccd4 | `skills/cook/references/quality-gates.md:98-100`; `tests/python/test_cook_prose_contract.py:169` |
| 44 | edge-cook-pasteurize.md | high | Pasteurize cannot emit the canonical handoff | deferred: owned by pasteurize | (none) | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-102` omits the Pasteurize transition. |
| 45 | edge-cook-pasteurize.md | medium | Tests cover only the Cook side of the dispatch | deferred: owned by pasteurize | (none) | Finding 44 must land first. |
| 46 | edge-cook-plate.md | high | The topology resolution has no typed storage contract | deferred: owned by shared | (none) | `src/easy_cheese/shared/handoff.py:38-87` defines no `plate_layout` field. |
| 47 | edge-cook-plate.md | high | Plate rejects the complete Cook `pr_plan` | deferred: owned by plate | (none) | `src/easy_cheese/skills/plate/publication.py:127-133` permits only `plate_layout`. |
| 48 | edge-cook-plate.md, edge-plate-cook.md | high | Terminal Plate dispatch has two owners | applied | cb2b03b2 | `skills/cook/SKILL.md:241-245`; `skills/cook/references/fan-pathway.md:342-346`; `tests/python/test_cook_prose_contract.py:130` |
| 49 | edge-plate-cook.md | blocker | The repair dispatch drops the run identity that Plate needs | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:68,101,111-112`; `tests/python/test_cook_prose_contract.py:69` |
| 50 | edge-plate-cook.md | high | The small-overlap path names an interface that does not exist | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:124-130`; `tests/python/test_cook_prose_contract.py:78` |
| 51 | edge-plate-cook.md | high | The overlap rule has no exact calculation | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:110-119`; `tests/python/test_cook_prose_contract.py:87` |
| 52 | edge-cook-press.md, edge-press-cook.md | blocker | The corrective Press continuation cannot reach Cook | deferred: owned by shared | (none) | `src/easy_cheese/shared/handoff.py:83-87` has no local continuation field. |
| 53 | edge-cook-press.md | high | The typed `CurdResult` payload stops at its declaration | deferred: owned by press | (none) | Press never resolves the declared result. |
| 54 | edge-cook-press.md | medium | Press drops Cook's `durable_flags` | deferred: owned by press | (none) | `skills/press/SKILL.md:94-101` omits the field. |
| 55 | edge-cook-press.md | medium | Press names the retired no-chain owner | deferred: owned by press | (none) | Cook now owns the fan pathway. |
| 56 | edge-wheypoint-cook.md | blocker | Wheypoint cannot carry a non-empty Cook baseline | deferred: owned by wheypoint | (none) | Finding 29 makes the Cook side one line, which Wheypoint can carry. |
| 57 | edge-wheypoint-cook.md | high | The two skill descriptions disagree about the checkpoint route | applied | (none) | Cook already keeps the explicit stop option at `skills/cook/SKILL.md:228`. The Wheypoint sentence is deferred to `wheypoint`. |
| 58 | edge-wheypoint-cook.md | high | The resume command does not match Cook's typed fan contract | applied | (none) | `skills/cook/SKILL.md:34-35,43` already separates a bare slug, a pointer, and `--resume <slug>`. The router rule is deferred to `wheypoint`. |
| 59 | hub-build.md | — | No `cook` row | not applicable | (none) | The note lists only `wheypoint -> build`. |

## Disagreements

- **Cure cap ownership.** `review-cook.md` and `edge-cook-cure.md` say that Age
  owns the two-pass cap. `edge-cook-age.md` says that the Cook phase table owns
  it. I kept Cook ownership. Age has no pass-count input, and
  `skills/age/references/handoff-detail.md:90-107` states that Age does not
  count passes. Age also starts in a fresh context for each pass, so it cannot
  observe a prior pass. The `age` and `cure` cure nodes must remove the
  contrary sentences from their own files.
- **The `--open-pr` propagation rule.** `skills/cook/references/auto-mode.md`
  appended the flag on every chain. `skills/cure/SKILL.md:236-245` forwards it
  only when it is in scope. I kept the Cure rule, because it matches the
  permission model in `skills/cook/SKILL.md:42`.

## Outward dependencies

- `shared` — `write_handoff_artifact` (`--body-file`, `--payload-schema`) and
  `read_handoff_slug` (`--phase`, `--slug`). The reader flags are unchanged;
  Cook prose now matches them.
- `shared` — `publication.accept`. It now rejects a non-`file` URI, so
  `tests/python/test_cook_contract_accept.py` asserts that error.
- `shared` — `handoff.py` preamble parsing. It accepts one physical line for
  each key, which drives the one-line `baseline:` contract.
- `schemas` — `CURD_PLAN_SCHEMA_URI`, `PlannerRequestKind`, `canonical_bytes`,
  `normalize_agent_output`, `validate_contract`, `supported_version_for`. No
  contract changed; Cook now passes bytes instead of text.
- `age` — `age-route` tokens in `skills/age/references/fan-out.md#router-call`.
- `plate` — `topology-preflight` mode and `run_branch` in `repair_dispatch`.
- `mold` — the `PlannerRequest` intake. No Mold command consumes it yet.
- `pasteurize` — the canonical repair handoff. No registered transition yet.

## STE100 status

compliant

No sentence in the nine Cook prose files exceeds 25 words.
No instruction uses the passive voice, except one sentence that a test in
another area locks:

- `skills/cook/SKILL.md:268-269` keeps `A terminal Age is publishable only with
  `next: done`.` and `` `next: cure` or a missing `next` halts the chain.``
  `tests/python/test_ultracook_skills.py:1379-1381` asserts both strings. The
  `build` area owns that file.

## Follow-ups

- `tests/python/test_cook_contract_accept.py::test_cook_pyz_rejects_unsafe_artifact_uri`
  fails against the checked-in `skills/cook/scripts/cook.pyz`. The bundle
  predates the `shared` fix. The barrier node's bundle rebuild clears it. A
  source probe confirms the current behavior: `ERROR: artifact
  'payload-op-unsafe' is not a file:// uri`.
- The `build` area should loosen
  `tests/python/test_ultracook_skills.py:1379-1381`, so Cook can use the active
  voice for its terminal Age gate.
- The `build` area should remove the retired manifest command cluster from
  `src/easy_cheese/skills/cook/commands.py` and rebuild the generated rows.
- The `age` and `cure` areas should remove Cure pass counting from their files.
- The `schemas` area should schedule curds from the plan dependency graph.
