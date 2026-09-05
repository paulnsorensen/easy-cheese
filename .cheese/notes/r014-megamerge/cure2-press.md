# Cure round 2 — press

This node applies the Press findings from the skill review, the edge reviews, and the hub reviews.

The area owns five files. Three shared modules hold the root cause of four findings. Those modules are outside every listed area path. This note records them as deferred.

## Findings

| # | Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-cheese-press.md, edge-cook-press.md, hub-shared.md | blocker | Press cannot publish or parse its documented handoff | applied | d6dba93d | `skills/press/SKILL.md:145-183` writes only the canonical preamble. `tests/python/test_press_prose_contract.py:33` parses it with `parse_handoff_slug`. |
| 2 | review-press.md, edge-cook-press.md, hub-shared.md | blocker | Press has no contract for the flags that Cook sends | applied | 8c278b0a, b45b738d | `skills/press/SKILL.md:20-36` defines `--auto`, `--hard`, and `--open-pr`. `skills/press/SKILL.md:130-142` defines auto mode. `tests/python/test_press_prose_contract.py:81,90` |
| 3 | review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-cheese-press.md | high | Press and Cheese assign different meanings to `artifact:` | applied | d6dba93d | `skills/press/SKILL.md:155,163` names the consumed Cook report. `tests/python/test_press_prose_contract.py:73` |
| 4 | review-press.md, hub-shared.md | high | The boundary audit accepts non-test metadata changes | applied in prose; code deferred: owned by shared | 563705ab | `skills/press/references/telemetry.md:74` requires a manual review of each `metadata` path. The classifier at `src/easy_cheese/shared/fanout/press_telemetry.py:61-67,260-266` is outside every area path. |
| 5 | review-press.md, hub-shared.md | high | Out-of-contract behavior has no route action | applied in prose; enum deferred: owned by shared | 26dd5a6c, e3462d1a | `skills/press/SKILL.md:113` maps a recorded concern to `ok-with-concerns`. `skills/press/references/gap-analysis.md:18` agrees. The `Outcome` enum at `src/easy_cheese/shared/fanout/press_route.py:10-16` is outside every area path. |
| 6 | edge-press-age.md | high | The Age reader loses the Press orientation | applied | d6dba93d | `skills/press/SKILL.md:145-161` puts `action:` and `telemetry:` in the report body. |
| 7 | edge-press-age.md | high | Age cannot read the Press findings that its contract requires | applied | d6dba93d | `skills/press/SKILL.md:171` defines `## Review follow-ups`. `tests/python/test_press_prose_contract.py:108` |
| 8 | edge-press-cook.md, edge-cook-press.md | high | The baseline block cannot cross the handoff | applied | 26dd5a6c | `skills/press/SKILL.md:100-104` reads one baseline artifact path. Cook now writes one path at `skills/cook/references/quality-gates.md:44-74`. `tests/python/test_press_prose_contract.py:117` |
| 9 | edge-press-cook.md | high | Press cannot preserve Cook control state across a correction | applied | 8c278b0a, 26dd5a6c | `skills/press/SKILL.md:34` preserves `durable_flags:`. `skills/press/SKILL.md:190` forwards only supplied flags. |
| 10 | edge-cook-press.md | high | The typed `CurdResult` payload stops at its declaration | applied | d6dba93d | `skills/press/SKILL.md:155` requires `artifact: .cheese/cook/<slug>.md`. Press now names the consumed result. |
| 11 | review-press.md, edge-press-cheese.md, edge-press-cook.md, edge-press-age.md, edge-cheese-press.md | high | Tests do not protect the seam | applied | 3b83ceb9 | `tests/python/test_press_prose_contract.py` adds 13 tests. |
| 12 | review-press.md, hub-shared.md | medium | The command summary omits the Age dispatch | applied | bf3086e8 | `src/easy_cheese/skills/press/commands.py:13`; `skills/press/references/commands.md:7` |
| 13 | review-press.md | medium | The third-RED text gives two different dispositions | applied | e3462d1a | `skills/press/references/gap-analysis.md:75-77`; `skills/press/SKILL.md:179` |
| 14 | edge-cook-press.md | medium | Press drops Cook's `durable_flags` | applied | 8c278b0a, d6dba93d | `skills/press/SKILL.md:34,152` |
| 15 | edge-cook-press.md, review-press.md | medium, low | Press names the retired no-chain owner | applied | b45b738d, ddec5288 | `skills/press/SKILL.md:142` tests the directive, not the source name. |
| 16 | review-press.md, edge-press-cheese.md, edge-cook-press.md | low | Press uses an unapproved metaphor | applied | 26dd5a6c | `skills/press/SKILL.md:202` |
| 17 | review-press.md, edge-press-cook.md, edge-cook-press.md | low | Gap analysis uses undefined abbreviations | applied | e3462d1a | `skills/press/references/gap-analysis.md:55` |
| 18 | edge-press-age.md | low | The Age usage text omits `--hard` | deferred: owned by age | — | `skills/age/SKILL.md:19-22` is outside this area. |
| 19 | edge-press-cheese.md, edge-cheese-press.md | low | Cheese prose exceeds the STE100 sentence limits | deferred: owned by cheese | — | `skills/cheese/SKILL.md:42,136` and four Cheese reference files. |
| 20 | edge-cook-press.md | low | Cook prose exceeds the STE100 sentence limits | deferred: owned by cook | — | `skills/cook/SKILL.md:63,241-250` |
| 21 | edge-press-cook.md, hub-shared.md | high | Press lacks the baseline classifier in its bundle | rejected | — | The manifest targets live in shared code. `review-press.md` simplifications keep the static Press manifest. Adding a fourth entry needs a shared owner. |

