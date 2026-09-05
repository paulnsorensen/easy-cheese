# Skill review cure — merged record

This note merges every row of every `cure2-*.md` note in this directory.
Each row keeps its source note, its area, its severity, its state, its
commit, and its evidence.

## Method

A script read the findings table of each `cure2-*.md` note.
It kept every table that has a `Severity` column and a `State` column.
It did not keep the commit tables, the edge tables, or the simplification
tables. A row that names no commit shows `—` in that column.

The second section lists each `deferred` row that no area applied.
A deferral names an owning area. The script marked a deferral as applied
only when that owning area also has an applied row whose evidence names the
same file. Every other deferral appears in the list below.

## Totals

| Measure | Count |
| --- | --- |
| Findings merged | 696 |
| Applied | 405 |
| Deferred | 243 |
| Rejected | 21 |
| Other state | 27 |
| Deferred with no matching applied fix | 158 |

## Every finding

| Source note | Area | Severity | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-affinage.md | `affinage` | blocker | applied | `0618f58d` | `skills/affinage/references/merge-conflict.md:12-20`; `skills/affinage/SKILL.md:108-116` |
| review-affinage.md | `affinage` | blocker | applied | `11d86ff4`, `7fbc587c` | `skills/affinage/references/handoff-templates.md:30-46`; `skills/affinage/SKILL.md:99-107` |
| review-affinage.md | `affinage` | high | applied | `fe6c68b4`, `8b932f03` | `skills/affinage/SKILL.md:62-68` |
| review-affinage.md, hub-shared.md | `affinage` | high | applied | `4404d5a2` | `skills/affinage/SKILL.md:189` |
| review-affinage.md | `affinage` | high | applied | `12c0ddf7` | `skills/affinage/references/report-template.md:40-43,78-79` |
| review-affinage.md | `affinage` | high | deferred: owned by the Affinage runtime module `post_reply.py`, which is outside the eight area paths | none | `src/easy_cheese/skills/affinage/post_reply.py:134-136` |
| review-affinage.md | `affinage` | medium | applied | `3e503090` | `skills/affinage/SKILL.md:44-46,54-57,87-88`; `references/flow-details.md:23,56-58,75-76`; `references/handoff-templates.md:21-24`; `references/auto-mode.md:11` |
| review-affinage.md | `affinage` | low | applied | `3e503090` | `skills/affinage/SKILL.md:174-175` |
| edge-affinage-cure.md | `affinage` | blocker | deferred: owned by cure and schemas; the fix adds a report repair path to `skills/cure/SKILL.md` and `src/easy_cheese_schemas/workflow.py` | none | `skills/cure/SKILL.md:49-75`; `src/easy_cheese_schemas/workflow.py:1180-1210` |
| edge-affinage-cure.md | `affinage` | high | applied on this side | `c024ea79` | `skills/affinage/references/report-template.md:7-12,26-43`; `tests/python/test_affinage_contract.py:121-136` |
| edge-affinage-cure.md | `affinage` | high | deferred: owned by cure; the fix loads `handoff_context.source_report` in `skills/cure/SKILL.md` | none | `skills/cure/SKILL.md:14-20`; `skills/cure/references/selection.md:23-45` |
| edge-affinage-cure.md | `affinage` | medium | deferred: owned by cure; the fix binds the Cure slug and headings in `skills/cure/SKILL.md` | none | `skills/cure/SKILL.md:135-180` |
| edge-affinage-cure.md | `affinage` | medium | applied on this side | `109a385a` | `tests/python/test_affinage_contract.py:118-136` |
| edge-affinage-hard-cheese.md | `affinage` | high | applied | `109a385a` | `tests/python/test_affinage_contract.py:139-160` |
| edge-affinage-pasteurize.md | `affinage` | blocker | deferred: owned by pasteurize; the fix adds output matchers to `repro_rerun.py` | none | `src/easy_cheese/skills/pasteurize/repro_rerun.py:42-56` |
| edge-affinage-pasteurize.md | `affinage` | high | deferred: owned by pasteurize; the fix adds a typed investigation request and result to `skills/pasteurize/SKILL.md` | none | `skills/pasteurize/SKILL.md:245-268` |
| edge-affinage-pasteurize.md | `affinage` | medium | deferred: the producer test needs the Pasteurize request contract from finding 16 | none | `skills/affinage/references/flow-details.md:86-91` |
| edge-cheese-affinage.md | `affinage` | high | applied on this side | `602b862f` | `skills/affinage/SKILL.md:36-40,73-75`; `tests/python/test_affinage_contract.py:166-172` |
| edge-cheese-affinage.md | `affinage` | high | deferred: owned by schemas; the fix registers an Affinage phase contract in `_compiled_phase_registry.py` | none | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103` |
| edge-cheese-affinage.md | `affinage` | medium | deferred: owned by cheese; the fix adds a typed `pr_ref` field to `continue-resume.md` | none | `skills/cheese/references/continue-resume.md:104-108` |
| edge-cheese-affinage.md | `affinage` | medium | applied | `602b862f` | `skills/affinage/SKILL.md:44-47`; `tests/python/test_affinage_contract.py:175-177` |
| edge-cheese-affinage.md | `affinage` | medium | applied on this side | `602b862f`, `109a385a` | `tests/python/test_affinage_contract.py:166-177` |
| hub-shared.md | `affinage` | medium | deferred: owned by shared; the fix adds help handling to `json_command` | none | `src/easy_cheese/shared/bundle_commands.py` |
| hub-schemas.md | `affinage` | blocker | deferred: owned by schemas and cure | none | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| hub-schemas.md | `affinage` | high | deferred: owned by cheese and schemas | none | `skills/cheese/references/continue-resume.md:98-122` |
| hub-build.md | `affinage` | — | not applicable | none | `.cheese/notes/r014-megamerge/hub-build.md` |
| review-age, hub-shared | `age` | blocker | applied | `9a17872` | `review_lock.py:56-64` disables textconv, external diff, hooks, and the fs monitor. `test_age_review_lock.py:293-303` proves it. |
| review-age, hub-shared, hub-schemas | `age` | blocker | applied | `a0d9563` | `SKILL.md:105-115` writes a body-only file. The gated writer creates the report. `test_age_report_contract.py:100-105` proves it. |
| review-age, hub-shared | `age` | blocker | applied | `9a17872` | `review_lock.py:81-100` fails closed for every git error except "not a git repository". `test_age_review_lock.py:306-317` proves it. |
| review-age | `age` | blocker | applied | `9a17872` | `review_lock.py:229-238` hashes the index and the worktree when HEAD is unborn. `test_age_review_lock.py:320-338` proves it. |
| review-age | `age` | blocker | applied | `9a17872` | `review_lock.py:103-118` excludes only this slug's lock, body, report, and HTML. `test_age_review_lock.py:341-370` proves the packet and another slug's report stay in the digest. |
| review-age, edge-age-cure | `age` | high | applied | `a0d9563` | `SKILL.md:113-115,167-175` derives `next` from the one recommended set and keeps every finding. |
| review-age, edge-cook-age, edge-cure-age | `age` | high | applied | `a0d9563`, `14f20a3` | `handoff-detail.md:112-124` holds auto mode. Age counts no passes. `/cook` owns the cap. |
| review-age, edge-cheese-age, hub-schemas | `age` | high | applied | `a0d9563` | `SKILL.md:110-113` passes the resolved artifact and the copied baseline. `test_age_report_contract.py:85-96` proves it. |
| review-age, edge-age-cure, hub-shared | `age` | high | applied | `a0d9563`, `14f20a3` | `report-example.md:8-20` publishes the exact parser form. `test_age_report_contract.py:31-62` parses it with `shared/findings.py`. |
| review-age, edge-press-age, hub-shared | `age` | high | applied | `a0d9563` | `SKILL.md:95-102` resolves the press artifact, validates the preamble, then reads the complete body. |
| review-age | `age` | high | applied | `4828042` | `fan-out.md:19-25` imports `easy_cheese.shared.fanout.age_route` and names the `PYTHONPATH` step. |
| review-age | `age` | high | applied | `4828042` | `sub-agent-gate.md:15-17` names the one Age lens-worker exception to the 2 KB ceiling. |
| review-age | `age` | high | applied | `4828042` | `packet.md:11,16,25-28` uses the real section names and the `### <dimension>` boundaries. |
| review-age | `age` | high | applied | `4828042` | `fan-out.md:105-107` keeps an escalated claim out of the findings sections. |
| review-age | `age` | high | applied | `4828042` | `voice.md:27-33` scopes the apply rule to a write-enabled phase. |
| review-age | `age` | high | applied | `4828042` | `dimensions.md:385-390` is the single ownership rule. Each `Boundaries:` line points there. |
| review-age | `age` | high | applied | `1fb941e` | `deslop-rust.md:40-42,110-112,146-149` corrects the `?`, `.expect()`, regex, and assertion advice. |
| review-age | `age` | high | applied | `1fb941e` | `deslop-rust.md:290-298,466-476` gives one suppression table and removes the equivalent `RUSTFLAGS` replacement. |
| review-age | `age` | high | applied | `1fb941e` | `deslop-shell.md:10-22,72-79,140-143,236-243` detects the shell and uses `return` in a sourced function. |
| review-age | `age` | high | applied | `1fb941e` | `deslop-typescript.md:96-104,116-121,205-210` preserves null semantics, handles the rejection, and states the clone requirements. |
| review-age | `age` | high | applied | `9a17872` | `review_lock.py:212-216,283-287` resolves the top-level work tree first. `test_age_review_lock.py:373-392` proves the nested case. |
| review-age | `age` | high | applied | `9a17872` | `review_lock.py:242-250,265-279` rejects a symlink component and writes with `O_NOFOLLOW`. `test_age_review_lock.py:395-405` proves it. |
| review-age | `age` | medium | applied | `a0d9563` | Frontmatter now says review every requested dimension, and all ten by default. |
| review-age, edge-cheese-age, edge-press-age | `age` | medium | applied | `a0d9563` | `SKILL.md:19-20` carries `[--hard]` on both forms. `test_age_report_contract.py:109-115` proves it. |
| review-age | `age` | medium | applied | `a0d9563` | `SKILL.md:160` reserves `don't know` for the report-level `## Confidence` line. |
| review-age | `age` | medium | applied | `14f20a3` | The effort table keeps `high` as the default. The prose under it uses the router's `low`, `medium`, or `high` value. `tests/python/test_agent_resolution_contract.py` fixes the cell vocabulary. |
| review-age, hub-schemas | `age` | medium | applied | `a0d9563`, `14f20a3` | `SKILL.md:186-188` records `## Agent resolution` in the body. `report-example.md § Body order` shows the section. |
| review-age | `age` | medium | applied | `4828042` | `fan-out.md:32-37` separates the base tier from the returned lens count. |
| review-age | `age` | medium | applied | `4828042` | `fan-out.md:100-104` verifies bounded batches with one result object for each claim. |
| review-age | `age` | medium | applied | `4828042` | `dimensions.md:24-27` states the sequential rule and the blocker cap. The packet now names one batch extraction. |
| review-age | `age` | medium | applied | `4828042` | `packet.md:13` detects the source roots and adds task-specific helper candidates. |
| review-age | `age` | medium | applied | `1fb941e` | `deslop-go.md:31-34,49-55,86-90` separates the named result from the bare return and describes an interface value correctly. |
| review-age | `age` | medium | applied | `1fb941e` | `deslop-python.md:31-47,55-63,90-93` states each precondition and adds the lazy-logging alternative. |
| review-age | `age` | medium | applied | `1fb941e` | `deslop-typescript.md:141-146,251-254` states the tree-shaking conditions and cites the applicable rule. |
| review-age | `age` | medium | applied | `4828042` | `report-example.md:44` uses `../../cook/`. The placeholders are now short instructions. |
| review-age | `age` | medium | applied | `4828042` | `handoff-detail.md:34-35` outdents the high option to a peer bullet. |
| review-age | `age` | medium | applied | `1e1c5ec` | `test_glossary_consumers.py:41-53` asserts a positive read directive and rejects a nearby negation. |
| review-age, hub-shared | `age` | medium | deferred: owned by shared | — | `age-route --help` parses the flag as JSON in `shared/bundle_commands.py` `json_command`. The generated preamble in `scripts/render_generated_regions.py` is owned by build. |
| review-age | `age` | low | applied | `4828042` | `dimensions.md:24-27` states the sequential rule. |
| review-age, hub-shared | `age` | low | applied | `1e1c5ec` | `commands.py:130` and `references/commands.md:16` say `Record`. |
| review-age | `age` | low | applied | `9a17872` | `verify()` validates the lock before the digest at `review_lock.py:319-325`. |
| review-age | `age` | low | rejected: not contained | — | A slug-specific input manifest for the lock digest changes the gate's threat model. The narrowed exclusion in finding 5 already removes the false pass. A manifest would reintroduce one. |
| review-age | `age` | low | applied | `1fb941e` | `deslop-shell.md:107-114` prefers `find` and uses `fd` only when the project declares it. |
| review-age | `age` | low | partly applied | `4828042` | `handoff-detail.md:90-100` names the current Cook flow and drops `curds`. The `/ultracook` alias note stays, because `tests/python/test_ultracook_skills.py:779-793` (build area) requires the term. Deferred: owned by build. |
| review-age | `age` | low | applied | `4828042` | `packet.md:5-8` states the true rebuild purpose. |
| review-age | `age` | low | applied | `4828042` | `sub-agent-gate.md:11-17,50-56` defines the size unit and links `SKILL.md § Sub-agent fan-out`. |
| review-age (simplification) | `age` | — | applied | `a0d9563` | `--comprehensive` is gone from `## Inputs`. |
| review-age (simplification) | `age` | — | rejected: owned by cheese | — | Moving `voice.md` and `sub-agent-gate.md` into the shared Cheese references touches seven other skills and the `cheese` area. Out of scope for this node. |
| review-age (simplification) | `age` | — | applied | `4828042` | The deferred v2 rubric is gone from `dimensions.md`. |
| review-age (simplification) | `age` | — | applied | `4828042` | `fan-out.md § Router call` owns the topology. `sub-agent-gate.md:54-56` points there. |
| review-age (simplification) | `age` | — | applied | `4828042` | `packet.md:16` names the exact `### <dimension>` extraction. |
| review-age (simplification) | `age` | — | applied | `4828042` | `report-example.md:59-77` holds placeholders. The worked findings appear once. |
| review-age (simplification) | `age` | — | rejected: not behaviour-preserving | — | One binary git runner would merge `_run_git` and `_stream_git`. The first needs a captured result for a returncode decision. The second must stream to the digest. Merging them would buffer the whole diff in memory. |
| review-age (simplification) | `age` | — | rejected: superseded | — | Removing the whole-file glossary test happened in finding 37, which replaced it with a stronger Flow assertion. |
| review-age (simplification) | `age` | — | rejected: low value | — | A shared lock-digest helper for `test_age_review_lock.py` saves four lines and hides the parse the test asserts on. |
| edge-age-cure | `age` | blocker | deferred: owned by schemas | — | Age emits Markdown; the typed Cure API needs a `CurdPlan` pointer. `cure2-schemas.md` owns the adapter. Age keeps the normal report path, which findings 8, 9, and 10 repaired. |
| edge-age-cure | `age` | high | applied | `a0d9563` | Same as finding 9. |
| edge-age-cure | `age` | high | applied | `a0d9563` | Same as finding 6. |
| edge-age-cure | `age` | high | applied | `a0d9563` | Same as finding 10. |
| edge-age-cure | `age` | high | applied | `a0d9563` | Same as finding 2. |
| edge-age-cure | `age` | medium | applied | `a0d9563`, `14f20a3` | `handoff-detail.md:120` forwards `--open-pr` and `--hard` on every auto dispatch. |
| edge-cheese-age | `age` | high | applied | `a0d9563` | Same as finding 8. |
| edge-cheese-age | `age` | high | deferred: owned by cheese | — | The coherence check at `skills/cheese/references/coherence-check.md:28-32` stops a valid pull-request route. Age already accepts a reference, a range, a path, and a slug at `SKILL.md:24-28`. |
| edge-cheese-age | `age` | medium | applied | `a0d9563` | `SKILL.md:39-42` accepts optional `handoff_context.wiki_hits` and reuses each valid hit. |
| edge-cheese-age | `age` | medium | applied | `a0d9563` | Same as finding 24. |
| edge-cheese-age | `age` | medium | deferred: owned by cheese | — | The Cheese-to-Age route table tests belong to `tests/python/test_cheese_routing_receipt.py`. |
| edge-cook-age | `age` | blocker | deferred: owned by schemas | — | The typed `ReviewRequest` to `ReviewResultWriterView` adapter and the `blocker` versus `critical` severity term live in `src/easy_cheese_schemas`. |
| edge-cook-age | `age` | high | applied | `a0d9563` | Same as finding 8. |
| edge-cook-age | `age` | high | applied | `a0d9563`, `14f20a3` | Same as finding 7. |
| edge-cook-age | `age` | high | applied | `a0d9563` | `SKILL.md:19,22-28` adds `--slug <slug>` and repeated `--scope <path>`. `test_age_report_contract.py:118-124` proves it. |
| edge-cook-age | `age` | high | applied | `a0d9563` | Same as finding 24. Age accepts the flag on both forms. Cook's own dispatch is deferred: owned by cook. |
| edge-cook-age | `age` | high | deferred: owned by cook | — | The two-sided Cook handoff to Age phase-decision test belongs to `tests/fanout/python`. |
| edge-cook-age | `age` | medium | deferred: owned by cook | — | `skills/cook/references/tdd-loop.md:53-64` must list the exact `age-route` tokens and link `fan-out.md#router-call`. Age publishes both at `fan-out.md:5-25`. |
| edge-cure-age | `age` | blocker | deferred: owned by schemas | — | Same adapter as finding 67. |
| edge-cure-age | `age` | high | deferred: owned by cure | — | The Cure writer drops its own report body. `skills/cure/SKILL.md:151-159` owns that command. |
| edge-cure-age | `age` | high | applied | `a0d9563` | Same as finding 70. Age now accepts repeated `--scope` and a required slug. |
| edge-cure-age | `age` | high | applied | `a0d9563`, `14f20a3` | Same as finding 7. |
| edge-cure-age | `age` | high | deferred: owned by cure | — | The end-to-end Cure-to-Age test needs the Cure writer fix in finding 75 first. |
| edge-cure-age | `age` | medium | deferred: owned by cure | — | `skills/cure/SKILL.md:161` misstates the `next` field. |
| edge-plate-age | `age` | medium | deferred: owned by plate | — | The cross-skill Plate-to-Age route test belongs to `tests/python/test_plate_contract.py`. |
| edge-plate-age | `age` | low | deferred: owned by plate | — | `skills/plate/SKILL.md:20` puts two prohibitions in one sentence. |
| edge-press-age | `age` | high | deferred: owned by press and shared | — | Press puts `action:` and `telemetry:` before the orientation, which the canonical parser misreads. `press_route.py` and `skills/press/SKILL.md` own the fix. Age now reads the complete press body (finding 10), so the review follow-ups reach the report. |
| edge-press-age | `age` | high | applied | `a0d9563` | Same as finding 10. |
| edge-press-age | `age` | medium | deferred: owned by press | — | The full Press report round-trip test belongs to `tests/shared/python`. |
| edge-press-age | `age` | low | applied | `a0d9563` | Same as finding 24. |
| hub-shared | `age` | blocker | applied | `9a17872` | Same as findings 1 and 3. |
| hub-shared | `age` | blocker | applied | `a0d9563` | Same as finding 2. |
| hub-shared | `age` | high | deferred: owned by shared | — | `read_handoff_slug.py:19-45` returns preamble fields only. Age no longer depends on it for the body (finding 10). |
| hub-shared | `age` | high | applied | `a0d9563` | Same as finding 9. |
| hub-shared | `age` | high | applied | `a0d9563` | Same as finding 8. |
| hub-schemas | `age` | blocker | applied | `a0d9563` | Same as finding 2. |
| hub-schemas | `age` | high | applied | `a0d9563` | Same as finding 8. |
| hub-build | `age` | high | deferred: owned by build | — | `scripts/check_bundles.py:461-499` reads only literal `Command(...)` calls. No `age` file is involved. |
| review-briesearch.md | `briesearch` | blocker | applied: `ground-check` rejects user information, a query value, and a fragment in a cited URL before the digest match | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:352-378`; `tests/python/test_briesearch_ledger.py:264-283` |
| review-briesearch.md | `briesearch` | blocker | applied: `budget-check` reports `BUDGET_UNDECLARED` for a used call kind with no declared limit | 71cf187 | `src/easy_cheese/skills/briesearch/budget.py:170-192`; `tests/python/test_briesearch_budget.py:355-374` |
| review-briesearch.md | `briesearch` | blocker | applied: local citations resolve under an allowed root, and both anchor forms are range-checked | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:241-305`; `tests/python/test_briesearch_ledger.py:286-330` |
| review-briesearch.md | `briesearch` | blocker | applied: the ledger retains `slug`, `title`, and `fetched`; `MANIFEST` binds the slug and the stored body; `FRESHNESS` binds the row date | d17975f, c2f8a8e | `src/easy_cheese/skills/briesearch/ledger.py:117-123,142`; `ground_check.py:568-612`; `tests/python/test_briesearch_ledger.py:369-425` |
| review-briesearch.md, hub-shared.md | `briesearch` | high | applied: `research_layout` enforces the four-to-six-word slug | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:27-31,52-65`; `tests/python/test_briesearch_research_layout.py:26-58` |
| review-briesearch.md | `briesearch` | high | applied: the table row parser is escape-aware | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:126-152`; `tests/python/test_briesearch_ledger.py:339-349` |
| review-briesearch.md | `briesearch` | medium | applied: a cached record no longer spends the call budget | 71cf187 | `src/easy_cheese/skills/briesearch/budget.py:110-113,177-192`; `tests/python/test_briesearch_budget.py:383-397` |
| review-briesearch.md | `briesearch` | medium | applied: confidence labels compare exactly, so a case variant fails | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:537-546`; `tests/python/test_briesearch_ledger.py:352-362` |
| review-briesearch.md | `briesearch` | low | applied: line counts are cached for each resolved path in one report check | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:200-208` |
| review-briesearch.md | `briesearch` | low | applied: seven prose files now follow ASD-STE100 | 3140259 | `skills/briesearch/SKILL.md:19`; `skills/briesearch/references/synthesis.md:3,24` |
| review-briesearch.md | `briesearch` | simplification | applied: `Call.canonical` is deleted; `_url_fields` returns two URL fields | d17975f | `src/easy_cheese/skills/briesearch/ledger.py:233-265` |
| review-briesearch.md | `briesearch` | simplification | applied: `commands.py` keeps the shared `derive_command` helper without change | none | `src/easy_cheese/skills/briesearch/commands.py:42-56` |
| edge-briesearch-mold.md, edge-mold-briesearch.md | `briesearch` | high | applied: `ResearchLayout` returns a corpus-relative `artifact` field | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:46,88`; `tests/python/test_briesearch_research_layout.py:61-67` |
| edge-briesearch-mold.md, edge-mold-briesearch.md | `briesearch` | high | applied on this side: the slug rule is now enforced at four to six words. See Disagreements | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:52-65` |
| edge-briesearch-mold.md | `briesearch` | high | deferred: owned by mold. Strict Mold validation must check tier-2 provenance | none | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-briesearch-mold.md | `briesearch` | high | applied in part: `evals.md` adds a route-authorization trace. The Mold-side consumer test is deferred: owned by mold | 3140259 | `skills/briesearch/references/evals.md:44-46` |
| edge-briesearch-mold.md | `briesearch` | medium | deferred: owned by mold. The artifact omission predicates must agree | none | `skills/mold/references/mini-spec-mode.md:62` |
| edge-briesearch-cook.md | `briesearch` | high | applied on this side: `evals.md` adds trace check 10, which requires a run to stop after it recommends a route. The Cook entry test is deferred: owned by cook | 3140259 | `skills/briesearch/references/evals.md:44` |
| edge-cheese-briesearch.md | `briesearch` | high | deferred: owned by cheese. Cheese must allocate the parent slug before the tier-2 call | none | `skills/cheese/references/escalation.md:10-22` |
| edge-cheese-briesearch.md | `briesearch` | high | deferred: owned by cheese. Tier-3 question ownership is a Cheese rule | none | `skills/cheese/references/escalation.md:19-26` |
| edge-cheese-briesearch.md | `briesearch` | medium | deferred: owned by cheese. The internal request and result packet is a Cheese contract | none | `skills/cheese/SKILL.md:44-48` |
| edge-cheese-briesearch.md, edge-mold-briesearch.md | `briesearch` | medium/high | applied in part: `evals.md` adds trace check 11 and a failure mode for a sidechain run that records `top-level`. The producing side is deferred: owned by cheese and mold | 3140259 | `skills/briesearch/references/evals.md:45-46,54` |
| edge-mold-briesearch.md | `briesearch` | high | deferred: owned by mold. Mold must map `don't know` to an open hypothesis | none | `skills/mold/references/validate-cycle.md:18-24` |
| edge-mold-briesearch.md | `briesearch` | medium | deferred: owned by mold and cheese. One sidechain result shape needs both callers | none | `skills/briesearch/SKILL.md:13` |
| hub-schemas.md | `briesearch` | n/a | rejected: the note lists no `briesearch` row | none | `.cheese/notes/r014-megamerge/hub-schemas.md` |
| hub-build.md | `briesearch` | n/a | rejected: the note lists no `briesearch` row | none | `.cheese/notes/r014-megamerge/hub-build.md` |
| review-build.md | `build` | blocker | applied | 7b4fb2c3 | tests/python/test_bundle_closure.py:187 |
| review-build.md | `build` | high | applied | 9f30c65c | scripts/check_bundles.py:471 |
| hub-build.md | `build` | high | applied | 9f30c65c | tests/python/test_check_bundles.py:316 |
| review-build.md | `build` | high | applied | 96a418a6 | scripts/check_bundles.py:757 |
| review-build.md | `build` | high | applied | 60eec2cb | justfile:4 |
| edge-build-schemas.md | `build` | high | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:62 |
| edge-build-schemas.md | `build` | high | applied | f86ac63d | scripts/render_generated_regions.py:151 |
| review-build.md | `build` | medium | rejected | none | src/easy_cheese/skills/wheypoint/storage.py:108 |
| edge-build-schemas.md | `build` | medium | applied | 5bde1de7 | scripts/render_generated_regions.py:45 |
| edge-schemas-build.md | `build` | medium | applied | 5bde1de7 | tests/python/test_phase_projection_types.py:24 |
| edge-schemas-build.md | `build` | medium | applied | f86ac63d | tests/python/test_writer_views_reference.py:56 |
| edge-build-schemas.md | `build` | medium | applied | 36106fc1 | justfile:42 |
| edge-build-docs.md | `build` | medium | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:86 |
| edge-docs-build.md | `build` | medium | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:86 |
| review-build.md | `build` | low | applied | b4ded1ae | tests/python/test_bundle_closure.py:53 |
| review-build.md | `build` | low | applied | 679cf5f6 | scripts/check_bundles.py:855 |
| edge-build-shared.md | `build` | low | applied | 5bde1de7 | scripts/render_generated_regions.py:290 |
| edge-build-schemas.md | `build` | low | deferred: owned by cook | none | skills/cook/SKILL.md:123 |
| edge-build-docs.md | `build` | low | deferred: owned by mold | none | skills/mold/references/adr.md:36 |
| edge-docs-build.md | `build` | low | deferred: owned by mold | none | skills/mold/references/grounding.md:11 |
| edge-build-schemas.md | `build` | low | deferred: owned by mold | none | skills/mold/references/curdle.md:158 |
| review-build.md | `build` | simplification | deferred: owned by press and easy-cheese-setup | none | src/easy_cheese/skills/press/commands.py:10 |
| review-build.md | `build` | simplification | applied | 2645cb06 | tests/python/test_pyz_bundle.py:34 |
| review-build.md | `build` | simplification | applied | 96a418a6 | scripts/check_bundles.py:757 |
| review-build.md | `build` | simplification | applied | 6ff8921b | scripts/check_bundles.py:562 |
| review-build.md | `build` | simplification | applied | 5bde1de7 | scripts/render_generated_regions.py:290 |
| review-build.md, edge-build-schemas.md | `build` | high | deferred: no listed area owns `.github/workflows/build-pyz.yml` | none | .github/workflows/build-pyz.yml:7 |
| review-build.md | `build` | high | deferred: no listed area owns `.github/workflows/validate.yml` | none | .github/workflows/validate.yml:79 |
| review-cheese.md | `cheese` | blocker | applied | `c805f3ba` | `skills/cheese/SKILL.md:43-45,85-88` |
| review-cheese.md | `cheese` | blocker | applied | `a2688b04` | `skills/cheese/references/decomposer.md:3-12,35-37` |
| review-cheese.md | `cheese` | high | applied | `d3fb7e45` | `skills/cheese/references/classification.md:92-103`; `routing-receipt.md:45-47` |
| review-cheese.md | `cheese` | high (telemetry) | applied | `a3e94878` | `skills/cheese/SKILL.md:52-54`; `coherence-check.md:9-11`; `routing-receipt.md:49-55` |
| review-cheese.md | `cheese` | high | applied | `9c3e994f` | `skills/cheese/references/classification.md:28,125-139`; `SKILL.md` affinage target |
| review-cheese.md | `cheese` | high | partly applied | `1caa85e1`, `60b8d817` | `skills/cheese/SKILL.md` flag rules. Mold and Pasteurize prose is `deferred: owned by mold` and `deferred: owned by pasteurize` |
| review-cheese.md | `cheese` | high (security) | applied | `1de55ade` | `skills/cheese/SKILL.md:37-44` |
| review-cheese.md | `cheese` | high | applied | `c5bdd8ec` | `skills/cheese/references/agent-resolution.md:85-94`; `routing-policy.md:38` |
| review-cheese.md | `cheese` | high | applied | `a812a831` | `skills/cheese/references/handback-contract.md` Boundaries table |
| review-cheese.md | `cheese` | medium | applied | `f326eea4` | `skills/cheese/references/optional-plugins.md:14-17,22-25,45-55` |
| review-cheese.md | `cheese` | medium (assertions) | applied | `57cf27a4` | `tests/python/test_cheese_routing_receipt.py:60-82`; `routing-receipt.md:22-25` |
| review-cheese.md | `cheese` | medium | applied | `94fbdb2c` | `skills/cheese/references/handback-contract.md` carrier table |
| review-cheese.md | `cheese` | medium (deslop) | applied | `2100ca83`, `f7e3daf4` | every `skills/cheese/**/*.md` prose file |
| edge-cheese-affinage.md | `cheese` | high | applied | `bf638a56` | `skills/cheese/references/continue-resume.md` affinage branch |
| edge-cheese-affinage.md | `cheese` | high | deferred: owned by schemas | — | The Affinage phase transition is not registered. Row 9 narrows the Cheese claim instead |
| edge-cheese-affinage.md | `cheese` | medium | rejected | — | A typed `pr_ref:` preamble key would not parse. The canonical parser accepts three optional keys. Row 12 confines the overload to legacy notes |
| edge-cheese-affinage.md | `cheese` | medium | applied | `bf638a56` | `continue-resume.md` requires `--stake` with `--auto` |
| edge-cheese-affinage.md | `cheese` | medium (assertions) | applied | `bf638a56` | `tests/python/test_cheese_contracts.py::TestAffinageResumeNormalizesItsReference` |
| edge-cheese-age.md | `cheese` | high | deferred: owned by age | — | The Age writer clears `artifact` and omits `baseline` |
| edge-cheese-age.md | `cheese` | high | applied | `c9aa88e7` | `skills/cheese/references/coherence-check.md` Age source rule |
| edge-cheese-age.md | `cheese` | medium | deferred: owned by age | — | Age declares no `handoff_context.wiki_hits` input |
| edge-cheese-age.md | `cheese` | medium | deferred: owned by age | — | `--hard` is missing from both Age command forms |
| edge-cheese-briesearch.md | `cheese` | high | applied | `d548839e` | `skills/cheese/references/escalation.md` tier 2 |
| edge-cheese-briesearch.md | `cheese` | high | partly applied | `d548839e` | Cheese states the `needs_input` rule. The Briesearch half is `deferred: owned by briesearch` |
| edge-cheese-briesearch.md | `cheese` | medium | applied | `d548839e` | `escalation.md` sets `invocation: sidechain` |
| edge-cheese-cook.md | `cheese` | blocker | partly applied | `1caa85e1` | Cheese never adds `--open-pr`. Cook auto mode adding it is `deferred: owned by cook` |
| edge-cheese-cook.md | `cheese` | blocker | applied | `1caa85e1` | `skills/cheese/SKILL.md` ultracook redirect row |
| edge-cheese-cook.md | `cheese` | high | applied | `d3fb7e45` | Cook owns the one fast-path rule |
| edge-cheese-cook.md | `cheese` | medium | deferred: owned by cook | — | Cook declares no `handoff_context.wiki_hits` input |
| edge-cheese-cure.md | `cheese` | blocker | deferred: owned by cure | — | The typed `CurdPlan` path needs a normal report repair path in Cure |
| edge-cheese-cure.md | `cheese` | blocker | deferred: owned by cure | — | The Cure writer command omits `--body-file` |
| edge-cheese-cure.md | `cheese` | high | deferred: owned by cure | — | The selection packet belongs to the Cure dispatch contract |
| edge-cheese-mold.md | `cheese` | high | applied | `d78baf3a` | `skills/cheese/references/escalation.md:11-16` |
| edge-cheese-mold.md | `cheese` | high | applied | `94fbdb2c` | `handback-contract.md` carrier table; `continue-resume.md` reads `spec_ref` |
| edge-cheese-pasteurize.md | `cheese` | high | deferred: owned by pasteurize | — | Pasteurize drops `--open-pr` and `--hard` |
| edge-cheese-pasteurize.md | `cheese` | high | deferred: owned by schemas | — | The registry has no Pasteurize phase |
| edge-cheese-pasteurize.md | `cheese` | medium | deferred: owned by pasteurize | — | Pasteurize has no Inputs section |
| edge-cheese-plate.md | `cheese` | high | partly applied | `60b8d817` | Cheese names Cure as the consumer. Mold and Pasteurize are deferred, as row 6 states |
| edge-cheese-plate.md | `cheese` | medium | applied | `60b8d817` | `skills/cheese/SKILL.md` `--open-pr` input |
| edge-cheese-plate.md | `cheese` | medium | deferred: owned by plate | — | Plate does not define the hard-gate failure mode |
| edge-cheese-press.md | `cheese` | blocker | deferred: owned by schemas | — | The canonical handoff model needs one typed local action |
| edge-press-cheese.md | `cheese` | high | deferred: owned by press | — | Press defines `artifact:` as an evidence path |
| edge-cheese-wheypoint.md | `cheese` | blocker | deferred: owned by wheypoint | — | The record and projection drop mode, task, order, baseline, and flag fields |
| edge-cheese-wheypoint.md | `cheese` | blocker | deferred: owned by wheypoint | — | See Disagreements. `tests/python/test_wheypoint_skill_contract.py:173` forbids `next: cut` |
| edge-cheese-wheypoint.md | `cheese` | high | deferred: owned by wheypoint | — | The projection emits a bare `status: gated` |
| edge-cheese-wheypoint.md | `cheese` | high | applied | `d39fe989` | `continue-resume.md` disposition branch |
| edge-cheese-wheypoint.md | `cheese` | high | deferred: owned by wheypoint | — | The resolver gates every legacy pull request artifact |
| edge-cheese-wheypoint.md | `cheese` | medium | applied | `bf638a56` | `continue-resume.md` lint description |
| edge-cook-cheese.md | `cheese` | blocker | deferred: owned by wheypoint | — | The resolver cannot resolve an exact Cook report path |
| edge-cook-cheese.md | `cheese` | high | deferred: owned by cook | — | Cook documents an invalid reader command |
| edge-cook-cheese.md | `cheese` | high | applied | `94fbdb2c` | `handback-contract.md` states the one `artifact:` meaning |
| edge-cook-cheese.md | `cheese` | high | deferred: owned by cook | — | The nested `baseline:` block cannot cross the seam |
| edge-cook-cheese.md | `cheese` | medium | applied | `5349fffb` | `skills/cheese/references/handoff-gate.md` gate example |
| edge-cure-cheese.md | `cheese` | blocker | deferred: owned by wheypoint | — | The resolver rejects an exact Cure report path |
| edge-cure-cheese.md | `cheese` | blocker | deferred: owned by cure | — | The Cure writer removes the report body |
| edge-cure-cheese.md | `cheese` | blocker | applied | `d39fe989` | `continue-resume.md` routes each disposition |
| edge-cure-cheese.md | `cheese` | high | deferred: owned by cure | — | The writer example cannot emit `next: done` |
| edge-cure-cheese.md | `cheese` | high | deferred: owned by cure | — | Cure loses baseline state |
| edge-cure-cheese.md | `cheese` | high | deferred: owned by cure | — | Cure weakens the fresh-context failure mode |
| edge-plate-cheese.md | `cheese` | high | applied | `60b8d817` | `skills/cheese/SKILL.md` names both Plate triggers |
| edge-plate-cheese.md | `cheese` | high | deferred: owned by plate | — | Plate does not handle a normalized `other:` answer |
| hub-schemas.md | `cheese` | high | applied | `a812a831` | `handback-contract.md` narrows the writer claim to the registry |
| hub-shared.md | `cheese` | untested edge | applied | `d3fb7e45` and this note | `escalation.md:50` still calls the current `resolve_slug` signature. The tests in `tests/python/test_cheese_contracts.py` now cover the router decision branches |
| hub-build.md | `cheese` | — | not applicable | — | No `cheese` row exists in `hub-build.md` |
| review-cook.md | `cook` | blocker | applied by `shared` | (none) | `src/easy_cheese/shared/publication.py:494-497` rejects a non-`file` scheme. A probe returned `artifact 'payload-op-unsafe' is not a file:// uri`. |
| review-cook.md, hub-schemas.md | `cook` | blocker | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1252-1277` runs declaration order. `skills/cook/references/fan-pathway.md:75-77` already requires topological waves. |
| review-cook.md, edge-cheese-cook.md, edge-cook-cure.md, edge-cook-plate.md, edge-cook-press.md | `cook` | blocker | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:27-30`; `skills/cook/SKILL.md:42`; `tests/python/test_cook_prose_contract.py:26` |
| review-cook.md | `cook` | blocker | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:8-13,90-95,101`; `tests/python/test_cook_prose_contract.py:47` |
| review-cook.md, edge-cook-age.md, edge-cook-cure.md | `cook` | blocker | rejected | (none) | Age has no pass-count input (`skills/age/SKILL.md:17-22`). `skills/age/references/handoff-detail.md:90-107` says Age does not count passes. Age starts in a fresh context for each pass. Cook keeps orchestrator ownership at `skills/cook/references/auto-mode.md:67-89`. See Disagreements. |
| review-cook.md | `cook` | high | applied | c90d9311 | `tests/python/test_cook_contract_accept.py:115-159` asserts the complete wrapper. |
| review-cook.md, edge-mold-cook.md | `cook` | medium/high | applied | c90d9311 | `tests/python/test_cook_contract_accept.py:162-179,192-199,215-224` |
| review-cook.md, all edge notes | `cook` | medium | applied | cb2b03b2, d5d47da7 | `skills/cook/SKILL.md:70-72`; `skills/cook/references/auto-mode.md:94-98`; `fan-pathway.md:186,285`; `package-report.md:70`; `tdd-loop.md:117,140-143,152`; `cook-discipline.md:38` |
| review-cook.md | `cook` | low | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:36-38,82,127` |
| review-cook.md | `cook` | low | applied | cb2b03b2 | `skills/cook/references/tdd-loop.md:64-66` links `age/references/fan-out.md#router-call`. `auto-mode.md:142-144` names each phase file. `tests/python/test_cook_prose_contract.py:178` checks every link. |
| review-cook.md | `cook` | simplification | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:47-50,89-92,113-116` |
| review-cook.md | `cook` | simplification | deferred: owned by build | (none) | `src/easy_cheese/skills/cook/commands.py:63-95` feeds the generated rows in `skills/cook/references/commands.md:15,26-29`. Removal needs the generated-region rebuild and the bundle-closure tests that `build` owns. |
| hub-schemas.md | `cook` | medium | applied | 5ddb39a4 | `src/easy_cheese/skills/cook/contract_handlers.py:56-70,98`; `tests/python/test_cook_contract_handlers.py:98,113,126` |
| hub-shared.md | `cook` | high | applied | cb2b03b2 | `skills/cook/SKILL.md:179-183`; `tests/python/test_cook_prose_contract.py:115` |
| hub-shared.md | `cook` | high | applied by `shared` | (none) | `src/easy_cheese/shared/publication.py:456-469` reads at most `MAX_CONTRACT_BYTES`. |
| edge-briesearch-cook.md | `cook` | high | deferred: owned by briesearch | (none) | The producer side owns the stop rule at `skills/briesearch/SKILL.md:23-30`. Cook's entry list at `skills/cook/SKILL.md:32-36` accepts no Briesearch report. |
| edge-cheese-cook.md | `cook` | blocker | deferred: owned by cheese | (none) | `skills/cheese/SKILL.md:189` forwards three flags. Cook accepts `--hard` at `skills/cook/SKILL.md:41`. |
| edge-cheese-cook.md | `cook` | high | deferred: owned by cheese | (none) | Cook owns the rule at `skills/cook/SKILL.md:49-54`. Cheese must reference it, not copy it. |
| edge-cheese-cook.md | `cook` | medium | applied | a2b7ccd4 | `skills/cook/SKILL.md:47-54`; `tests/python/test_cook_prose_contract.py:160` |
| edge-cheese-cook.md | `cook` | medium | deferred: owned by cheese | (none) | Cook defines the flag at `skills/cook/SKILL.md:40`. |
| edge-cook-age.md | `cook` | blocker | deferred: owned by age | (none) | `skills/age/phase-contract.yaml:5-10` declares `CurdResult` input, but `src/easy_cheese/skills/age/commands.py:11-106` has no adapter. |
| edge-cook-age.md | `cook` | high | deferred: owned by age | (none) | `skills/age/SKILL.md:112-115` passes an empty artifact and omits `--baseline`. |
| edge-cook-age.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:47-51`; `tests/python/test_cook_prose_contract.py:36` |
| edge-cook-age.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/auto-mode.md:30,42,51` |
| edge-cook-age.md | `cook` | high | deferred: owned by age | (none) | The adapter in finding 21 must land before a seam test can run. |
| edge-cook-age.md | `cook` | medium | applied | cb2b03b2 | `skills/cook/references/tdd-loop.md:64-66` |
| edge-cook-cheese.md | `cook` | blocker | deferred: owned by wheypoint | (none) | `src/easy_cheese/skills/wheypoint/legacy.py:350-366` searches only `.cheese/notes/<slug>.md`. |
| edge-cook-cheese.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/fan-pathway.md:48-53`; `tests/python/test_cook_prose_contract.py:95` |
| edge-cook-cheese.md, edge-press-cook.md, edge-wheypoint-cook.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:44-74` defines a one-line artifact reference. `skills/cook/SKILL.md:153` and `:203-206` agree. `tests/python/test_cook_prose_contract.py:58` |
| edge-cook-cheese.md | `cook` | high | applied | cb2b03b2 | `skills/cook/SKILL.md:150,164-169`; `tests/python/test_cook_prose_contract.py:122` |
| edge-cook-cheese.md | `cook` | medium | deferred: owned by cheese | (none) | `skills/cheese/references/handoff-gate.md:27-54` holds the example. |
| edge-cook-cheese.md | `cook` | medium | deferred: owned by cheese | (none) | The resolver in finding 27 must land first. |
| edge-cook-cure.md | `cook` | blocker | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1043-1119` diagnoses only failed writer output. |
| edge-cook-cure.md | `cook` | blocker | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:331-376` has no diagnosis field. |
| edge-cook-cure.md | `cook` | blocker | deferred: owned by schemas | (none) | `src/easy_cheese_schemas/workflow.py:1192-1198` requires every plan curd. |
| edge-cook-cure.md | `cook` | blocker | deferred: owned by schemas | (none) | `CureDiagnosisBinding` has no registered schema. |
| edge-cook-cure.md | `cook` | high | deferred: owned by schemas | (none) | Findings 33 to 36 must land first. |
| edge-cook-mold.md | `cook` | blocker | deferred: owned by mold | (none) | `src/easy_cheese/skills/mold/commands.py:10-94` has no intake command. Cook now publishes and names the validated request at `skills/cook/references/fan-pathway.md:113-129`. |
| edge-cook-mold.md | `cook` | high | applied | a2b7ccd4 | `skills/cook/references/fan-pathway.md:113-116`; `tests/python/test_cook_prose_contract.py:140` |
| edge-cook-mold.md | `cook` | high | applied | a2b7ccd4 | `skills/cook/references/fan-pathway.md:119-125` |
| edge-cook-mold.md | `cook` | high | applied | a2b7ccd4 | `skills/cook/SKILL.md:20,22` admits `next: mold`. `fan-pathway.md:129` fixes `status: ok`. `tests/python/test_cook_prose_contract.py:153` |
| edge-cook-mold.md | `cook` | medium | deferred: owned by mold | (none) | Finding 38 must land first. |
| edge-cook-pasteurize.md | `cook` | high | applied | a2b7ccd4 | `skills/cook/references/quality-gates.md:98-100`; `tests/python/test_cook_prose_contract.py:169` |
| edge-cook-pasteurize.md | `cook` | high | deferred: owned by pasteurize | (none) | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-102` omits the Pasteurize transition. |
| edge-cook-pasteurize.md | `cook` | medium | deferred: owned by pasteurize | (none) | Finding 44 must land first. |
| edge-cook-plate.md | `cook` | high | deferred: owned by shared | (none) | `src/easy_cheese/shared/handoff.py:38-87` defines no `plate_layout` field. |
| edge-cook-plate.md | `cook` | high | deferred: owned by plate | (none) | `src/easy_cheese/skills/plate/publication.py:127-133` permits only `plate_layout`. |
| edge-cook-plate.md, edge-plate-cook.md | `cook` | high | applied | cb2b03b2 | `skills/cook/SKILL.md:241-245`; `skills/cook/references/fan-pathway.md:342-346`; `tests/python/test_cook_prose_contract.py:130` |
| edge-plate-cook.md | `cook` | blocker | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:68,101,111-112`; `tests/python/test_cook_prose_contract.py:69` |
| edge-plate-cook.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:124-130`; `tests/python/test_cook_prose_contract.py:78` |
| edge-plate-cook.md | `cook` | high | applied | cb2b03b2 | `skills/cook/references/quality-gates.md:110-119`; `tests/python/test_cook_prose_contract.py:87` |
| edge-cook-press.md, edge-press-cook.md | `cook` | blocker | deferred: owned by shared | (none) | `src/easy_cheese/shared/handoff.py:83-87` has no local continuation field. |
| edge-cook-press.md | `cook` | high | deferred: owned by press | (none) | Press never resolves the declared result. |
| edge-cook-press.md | `cook` | medium | deferred: owned by press | (none) | `skills/press/SKILL.md:94-101` omits the field. |
| edge-cook-press.md | `cook` | medium | deferred: owned by press | (none) | Cook now owns the fan pathway. |
| edge-wheypoint-cook.md | `cook` | blocker | deferred: owned by wheypoint | (none) | Finding 29 makes the Cook side one line, which Wheypoint can carry. |
| edge-wheypoint-cook.md | `cook` | high | applied | (none) | Cook already keeps the explicit stop option at `skills/cook/SKILL.md:228`. The Wheypoint sentence is deferred to `wheypoint`. |
| edge-wheypoint-cook.md | `cook` | high | applied | (none) | `skills/cook/SKILL.md:34-35,43` already separates a bare slug, a pointer, and `--resume <slug>`. The router rule is deferred to `wheypoint`. |
| hub-build.md | `cook` | — | not applicable | (none) | The note lists only `wheypoint -> build`. |
| review-cure.md | `cure` | blocker | applied | d664824c | `skills/cure/SKILL.md:157-181` |
| review-cure.md | `cure` | blocker | applied | 646630b4 | `skills/cure/SKILL.md:49-57,68-72` |
| review-cure.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| review-cure.md | `cure` | high | applied | 70a099b8 | `skills/cure/SKILL.md:106-107,230,246`; `references/post-pr-writeback.md:6-9` |
| review-cure.md | `cure` | high | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| review-cure.md | `cure` | low | applied | ce2e62d8 | `references/selection.md:65` |
| review-cure.md | `cure` | low | applied | ce2e62d8, 70a099b8 | `skills/cure/SKILL.md:31,246` |
| review-cure.md | `cure` | STE100 | applied | 8c91ae87, 58ddb14e | `skills/cure/SKILL.md:45,128`; `references/cure-discipline.md:5,7,53` |
| review-cure.md | `cure` | simplification | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| review-cure.md | `cure` | simplification | applied | d664824c | `skills/cure/SKILL.md:157-181` |
| review-cure.md | `cure` | simplification | applied | 70a099b8 | `references/post-pr-writeback.md` |
| review-cure.md | `cure` | simplification | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| review-cure.md | `cure` | simplification | rejected: no change needed | none | `src/easy_cheese/skills/cure/commands.py:66-92` |
| edge-affinage-cure.md | `cure` | blocker | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-affinage-cure.md | `cure` | high | deferred: owned by shared | none | `src/easy_cheese/shared/findings.py:40-53` |
| edge-affinage-cure.md | `cure` | high | applied | 646630b4 | `skills/cure/SKILL.md:49-51` |
| edge-affinage-cure.md | `cure` | medium | applied | 69eb5e8a | `skills/cure/SKILL.md:196-199` |
| edge-affinage-cure.md | `cure` | medium | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py` |
| edge-age-cure.md | `cure` | blocker | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-age-cure.md | `cure` | high | deferred: owned by age | none | `skills/age/SKILL.md:157-164` |
| edge-age-cure.md | `cure` | high | deferred: owned by age | none | `skills/age/SKILL.md:183-188` |
| edge-age-cure.md | `cure` | high | deferred: owned by age | none | `skills/age/SKILL.md:92-95` |
| edge-age-cure.md | `cure` | high | deferred: owned by age | none | `skills/age/SKILL.md:112-116` |
| edge-age-cure.md | `cure` | medium | applied | 0dea5b95 | `skills/cure/SKILL.md:99,272`; `references/auto-mode.md:16-18` |
| edge-cheese-cure.md | `cure` | blocker | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-cheese-cure.md | `cure` | blocker | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cheese-cure.md | `cure` | high | deferred: owned by cheese | none | `skills/cheese/SKILL.md:195-201` |
| edge-cheese-cure.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| edge-cheese-cure.md | `cure` | medium | deferred: owned by cheese | none | `skills/cheese/references/classification.md:133-143` |
| edge-cook-cure.md | `cure` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1043-1119` |
| edge-cook-cure.md | `cure` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:331-376` |
| edge-cook-cure.md | `cure` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1192-1198` |
| edge-cook-cure.md | `cure` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/_compiled_phase_registry.py:105` |
| edge-cook-cure.md | `cure` | high | applied on this side | none | `skills/cure/SKILL.md:200-201` already assigns the cap to Age |
| edge-cook-cure.md | `cure` | high | deferred: owned by cook | none | `skills/cook/references/auto-mode.md:23-28` |
| edge-cook-cure.md | `cure` | high | deferred: owned by schemas | none | `tests/schemas/python/test_workflow_thread.py:766-918` |
| edge-cure-age.md | `cure` | blocker | deferred: owned by schemas | none | `skills/cure/phase-contract.yaml:5-10` |
| edge-cure-age.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cure-age.md | `cure` | high | applied | 0dea5b95 | `skills/cure/SKILL.md:99-102,272` |
| edge-cure-age.md | `cure` | high | deferred: owned by age | none | `skills/age/SKILL.md:214-225` |
| edge-cure-age.md | `cure` | high | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:147-164` |
| edge-cure-age.md | `cure` | medium | applied | d664824c | `skills/cure/SKILL.md:180-181` |
| edge-cure-cheese.md | `cure` | blocker | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/resolve.py:118-144` |
| edge-cure-cheese.md | `cure` | blocker | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cure-cheese.md | `cure` | blocker | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-120` |
| edge-cure-cheese.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| edge-cure-cheese.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:163-179` |
| edge-cure-cheese.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:153-155` |
| edge-cure-cheese.md | `cure` | high | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| edge-cure-cheese.md | `cure` | medium | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:79-117` |
| edge-cure-hard-cheese.md | `cure` | high | applied | 0dea5b95 | `skills/cure/SKILL.md:259-263` |
| edge-cure-hard-cheese.md | `cure` | medium | deferred: owned by hard-cheese | none | `tests/python/test_hard_cheese.py:156-166` |
| edge-cure-mold.md | `cure` | high | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-cure-mold.md | `cure` | high | applied | 58ddb14e | `references/domain-model-correction.md:16-27` |
| edge-cure-mold.md | `cure` | high | deferred: owned by shared | none | `src/easy_cheese/shared/paths.py:555-602` |
| edge-cure-mold.md | `cure` | medium | applied | 58ddb14e | `references/domain-model-correction.md:41-43` |
| edge-cure-plate.md | `cure` | high | applied | 70a099b8 | `references/post-pr-writeback.md:6-9` |
| edge-cure-plate.md | `cure` | medium | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:153-164` |
| hub-shared.md | `cure` | blocker | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| hub-shared.md | `cure` | high | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| hub-schemas.md | `cure` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| hub-schemas.md | `cure` | medium | deferred: owned by schemas | none | `tests/schemas/python/test_workflow_thread.py:766-919` |
| hub-build.md | `cure` | — | rejected: not applicable | none | `.cheese/notes/r014-megamerge/hub-build.md` |
| review-docs.md | `docs` | high | applied | `427dfac5` | `.cheese/notes/r014-megamerge/re-review.md:5,44,63,67` |
| review-docs.md | `docs` | high | applied | `56dba2c2` | `.cheese/issues/477-suggestions.md:3-14`; `.cheese/plans/release-0-14-decisions.md:199-207` |
| review-docs.md | `docs` | high | applied | `db185240` | `CONTRIBUTING.md:50-61`; `tests/python/test_contributing_contract.py:13-21` |
| review-docs.md | `docs` | high | applied | `db185240` | `CONTRIBUTING.md:14-32,66-75`; `tests/python/test_contributing_contract.py:24-36` |
| review-docs.md | `docs` | medium | applied | `5b33d360` | `.cheese/notes/r014-megamerge/dependency-map.md:186-189`; `.cheese/notes/r014-megamerge/docs.md:34-37` |
| review-docs.md | `docs` | medium | applied | `f526e345` | `.cheese/notes/r014-megamerge/cheese.md:5-14`; `.cheese/plans/release-0-14-decisions.md:14-36` |
| review-docs.md | `docs` | low | applied | `76ff9958` | `.cheese/notes/r014-megamerge/hard-cheese.md:44-47` |
| review-docs.md | `docs` | low | applied | `057b8e00` | `tests/js/sidebar-toc.test.mjs:63` |
| review-docs.md | `docs` | simplification | applied | `057b8e00` | `website/components/sidebar-toc.mjs:22,34`; `website/components/Sidebar.astro:11` |
| review-docs.md | `docs` | simplification | applied | `db185240` | `CONTRIBUTING.md:66-75` |
| review-docs.md | `docs` | simplification | applied | `56dba2c2` | `.cheese/issues/477-suggestions.md:37,178` |
| review-docs.md | `docs` | simplification | applied | `427dfac5` | `.cheese/notes/r014-megamerge/re-review.md:67,92,101` |
| review-docs.md | `docs` | simplification | no change needed | none | `website/components/sidebar-toc.mjs:1-55` |
| edge-build-docs.md | `docs` | medium | rejected: duplicate | none | `.cheese/notes/r014-megamerge/cure2-build.md:23`; `tests/python/test_justfile_ci_contract.py:86` |
| edge-docs-build.md | `docs` | medium | rejected: duplicate | none | `.cheese/notes/r014-megamerge/cure2-build.md:24`; `tests/python/test_justfile_ci_contract.py:86` |
| edge-build-docs.md | `docs` | low | deferred: owned by mold | none | `skills/mold/references/adr.md:36` |
| edge-docs-build.md | `docs` | low | deferred: owned by mold | none | `skills/mold/references/grounding.md:11` |
| review-easy-cheese-setup.md, hub-shared.md | `easy-cheese-setup` | blocker | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:43-44`; `tests/python/test_easy_cheese_setup_contract.py:18-31` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | high | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | medium | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:172-195` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | medium | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:64-66` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | medium | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:314-323` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | medium | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:40-41`; `tests/python/test_easy_cheese_setup_contract.py:41-44` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | low | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:22,26,55`; `tests/python/test_easy_cheese_setup_contract.py:34-38` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | simplification | applied | `3b4969ce` | `src/easy_cheese/skills/easy_cheese_setup/commands.py:10-35` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | simplification | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:338-357` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | simplification | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:172-295` |
| hub-shared.md | `easy-cheese-setup` | edge | partial | `ad7b468a`, `3b4969ce` | The two prose contracts now match the code. The three runtime contracts stay with `shared`. |
| review-hard-cheese | `hard-cheese` | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| review-hard-cheese | `hard-cheese` | blocker | rejected: the fix contradicts the rubric in the same file and an out-of-area test. Applied the underlying contradiction fix instead. | `docs(hard-cheese): remove the causal-understanding claim` | `skills/hard-cheese/references/judge-prompt.md:29-35`; `tests/python/test_hard_cheese.py:83-120` |
| review-hard-cheese | `hard-cheese` | blocker | applied | `fix(hard-cheese): pin the judge reviewer to powerful power` | `skills/hard-cheese/SKILL.md:130,218` |
| review-hard-cheese | `hard-cheese` | blocker | deferred: root cause in `append_attempt.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/append_attempt.py:110-117` |
| review-hard-cheese | `hard-cheese` | high | applied | `fix(hard-cheese): isolate untrusted judge input from instructions` | `skills/hard-cheese/references/judge-prompt.md:33-40` |
| review-hard-cheese | `hard-cheese` | high | applied | `docs(hard-cheese): record the telemetry content-retention divergence` | `skills/hard-cheese/SKILL.md:23,155-167` |
| review-hard-cheese | `hard-cheese` | high | applied | `fix(hard-cheese): add ERROR to the artifact status list` | `skills/hard-cheese/SKILL.md:111` |
| review-hard-cheese | `hard-cheese` | low | applied | `docs(hard-cheese): apply ASD-STE100 to the skill and composition prose` | `skills/hard-cheese/SKILL.md:27-32,47,135,173,213`; `skills/hard-cheese/references/composition.md:13,17,19,22,49,51` |
| edge-affinage-hard-cheese | `hard-cheese` | high | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:44-58` |
| edge-cure-hard-cheese | `hard-cheese` | high | deferred: owned by `cure`. The hard-cheese side now publishes the status matrix. | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/references/composition.md:35-46`; `skills/cure/SKILL.md:232` |
| edge-cure-hard-cheese | `hard-cheese` | medium | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:81-91` |
| edge-mold-hard-cheese | `hard-cheese` | blocker | deferred: owned by `mold` | none | `skills/mold/SKILL.md:47,131`; `skills/mold/references/mini-spec-mode.md:5-8` |
| edge-mold-hard-cheese | `hard-cheese` | high | deferred: owned by `mold` | none | `tests/python/test_hard_cheese.py:150-153` |
| edge-plate-hard-cheese | `hard-cheese` | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| edge-plate-hard-cheese | `hard-cheese` | high | applied for the prose contract; the validating command is deferred with finding 14 | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/SKILL.md:62-71` |
| edge-plate-hard-cheese | `hard-cheese` | high | applied | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/references/composition.md:35-46` |
| edge-plate-hard-cheese | `hard-cheese` | high | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:65-91` |
| hub-shared (`hard-cheese -> shared`) | `hard-cheese` | ok | no change required | none | `src/easy_cheese/skills/hard_cheese/commands.py:7-39` |
| hub-schemas | `hard-cheese` | n/a | no `hard-cheese` row | none | `.cheese/notes/r014-megamerge/hub-schemas.md` |
| hub-build | `hard-cheese` | n/a | no `hard-cheese` row | none | `.cheese/notes/r014-megamerge/hub-build.md` |
| review-melt.md | `melt` | blocker | applied | `9d23b4db` | `skills/melt/references/cascade-stages.md:9-13`; test `tests/python/test_melt_prose_contract.py:15` |
| review-melt.md | `melt` | blocker | applied | `89c6adb9` | `skills/melt/SKILL.md:212-276`; tests `tests/python/test_melt_prose_contract.py:50,68,77` |
| review-melt.md | `melt` | high | applied | `7d7856a1` | `skills/melt/SKILL.md:26-30,142-174`; test `tests/python/test_melt_prose_contract.py:25` |
| review-melt.md | `melt` | low | applied | `c6a324d5` | `skills/melt/SKILL.md:209-211` (zdiff3 bullet) |
| review-melt.md | `melt` | simplification | applied | `9d23b4db` | `skills/melt/references/cascade-stages.md:9-13` |
| review-melt.md | `melt` | simplification | applied | `89c6adb9` | `skills/melt/SKILL.md:217-261` |
| review-melt.md | `melt` | simplification | applied | `7d7856a1` | `skills/melt/SKILL.md:144-154` |
| review-melt.md | `melt` | simplification | no change | none | `src/easy_cheese/skills/melt/commands.py:10-59` already holds five decorated callables |
| review-melt.md | `melt` | follow-up | deferred: owned by cheese | none | `skills/cheese/references/handoff-gate.md:207-218` |
| hub-shared.md | `melt` | ok | no change | none | `src/easy_cheese/skills/melt/commands.py:7-63` |
| review-mold.md | `mold` | blocker | applied | b28291c8 | `skills/mold/references/grounding.md:22-27,35-37` |
| review-mold.md | `mold` | blocker | applied | b28291c8 | `skills/mold/references/grounding.md:24-26,38` |
| review-mold.md | `mold` | blocker | applied | b28291c8 | `skills/mold/references/grounding.md:67` |
| review-mold.md | `mold` | blocker | applied | 4bb79e1f | `skills/mold/references/curdle.md:20-22` |
| review-mold.md | `mold` | blocker | applied | 204c5995 | `src/easy_cheese/skills/mold/contract_handlers.py:131-132`; `tests/python/test_mold_contract_handlers.py:41-48` |
| review-mold.md | `mold` | blocker | applied | bbed2879 | `skills/mold/SKILL.md:24,137`; `skills/mold/references/curdle.md:391-404` |
| review-mold.md | `mold` | blocker | applied | 82fff885 | `skills/mold/SKILL.md:98-109` |
| review-mold.md | `mold` | blocker | applied in part | 542ff418, 86f355d4 | `skills/mold/references/curdle.md:47`; `skills/mold/references/mini-spec-mode.md:26` |
| review-mold.md | `mold` | blocker | deferred: owned by schemas | — | `src/easy_cheese_schemas/contracts.py:2400-2417` |
| review-mold.md | `mold` | high | rejected: not reproducible at HEAD | — | `is_hardened_provenance` and `is_new_mold_spec` both reject `mold-handshake # comment`; probe run in this node |
| review-mold.md | `mold` | high | applied | 204c5995 | `tests/python/test_mold_contract_publish.py:154-188` |
| review-mold.md | `mold` | high | deferred: the single-constructor rewrite needs `spec_format.py` and the schemas fixtures, which are outside this area | — | `src/easy_cheese/skills/mold/validate_spec.py:223-730` |
| review-mold.md | `mold` | medium | applied | b28291c8 | `skills/mold/references/grounding.md:39` |
| review-mold.md | `mold` | low | deferred: the removal also edits `tests/python/test_gate_graph.py:359`, which is outside this area | — | `src/easy_cheese/skills/mold/gate_graph.py:242-249,269-274` |
| review-mold.md | `mold` | simplification | applied | aae02e86 | `src/easy_cheese/skills/mold/contract_handlers.py:34-53` |
| review-mold.md | `mold` | simplification | applied | 70a6103e | `src/easy_cheese/skills/mold/gate_graph.py:75-78`; `skills/mold/references/handshake.md:40` |
| review-mold.md | `mold` | simplification | rejected: the checklist is the prose authority and the test already locks the two sets together; generation would invert that direction | — | `src/easy_cheese/skills/mold/gate_graph.py:14-18` |
| review-mold.md | `mold` | simplification | deferred: same scope as the validator rewrite above | — | `src/easy_cheese/skills/mold/validate_spec.py:594-632` |
| review-mold.md | `mold` | STE100 | applied | 1d2736ba | `skills/mold/SKILL.md:12-13,19,23`; `skills/mold/references/*.md` |
| edge-mold-hard-cheese.md | `mold` | blocker | applied | d042580d | `skills/mold/SKILL.md:47,127-131,137`; `skills/mold/references/mini-spec-mode.md:9`; `skills/mold/references/curdle.md:413-414` |
| edge-mold-hard-cheese.md | `mold` | high | applied | d042580d | `tests/python/test_mold_hard_propagation.py:22-59` |
| edge-mold-cook.md | `mold` | blocker | applied | bbed2879 | `skills/mold/references/curdle.md:391-404` |
| edge-mold-cook.md | `mold` | high | deferred: owned by schemas (`resolve_artifact`) and shared (`publication`) | — | `src/easy_cheese_schemas/artifacts.py:65-113` |
| edge-mold-cook.md | `mold` | high | deferred: owned by cook | — | `tests/python/test_cook_contract_accept.py:136-168` |
| edge-mold-briesearch.md | `mold` | high | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:78-87` |
| edge-mold-briesearch.md | `mold` | high | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:82` |
| edge-mold-briesearch.md | `mold` | high | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:86` |
| edge-mold-briesearch.md | `mold` | high | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:84-85` |
| edge-mold-briesearch.md | `mold` | high | deferred: the producer half needs `research_layout.py`, which belongs to briesearch | — | `tests/python/test_briesearch_ledger.py:124-126` |
| edge-mold-briesearch.md | `mold` | medium | deferred: owned by briesearch | — | `skills/briesearch/references/synthesis.md:80-110` |
| edge-briesearch-mold.md | `mold` | high | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:85` |
| edge-briesearch-mold.md | `mold` | high | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:84` |
| edge-briesearch-mold.md | `mold` | high | deferred: the document rules live in `src/easy_cheese_schemas`, which is outside this area | — | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-briesearch-mold.md | `mold` | medium | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:87` |
| edge-schemas-mold.md | `mold` | high | applied in part | 86f355d4 | `skills/mold/references/mini-spec-mode.md:38-45`; `tests/python/test_mold_mini_spec_template.py:57-104` |
| edge-schemas-mold.md | `mold` | high | deferred: `_MINI_SPEC_REQUIRED_SECTIONS` and the strict fixtures belong to schemas | — | `src/easy_cheese_schemas/spec_format.py:33-35`; `src/easy_cheese/skills/mold/validate_spec.py:490-509` |
| edge-schemas-mold.md | `mold` | medium | applied | 86f355d4 | `tests/python/test_mold_mini_spec_template.py:76-104` |
| edge-cheese-mold.md | `mold` | high | deferred: owned by cheese | — | `skills/cheese/references/escalation.md:10-16` |
| edge-cheese-mold.md | `mold` | high | applied on the Mold side | bbed2879 | `skills/mold/SKILL.md:24,137` |
| edge-cheese-mold.md | `mold` | medium | deferred: the consumer half is a cheese test | — | `tests/python/test_cheese_routing_receipt.py:47-57` |
| edge-cook-mold.md | `mold` | blocker | deferred: the emission command belongs to cook and shared | — | `src/easy_cheese/shared/write_handoff_artifact.py:125-162` |
| edge-cook-mold.md | `mold` | high | deferred: owned by cook | — | `skills/cook/references/fan-pathway.md:62-67` |
| edge-cook-mold.md | `mold` | high | deferred: owned by cook and schemas | — | `src/easy_cheese_schemas/contracts.py:1034-1080` |
| edge-cook-mold.md | `mold` | high | deferred: owned by cook | — | `skills/cook/SKILL.md:219-230` |
| edge-cure-mold.md | `mold` | high | deferred: owned by cure | — | `skills/cure/SKILL.md:49-53` |
| edge-cure-mold.md | `mold` | high | deferred: owned by cure | — | `skills/cure/references/domain-model-correction.md:5-31` |
| edge-cure-mold.md | `mold` | high | deferred: the consumer half is a cure test | — | `tests/python/test_glossary_consumers.py` |
| edge-cure-mold.md | `mold` | medium | deferred: Mold already states the optional rule; Cure must follow it | — | `skills/mold/references/curdle.md:330` |
| hub-shared.md | `mold` | blocker | applied | bbed2879 | `skills/mold/references/curdle.md:391-402` |
| hub-shared.md | `mold` | blocker | applied | 204c5995 | `src/easy_cheese/skills/mold/contract_handlers.py:131-132` |
| hub-shared.md | `mold` | high | rejected: not reproducible at HEAD, as above | — | `src/easy_cheese_schemas/spec_format.py:95-102`; `src/easy_cheese/shared/taste_test.py:549-554` |
| hub-shared.md | `mold` | high | applied | 204c5995 | `tests/python/test_mold_contract_publish.py:172-188` |
| hub-schemas.md | `mold` | medium | applied in part | 86f355d4 | `skills/mold/references/mini-spec-mode.md:38-45` |
| hub-build.md | `mold` | — | not applicable | — | `.cheese/notes/r014-megamerge/hub-build.md` |
| review-pasteurize.md | `pasteurize` | blocker | applied | `70550468` | `src/easy_cheese/skills/pasteurize/debug_tag_sweep.py:77-91,122-170`; `skills/pasteurize/SKILL.md:240-253`; `tests/pasteurize/python/test_debug_tag_sweep.py:224-407` |
| review-pasteurize.md | `pasteurize` | blocker | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:102-170`; `tests/pasteurize/python/test_repro_rerun.py:117-196` |
| review-pasteurize.md | `pasteurize` | blocker | partly applied | `053be9c6` | `skills/pasteurize/SKILL.md:332-363`. The template now parses. The phase registration is `deferred: owned by schemas` — see Disagreements. |
| review-pasteurize.md | `pasteurize` | high | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:39-40` |
| review-pasteurize.md | `pasteurize` | high | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:49-99,126-143`; `tests/pasteurize/python/test_repro_rerun.py:199-230` |
| review-pasteurize.md | `pasteurize` | high | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:3-10` |
| review-pasteurize.md | `pasteurize` | medium | rejected | (none) | `tests/python/test_fanout_sizing_docs.py:229-270` asserts the fan-out table and its constants. Removal needs an edit in a test file outside this area. |
| review-pasteurize.md | `pasteurize` | medium | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:18-36` |
| review-pasteurize.md | `pasteurize` | low | deferred | (none) | `tests/python/test_fanout_sizing_docs.py:232-233` asserts the literal `score < 250` and `score > 250`. The fix needs an edit outside this area. |
| review-pasteurize.md | `pasteurize` | STE100 | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:85-86` |
| review-pasteurize.md | `pasteurize` | STE100 | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:153-154` |
| review-pasteurize.md | `pasteurize` | STE100 | applied | `ad804f64` | `skills/pasteurize/references/commands.md:8` |
| review-pasteurize.md | `pasteurize` | STE100 | applied | `ad804f64` | `skills/pasteurize/references/commands.md:9` |
| edge-affinage-pasteurize.md | `pasteurize` | blocker | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:102-117`; `tests/pasteurize/python/test_repro_rerun.py:120-129` |
| edge-affinage-pasteurize.md | `pasteurize` | high | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:48-81` |
| edge-affinage-pasteurize.md | `pasteurize` | medium | partly applied | `eafcb9ea` | The consumer side has expectation tests. The Affinage producer test is `deferred: owned by affinage`. |
| edge-affinage-pasteurize.md | `pasteurize` | STE100 | deferred | (none) | `deferred: owned by affinage` |
| edge-cheese-pasteurize.md | `pasteurize` | high | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:65-72` |
| edge-cheese-pasteurize.md | `pasteurize` | high | partly applied | `053be9c6` | The preamble now matches the parser. The registry entry is `deferred: owned by schemas`. |
| edge-cheese-pasteurize.md | `pasteurize` | high | applied | `053be9c6` | `skills/pasteurize/SKILL.md:111-112,353-363,401-404` |
| edge-cheese-pasteurize.md | `pasteurize` | high | deferred | (none) | The transition test needs the phase registry entry from row 19. |
| edge-cheese-pasteurize.md | `pasteurize` | medium | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:74-77` |
| edge-cheese-pasteurize.md | `pasteurize` | STE100 | deferred | (none) | `deferred: owned by cheese` |
| edge-cheese-pasteurize.md | `pasteurize` | STE100 | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:99-103,217-218,285` |
| edge-cook-pasteurize.md | `pasteurize` | high | applied on the Cook side | `a2b7ccd4` | `cure2-cook.md:52` records the Cook fix. This side keeps `.cheese/pasteurize/<slug>.md` and names the output contract at `skills/pasteurize/SKILL.md:327-367`. |
| edge-cook-pasteurize.md | `pasteurize` | high | partly applied | `053be9c6` | Same as row 19. |
| edge-cook-pasteurize.md | `pasteurize` | medium | deferred | (none) | The seam test needs the phase registry entry from row 19. |
| edge-cook-pasteurize.md | `pasteurize` | STE100 | deferred | (none) | `deferred: owned by cook` |
| hub-shared.md | `pasteurize` | medium | deferred | (none) | `deferred: owned by shared`. The fix belongs to `json_command` in `src/easy_cheese/shared/`. |
| hub-schemas.md | `pasteurize` | high | deferred | (none) | `deferred: owned by cheese and schemas` |
| hub-build.md | `pasteurize` | — | not applicable | (none) | `hub-build.md` lists only `wheypoint -> build`. |
| review-plate.md | `plate` | high | deferred: owned by the `gh` skill, which is outside the plate area paths | — | `skills/plate/SKILL.md:5-8,18-22` keeps exclusive creation. `skill://gh:5-12` still routes creation |
| review-plate.md | `plate` | high | applied | d7b66ec0 | `src/easy_cheese/skills/plate/stack_tools.py:61-95`; `tests/python/test_plate_runtime.py:274-303` |
| review-plate.md | `plate` | high | applied | 3b963978 | `tests/python/test_plate_contract.py:101-131` |
| review-plate.md | `plate` | medium | applied | 45598f90 | `skills/plate/SKILL.md:37-39` |
| review-plate.md | `plate` | medium | applied | 45598f90 | `skills/plate/SKILL.md:29,41-50` |
| review-plate.md | `plate` | low | applied | 45598f90 | `skills/plate/SKILL.md:4-8,20,63,65,92,101,123` |
| review-plate.md | `plate` | low | applied | f3b8c569 | `src/easy_cheese/skills/plate/commands.py:26-29`; `skills/plate/references/commands.md:7` |
| review-plate.md | `plate` | low | applied | aa80b223 | `skills/plate/references/durable-writes.md:3-4,39-40` |
| review-plate.md | `plate` | low | applied | aa80b223 | `skills/plate/references/gh-stack.md:3-5,22-23,30-46,66-67,100` |
| review-plate.md | `plate` | low | applied | aa80b223 | `skills/plate/references/ordinary-pr.md:3,20,41,46,63` |
| review-plate.md | `plate` | low | applied | aa80b223 | `skills/plate/references/stacks.md:3-5,9,19,21,33,46,56` |
| review-plate.md | `plate` | low | applied | 0b3ffb93 | `skills/plate/references/topology.md:18,33,54` |
| review-plate.md | `plate` | simplification | applied | 45598f90 | `skills/plate/SKILL.md:29` |
| review-plate.md | `plate` | simplification | applied | 45598f90 | `skills/plate/SKILL.md:37-39` |
| review-plate.md | `plate` | simplification | rejected: the target file `tests/python/test_ultracook_skills.py` belongs to the `build` area | — | `tests/python/test_plate_contract.py:395-433` |
| review-plate.md | `plate` | simplification | applied | d7b66ec0 | `src/easy_cheese/skills/plate/stack_tools.py:57-95` |
| review-plate.md | `plate` | simplification | applied | aa80b223 | `skills/plate/references/ordinary-pr.md:20` |
| edge-cheese-plate.md | `plate` | high | deferred: owned by `mold` and `pasteurize` | — | Plate accepts `--hard` at `skills/plate/SKILL.md:52` |
| edge-cheese-plate.md | `plate` | high | deferred: owned by `cheese`, which owns the route matrix | — | `skills/cheese/references/handoff-gate.md:56-75` |
| edge-cheese-plate.md | `plate` | medium | deferred: owned by `cheese` and `cure` | — | Plate documents no `--open-pr` input |
| edge-cheese-plate.md | `plate` | medium | applied | 45598f90 | `skills/plate/SKILL.md:56-65`; `tests/python/test_plate_contract.py:65-84` |
| edge-cook-plate.md | `plate` | blocker | deferred: owned by `cook` | — | `skills/cook/references/auto-mode.md` |
| edge-cook-plate.md | `plate` | high | deferred: owned by `schemas` | — | `skills/plate/references/topology.md:66-70` persists `plate_layout` |
| edge-cook-plate.md | `plate` | high | deferred: owned by `schemas`, which holds the canonical `PrPlan` | — | `src/easy_cheese/skills/plate/publication.py` reads the canonical model |
| edge-cook-plate.md | `plate` | high | deferred: owned by `cook` | — | `skills/cook/references/fan-pathway.md:320-322` |
| edge-cook-plate.md | `plate` | medium | applied on the Plate side | 0b3ffb93, 212782c7 | `tests/python/test_plate_contract.py:52-110,395-425` |
| edge-cure-plate.md | `plate` | high | deferred: owned by `cure` | — | `skills/plate/SKILL.md:70-83` already requires every write first |
| edge-cure-plate.md | `plate` | medium | deferred: owned by `cure` for the producer half | — | `tests/python/test_plate_contract.py:426-434` |
| edge-plate-age.md | `plate` | medium | applied | 212782c7 | `tests/python/test_plate_contract.py:395-425` |
| edge-plate-age.md | `plate` | low | applied | 45598f90 | `skills/plate/SKILL.md:21` |
| edge-plate-cheese.md | `plate` | high | deferred: owned by `cheese` | — | `skills/plate/references/topology.md:27-31` names both triggers |
| edge-plate-cheese.md | `plate` | high | applied | 0b3ffb93 | `skills/plate/references/topology.md:52-61` |
| edge-plate-cheese.md | `plate` | high | applied on the Plate side | 0b3ffb93 | `tests/python/test_plate_contract.py:52-77` |
| edge-plate-cook.md | `plate` | blocker | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:82-85`; `tests/python/test_plate_contract.py:80-96` |
| edge-plate-cook.md | `plate` | high | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:104-107` |
| edge-plate-cook.md | `plate` | high | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:87-97` |
| edge-plate-cook.md | `plate` | medium | applied on the Plate side | 0b3ffb93 | `tests/python/test_plate_contract.py:79-96` |
| edge-plate-hard-cheese.md | `plate` | blocker | deferred: owned by `hard-cheese` (`freshness_check.py`) | — | Plate now sends `tracked_diff_digest` at `skills/plate/references/durable-writes.md:58-70` |
| edge-plate-hard-cheese.md | `plate` | high | applied on the Plate side | 45598f90 | `skills/plate/references/durable-writes.md:58-70`; `tests/python/test_plate_contract.py:65-78` |
| edge-plate-hard-cheese.md | `plate` | high | applied on the Plate side | 45598f90 | `skills/plate/SKILL.md:56-65` |
| edge-plate-hard-cheese.md | `plate` | high | applied on the Plate side | 45598f90 | `tests/python/test_plate_contract.py:65-84` |
| hub-shared.md | `plate` | ok | no change needed | — | `src/easy_cheese/skills/plate/commands.py:8-34` |
| hub-schemas.md | `plate` | — | no change needed | — | — |
| hub-build.md | `plate` | — | no change needed | — | — |
| review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-cheese-press.md, edge-cook-press.md, hub-shared.md | `press` | blocker | applied | d6dba93d | `skills/press/SKILL.md:145-183` writes only the canonical preamble. `tests/python/test_press_prose_contract.py:33` parses it with `parse_handoff_slug`. |
| review-press.md, edge-cook-press.md, hub-shared.md | `press` | blocker | applied | 8c278b0a, b45b738d | `skills/press/SKILL.md:20-36` defines `--auto`, `--hard`, and `--open-pr`. `skills/press/SKILL.md:130-142` defines auto mode. `tests/python/test_press_prose_contract.py:81,90` |
| review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-cheese-press.md | `press` | high | applied | d6dba93d | `skills/press/SKILL.md:155,163` names the consumed Cook report. `tests/python/test_press_prose_contract.py:73` |
| review-press.md, hub-shared.md | `press` | high | applied in prose; code deferred: owned by shared | 563705ab | `skills/press/references/telemetry.md:74` requires a manual review of each `metadata` path. The classifier at `src/easy_cheese/shared/fanout/press_telemetry.py:61-67,260-266` is outside every area path. |
| review-press.md, hub-shared.md | `press` | high | applied in prose; enum deferred: owned by shared | 26dd5a6c, e3462d1a | `skills/press/SKILL.md:113` maps a recorded concern to `ok-with-concerns`. `skills/press/references/gap-analysis.md:18` agrees. The `Outcome` enum at `src/easy_cheese/shared/fanout/press_route.py:10-16` is outside every area path. |
| edge-press-age.md | `press` | high | applied | d6dba93d | `skills/press/SKILL.md:145-161` puts `action:` and `telemetry:` in the report body. |
| edge-press-age.md | `press` | high | applied | d6dba93d | `skills/press/SKILL.md:171` defines `## Review follow-ups`. `tests/python/test_press_prose_contract.py:108` |
| edge-press-cook.md, edge-cook-press.md | `press` | high | applied | 26dd5a6c | `skills/press/SKILL.md:100-104` reads one baseline artifact path. Cook now writes one path at `skills/cook/references/quality-gates.md:44-74`. `tests/python/test_press_prose_contract.py:117` |
| edge-press-cook.md | `press` | high | applied | 8c278b0a, 26dd5a6c | `skills/press/SKILL.md:34` preserves `durable_flags:`. `skills/press/SKILL.md:190` forwards only supplied flags. |
| edge-cook-press.md | `press` | high | applied | d6dba93d | `skills/press/SKILL.md:155` requires `artifact: .cheese/cook/<slug>.md`. Press now names the consumed result. |
| review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-press-age.md, edge-cheese-press.md | `press` | high | applied | 3b83ceb9 | `tests/python/test_press_prose_contract.py` adds 13 tests. |
| review-press.md, hub-shared.md | `press` | medium | applied | bf3086e8 | `src/easy_cheese/skills/press/commands.py:13`; `skills/press/references/commands.md:7` |
| review-press.md | `press` | medium | applied | e3462d1a | `skills/press/references/gap-analysis.md:75-77`; `skills/press/SKILL.md:179` |
| edge-cook-press.md | `press` | medium | applied | 8c278b0a, d6dba93d | `skills/press/SKILL.md:34,152` |
| edge-cook-press.md, review-press.md | `press` | medium, low | applied | b45b738d, ddec5288 | `skills/press/SKILL.md:142` tests the directive, not the source name. |
| review-press.md, edge-press-cheese.md, edge-cook-press.md | `press` | low | applied | 26dd5a6c | `skills/press/SKILL.md:202` |
| review-press.md, edge-press-cook.md, edge-cook-press.md | `press` | low | applied | e3462d1a | `skills/press/references/gap-analysis.md:55` |
| edge-press-age.md | `press` | low | deferred: owned by age | — | `skills/age/SKILL.md:19-22` is outside this area. |
| edge-press-cheese.md, edge-cheese-press.md | `press` | low | deferred: owned by cheese | — | `skills/cheese/SKILL.md:42,136` and four Cheese reference files. |
| edge-cook-press.md | `press` | low | deferred: owned by cook | — | `skills/cook/SKILL.md:63,241-250` |
| edge-press-cook.md, hub-shared.md | `press` | high | rejected | — | The manifest targets live in shared code. `review-press.md` simplifications keep the static Press manifest. Adding a fourth entry needs a shared owner. |
| review-schemas.md | `schemas` | high | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:676-690` |
| review-schemas.md | `schemas` | high | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:145-166`; `tests/schemas/python/goldens/normalization-receipt.json:1` |
| review-schemas.md | `schemas` | medium | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:617-632` |
| review-schemas.md | `schemas` | low | deferred: owned by mold and shared | none | The rename regenerates `src/easy_cheese/shared/document_rules.py:9,45` and `skills/mold/references/curdle.md:175,187`. |
| review-schemas.md | `schemas` | low | applied | `ce662297` | `src/easy_cheese_schemas/compat.py:9-11`; `tests/python/fixtures/spec_format/valid_spec.md:72` |
| review-schemas.md | `schemas` | simplification | applied as equality | `6a71e452` | The compatibility contract keeps both published fields. The model now requires them to agree at `src/easy_cheese_schemas/contracts.py:685-690`. |
| review-schemas.md | `schemas` | simplification | deferred: owned by mold and shared | none | The rename touches the same generated files as the low finding above. |
| edge-build-schemas.md | `schemas` | high | deferred: owned by build | none | `scripts/render_generated_regions.py:151-165` |
| edge-build-schemas.md | `schemas` | high | deferred: owned by build | none | `justfile:2,15-31` |
| edge-build-schemas.md | `schemas` | medium | deferred: owned by build | none | `scripts/render_generated_regions.py:53-56` |
| edge-build-schemas.md | `schemas` | medium | deferred: owned by build | none | `scripts/build_pyz.py:112-154` |
| edge-build-schemas.md | `schemas` | low | deferred: owned by cook | none | `skills/cook/SKILL.md:123` |
| edge-build-schemas.md | `schemas` | ste100 | deferred: owned by mold | none | `skills/mold/references/curdle.md:158` |
| edge-schemas-build.md | `schemas` | medium | deferred: owned by build | none | This row repeats the `_ContractVersion` finding above. |
| edge-schemas-build.md | `schemas` | medium | deferred: owned by build | none | This row repeats the writer reference finding above. |
| edge-schemas-mold.md | `schemas` | high | deferred: owned by mold and shared | none | `src/easy_cheese/skills/mold/validate_spec.py:595-634`; `src/easy_cheese/shared/taste_test.py:662-689` |
| edge-schemas-mold.md | `schemas` | medium | deferred: owned by mold | none | `tests/python/test_mold_taste_test.py:207-216` |
| edge-schemas-mold.md | `schemas` | ste100 | deferred: owned by mold | none | `skills/mold/SKILL.md:94-100`; `skills/mold/references/mini-spec-mode.md:31` |
| edge-schemas-shared.md | `schemas` | blocker | applied by shared | `b18b463b` | That fix broke one shared test. See `Follow-ups`. |
| edge-schemas-shared.md | `schemas` | blocker | applied by shared | `466ce044` | `src/easy_cheese/shared/publication.py:517-526` |
| edge-schemas-shared.md | `schemas` | high | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:685-690` |
| edge-schemas-shared.md | `schemas` | high | applied | `6a71e452` | `tests/schemas/python/test_contracts.py:1124-1185` |
| edge-schemas-shared.md | `schemas` | high | deferred: owned by shared | none | `src/easy_cheese/shared/publication.py:418-425` |
| edge-schemas-shared.md | `schemas` | high | deferred: owned by shared | none | `src/easy_cheese/shared/taste_test.py:681-689` |
| edge-schemas-wheypoint.md | `schemas` | blocker | applied | `3de3c695` | The model rejects a later revision without a parent at `src/easy_cheese_schemas/wheypoint.py:690-700`. |
| edge-schemas-wheypoint.md | `schemas` | blocker | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lineage.py:68-124` |
| edge-schemas-wheypoint.md | `schemas` | high | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lint.py:399-452` |
| edge-schemas-wheypoint.md | `schemas` | high | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lint.py:415-451` |
| edge-schemas-wheypoint.md | `schemas` | high | deferred: owned by wheypoint | none | `skills/wheypoint/SKILL.md:79-82` |
| edge-shared-schemas.md | `schemas` | high | applied | `fb61b3bc` | `src/easy_cheese_schemas/compat.py:444-508`; `tests/python/test_schemas_compat.py:342-410` |
| edge-shared-schemas.md | `schemas` | high | applied | `6a71e452` | This row repeats the receipt identity finding above. |
| edge-shared-schemas.md | `schemas` | high | applied | `6a71e452` | This row repeats the null source finding above. |
| hub-schemas.md | `schemas` | blocker | deferred: owned by age | none | `skills/age/SKILL.md:112-115` |
| hub-schemas.md | `schemas` | blocker | deferred: owned by cook | none | `src/easy_cheese/skills/cook/workflow.py:1252-1277` |
| hub-schemas.md | `schemas` | blocker | deferred: owned by cure | none | `src/easy_cheese/skills/cook/workflow.py:1192-1210` |
| hub-schemas.md | `schemas` | high | deferred: owned by age | none | `tests/python/test_age_review_lock.py:38-47` |
| hub-schemas.md | `schemas` | high | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:98-122` |
| hub-schemas.md | `schemas` | medium | deferred: owned by cook | none | `src/easy_cheese/skills/cook/contract_handlers.py:53-64` |
| hub-schemas.md | `schemas` | medium | deferred: owned by cure | none | `tests/schemas/python/test_workflow_thread.py:766-919` |
| hub-schemas.md | `schemas` | medium | deferred: owned by mold | none | This row repeats the mini-spec Grounding finding above. |
| review-shared.md | `shared` | blocker | applied before this node | b18b463b | `src/easy_cheese/shared/publication.py:132-168` |
| review-shared.md | `shared` | blocker | applied before this node | 466ce044 | `src/easy_cheese/shared/publication.py:531-543` |
| review-shared.md | `shared` | high | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| review-shared.md | `shared` | high | applied | 3397d5a8 | `src/easy_cheese/shared/publication.py:301-317,326-352` |
| review-shared.md | `shared` | high | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:223-634` |
| review-shared.md | `shared` | medium | applied | a5796759 | `src/easy_cheese/shared/bundle_commands.py:86-95` |
| review-shared.md | `shared` | low | applied | 3f20e2df | `src/easy_cheese/shared/publication.py:89-101` |
| review-shared.md | `shared` | low | applied | 3f20e2df | `tests/python/test_artifact_path.py:90` |
| review-shared.md | `shared` | simplification | applied | a5796759 | `src/easy_cheese/shared/bundle_commands.py:86-95` |
| review-shared.md | `shared` | simplification | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:501-802` |
| review-shared.md | `shared` | simplification | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:37-99` |
| review-shared.md | `shared` | simplification | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-450` |
| review-shared.md | `shared` | simplification | applied | 3397d5a8 | `src/easy_cheese/shared/publication.py:301-352` |
| edge-schemas-shared.md | `shared` | blocker | applied before this node | b18b463b | `src/easy_cheese/shared/publication.py:132-168` |
| edge-schemas-shared.md | `shared` | blocker | applied before this node | 466ce044 | `src/easy_cheese/shared/publication.py:531-543` |
| edge-schemas-shared.md | `shared` | high | applied | 0578d964 | `src/easy_cheese/shared/publication.py:497-506` |
| edge-schemas-shared.md | `shared` | high | deferred: owned by schemas | none | `tests/schemas/python/goldens/normalization-receipt.json:1` |
| edge-schemas-shared.md | `shared` | high | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| edge-schemas-shared.md | `shared` | high | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:681-689` |
| edge-shared-schemas.md | `shared` | high | applied | 0578d964 | `src/easy_cheese/shared/migrate.py:100-110` |
| edge-shared-schemas.md | `shared` | high | applied | 0578d964 | `src/easy_cheese/shared/publication.py:497-506` |
| edge-shared-schemas.md | `shared` | high | deferred: owned by schemas | none | `src/easy_cheese_schemas/contracts.py:637-644` |
| edge-build-shared.md | `shared` | low | deferred: owned by build | none | `scripts/render_generated_regions.py:47-50` |
| hub-shared.md | `shared` | blocker | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:436-450` |
| hub-shared.md | `shared` | high | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| hub-shared.md | `shared` | blocker | deferred: owned by age | none | `src/easy_cheese/skills/age/review_lock.py:50-52` |
| hub-shared.md | `shared` | blocker | deferred: owned by age | none | `src/easy_cheese/skills/age/review_lock.py:63-67` |
| hub-shared.md | `shared` | blocker | deferred: owned by age | none | `skills/age/SKILL.md:111-115` |
| hub-shared.md | `shared` | blocker | deferred: owned by cure | none | `skills/cure/SKILL.md:97-99` |
| hub-shared.md | `shared` | blocker | deferred: owned by easy-cheese-setup | none | `skills/easy-cheese-setup/SKILL.md:38-40` |
| hub-shared.md | `shared` | blocker | deferred: owned by mold | none | `skills/mold/SKILL.md:20-24` |
| hub-shared.md | `shared` | blocker | deferred: owned by mold | none | `src/easy_cheese/skills/mold/contract_handlers.py:88-102` |
| hub-shared.md | `shared` | blocker | deferred: owned by press | none | `skills/press/SKILL.md:123-143` |
| hub-shared.md | `shared` | blocker | deferred: owned by press | none | `src/easy_cheese/shared/press_route.py:23-27` |
| hub-shared.md | `shared` | blocker | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/projection.py:68-81` |
| hub-shared.md | `shared` | high | deferred: owned by affinage | none | `skills/affinage/SKILL.md:171-183` |
| hub-shared.md | `shared` | high | deferred: owned by age | none | `src/easy_cheese/shared/read_handoff_slug.py:19-45` |
| hub-shared.md | `shared` | high | deferred: owned by age | none | `skills/age/SKILL.md:157-166` |
| hub-shared.md | `shared` | high | deferred: owned by age | none | `skills/age/SKILL.md:112-116` |
| hub-shared.md | `shared` | high | deferred: owned by briesearch | none | `src/easy_cheese/skills/briesearch/research_layout.py:37-43` |
| hub-shared.md | `shared` | high | deferred: owned by cook | none | `skills/cook/SKILL.md:126-160` |
| hub-shared.md | `shared` | high | deferred: owned by cure | none | `skills/cure/SKILL.md:153-171` |
| hub-shared.md | `shared` | high | deferred: owned by easy-cheese-setup | none | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| hub-shared.md | `shared` | high | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:637-645` |
| hub-shared.md | `shared` | high | deferred: owned by mold | none | `tests/python/test_mold_contract_publish.py:85-105` |
| hub-shared.md | `shared` | high | deferred: owned by press | none | `src/easy_cheese/shared/press_telemetry.py:58-78` |
| hub-shared.md | `shared` | high | deferred: owned by press | none | `src/easy_cheese/shared/press_route.py:10-16` |
| hub-shared.md | `shared` | high | deferred: owned by wheypoint | none | `tests/python/test_wheypoint_skill_contract.py:156-161` |
| hub-shared.md | `shared` | medium | deferred: owned by easy-cheese-setup, press, build | none | `hub-shared.md` medium list |
| hub-shared.md | `shared` | low | deferred: owned by age | none | `src/easy_cheese/skills/age/commands.py:127-130` |
| this node | `shared` | gate | applied | ff4a47a7 | `tests/python/test_publication_gateway.py:111-118` |
| this node | `shared` | gate | applied | 435f166d | `src/easy_cheese/shared/migrate.py:105-110` |
| this node | `shared` | gate | applied | d4d7f110 | `tests/wheypoint/python/test_storage.py:85` |
| review-wheypoint.md | `wheypoint` | blocker | applied | `9a15b5cc` | `src/easy_cheese/skills/wheypoint/commit.py:336-352`; `src/easy_cheese/skills/wheypoint/wheypoint.py:295-323` |
| review-wheypoint.md | `wheypoint` | blocker | applied in part | `c8a0b8c2`, `4c65cb30` | The command now refuses each unknown key at `src/easy_cheese/skills/wheypoint/wheypoint.py:198-204`. The prose separates the two formats at `skills/wheypoint/SKILL.md:79-121`. |
| review-wheypoint.md | `wheypoint` | blocker | deferred: owned by schemas | none | `src/easy_cheese_schemas/wheypoint.py:282-290,542-569` |
| review-wheypoint.md | `wheypoint` | blocker | applied | `00963235` | `src/easy_cheese/skills/wheypoint/projection.py:38-50,77-120`; `tests/wheypoint/python/test_shared_handoff_seam.py:27-108` |
| review-wheypoint.md | `wheypoint` | blocker | applied on this side | `4c65cb30` | `skills/wheypoint/SKILL.md:85,189-193`; `tests/python/test_wheypoint_skill_contract.py:171-192` |
| review-wheypoint.md | `wheypoint` | blocker | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-124` |
| review-wheypoint.md | `wheypoint` | high | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:464-521`; `tests/wheypoint/python/test_compaction_proof.py:116-176` |
| review-wheypoint.md | `wheypoint` | high | applied | `00963235`, `4c65cb30` | `tests/wheypoint/python/test_shared_handoff_seam.py`; `tests/python/test_wheypoint_skill_contract.py:171-192` |
| review-wheypoint.md | `wheypoint` | medium | applied | `2468f0eb` | `src/easy_cheese/skills/wheypoint/records.py:188-200`; `tests/wheypoint/python/test_storage.py:784-826` |
| review-wheypoint.md | `wheypoint` | simplification | applied as separation | `4c65cb30` | See `Disagreements`. |
| review-wheypoint.md | `wheypoint` | simplification | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:36,244-249` |
| review-wheypoint.md | `wheypoint` | simplification | applied in part | `9a15b5cc` | The durability sequence now lives in `commit._finalize`. The transport stays in `wheypoint.py`. See `Disagreements`. |
| review-wheypoint.md | `wheypoint` | simplification | applied | `00963235` | `tests/wheypoint/python/test_shared_handoff_seam.py` |
| edge-cheese-wheypoint.md | `wheypoint` | blocker | applied in part | `c8a0b8c2` | This row repeats the intent field row above. The typed fields stay deferred to schemas. |
| edge-cheese-wheypoint.md | `wheypoint` | blocker | applied on this side | `4c65cb30` | The Cheese route stays deferred to cheese. |
| edge-cheese-wheypoint.md | `wheypoint` | high | applied | `00963235` | A gated projection now carries a derived reason at `src/easy_cheese/skills/wheypoint/projection.py:77-95`. |
| edge-cheese-wheypoint.md | `wheypoint` | high | applied on this side | `1a7afb54` | The resolver already routes by disposition at `src/easy_cheese/skills/wheypoint/resolve.py:513-516`. The skill prose now says a legacy halt stops at `skills/wheypoint/SKILL.md:185-188`. The Cheese branches stay deferred to cheese. |
| edge-cheese-wheypoint.md | `wheypoint` | high | applied | `94abd277` | `src/easy_cheese/skills/wheypoint/resolve.py:372-411`; `tests/wheypoint/python/test_legacy_artifact.py:40-85` |
| edge-cheese-wheypoint.md | `wheypoint` | high | applied | `00963235`, `94abd277` | `tests/wheypoint/python/test_shared_handoff_seam.py`; `tests/wheypoint/python/test_legacy_artifact.py` |
| edge-cheese-wheypoint.md | `wheypoint` | medium | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:54-59` |
| edge-cheese-wheypoint.md | `wheypoint` | ste100 | deferred: owned by cheese | none | `skills/cheese/SKILL.md:136`; `skills/cheese/references/continue-resume.md:255` |
| edge-schemas-wheypoint.md | `wheypoint` | blocker | applied | `b70ddce3` | `src/easy_cheese/skills/wheypoint/lineage.py:20,94-109`; `tests/wheypoint/python/test_lineage_ancestry.py:35-81` |
| edge-schemas-wheypoint.md | `wheypoint` | high | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:418-461`; `tests/wheypoint/python/test_compaction_proof.py:63-113` |
| edge-schemas-wheypoint.md | `wheypoint` | high | applied | `12cb4002` | This row repeats the prior compaction row above. |
| edge-schemas-wheypoint.md | `wheypoint` | high | applied | `4c65cb30` | `skills/wheypoint/SKILL.md:85,189-193` |
| edge-wheypoint-cook.md | `wheypoint` | blocker | applied in part | `c8a0b8c2`, `1a7afb54` | The command refuses the key rather than drop it. The prose no longer promises carry-forward at `skills/wheypoint/SKILL.md:151-161`. The typed field stays deferred to schemas. |
| edge-wheypoint-cook.md | `wheypoint` | high | deferred: owned by schemas | none | The seam test needs the typed field the schemas area owns. |
| edge-wheypoint-cook.md | `wheypoint` | high | applied | `25d43a95` | `skills/wheypoint/SKILL.md:18-23` |
| edge-wheypoint-cook.md | `wheypoint` | high | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-120` |
| hub-shared.md | `wheypoint` | blocker | applied | `00963235` | This row repeats the projection blocker above. |
| hub-shared.md | `wheypoint` | high | applied | `00963235` | `tests/wheypoint/python/test_shared_handoff_seam.py` |
| hub-schemas.md | `wheypoint` | ok | no change needed | none | `src/easy_cheese/skills/wheypoint/records.py:30-39` |
| hub-build.md | `wheypoint` | untested | deferred: owned by build | none | `scripts/check_bundles.py:461-499` |
| cure2-schemas.md | `wheypoint` | follow-up | applied | `7dc8cc26` | `tests/wheypoint/python/test_storage.py:399-421` |
| Copilot PR #614 | `wheypoint` | external | no change needed | none | The guard is already present at `src/easy_cheese/skills/wheypoint/storage.py:191`. |
| Copilot PR #614 | `wheypoint` | external | no change needed | none | No reference file under `skills/wheypoint/` contains such a path. |

