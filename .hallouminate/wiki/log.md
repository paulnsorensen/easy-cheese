# Ingest Log

## Log

- 2026-07-22 · cook+age:baseline-repair-pathway · merged · adr/baseline-repair-pathway-004.md · dispatch-brief-level override (chain forward with `--auto --open-pr` via prompt instruction, not a SKILL.md edit) added to the Decision bullet.
- 2026-07-22 · cook+age:baseline-repair-pathway · merged · adr/plate-publication-boundary-001.md · new pre-check ahead of New-PR topology policy: a `worktree-agent-repair-*` branch resolves through the repair pathway's mechanical file-overlap check first.


- 2026-07-24 · c46a53ce6c7ef323 · merged · architecture/ultracook-agent-topology.md · ownership moved to /cook fan pathway in PR #316; /ultracook retired in PR #317; topology invariants retained, footnotes recited, Supersedes recorded.
- 2026-07-24 · c46a53ce6c7ef323 · new-page · architecture/age-fanout-router.md · deterministic age router: N∈{1,4,10} + hard overrides, purity/sibling-CLI gotcha, bundle deployment, open effort:low decision.
- 2026-07-24 · c46a53ce6c7ef323 · merged · fanout-engine-entities.md · added The Curd block entity (locked decomposition vocabulary, single producer contract, legacy prompt scope note) + shared disjoint_errors extraction; /ultracook framing corrected to /cook.



- 2026-07-27 · 68af0b0391e6bbd2 · new-page · skill-size-budget.md · Anthropic's published skill limits (hard vs soft), the three load levels, measured anthropics/skills sizes (median 129 lines), this repo's 16-skill audit (6 over the 5k-token budget, 20 nested refs, 6 orphans), and arXiv 2603.29919 F3 on splitting-without-routing.
- 2026-07-27 · 68af0b0391e6bbd2 · new-page · adr/skill-size-ratchet-001.md · gate on estimated tokens not lines; all 16 skills pass 500 lines while 6 fail the 5k-token budget.
- 2026-07-27 · 68af0b0391e6bbd2 · new-page · adr/skill-size-ratchet-002.md · no tokenizer dependency; bytes//4 in stdlib, tiktoken is the wrong tokenizer and count_tokens needs a CI secret.
- 2026-07-27 · 68af0b0391e6bbd2 · new-page · adr/skill-size-ratchet-003.md · grandfathered ratchet over flat cap, mirroring skill-overlap-ratchet-004's reviewed-baseline reasoning.
- 2026-07-27 · 68af0b0391e6bbd2 · merged · architecture.md · Progressive disclosure section gained the three named load levels and their token costs, distinguished from the four-directory file layout; no-auto-discovery and split-without-routing noted.
- 2026-07-27 · 68af0b0391e6bbd2 · conflict-flagged · skill-size-budget.md · skills/cheese/references/skill-authoring.md:32-54 sets an 80-150 line budget that 12 of 16 skills exceed, against Anthropic's 500 lines / 5k tokens — kept both, flagged for human resolution.
- 2026-07-27 · 68af0b0391e6bbd2 · conflict-flagged · skill-size-budget.md · skills/cheese/references/skill-authoring.md:115-117 says references are "one level deep" then "two levels is the maximum depth" — self-contradictory; Anthropic states one level. Flagged for human resolution.