## Simplifications

| Simplification | State | Evidence |
| --- | --- | --- |
| Keep one route truth table in `references/gap-analysis.md` | rejected | The two tables serve two readers. `SKILL.md` maps the router action to the preamble. `gap-analysis.md` maps the outcome to the router action. |
| Make `SKILL.md` link to the gap-analysis table | applied | `skills/press/SKILL.md:104` |
| Use the canonical handoff writer and parser | applied | `skills/press/SKILL.md:147` |
| Keep Press-only fields in the report body | applied | `skills/press/SKILL.md:165-171` |
| Compare changes with approved test paths | applied in prose | `skills/press/references/telemetry.md:74` |
| Remove old readiness labels after the route supports concerns | applied | `skills/press/SKILL.md:106-113` |
| Keep the static command manifest | applied | `src/easy_cheese/skills/press/commands.py:9-20` is unchanged in shape. |
| Do not add a Press-local handoff parser | applied | Press adds no parser. |

## Broken edges

| Edge | Press side at this commit |
| --- | --- |
| press -> cook | Press writes no `next: press`. The corrective `Continue` stays inside the Press phase. |
| press -> age | Press writes the canonical preamble and a `## Review follow-ups` body section. |
| press -> cheese | Press emits no `action:` or `telemetry:` preamble key. |
| press -> shared `press-route` | Prose maps a recorded concern to `ok-with-concerns`. The enum change is deferred. |
| press -> shared `press-telemetry` | Prose rejects non-test metadata paths. The classifier change is deferred. |
| ultracook -> press | Press tests the no-chain directive, not the retired source name. |

## Disagreements

- `edge-press-cheese.md` and `edge-cheese-press.md` ask for a new typed local action in the canonical handoff model. `edge-cook-press.md` asks for the same field. The typed schema contract at `src/easy_cheese/shared/handoff.py:87` accepts three optional keys. `cure2-cheese.md` row 41 records that a new preamble key repeats the `action:` defect. This node keeps the typed schema contract. Press writes no durable handoff for a corrective `Continue`. The corrective loop stays inside the Press phase, which the review calls the correct ownership.

## Gate

`bash .milknado/reconcile-gate.sh` exits 0. The Press prose contract suite reports 13 passes.

## Follow-ups

- Reject non-test `metadata` paths in `src/easy_cheese/shared/fanout/press_telemetry.py`. No cure node owns this file.
- Add an out-of-contract concern outcome to `src/easy_cheese/shared/fanout/press_route.py`. No cure node owns this file.
- Expose the shared baseline classifier through the Press bundle after a shared owner accepts it.
- Add `[--hard]` to both Age usage forms in `skills/age/SKILL.md`.
- Update the dependency map to name Cook as the no-chain owner.
- Two pre-existing failures remain outside this area: `tests/python/test_docs_emphasis_guard.py::test_harness_portability_reference_is_linked_from_workflow_docs` and `tests/python/test_ultracook_skills.py::TestCureCanonicalPathway::test_cure_uses_canonical_contracts`. Both name `skills/cure/SKILL.md`.
- `tests/python/test_transport_audit.py` reports unaccounted question sites in `skills/briesearch/references/evals.md` and `skills/hard-cheese/references/composition.md`.