## Deferred rows that no area applied

Each row below stayed open at this commit. The reason column repeats the
state text from the source note.

| Source note | Area | Owner | Severity | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-affinage.md | `affinage` | `the` | high | deferred: owned by the Affinage runtime module `post_reply.py`, which is outside the eight area paths | `src/easy_cheese/skills/affinage/post_reply.py:134-136` |
| edge-affinage-pasteurize.md | `affinage` | `—` | medium | deferred: the producer test needs the Pasteurize request contract from finding 16 | `skills/affinage/references/flow-details.md:86-91` |
| edge-cheese-affinage.md | `affinage` | `schemas` | high | deferred: owned by schemas; the fix registers an Affinage phase contract in `_compiled_phase_registry.py` | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103` |
| hub-schemas.md | `affinage` | `schemas` | blocker | deferred: owned by schemas and cure | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| review-age, hub-shared | `age` | `shared` | medium | deferred: owned by shared | `age-route --help` parses the flag as JSON in `shared/bundle_commands.py` `json_command`. The generated preamble in `scripts/render_generated_regions.py` is owned by build. |
| edge-age-cure | `age` | `schemas` | blocker | deferred: owned by schemas | Age emits Markdown; the typed Cure API needs a `CurdPlan` pointer. `cure2-schemas.md` owns the adapter. Age keeps the normal report path, which findings 8, 9, and 10 repaired. |
| edge-cook-age | `age` | `schemas` | blocker | deferred: owned by schemas | The typed `ReviewRequest` to `ReviewResultWriterView` adapter and the `blocker` versus `critical` severity term live in `src/easy_cheese_schemas`. |
| edge-cook-age | `age` | `cook` | high | deferred: owned by cook | The two-sided Cook handoff to Age phase-decision test belongs to `tests/fanout/python`. |
| edge-cure-age | `age` | `schemas` | blocker | deferred: owned by schemas | Same adapter as finding 67. |
| edge-cure-age | `age` | `cure` | high | deferred: owned by cure | The end-to-end Cure-to-Age test needs the Cure writer fix in finding 75 first. |
| edge-press-age | `age` | `press` | medium | deferred: owned by press | The full Press report round-trip test belongs to `tests/shared/python`. |
| hub-shared | `age` | `shared` | high | deferred: owned by shared | `read_handoff_slug.py:19-45` returns preamble fields only. Age no longer depends on it for the body (finding 10). |
| edge-briesearch-mold.md | `briesearch` | `mold` | high | deferred: owned by mold. Strict Mold validation must check tier-2 provenance | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-mold-briesearch.md | `briesearch` | `mold` | high | deferred: owned by mold. Mold must map `don't know` to an open hypothesis | `skills/mold/references/validate-cycle.md:18-24` |
| edge-mold-briesearch.md | `briesearch` | `mold` | medium | deferred: owned by mold and cheese. One sidechain result shape needs both callers | `skills/briesearch/SKILL.md:13` |
| edge-build-docs.md | `build` | `mold` | low | deferred: owned by mold | skills/mold/references/adr.md:36 |
| review-build.md, edge-build-schemas.md | `build` | `—` | high | deferred: no listed area owns `.github/workflows/build-pyz.yml` | .github/workflows/build-pyz.yml:7 |
| review-build.md | `build` | `—` | high | deferred: no listed area owns `.github/workflows/validate.yml` | .github/workflows/validate.yml:79 |
| edge-cheese-affinage.md | `cheese` | `schemas` | high | deferred: owned by schemas | The Affinage phase transition is not registered. Row 9 narrows the Cheese claim instead |
| edge-cheese-age.md | `cheese` | `age` | high | deferred: owned by age | The Age writer clears `artifact` and omits `baseline` |
| edge-cheese-age.md | `cheese` | `age` | medium | deferred: owned by age | Age declares no `handoff_context.wiki_hits` input |
| edge-cheese-age.md | `cheese` | `age` | medium | deferred: owned by age | `--hard` is missing from both Age command forms |
| edge-cheese-cook.md | `cheese` | `cook` | medium | deferred: owned by cook | Cook declares no `handoff_context.wiki_hits` input |
| edge-cheese-cure.md | `cheese` | `cure` | blocker | deferred: owned by cure | The typed `CurdPlan` path needs a normal report repair path in Cure |
| edge-cheese-cure.md | `cheese` | `cure` | blocker | deferred: owned by cure | The Cure writer command omits `--body-file` |
| edge-cheese-cure.md | `cheese` | `cure` | high | deferred: owned by cure | The selection packet belongs to the Cure dispatch contract |
| edge-cheese-pasteurize.md | `cheese` | `pasteurize` | high | deferred: owned by pasteurize | Pasteurize drops `--open-pr` and `--hard` |
| edge-cheese-pasteurize.md | `cheese` | `schemas` | high | deferred: owned by schemas | The registry has no Pasteurize phase |
| edge-cheese-pasteurize.md | `cheese` | `pasteurize` | medium | deferred: owned by pasteurize | Pasteurize has no Inputs section |
| edge-cheese-plate.md | `cheese` | `plate` | medium | deferred: owned by plate | Plate does not define the hard-gate failure mode |
| edge-cheese-press.md | `cheese` | `schemas` | blocker | deferred: owned by schemas | The canonical handoff model needs one typed local action |
| edge-press-cheese.md | `cheese` | `press` | high | deferred: owned by press | Press defines `artifact:` as an evidence path |
| edge-cheese-wheypoint.md | `cheese` | `wheypoint` | blocker | deferred: owned by wheypoint | The record and projection drop mode, task, order, baseline, and flag fields |
| edge-cheese-wheypoint.md | `cheese` | `wheypoint` | high | deferred: owned by wheypoint | The projection emits a bare `status: gated` |
| edge-cheese-wheypoint.md | `cheese` | `wheypoint` | high | deferred: owned by wheypoint | The resolver gates every legacy pull request artifact |
| edge-cook-cheese.md | `cheese` | `wheypoint` | blocker | deferred: owned by wheypoint | The resolver cannot resolve an exact Cook report path |
| edge-cook-cheese.md | `cheese` | `cook` | high | deferred: owned by cook | Cook documents an invalid reader command |
| edge-cook-cheese.md | `cheese` | `cook` | high | deferred: owned by cook | The nested `baseline:` block cannot cross the seam |
| edge-cure-cheese.md | `cheese` | `wheypoint` | blocker | deferred: owned by wheypoint | The resolver rejects an exact Cure report path |
| edge-cure-cheese.md | `cheese` | `cure` | blocker | deferred: owned by cure | The Cure writer removes the report body |
| edge-cure-cheese.md | `cheese` | `cure` | high | deferred: owned by cure | The writer example cannot emit `next: done` |
| edge-cure-cheese.md | `cheese` | `cure` | high | deferred: owned by cure | Cure loses baseline state |
| edge-cure-cheese.md | `cheese` | `cure` | high | deferred: owned by cure | Cure weakens the fresh-context failure mode |
| edge-plate-cheese.md | `cheese` | `plate` | high | deferred: owned by plate | Plate does not handle a normalized `other:` answer |
| review-cook.md, hub-schemas.md | `cook` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1252-1277` runs declaration order. `skills/cook/references/fan-pathway.md:75-77` already requires topological waves. |
| review-cook.md | `cook` | `build` | simplification | deferred: owned by build | `src/easy_cheese/skills/cook/commands.py:63-95` feeds the generated rows in `skills/cook/references/commands.md:15,26-29`. Removal needs the generated-region rebuild and the bundle-closure tests that `build` owns. |
| edge-cheese-cook.md | `cook` | `cheese` | high | deferred: owned by cheese | Cook owns the rule at `skills/cook/SKILL.md:49-54`. Cheese must reference it, not copy it. |
| edge-cheese-cook.md | `cook` | `cheese` | medium | deferred: owned by cheese | Cook defines the flag at `skills/cook/SKILL.md:40`. |
| edge-cook-age.md | `cook` | `age` | blocker | deferred: owned by age | `skills/age/phase-contract.yaml:5-10` declares `CurdResult` input, but `src/easy_cheese/skills/age/commands.py:11-106` has no adapter. |
| edge-cook-age.md | `cook` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:112-115` passes an empty artifact and omits `--baseline`. |
| edge-cook-age.md | `cook` | `age` | high | deferred: owned by age | The adapter in finding 21 must land before a seam test can run. |
| edge-cook-cheese.md | `cook` | `wheypoint` | blocker | deferred: owned by wheypoint | `src/easy_cheese/skills/wheypoint/legacy.py:350-366` searches only `.cheese/notes/<slug>.md`. |
| edge-cook-cheese.md | `cook` | `cheese` | medium | deferred: owned by cheese | The resolver in finding 27 must land first. |
| edge-cook-cure.md | `cook` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1043-1119` diagnoses only failed writer output. |
| edge-cook-cure.md | `cook` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:331-376` has no diagnosis field. |
| edge-cook-cure.md | `cook` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1192-1198` requires every plan curd. |
| edge-cook-cure.md | `cook` | `schemas` | blocker | deferred: owned by schemas | `CureDiagnosisBinding` has no registered schema. |
| edge-cook-cure.md | `cook` | `schemas` | high | deferred: owned by schemas | Findings 33 to 36 must land first. |
| edge-cook-mold.md | `cook` | `mold` | blocker | deferred: owned by mold | `src/easy_cheese/skills/mold/commands.py:10-94` has no intake command. Cook now publishes and names the validated request at `skills/cook/references/fan-pathway.md:113-129`. |
| edge-cook-mold.md | `cook` | `mold` | medium | deferred: owned by mold | Finding 38 must land first. |
| edge-cook-pasteurize.md | `cook` | `pasteurize` | high | deferred: owned by pasteurize | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-102` omits the Pasteurize transition. |
| edge-cook-pasteurize.md | `cook` | `pasteurize` | medium | deferred: owned by pasteurize | Finding 44 must land first. |
| edge-cook-plate.md | `cook` | `shared` | high | deferred: owned by shared | `src/easy_cheese/shared/handoff.py:38-87` defines no `plate_layout` field. |
| edge-cook-plate.md | `cook` | `plate` | high | deferred: owned by plate | `src/easy_cheese/skills/plate/publication.py:127-133` permits only `plate_layout`. |
| edge-cook-press.md, edge-press-cook.md | `cook` | `shared` | blocker | deferred: owned by shared | `src/easy_cheese/shared/handoff.py:83-87` has no local continuation field. |
| edge-cook-press.md | `cook` | `press` | high | deferred: owned by press | Press never resolves the declared result. |
| edge-cook-press.md | `cook` | `press` | medium | deferred: owned by press | Cook now owns the fan pathway. |
| edge-wheypoint-cook.md | `cook` | `wheypoint` | blocker | deferred: owned by wheypoint | Finding 29 makes the Cook side one line, which Wheypoint can carry. |
| edge-affinage-cure.md | `cure` | `shared` | high | deferred: owned by shared | `src/easy_cheese/shared/findings.py:40-53` |
| edge-age-cure.md | `cure` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:157-164` |
| edge-age-cure.md | `cure` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:183-188` |
| edge-age-cure.md | `cure` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:92-95` |
| edge-age-cure.md | `cure` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:112-116` |
| edge-cook-cure.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1043-1119` |
| edge-cook-cure.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:331-376` |
| edge-cook-cure.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1192-1198` |
| edge-cook-cure.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/_compiled_phase_registry.py:105` |
| edge-cook-cure.md | `cure` | `schemas` | high | deferred: owned by schemas | `tests/schemas/python/test_workflow_thread.py:766-918` |
| edge-cure-age.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `skills/cure/phase-contract.yaml:5-10` |
| edge-cure-age.md | `cure` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:214-225` |
| edge-cure-hard-cheese.md | `cure` | `hard-cheese` | medium | deferred: owned by hard-cheese | `tests/python/test_hard_cheese.py:156-166` |
| edge-cure-mold.md | `cure` | `shared` | high | deferred: owned by shared | `src/easy_cheese/shared/paths.py:555-602` |
| hub-schemas.md | `cure` | `schemas` | blocker | deferred: owned by schemas | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| hub-schemas.md | `cure` | `schemas` | medium | deferred: owned by schemas | `tests/schemas/python/test_workflow_thread.py:766-919` |
| edge-build-docs.md | `docs` | `mold` | low | deferred: owned by mold | `skills/mold/references/adr.md:36` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | `shared` | high | deferred: owned by shared | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | `shared` | medium | deferred: owned by shared | `src/easy_cheese/shared/hallouminate_setup.py:172-195` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | `shared` | medium | deferred: owned by shared | `src/easy_cheese/shared/hallouminate_setup.py:314-323` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | `shared` | simplification | deferred: owned by shared | `src/easy_cheese/shared/hallouminate_setup.py:338-357` |
| review-easy-cheese-setup.md | `easy-cheese-setup` | `shared` | simplification | deferred: owned by shared | `src/easy_cheese/shared/hallouminate_setup.py:172-295` |
| review-hard-cheese | `hard-cheese` | `—` | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| review-hard-cheese | `hard-cheese` | `—` | blocker | deferred: root cause in `append_attempt.py`, outside the five area paths | `src/easy_cheese/skills/hard_cheese/append_attempt.py:110-117` |
| edge-mold-hard-cheese | `hard-cheese` | `mold` | high | deferred: owned by `mold` | `tests/python/test_hard_cheese.py:150-153` |
| edge-plate-hard-cheese | `hard-cheese` | `—` | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| review-mold.md | `mold` | `—` | high | deferred: the single-constructor rewrite needs `spec_format.py` and the schemas fixtures, which are outside this area | `src/easy_cheese/skills/mold/validate_spec.py:223-730` |
| review-mold.md | `mold` | `—` | low | deferred: the removal also edits `tests/python/test_gate_graph.py:359`, which is outside this area | `src/easy_cheese/skills/mold/gate_graph.py:242-249,269-274` |
| review-mold.md | `mold` | `—` | simplification | deferred: same scope as the validator rewrite above | `src/easy_cheese/skills/mold/validate_spec.py:594-632` |
| edge-mold-cook.md | `mold` | `schemas` | high | deferred: owned by schemas (`resolve_artifact`) and shared (`publication`) | `src/easy_cheese_schemas/artifacts.py:65-113` |
| edge-mold-briesearch.md | `mold` | `—` | high | deferred: the producer half needs `research_layout.py`, which belongs to briesearch | `tests/python/test_briesearch_ledger.py:124-126` |
| edge-briesearch-mold.md | `mold` | `—` | high | deferred: the document rules live in `src/easy_cheese_schemas`, which is outside this area | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-schemas-mold.md | `mold` | `—` | high | deferred: `_MINI_SPEC_REQUIRED_SECTIONS` and the strict fixtures belong to schemas | `src/easy_cheese_schemas/spec_format.py:33-35`; `src/easy_cheese/skills/mold/validate_spec.py:490-509` |
| edge-cheese-mold.md | `mold` | `—` | medium | deferred: the consumer half is a cheese test | `tests/python/test_cheese_routing_receipt.py:47-57` |
| edge-cook-mold.md | `mold` | `—` | blocker | deferred: the emission command belongs to cook and shared | `src/easy_cheese/shared/write_handoff_artifact.py:125-162` |
| edge-cook-mold.md | `mold` | `cook` | high | deferred: owned by cook and schemas | `src/easy_cheese_schemas/contracts.py:1034-1080` |
| edge-cure-mold.md | `mold` | `cure` | high | deferred: owned by cure | `skills/cure/references/domain-model-correction.md:5-31` |
| edge-cure-mold.md | `mold` | `—` | high | deferred: the consumer half is a cure test | `tests/python/test_glossary_consumers.py` |
| edge-cure-mold.md | `mold` | `—` | medium | deferred: Mold already states the optional rule; Cure must follow it | `skills/mold/references/curdle.md:330` |
| review-pasteurize.md | `pasteurize` | `—` | low | deferred | `tests/python/test_fanout_sizing_docs.py:232-233` asserts the literal `score < 250` and `score > 250`. The fix needs an edit outside this area. |
| edge-affinage-pasteurize.md | `pasteurize` | `—` | STE100 | deferred | `deferred: owned by affinage` |
| edge-cheese-pasteurize.md | `pasteurize` | `—` | high | deferred | The transition test needs the phase registry entry from row 19. |
| edge-cheese-pasteurize.md | `pasteurize` | `—` | STE100 | deferred | `deferred: owned by cheese` |
| edge-cook-pasteurize.md | `pasteurize` | `—` | medium | deferred | The seam test needs the phase registry entry from row 19. |
| edge-cook-pasteurize.md | `pasteurize` | `—` | STE100 | deferred | `deferred: owned by cook` |
| hub-shared.md | `pasteurize` | `—` | medium | deferred | `deferred: owned by shared`. The fix belongs to `json_command` in `src/easy_cheese/shared/`. |
| hub-schemas.md | `pasteurize` | `—` | high | deferred | `deferred: owned by cheese and schemas` |
| review-plate.md | `plate` | `the` | high | deferred: owned by the `gh` skill, which is outside the plate area paths | `skills/plate/SKILL.md:5-8,18-22` keeps exclusive creation. `skill://gh:5-12` still routes creation |
| edge-cheese-plate.md | `plate` | `mold` | high | deferred: owned by `mold` and `pasteurize` | Plate accepts `--hard` at `skills/plate/SKILL.md:52` |
| edge-cheese-plate.md | `plate` | `cheese` | medium | deferred: owned by `cheese` and `cure` | Plate documents no `--open-pr` input |
| edge-cook-plate.md | `plate` | `schemas` | high | deferred: owned by `schemas` | `skills/plate/references/topology.md:66-70` persists `plate_layout` |
| edge-cook-plate.md | `plate` | `schemas` | high | deferred: owned by `schemas`, which holds the canonical `PrPlan` | `src/easy_cheese/skills/plate/publication.py` reads the canonical model |
| edge-cure-plate.md | `plate` | `cure` | high | deferred: owned by `cure` | `skills/plate/SKILL.md:70-83` already requires every write first |
| edge-cure-plate.md | `plate` | `cure` | medium | deferred: owned by `cure` for the producer half | `tests/python/test_plate_contract.py:426-434` |
| edge-plate-cheese.md | `plate` | `cheese` | high | deferred: owned by `cheese` | `skills/plate/references/topology.md:27-31` names both triggers |
| edge-plate-hard-cheese.md | `plate` | `hard-cheese` | blocker | deferred: owned by `hard-cheese` (`freshness_check.py`) | Plate now sends `tracked_diff_digest` at `skills/plate/references/durable-writes.md:58-70` |
| edge-press-age.md | `press` | `age` | low | deferred: owned by age | `skills/age/SKILL.md:19-22` is outside this area. |
| review-schemas.md | `schemas` | `mold` | medium | deferred: owned by mold | `src/easy_cheese/skills/mold/validate_spec.py:617-632` |
| review-schemas.md | `schemas` | `mold` | simplification | deferred: owned by mold and shared | The rename touches the same generated files as the low finding above. |
| edge-build-schemas.md | `schemas` | `build` | high | deferred: owned by build | `justfile:2,15-31` |
| edge-build-schemas.md | `schemas` | `build` | medium | deferred: owned by build | `scripts/build_pyz.py:112-154` |
| edge-schemas-build.md | `schemas` | `build` | medium | deferred: owned by build | This row repeats the `_ContractVersion` finding above. |
| edge-schemas-build.md | `schemas` | `build` | medium | deferred: owned by build | This row repeats the writer reference finding above. |
| edge-schemas-mold.md | `schemas` | `mold` | high | deferred: owned by mold and shared | `src/easy_cheese/skills/mold/validate_spec.py:595-634`; `src/easy_cheese/shared/taste_test.py:662-689` |
| edge-schemas-mold.md | `schemas` | `mold` | medium | deferred: owned by mold | `tests/python/test_mold_taste_test.py:207-216` |
| edge-schemas-shared.md | `schemas` | `shared` | high | deferred: owned by shared | `src/easy_cheese/shared/taste_test.py:681-689` |
| hub-schemas.md | `schemas` | `age` | blocker | deferred: owned by age | `skills/age/SKILL.md:112-115` |
| hub-schemas.md | `schemas` | `cook` | blocker | deferred: owned by cook | `src/easy_cheese/skills/cook/workflow.py:1252-1277` |
| hub-schemas.md | `schemas` | `cure` | blocker | deferred: owned by cure | `src/easy_cheese/skills/cook/workflow.py:1192-1210` |
| hub-schemas.md | `schemas` | `age` | high | deferred: owned by age | `tests/python/test_age_review_lock.py:38-47` |
| hub-schemas.md | `schemas` | `cure` | medium | deferred: owned by cure | `tests/schemas/python/test_workflow_thread.py:766-919` |
| hub-schemas.md | `schemas` | `mold` | medium | deferred: owned by mold | This row repeats the mini-spec Grounding finding above. |
| review-shared.md | `shared` | `mold` | high | deferred: owned by mold | `src/easy_cheese/skills/mold/validate_spec.py:223-634` |
| review-shared.md | `shared` | `mold` | simplification | deferred: owned by mold | `src/easy_cheese/shared/taste_test.py:501-802` |
| review-shared.md | `shared` | `mold` | simplification | deferred: owned by mold | `src/easy_cheese/shared/taste_test.py:37-99` |
| edge-schemas-shared.md | `shared` | `mold` | high | deferred: owned by mold | `src/easy_cheese/shared/taste_test.py:681-689` |
| hub-shared.md | `shared` | `age` | blocker | deferred: owned by age | `src/easy_cheese/skills/age/review_lock.py:50-52` |
| hub-shared.md | `shared` | `age` | blocker | deferred: owned by age | `src/easy_cheese/skills/age/review_lock.py:63-67` |
| hub-shared.md | `shared` | `age` | blocker | deferred: owned by age | `skills/age/SKILL.md:111-115` |
| hub-shared.md | `shared` | `press` | blocker | deferred: owned by press | `src/easy_cheese/shared/press_route.py:23-27` |
| hub-shared.md | `shared` | `age` | high | deferred: owned by age | `src/easy_cheese/shared/read_handoff_slug.py:19-45` |
| hub-shared.md | `shared` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:157-166` |
| hub-shared.md | `shared` | `age` | high | deferred: owned by age | `skills/age/SKILL.md:112-116` |
| hub-shared.md | `shared` | `easy-cheese-setup` | high | deferred: owned by easy-cheese-setup | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| hub-shared.md | `shared` | `mold` | high | deferred: owned by mold | `src/easy_cheese/skills/mold/validate_spec.py:637-645` |
| hub-shared.md | `shared` | `press` | high | deferred: owned by press | `src/easy_cheese/shared/press_telemetry.py:58-78` |
| hub-shared.md | `shared` | `press` | high | deferred: owned by press | `src/easy_cheese/shared/press_route.py:10-16` |
| hub-shared.md | `shared` | `easy-cheese-setup` | medium | deferred: owned by easy-cheese-setup, press, build | `hub-shared.md` medium list |
| hub-shared.md | `shared` | `age` | low | deferred: owned by age | `src/easy_cheese/skills/age/commands.py:127-130` |
| edge-wheypoint-cook.md | `wheypoint` | `schemas` | high | deferred: owned by schemas | The seam test needs the typed field the schemas area owns. |

