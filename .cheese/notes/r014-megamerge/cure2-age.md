# Cure round 2: age

Every finding from `review-age.md`, the six `age` edge notes, and the three hub
notes appears below. `skill-review-cure.md` does not exist at this commit.

## Commits

| Short SHA | Subject |
| --- | --- |
| `9a17872` | fix(age): harden the review lock against textconv, failure, and scope gaps |
| `a0d9563` | fix(age): correct the report, handoff, and flag contract in SKILL.md |
| `a4241da` | test(age): bind the published report contract to the cure parser |
| `4828042` | fix(age): repair the reference contracts and remove the contradictions |
| `1fb941e` | fix(age): correct the language de-slop catalogs |
| `1e1c5ec` | fix(age): harden the glossary test and repair the remaining STE100 violations |
| `14f20a3` | refactor(age): move the tool table, auto mode, and body order into references |

## Findings

| # | Source note | Severity | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | review-age, hub-shared | blocker | applied | `9a17872` | `review_lock.py:56-64` disables textconv, external diff, hooks, and the fs monitor. `test_age_review_lock.py:293-303` proves it. |
| 2 | review-age, hub-shared, hub-schemas | blocker | applied | `a0d9563` | `SKILL.md:105-115` writes a body-only file. The gated writer creates the report. `test_age_report_contract.py:100-105` proves it. |
| 3 | review-age, hub-shared | blocker | applied | `9a17872` | `review_lock.py:81-100` fails closed for every git error except "not a git repository". `test_age_review_lock.py:306-317` proves it. |
| 4 | review-age | blocker | applied | `9a17872` | `review_lock.py:229-238` hashes the index and the worktree when HEAD is unborn. `test_age_review_lock.py:320-338` proves it. |
| 5 | review-age | blocker | applied | `9a17872` | `review_lock.py:103-118` excludes only this slug's lock, body, report, and HTML. `test_age_review_lock.py:341-370` proves the packet and another slug's report stay in the digest. |
| 6 | review-age, edge-age-cure | high | applied | `a0d9563` | `SKILL.md:113-115,167-175` derives `next` from the one recommended set and keeps every finding. |
| 7 | review-age, edge-cook-age, edge-cure-age | high | applied | `a0d9563`, `14f20a3` | `handoff-detail.md:112-124` holds auto mode. Age counts no passes. `/cook` owns the cap. |
| 8 | review-age, edge-cheese-age, hub-schemas | high | applied | `a0d9563` | `SKILL.md:110-113` passes the resolved artifact and the copied baseline. `test_age_report_contract.py:85-96` proves it. |
| 9 | review-age, edge-age-cure, hub-shared | high | applied | `a0d9563`, `14f20a3` | `report-example.md:8-20` publishes the exact parser form. `test_age_report_contract.py:31-62` parses it with `shared/findings.py`. |
| 10 | review-age, edge-press-age, hub-shared | high | applied | `a0d9563` | `SKILL.md:95-102` resolves the press artifact, validates the preamble, then reads the complete body. |
| 11 | review-age | high | applied | `4828042` | `fan-out.md:19-25` imports `easy_cheese.shared.fanout.age_route` and names the `PYTHONPATH` step. |
| 12 | review-age | high | applied | `4828042` | `sub-agent-gate.md:15-17` names the one Age lens-worker exception to the 2 KB ceiling. |
| 13 | review-age | high | applied | `4828042` | `packet.md:11,16,25-28` uses the real section names and the `### <dimension>` boundaries. |
| 14 | review-age | high | applied | `4828042` | `fan-out.md:105-107` keeps an escalated claim out of the findings sections. |
| 15 | review-age | high | applied | `4828042` | `voice.md:27-33` scopes the apply rule to a write-enabled phase. |
| 16 | review-age | high | applied | `4828042` | `dimensions.md:385-390` is the single ownership rule. Each `Boundaries:` line points there. |
| 17 | review-age | high | applied | `1fb941e` | `deslop-rust.md:40-42,110-112,146-149` corrects the `?`, `.expect()`, regex, and assertion advice. |
| 18 | review-age | high | applied | `1fb941e` | `deslop-rust.md:290-298,466-476` gives one suppression table and removes the equivalent `RUSTFLAGS` replacement. |
| 19 | review-age | high | applied | `1fb941e` | `deslop-shell.md:10-22,72-79,140-143,236-243` detects the shell and uses `return` in a sourced function. |
| 20 | review-age | high | applied | `1fb941e` | `deslop-typescript.md:96-104,116-121,205-210` preserves null semantics, handles the rejection, and states the clone requirements. |
| 21 | review-age | high | applied | `9a17872` | `review_lock.py:212-216,283-287` resolves the top-level work tree first. `test_age_review_lock.py:373-392` proves the nested case. |
| 22 | review-age | high | applied | `9a17872` | `review_lock.py:242-250,265-279` rejects a symlink component and writes with `O_NOFOLLOW`. `test_age_review_lock.py:395-405` proves it. |
| 23 | review-age | medium | applied | `a0d9563` | Frontmatter now says review every requested dimension, and all ten by default. |
| 24 | review-age, edge-cheese-age, edge-press-age | medium | applied | `a0d9563` | `SKILL.md:19-20` carries `[--hard]` on both forms. `test_age_report_contract.py:109-115` proves it. |
| 25 | review-age | medium | applied | `a0d9563` | `SKILL.md:160` reserves `don't know` for the report-level `## Confidence` line. |
| 26 | review-age | medium | applied | `14f20a3` | The effort table keeps `high` as the default. The prose under it uses the router's `low`, `medium`, or `high` value. `tests/python/test_agent_resolution_contract.py` fixes the cell vocabulary. |
| 27 | review-age, hub-schemas | medium | applied | `a0d9563`, `14f20a3` | `SKILL.md:186-188` records `## Agent resolution` in the body. `report-example.md § Body order` shows the section. |
| 28 | review-age | medium | applied | `4828042` | `fan-out.md:32-37` separates the base tier from the returned lens count. |
| 29 | review-age | medium | applied | `4828042` | `fan-out.md:100-104` verifies bounded batches with one result object for each claim. |
| 30 | review-age | medium | applied | `4828042` | `dimensions.md:24-27` states the sequential rule and the blocker cap. The packet now names one batch extraction. |
| 31 | review-age | medium | applied | `4828042` | `packet.md:13` detects the source roots and adds task-specific helper candidates. |
| 32 | review-age | medium | applied | `1fb941e` | `deslop-go.md:31-34,49-55,86-90` separates the named result from the bare return and describes an interface value correctly. |
| 33 | review-age | medium | applied | `1fb941e` | `deslop-python.md:31-47,55-63,90-93` states each precondition and adds the lazy-logging alternative. |
| 34 | review-age | medium | applied | `1fb941e` | `deslop-typescript.md:141-146,251-254` states the tree-shaking conditions and cites the applicable rule. |
| 35 | review-age | medium | applied | `4828042` | `report-example.md:44` uses `../../cook/`. The placeholders are now short instructions. |
| 36 | review-age | medium | applied | `4828042` | `handoff-detail.md:34-35` outdents the high option to a peer bullet. |
| 37 | review-age | medium | applied | `1e1c5ec` | `test_glossary_consumers.py:41-53` asserts a positive read directive and rejects a nearby negation. |
| 38 | review-age, hub-shared | medium | deferred: owned by shared | — | `age-route --help` parses the flag as JSON in `shared/bundle_commands.py` `json_command`. The generated preamble in `scripts/render_generated_regions.py` is owned by build. |
| 39 | review-age | low | applied | `4828042` | `dimensions.md:24-27` states the sequential rule. |
| 40 | review-age, hub-shared | low | applied | `1e1c5ec` | `commands.py:130` and `references/commands.md:16` say `Record`. |
| 41 | review-age | low | applied | `9a17872` | `verify()` validates the lock before the digest at `review_lock.py:319-325`. |
| 42 | review-age | low | rejected: not contained | — | A slug-specific input manifest for the lock digest changes the gate's threat model. The narrowed exclusion in finding 5 already removes the false pass. A manifest would reintroduce one. |
| 43 | review-age | low | applied | `1fb941e` | `deslop-shell.md:107-114` prefers `find` and uses `fd` only when the project declares it. |
| 44 | review-age | low | partly applied | `4828042` | `handoff-detail.md:90-100` names the current Cook flow and drops `curds`. The `/ultracook` alias note stays, because `tests/python/test_ultracook_skills.py:779-793` (build area) requires the term. Deferred: owned by build. |
| 45 | review-age | low | applied | `4828042` | `packet.md:5-8` states the true rebuild purpose. |
| 46 | review-age | low | applied | `4828042` | `sub-agent-gate.md:11-17,50-56` defines the size unit and links `SKILL.md § Sub-agent fan-out`. |
| 47 | review-age (simplification) | — | applied | `a0d9563` | `--comprehensive` is gone from `## Inputs`. |
| 48 | review-age (simplification) | — | rejected: owned by cheese | — | Moving `voice.md` and `sub-agent-gate.md` into the shared Cheese references touches seven other skills and the `cheese` area. Out of scope for this node. |
| 49 | review-age (simplification) | — | applied | `4828042` | The deferred v2 rubric is gone from `dimensions.md`. |
| 50 | review-age (simplification) | — | applied | `4828042` | `fan-out.md § Router call` owns the topology. `sub-agent-gate.md:54-56` points there. |
| 51 | review-age (simplification) | — | applied | `4828042` | `packet.md:16` names the exact `### <dimension>` extraction. |
| 52 | review-age (simplification) | — | applied | `4828042` | `report-example.md:59-77` holds placeholders. The worked findings appear once. |
| 53 | review-age (simplification) | — | rejected: not behaviour-preserving | — | One binary git runner would merge `_run_git` and `_stream_git`. The first needs a captured result for a returncode decision. The second must stream to the digest. Merging them would buffer the whole diff in memory. |
| 54 | review-age (simplification) | — | rejected: superseded | — | Removing the whole-file glossary test happened in finding 37, which replaced it with a stronger Flow assertion. |
| 55 | review-age (simplification) | — | rejected: low value | — | A shared lock-digest helper for `test_age_review_lock.py` saves four lines and hides the parse the test asserts on. |
| 56 | edge-age-cure | blocker | deferred: owned by schemas | — | Age emits Markdown; the typed Cure API needs a `CurdPlan` pointer. `cure2-schemas.md` owns the adapter. Age keeps the normal report path, which findings 8, 9, and 10 repaired. |
| 57 | edge-age-cure | high | applied | `a0d9563` | Same as finding 9. |
| 58 | edge-age-cure | high | applied | `a0d9563` | Same as finding 6. |
| 59 | edge-age-cure | high | applied | `a0d9563` | Same as finding 10. |
| 60 | edge-age-cure | high | applied | `a0d9563` | Same as finding 2. |
| 61 | edge-age-cure | medium | applied | `a0d9563`, `14f20a3` | `handoff-detail.md:120` forwards `--open-pr` and `--hard` on every auto dispatch. |
| 62 | edge-cheese-age | high | applied | `a0d9563` | Same as finding 8. |
| 63 | edge-cheese-age | high | deferred: owned by cheese | — | The coherence check at `skills/cheese/references/coherence-check.md:28-32` stops a valid pull-request route. Age already accepts a reference, a range, a path, and a slug at `SKILL.md:24-28`. |
| 64 | edge-cheese-age | medium | applied | `a0d9563` | `SKILL.md:39-42` accepts optional `handoff_context.wiki_hits` and reuses each valid hit. |
| 65 | edge-cheese-age | medium | applied | `a0d9563` | Same as finding 24. |
| 66 | edge-cheese-age | medium | deferred: owned by cheese | — | The Cheese-to-Age route table tests belong to `tests/python/test_cheese_routing_receipt.py`. |
| 67 | edge-cook-age | blocker | deferred: owned by schemas | — | The typed `ReviewRequest` to `ReviewResultWriterView` adapter and the `blocker` versus `critical` severity term live in `src/easy_cheese_schemas`. |
| 68 | edge-cook-age | high | applied | `a0d9563` | Same as finding 8. |
| 69 | edge-cook-age | high | applied | `a0d9563`, `14f20a3` | Same as finding 7. |
| 70 | edge-cook-age | high | applied | `a0d9563` | `SKILL.md:19,22-28` adds `--slug <slug>` and repeated `--scope <path>`. `test_age_report_contract.py:118-124` proves it. |
| 71 | edge-cook-age | high | applied | `a0d9563` | Same as finding 24. Age accepts the flag on both forms. Cook's own dispatch is deferred: owned by cook. |
| 72 | edge-cook-age | high | deferred: owned by cook | — | The two-sided Cook handoff to Age phase-decision test belongs to `tests/fanout/python`. |
| 73 | edge-cook-age | medium | deferred: owned by cook | — | `skills/cook/references/tdd-loop.md:53-64` must list the exact `age-route` tokens and link `fan-out.md#router-call`. Age publishes both at `fan-out.md:5-25`. |
| 74 | edge-cure-age | blocker | deferred: owned by schemas | — | Same adapter as finding 67. |
| 75 | edge-cure-age | high | deferred: owned by cure | — | The Cure writer drops its own report body. `skills/cure/SKILL.md:151-159` owns that command. |
| 76 | edge-cure-age | high | applied | `a0d9563` | Same as finding 70. Age now accepts repeated `--scope` and a required slug. |
| 77 | edge-cure-age | high | applied | `a0d9563`, `14f20a3` | Same as finding 7. |
| 78 | edge-cure-age | high | deferred: owned by cure | — | The end-to-end Cure-to-Age test needs the Cure writer fix in finding 75 first. |
| 79 | edge-cure-age | medium | deferred: owned by cure | — | `skills/cure/SKILL.md:161` misstates the `next` field. |
| 80 | edge-plate-age | medium | deferred: owned by plate | — | The cross-skill Plate-to-Age route test belongs to `tests/python/test_plate_contract.py`. |
| 81 | edge-plate-age | low | deferred: owned by plate | — | `skills/plate/SKILL.md:20` puts two prohibitions in one sentence. |
| 82 | edge-press-age | high | deferred: owned by press and shared | — | Press puts `action:` and `telemetry:` before the orientation, which the canonical parser misreads. `press_route.py` and `skills/press/SKILL.md` own the fix. Age now reads the complete press body (finding 10), so the review follow-ups reach the report. |
| 83 | edge-press-age | high | applied | `a0d9563` | Same as finding 10. |
| 84 | edge-press-age | medium | deferred: owned by press | — | The full Press report round-trip test belongs to `tests/shared/python`. |
| 85 | edge-press-age | low | applied | `a0d9563` | Same as finding 24. |
| 86 | hub-shared | blocker | applied | `9a17872` | Same as findings 1 and 3. |
| 87 | hub-shared | blocker | applied | `a0d9563` | Same as finding 2. |
| 88 | hub-shared | high | deferred: owned by shared | — | `read_handoff_slug.py:19-45` returns preamble fields only. Age no longer depends on it for the body (finding 10). |
| 89 | hub-shared | high | applied | `a0d9563` | Same as finding 9. |
| 90 | hub-shared | high | applied | `a0d9563` | Same as finding 8. |
| 91 | hub-schemas | blocker | applied | `a0d9563` | Same as finding 2. |
| 92 | hub-schemas | high | applied | `a0d9563` | Same as finding 8. |
| 93 | hub-build | high | deferred: owned by build | — | `scripts/check_bundles.py:461-499` reads only literal `Command(...)` calls. No `age` file is involved. |

