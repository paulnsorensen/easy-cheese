# Skill review round r014 decisions

Release 0.14 ran a full skill review: one xhigh review per skill, one per skill-to-skill edge, hub reviews for `shared`, `schemas`, and `build`, then two cure rounds, published on PR #614. The per-finding ledgers were transient and are gone. This page keeps the conventions the round established and the disagreements it settled, so nobody re-litigates them. Contract details live in [handoff-preamble-grammar](../architecture/handoff-preamble-grammar.md).

## Cure-node scope rule

A per-skill cure node edits only its declared area paths. A finding whose root cause lives in another area is recorded as `deferred: owned by <area>` and left for that area's node, which reads the same edge or hub note. One exception: a repo-wide gate that blocks every later node (for example `just typecheck` at zero warnings) may receive a minimal, behavior-preserving patch outside the area, such as binding an unused result to `_`. That patch never changes the other area's contract or test intent.

## Settled disagreements

- **Two-pass cap owner is Cook.** Age restarts context each pass and has no pass-count input, so it cannot own the cap. The Cook phase table owns it (`skills/cook/references/auto-mode.md:59-81`); Cure does not count either. Rejected: Age ownership.
- **`--open-pr` is never synthesized.** Auto mode forwards the flag only when the user supplied it (`skills/cook/references/auto-mode.md:27-30`). Rejected: appending `--open-pr` on every auto chain.
- **SOLO level 3 is Multistructural.** The hard-cheese rubric uses the Biggs and Collis mapping: Multistructural is level 3 and Relational is level 4 (`skills/hard-cheese/references/judge-prompt.md:23-39`, `tests/python/test_hard_cheese.py:83-120`). The review claim that level 3 is "Relational" was wrong; the real defect was a sentence that credited level 3 with causal understanding, and that sentence was removed. Rejected: relabeling level 3.
- **Research slugs are four to six words.** `ResearchLayout` enforces `MIN_SLUG_WORDS = 4` and `MAX_SLUG_WORDS = 6` (`src/easy_cheese/skills/briesearch/research_layout.py:27-31`). Mold keeps its parent slugs inside that range. Rejected: letting a one-to-four-word Mold range also satisfy Briesearch.
- **Press keeps two route tables.** `skills/press/SKILL.md` maps router action to preamble; `references/gap-analysis.md` maps outcome to action. They serve different readers. Rejected: one merged table.
- **The closure checker uses `sys.stdlib_module_names` only.** `wheypoint/storage.py:108-114` imports `msvcrt` in a Windows-only branch; a rule that rejects modules unimportable on the current interpreter would flag correct code. Rejected: platform-conditional stdlib rejection.
- **Wheypoint documents two handoff formats.** `resolve` still reads handwritten legacy notes through `LegacyHandoffSlug`, so the legacy format stays documented in a labeled section while `checkpoint` refuses every legacy key. Rejected: deleting the legacy instructions.
- **`ResearchLayout` moved to its one consumer.** It left `shared/paths.py` for `briesearch/research_layout.py`. Rejected: keeping a single-consumer helper in shared.
- **Melt classifies formats at runtime.** `conflict_summary.py` asks `mergiraf languages`; a static prose list drifted (it excluded Bash, YAML, and JSON). Rejected: a static list.
- **Grounding is gated at the artifact.** `GroundingProbe`/`GroundingOutcome`/`GroundingRow` in `contracts.py` gate the Mold spec because Mold has no harness telemetry for a span-level check. `unavailable` is valid only with non-empty evidence. Rejected: a span-level check.
- **Durable writes land before Plate.** Cure's post-PR write-back ran after Plate published; it now runs first while keeping its name (`skills/cure/SKILL.md:106-107,230,246`).

## Pinned prose strings

- `tests/python/test_docs_emphasis_guard.py:93` asserts the verbatim phrase "slash commands are host renderings, not the control model" in every workflow skill. A review that calls it a false quotation is rejected; only the surrounding fallback text may change.
- `${CLAUDE_SKILL_DIR}` is forbidden in invocation paths (`skills/cheese/references/harness-portability.md:15-17,70-80`).
- ASD-STE100 governs explanatory prose in `SKILL.md` and `references/*.md`. Quoted bad examples, quoted rubric text, and literal transport strings such as a `prompt:` value are exempt.
- Skill frontmatter descriptions name concrete "Use when" user phrases, not only a capability summary.
- Reviewer and judge roles resolve at `powerful` power through the shared resolver (`skills/cheese/references/agent-resolution.md:83-113`); an authoritative review halts when fresh-context isolation is unavailable, with Cook's small-diff gate (`skills/cook/references/tdd-loop.md:68-78`) as the one inline exception.
- Age `location:` accepts only `class`, `module`, `cross-module`, or `contract` (`skills/age/references/dimensions.md:44-65`); a clean review emits `next: done`, not `next: cure`.
- History: `tests/python/test_wheypoint_skill_contract.py` once banned the literal `next: cut` even though `NextMove.CUT` is valid. That absence test no longer exists on this branch; the ban is retired.

## Release 0.14 policy decisions

- **Spec format:** v0.13 specs are read with a notice; mint and rewrite require the current format via `spec_format.py`. No `--legacy` or `--lenient` flag. `gate_applicability.disposition` keeps the `red-required` value for now.
- **Contract versions:** `schema_runtime.py` requires exact version equality (see [writer-view-boundary-simplification-001](../adr/writer-view-boundary-simplification-001.md)). Before any minor bump, add `@contract(version, min_readable_minor)`, keep minors additive, and use `compat.py`'s classify-only pattern. Rejected: restoring a payload-migration registry.
- **CI gap:** PR #560 merged with a failing `build-pyz` because `main` had no required status checks (#562). Bundle tests skipped instead of failing when tools were absent, and a path filter excluded bundle-test-only PRs. Required checks are the fix, not a stricter local gate.
- **Skill isolation is documented, not compiled.** Command surfaces are enforced; cross-skill import rejection, impure-wheel rejection, and archive-escape checks remain open (#477 waves A2-A4). `SKILL.md` examples call only `skills/<self>/scripts/<self>.pyz`.

_Source: r014 skill-review round notes and `.cheese/plans/release-0-14-decisions.md` (ingest hash 499c49c7b67d5eb6) · Updated: 2026-09-04 · Supersedes: the review-time "Relational level 3" claim and the `next: cut` ban_