- 2026-07-27 · 68af0b0391e6bbd2 · merged · adr/skill-size-ratchet-001.md · ADR-001a amends the target from Anthropic's 5,000 to this repo's 3,600 tokens (150 lines x measured 95 B/line); provenance of the superseded 80-150 line figure recorded (PR #138, adapted from Pocock's <100-line cap, never measured here, no readers).
- 2026-07-27 · 68af0b0391e6bbd2 · merged · skill-size-budget.md · conflict #1 RESOLVED — repo budget restated in tokens at 3,600, tighter than the platform ceiling; measurement table corrected to body-only figures the gate actually reads (8 of 16 over budget, not 6); Supersedes: the "80-150 lines" budget in skills/cheese/references/skill-authoring.md:32-54 · 2026-07-27.



- 2026-07-28 · 68af0b0391e6bbd2 · merged · adr/cheese-kernel-shared-refs-001.md · ADR-001a records skill-authoring.md leaving skills/cheese/references/ for .agents/skills/skill-authoring/SKILL.md; it entered cheese as an R100 zero-diff passenger of the shared/ batch move (f458a439, PR #242), had 3 inbound links against the kernel's 10-26, and all 3 cited only the Iron Law template that both discipline files already carry inline. Narrows ADR-001's membership by one; does not reverse it. Supersedes: skill-authoring.md's membership in the cheese kernel · 2026-07-28.
- 2026-07-28 · 68af0b0391e6bbd2 · merged · skill-size-budget.md, skill-parity-analysis.md · retargeted every skill-authoring.md path to .agents/skills/skill-authoring/SKILL.md; the remaining nested-reference conflict now cites the section by name rather than a line range, since line numbers shifted with the added frontmatter.



- 2026-07-28 · 68af0b0391e6bbd2 · merged · adr/cheese-kernel-shared-refs-001.md · the .agents/skills/* allowlist trap in ADR-001a's Consequences bit for real: a prior agent renamed .agents/skills/pythonic to python-authoring without adding a `!` line, so the renamed file was gitignored and existed only on local disk while git carried an unstaged deletion of the old path. Recovered (content was byte-identical to HEAD), renamed properly to authoring-python with the frontmatter `name` corrected to match. Every tracked .agents skill dir needs its own `!` line or it is silently untracked.



- 2026-07-28 · 68af0b0391e6bbd2 · merged · adr/skill-size-ratchet-003.md · ADR-003a brings .agents/skills/ into validate_skills.py (narrow dot-filter allowance, frontmatter + size ratchet in scope, reference-topology checks out of scope); validator now reports 18 files; markdownlint globs widened to .agents/**/*.md in justfile and CI. Closes both accepted-cost gaps from cheese-kernel-shared-refs ADR-001a. Nested allowlist 20 to 19 as real cleanup from the skill-authoring unlink.
- 2026-07-28 · 68af0b0391e6bbd2 · merged · log.md · final .agents naming settled: python-authoring (H1 "Authoring Python") and skill-authoring, both with name matching their directory, both now validated and linted.



- 2026-08-02 · wiki-harvest · curated · architecture.md, workflow-invariants.md · corrected stale present-tense framing that listed `/ultracook` as an active pipeline skill. `/ultracook` was retired to a redirect stub (PR #317) with fan-path ownership moved to `/cook` (PR #316): the pipeline-table row and auto-chain prose now attribute the fan pathway and the `cook → press → age → cure → age → cure → age` `--auto` chain to `/cook`, and the stale `skills/cook/SKILL.md:132` citation was corrected to `:134`. Aligns the two foundational pages with architecture/ultracook-agent-topology.md, fanout-engine-entities.md, and this log.
- 2026-08-06 · ea414a8dc98ddb4e · new-page · architecture/workflow-contract-map.md · recovered planner/curdler ownership, distinguished current CurdBlock behavior from target CurdPlan contracts, recorded Cook/Cure and Age/Pasteurize seams as design work, and ordered schema self-consumption before Milknado import.
- 2026-08-08 · wiki-curator:outer-tdd-gates · curated · adr/outer-tdd-gates-001.md, adr/outer-tdd-gates-002.md, adr/outer-tdd-gates-003.md, adr/outer-tdd-gates-004.md, adr/outer-tdd-gates-005.md, domain-model.md · recorded the accepted outer-TDD boundary decisions alongside PR #396: phase-neutral GateReceipt evidence, Cut ownership, Press corrective continuations, Mold Test Contracts, and explicit applicability.

- 2026-08-08 · wiki-curator:wheypoint-continuity-kernel · curated · adr/wheypoint-continuity-kernel-001.md, adr/wheypoint-continuity-kernel-002.md, adr/wheypoint-continuity-kernel-003.md, adr/wheypoint-provenance-schema-001.md, domain-model.md · recovered the continuity-kernel ADR set omitted from implementation PR #384; recorded WheypointRecord as continuity authority, immutable delta/revision semantics, projection-only Markdown, and the dedicated runtime boundary.
- 2026-08-09 · wiki-harvest · curated · domain-model.md · resolved a committed 3-way merge conflict landed by PR #398: `<<<<<<< ours`/`||||||| original`/`=======`/`>>>>>>> theirs` markers were live in the tree around the `## Outside-in RED gating` section. Took the `ours` side (the section PR #396 added); the other two sides carried only a duplicate `_Code_: NEW ENTITY` line. `validate_wiki.py` is structural-only, so it passed the gate green — see tooling.md.
- 2026-08-09 · wiki-harvest · curated · architecture.md, workflow-invariants.md · added `/cut` to the pipeline. PR #396 inserted the outside-in RED phase between mold and cook (`culture → mold → cut → cook → press → age → cure → plate`), and both foundational pages still printed the seven-phase order. Recorded the non-obvious parts: Cut cannot be skipped by starting at `/cook` (cook's GateReceipt preflight invokes it synchronously), and `--auto`'s chain is now receipt-shaped — a closed `not-applicable` receipt skips Press because Press has no contract to attack, not for speed. Noted that culture/age/cure/affinage footers still print the pre-Cut string.
- 2026-08-09 · wiki-harvest · curated · tooling.md, architecture.md · corrected the `.pyz` story. The bundle roster was six skills; it is thirteen plus a fanned-out `common.pyz` (`SKILLS`/`COMMON_CONSUMERS` in `scripts/build_pyz.py`). More importantly, `build-pyz.yml` no longer rebuilds and commits bundles — it runs read-only and *verifies* them via `check_bundles.py` (CRC comparison, since ZIP_DEFLATED output varies by zlib build), so a stale bundle reds the PR instead of self-healing. The `justfile:39` comment still claims the old behavior. Also added the missing `publish-pypi`, `docs-retry`, and `skill-overlap` workflows and the `cargo`-dependent `test-skill-overlap` leg of `just check`.

- 2026-08-23 · 95363c78068f772a · merged · architecture/workflow-contract-map.md · ingested durable orchestration ownership, ingress, review-correlation, and curd-identity details; newer accepted plan and schema decisions supersede conflicting July claims.
- 2026-08-23 · 95363c78068f772a · merged · specs/milknado-executor-recovery.md · preserved append-only checkpoint history and self-contained terminal outcomes under the later locked recovery protocol.
- 2026-08-23 · 95363c78068f772a · skipped-near-duplicate · — · omitted duplicate, superseded, unresolved, and transient handoff/environment material from the tracked July checkpoint.

- 2026-08-24 · mold:enforceable-skill-boundaries · approved · specs/enforceable-skill-boundaries.md, adr/skill-boundary-protocol-001.md, adr/skill-boundary-normalization-002.md, adr/skill-bundle-authority-003.md, adr/legacy-adapter-lifecycle-004.md, domain-model.md, architecture/workflow-contract-map.md · recorded the nine-curd Mold → Cook boundary plan, pointer-last publication, BAML-informed generous writer ingress, strict canonical acceptance, layout-derived one-skill bundles, and exact sunset-bound legacy adapters.
