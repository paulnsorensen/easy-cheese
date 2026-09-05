# Cure round 2 — mold

This note records every finding from the mold review notes, the mold edge notes,
and the hub notes. It gives the state, the commit, and the evidence.
`skills/mold/references/validate-cycle.md` and
`skills/mold/references/handoff-menus.md` are not in this node's area path list.
The node defers each fix that belongs to those two files.

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-mold.md | blocker | The wiki probe selects the first global wiki corpus | applied | b28291c8 | `skills/mold/references/grounding.md:22-27,35-37` |
| review-mold.md | blocker | The probe returns silently when no wiki exists | applied | b28291c8 | `skills/mold/references/grounding.md:24-26,38` |
| review-mold.md | blocker | `no prior evidence` satisfies `grounding-recorded` | applied | b28291c8 | `skills/mold/references/grounding.md:67` |
| review-mold.md | blocker | Curdle interpolates an unvalidated user slug | applied | 4bb79e1f | `skills/mold/references/curdle.md:20-22` |
| review-mold.md | blocker | `migrate` exposes caller-selected phases | applied | 204c5995 | `src/easy_cheese/skills/mold/contract_handlers.py:131-132`; `tests/python/test_mold_contract_handlers.py:41-48` |
| review-mold.md | blocker | The normal flow never publishes the plan | applied | bbed2879 | `skills/mold/SKILL.md:24,137`; `skills/mold/references/curdle.md:391-404` |
| review-mold.md | blocker | SKILL.md permits only `tracer` and `contract-matrix` | applied | 82fff885 | `skills/mold/SKILL.md:98-109` |
| review-mold.md | blocker | Templates omit the `agent_resolution` block | applied in part | 542ff418, 86f355d4 | `skills/mold/references/curdle.md:47`; `skills/mold/references/mini-spec-mode.md:26` |
| review-mold.md | blocker | `MoldSpecFrontmatter` cannot model `agent_resolution` | deferred: owned by schemas | — | `src/easy_cheese_schemas/contracts.py:2400-2417` |
| review-mold.md | high | Strict validation accepts an unknown source marker | rejected: not reproducible at HEAD | — | `is_hardened_provenance` and `is_new_mold_spec` both reject `mold-handshake # comment`; probe run in this node |
| review-mold.md | high | The publish test omits route and schema assertions | applied | 204c5995 | `tests/python/test_mold_contract_publish.py:154-188` |
| review-mold.md | high | `validate_spec.py` repeats parsing and typed reconstruction | deferred: the single-constructor rewrite needs `spec_format.py` and the schemas fixtures, which are outside this area | — | `src/easy_cheese/skills/mold/validate_spec.py:223-730` |
| review-mold.md | medium | Each probe repeats `list_corpora` | applied | b28291c8 | `skills/mold/references/grounding.md:39` |
| review-mold.md | low | `gate-graph --state` reads and discards the state | deferred: the removal also edits `tests/python/test_gate_graph.py:359`, which is outside this area | — | `src/easy_cheese/skills/mold/gate_graph.py:242-249,269-274` |
| review-mold.md | simplification | Extract one JSON object helper | applied | aae02e86 | `src/easy_cheese/skills/mold/contract_handlers.py:34-53` |
| review-mold.md | simplification | Remove hard-coded gate counts | applied | 70a6103e | `src/easy_cheese/skills/mold/gate_graph.py:75-78`; `skills/mold/references/handshake.md:40` |
| review-mold.md | simplification | Generate the handshake checklist from `GATE_MODEL` | rejected: the checklist is the prose authority and the test already locks the two sets together; generation would invert that direction | — | `src/easy_cheese/skills/mold/gate_graph.py:14-18` |
| review-mold.md | simplification | Make the typed document the only semantic parse result | deferred: same scope as the validator rewrite above | — | `src/easy_cheese/skills/mold/validate_spec.py:594-632` |
| review-mold.md | STE100 | Ten prose files carry violations | applied | 1d2736ba | `skills/mold/SKILL.md:12-13,19,23`; `skills/mold/references/*.md` |
| edge-mold-hard-cheese.md | blocker | Mold drops `--hard` on several Cook routes | applied | d042580d | `skills/mold/SKILL.md:47,127-131,137`; `skills/mold/references/mini-spec-mode.md:9`; `skills/mold/references/curdle.md:413-414` |
| edge-mold-hard-cheese.md | high | The propagation test checks token presence only | applied | d042580d | `tests/python/test_mold_hard_propagation.py:22-59` |
| edge-mold-cook.md | blocker | The normal handoff bypasses canonical acceptance | applied | bbed2879 | `skills/mold/references/curdle.md:391-404` |
| edge-mold-cook.md | high | Cook can fetch HTTPS from a tampered pointer | deferred: owned by schemas (`resolve_artifact`) and shared (`publication`) | — | `src/easy_cheese_schemas/artifacts.py:65-113` |
| edge-mold-cook.md | high | Cook tests use stale resolver errors | deferred: owned by cook | — | `tests/python/test_cook_contract_accept.py:136-168` |
| edge-mold-briesearch.md | high | The Mold sidechain request has no defined packet | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:78-87` |
| edge-mold-briesearch.md | high | A Mold sidechain can become a top-level run | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:82` |
| edge-mold-briesearch.md | high | Mold does not map an inconclusive result | applied | 415f46e5 | `skills/mold/references/mini-spec-mode.md:86` |
| edge-mold-briesearch.md | high | The slug and artifact path contracts conflict | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:84-85` |
| edge-mold-briesearch.md | high | No test crosses the seam | deferred: the producer half needs `research_layout.py`, which belongs to briesearch | — | `tests/python/test_briesearch_ledger.py:124-126` |
| edge-mold-briesearch.md | medium | Briesearch defines two sidechain outputs | deferred: owned by briesearch | — | `skills/briesearch/references/synthesis.md:80-110` |
| edge-briesearch-mold.md | high | The artifact path representations conflict | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:85` |
| edge-briesearch-mold.md | high | The slug limits conflict | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:84` |
| edge-briesearch-mold.md | high | Strict validation ignores tier-2 provenance | deferred: the document rules live in `src/easy_cheese_schemas`, which is outside this area | — | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-briesearch-mold.md | medium | The artifact omission rules use different predicates | applied on the Mold side | 415f46e5 | `skills/mold/references/mini-spec-mode.md:87` |
| edge-schemas-mold.md | high | The strict mini-spec path invents Grounding rows | applied in part | 86f355d4 | `skills/mold/references/mini-spec-mode.md:38-45`; `tests/python/test_mold_mini_spec_template.py:57-104` |
| edge-schemas-mold.md | high | Strict validation supplies frontmatter defaults | deferred: `_MINI_SPEC_REQUIRED_SECTIONS` and the strict fixtures belong to schemas | — | `src/easy_cheese_schemas/spec_format.py:33-35`; `src/easy_cheese/skills/mold/validate_spec.py:490-509` |
| edge-schemas-mold.md | medium | No test runs the documented mini-spec under `--strict` | applied | 86f355d4 | `tests/python/test_mold_mini_spec_template.py:76-104` |
| edge-cheese-mold.md | high | Cheese names the wrong output path | deferred: owned by cheese | — | `skills/cheese/references/escalation.md:10-16` |
| edge-cheese-mold.md | high | The specification pointer has incompatible carriers | applied on the Mold side | bbed2879 | `skills/mold/SKILL.md:24,137` |
| edge-cheese-mold.md | medium | No test exercises the edge from both sides | deferred: the consumer half is a cheese test | — | `tests/python/test_cheese_routing_receipt.py:47-57` |
| edge-cook-mold.md | blocker | The planner payload crosses no validated boundary | deferred: the emission command belongs to cook and shared | — | `src/easy_cheese/shared/write_handoff_artifact.py:125-162` |
| edge-cook-mold.md | high | Cook and Mold assign different planner owners | deferred: owned by cook | — | `skills/cook/references/fan-pathway.md:62-67` |
| edge-cook-mold.md | high | Failure semantics select no valid request kind | deferred: owned by cook and schemas | — | `src/easy_cheese_schemas/contracts.py:1034-1080` |
| edge-cook-mold.md | high | The status rules can stop the Mold route | deferred: owned by cook | — | `skills/cook/SKILL.md:219-230` |
| edge-cure-mold.md | high | Cure requires an untransported `PlannerResult` | deferred: owned by cure | — | `skills/cure/SKILL.md:49-53` |
| edge-cure-mold.md | high | Cure cannot read every domain model backend | deferred: owned by cure | — | `skills/cure/references/domain-model-correction.md:5-31` |
| edge-cure-mold.md | high | No test proves canonical-term preservation | deferred: the consumer half is a cure test | — | `tests/python/test_glossary_consumers.py` |
| edge-cure-mold.md | medium | The `Avoid` field has two cardinality rules | deferred: Mold already states the optional rule; Cure must follow it | — | `skills/mold/references/curdle.md:330` |
| hub-shared.md | blocker | The normal Mold flow bypasses shared publication | applied | bbed2879 | `skills/mold/references/curdle.md:391-402` |
| hub-shared.md | blocker | Mold exposes caller-selected publication phases | applied | 204c5995 | `src/easy_cheese/skills/mold/contract_handlers.py:131-132` |
| hub-shared.md | high | Mold has two source policies for one document | rejected: not reproducible at HEAD, as above | — | `src/easy_cheese_schemas/spec_format.py:95-102`; `src/easy_cheese/shared/taste_test.py:549-554` |
| hub-shared.md | high | Publication tests do not protect route identity | applied | 204c5995 | `tests/python/test_mold_contract_publish.py:172-188` |
| hub-schemas.md | medium | Mold records probes that did not occur | applied in part | 86f355d4 | `skills/mold/references/mini-spec-mode.md:38-45` |
| hub-build.md | — | No row names `mold` | not applicable | — | `.cheese/notes/r014-megamerge/hub-build.md` |

## Verification

- `pytest tests/python` reports 28 failures before this node and 28 after it.
- The six mold-owned failures that the STE100 rewrite introduced are repaired in
  the same commit series. No new failure remains.
- The remaining 28 failures belong to other areas or wait for the bundle
  rebuild. The list is under `Follow-ups`.

## Follow-ups

- Add `agent_resolution` to `MoldSpecFrontmatter` and require it in strict
  validation (schemas).
- Require Grounding and the full frontmatter for a strict `agent-mini-spec`
  document. Then remove both synthetic Grounding paths (schemas and shared).
- Restrict `resolve_artifact` to local schemes for publication acceptance
  (schemas and shared).
- Remove `gate-graph --state` together with its test.
- Append `--hard` in `skills/mold/references/handoff-menus.md`. That file is
  outside this node's area path list.
- Add `invocation: sidechain` to `skills/mold/references/validate-cycle.md`.
  That file is outside this node's area path list.
- Add the Mold-to-Briesearch and Briesearch-to-Mold seam tests.
- Repair `test_docs_emphasis_guard` (cure), `test_shared_migrate` (shared),
  `test_transport_audit` (cure and briesearch), `test_ultracook_skills` (cure),
  `test_cook_contract_accept` (cook), and `test_package_report_baseline_docs`
  (cook).
- Rebuild every bundle. `test_pyz_bundle` reports the stale archives.