## Broken edges

| Edge | This side now | Note |
| --- | --- | --- |
| `age -> shared` | matches | The writer receives an artifact, a baseline, and a body-only file. The lock fails closed. The published finding form matches `shared/findings.py`. |
| `cook -> age` | matches | Age holds no pass counter. It accepts `--hard`, a slug, and repeated scopes. The typed adapter is deferred to `schemas`. |
| `age -> cure` | matches | The report carries every finding, the parser form, the press follow-ups, and a `next` derived from one selection. |
| `affinage -> age` | matches | `sub-agent-gate.md` no longer claims that Affinage uses the Age router. |
| `build -> age` | partly | `commands.md` now advertises record-only `review-lock`. The `--help` promise is deferred to `shared` and `build`. |
| `press -> age` | partly | Age reads the complete press body. The Press preamble order is deferred to `press`. |
| `cheese -> age` | matches | Age accepts routed `wiki_hits` and both flag forms. The coherence rule is deferred to `cheese`. |
| `plate -> age` | unchanged | The contract already agreed. Only the missing test remains, deferred to `plate`. |

## Disagreements

- `review-age.md` asks for a slug-specific lock manifest (low). `hub-schemas.md` and
  `review-age.md` blocker 5 ask the lock to cover the packet. The two conflict.
  I kept the typed gate contract: the lock covers every review input except this
  slug's own outputs. Finding 42 records the rejection.
- `review-age.md` asks to remove every `/ultracook` term (low).
  `tests/python/test_ultracook_skills.py:779-793` in the build area requires the
  term. I kept one alias sentence that names `/cook` as the live flow, and
  deferred the test change to `build`. Finding 44 records the choice.
- `review-age.md` asks the effort table to accept the router value (medium).
  `tests/python/test_agent_resolution_contract.py:33` restricts the cell to
  `low`, `medium`, or `high`. I kept the typed vocabulary in the cell and put the
  router override in prose. Finding 26 records the choice.

## Test state

- The area gate passes: `ruff`, `just typecheck`, `validate_skills.py`, and 34
  area tests.
- `tests/python` reports 1588 passes and 23 failures.
- All 23 failures also fail at `c7a75d48`, the commit before this node.
- The failures are `test_pyz_bundle.py` (stale bundles), `test_cook_contract_accept.py`,
  `test_shared_migrate.py`, and `test_build_pyz_tree_staging.py`. No `age` file is involved.

## STE100 status

compliant

- Every file that `review-age.md § STE100 status` names is repaired.
- This note uses short active sentences and one term for each meaning.
