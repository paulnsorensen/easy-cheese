# Cure round 2: briesearch

## Scope

This node applies the `briesearch` findings from the skill review, the four
edge reviews, and the three hub reviews. It edits only the `briesearch` area
paths. It records every other finding as `deferred: owned by <area>`.

## Findings

| Source note | Severity | State | Commit | Evidence |
| --- | --- | --- | --- | --- |
| review-briesearch.md | blocker | applied: `ground-check` rejects user information, a query value, and a fragment in a cited URL before the digest match | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:352-378`; `tests/python/test_briesearch_ledger.py:264-283` |
| review-briesearch.md | blocker | applied: `budget-check` reports `BUDGET_UNDECLARED` for a used call kind with no declared limit | 71cf187 | `src/easy_cheese/skills/briesearch/budget.py:170-192`; `tests/python/test_briesearch_budget.py:355-374` |
| review-briesearch.md | blocker | applied: local citations resolve under an allowed root, and both anchor forms are range-checked | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:241-305`; `tests/python/test_briesearch_ledger.py:286-330` |
| review-briesearch.md | blocker | applied: the ledger retains `slug`, `title`, and `fetched`; `MANIFEST` binds the slug and the stored body; `FRESHNESS` binds the row date | d17975f, c2f8a8e | `src/easy_cheese/skills/briesearch/ledger.py:117-123,142`; `ground_check.py:568-612`; `tests/python/test_briesearch_ledger.py:369-425` |
| review-briesearch.md, hub-shared.md | high | applied: `research_layout` enforces the four-to-six-word slug | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:27-31,52-65`; `tests/python/test_briesearch_research_layout.py:26-58` |
| review-briesearch.md | high | applied: the table row parser is escape-aware | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:126-152`; `tests/python/test_briesearch_ledger.py:339-349` |
| review-briesearch.md | medium | applied: a cached record no longer spends the call budget | 71cf187 | `src/easy_cheese/skills/briesearch/budget.py:110-113,177-192`; `tests/python/test_briesearch_budget.py:383-397` |
| review-briesearch.md | medium | applied: confidence labels compare exactly, so a case variant fails | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:537-546`; `tests/python/test_briesearch_ledger.py:352-362` |
| review-briesearch.md | low | applied: line counts are cached for each resolved path in one report check | c2f8a8e | `src/easy_cheese/skills/briesearch/ground_check.py:200-208` |
| review-briesearch.md | low | applied: seven prose files now follow ASD-STE100 | 3140259 | `skills/briesearch/SKILL.md:19`; `skills/briesearch/references/synthesis.md:3,24` |
| review-briesearch.md | simplification | applied: `Call.canonical` is deleted; `_url_fields` returns two URL fields | d17975f | `src/easy_cheese/skills/briesearch/ledger.py:233-265` |
| review-briesearch.md | simplification | applied: `commands.py` keeps the shared `derive_command` helper without change | none | `src/easy_cheese/skills/briesearch/commands.py:42-56` |
| edge-briesearch-mold.md, edge-mold-briesearch.md | high | applied: `ResearchLayout` returns a corpus-relative `artifact` field | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:46,88`; `tests/python/test_briesearch_research_layout.py:61-67` |
| edge-briesearch-mold.md, edge-mold-briesearch.md | high | applied on this side: the slug rule is now enforced at four to six words. See Disagreements | 6e99517 | `src/easy_cheese/skills/briesearch/research_layout.py:52-65` |
| edge-briesearch-mold.md | high | deferred: owned by mold. Strict Mold validation must check tier-2 provenance | none | `src/easy_cheese/skills/mold/validate_spec.py:637-735` |
| edge-briesearch-mold.md | high | applied in part: `evals.md` adds a route-authorization trace. The Mold-side consumer test is deferred: owned by mold | 3140259 | `skills/briesearch/references/evals.md:44-46` |
| edge-briesearch-mold.md | medium | deferred: owned by mold. The artifact omission predicates must agree | none | `skills/mold/references/mini-spec-mode.md:62` |
| edge-briesearch-cook.md | high | applied on this side: `evals.md` adds trace check 10, which requires a run to stop after it recommends a route. The Cook entry test is deferred: owned by cook | 3140259 | `skills/briesearch/references/evals.md:44` |
| edge-cheese-briesearch.md | high | deferred: owned by cheese. Cheese must allocate the parent slug before the tier-2 call | none | `skills/cheese/references/escalation.md:10-22` |
| edge-cheese-briesearch.md | high | deferred: owned by cheese. Tier-3 question ownership is a Cheese rule | none | `skills/cheese/references/escalation.md:19-26` |
| edge-cheese-briesearch.md | medium | deferred: owned by cheese. The internal request and result packet is a Cheese contract | none | `skills/cheese/SKILL.md:44-48` |
| edge-cheese-briesearch.md, edge-mold-briesearch.md | medium/high | applied in part: `evals.md` adds trace check 11 and a failure mode for a sidechain run that records `top-level`. The producing side is deferred: owned by cheese and mold | 3140259 | `skills/briesearch/references/evals.md:45-46,54` |
| edge-mold-briesearch.md | high | deferred: owned by mold. Mold must map `don't know` to an open hypothesis | none | `skills/mold/references/validate-cycle.md:18-24` |
| edge-mold-briesearch.md | medium | deferred: owned by mold and cheese. One sidechain result shape needs both callers | none | `skills/briesearch/SKILL.md:13` |
| hub-schemas.md | n/a | rejected: the note lists no `briesearch` row | none | `.cheese/notes/r014-megamerge/hub-schemas.md` |
| hub-build.md | n/a | rejected: the note lists no `briesearch` row | none | `.cheese/notes/r014-megamerge/hub-build.md` |

## Disagreements

- Research slug size. `review-briesearch.md` and `hub-shared.md` require four to
  six words. `edge-briesearch-mold.md` and `edge-mold-briesearch.md` want the
  Mold parent slug, which permits one to four words. The typed contract is the
  `ResearchLayout` result, and both area-owning notes require the longer rule,
  so `research_layout` now enforces four to six words. A four-word parent slug
  satisfies both prose contracts. Mold owns the change to its own slug rule.

## Cross-area edit

`tests/python/test_artifact_path.py` belongs to the `shared` area. The slug rule
made three research-layout cases in that file fail. The edit is limited to the
fixture slugs and the new expected `artifact` key. No shared source file
changed. `cure2-shared.md` deferred this finding to `briesearch`.

## Commit discipline

Five commits landed. Each one carries a Conventional Commits subject and names
its source note. The `ground-check` commit covers four findings in one module,
because the checks share the row context and the report walk.

## Gate

`reconcile-gate.sh` passes. `ruff check`, `just typecheck`,
`validate_skills.py`, and 101 area tests are green. `just lint-py-dead-code`
also passes.

## Follow-ups

- Cheese must pass a slug and `invocation: sidechain` for a tier-2 research
  call, and must own the tier-3 user question.
- Mold must validate tier-2 provenance, map `don't know` to an open hypothesis,
  and record the corpus-relative `artifact` path.
- Cook must add an entry test that requires an explicit implementation request.
