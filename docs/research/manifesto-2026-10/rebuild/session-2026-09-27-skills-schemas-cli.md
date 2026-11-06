# Rebuild exercise, session 3 (2026-09-27): skills map, schema position, CLI thread digest

Work id: `rebuild-easy-cheese-from-scratch`. Session: Claude `e5585898-7870-4504-a3d8-75a395b35c4b` in worktree `t3code-ab6a64c7` (branch `t3code/review-skills-simplification-plan`).
No source change. No commit. Hallouminate MCP failed to connect, so wiki pages were read from the tree.

## 1. Where the plan lives

| Record | Date | What it holds |
| --- | --- | --- |
| Wheypoint `rebuild-easy-cheese-from-scratch` rev 1 | 09-21 | Measured facts, six open forks, agent recommendation, `next: culture`. |
| Wiki `skill-optimization-landscape.md` (PR #727) | 09-26 | GEPA/agent-lab optimizer plan, harness inventory, per-skill graders, suggested order. Records the rebuild forks as constraints. |
| Prune audit `.cheese/skill-prune/actionable.json` (main checkout) | 06-25 | 157 confirm / 39 soften across 18 skills. **Applied**: 2 of 119 applicable confirmed findings still present (both in `cheese`). |
| WGS audit `.cheese/notes/wgs-audit-report.md` (main checkout) | 06 | Rubric audit, all tiers applied, net -640 lines. |
| Thread "Easy Cheese CLI and schema rebuild" | 09-24 | Transcript only, see section 4. |
| Spec `specs/wheypoint-cli.md` (XDG corpus) | 09-24 | Shipped as #718, #719, #724, #725, #726. |
| Spec `enforceable-skill-boundaries.md` (cli-rebuild worktree) | 08-24 | HandoffPointer, NormalizationReceipt, `@bundle_command`, contract migrate/accept/publish. Partly landed (#699, #702). |

## 2. Skill map (own read of all 16 SKILL.md files)

Pipeline: `culture -> mold -> cook -> press -> age -> cure -> plate`; `cheese` routes in; `affinage`, `pasteurize` are side entries; `melt`, `wheypoint`, `hard-cheese`, `easy-cheese-setup` are utilities; `ultracook` is a redirect.
Every phase skill follows one template: phase-entry block (`wheypoint-resolve`), inputs with the same five flags (`--auto --safe --open-pr --hard --continue`), flow, handoff slug via `write-handoff-artifact`, handoff gate, agent-resolution table.

| Skill | SKILL.md | refs | py | verbs | sessions/60d |
| --- | --- | --- | --- | --- | --- |
| age | 269 | 2,948 | 1,739 | 17 | 968 |
| cook | 290 | 1,504 | 5,531 | 28 | 525 |
| plate | 210 | 827 | 1,041 | 6 | 131 |
| cure | 321 | 459 | 131 | 10 | 124 |
| briesearch | 100 | 598 | 1,569 | 4 | 122 |
| cheese | 250 | 2,047 | 0 | 0 | 88 |
| affinage | 300 | 305 | 637 | 5 | 76 |
| mold | 149 | 1,750 | 3,846 | 11 | 69 |
| press | 228 | 184 | 59 | 4 | 64 |
| pasteurize | 421 | 24 | 527 | 3 | 56 |
| wheypoint | 133 | 405 | 106 (+~5,000 shared) | 10 | 44 |
| melt | 280 | 122 | 1,469 | 5 | 43 |
| culture | 102 | 0 | 0 | 0 | 27 |
| hard-cheese | 246 | 167 | 883 | 3 | 1 |
| easy-cheese-setup | 77 | 10 | 47 | 4 | 0 |
| ultracook | 23 | 410 | 0 | 0 | retired |

Totals: SKILL.md 3,399 lines; references 11,760; shared Python 24,761; schemas 10,315. Largest shared modules: `workflow.py` 2,235, `taste_test.py` 1,560, `fanout/run_fan.py` 1,138, `mold_cook_handoff.py` 1,055, `fanout/age_route.py` 1,007. Wheypoint kernel about 5,000 lines.
Cross-skill links into `cheese/references`: mold 46, cook 23, age 22. The router hosts the kernel.

Structural findings:

- Per-phase boilerplate (phase entry, "slash commands are host renderings" paragraph, agent-resolution table, voice/formatting/routing pointers) repeats in ten skills, about 30 lines each. This is why `age` and `cure` sit at the 3,600-token ceiling.
- Fan-out is on by default: `cheese` cook-intent default is `/cook --auto`, and a decomposable spec starts the fan pathway automatically. The 09-21 leaning was single-writer default.
- `age` ships 1,791 lines of deslop-<lang> catalogs while the separate `de-slop` skill (454 sessions) lives outside the repo.
- `ultracook` redirect still ships 410 reference lines; `cook` reads `manifest-schema.json` and `curd-prompt.md` from there.

## 3. Simplification order (agent recommendation, not decided)

1. Settle the fan-out fork; flip `cheese` default to single-writer cook, fan explicit opt-in.
2. Collapse per-phase boilerplate into one shared phase-contract reference, or have `wheypoint-resolve` emit it.
3. Delete `ultracook`; move the two live files into `cook/references`.
4. Park `hard-cheese` (1 session / 60 days, ~1,300 lines).
5. Fold `culture` internal mode into `cheese` step 1; keep user-facing mode only for the record ledger.
6. Decide de-slop's home (age catalogs vs standalone skill).
7. Shrink `mold` after step 1 (18 refs, 11 verbs, 69 sessions).

Do not start the GEPA optimizer before steps 1 and 3; its candidate set depends on them.

## 4. Thread digest: "Easy Cheese CLI and schema rebuild" (09-24 09:12, worktree `easy-cheese-cli-rebuild-3ae768`)

Opened from a pasted canvas (`/tmp/claude-1000/.../63656582-.../images/1.webp`): `cheese` forks into `culture` and `mold`; mold fans to pasteurize, briesearch, wiki grounding, grill/duck, spec (small single PR | design doc to stack | large to RFD), spike; second fork feeds `cook`/`age`; press; plate. Side notes: "wheypoint vs milknado execution?", "plan / execution / curd plan etc.", "settings", "ui", "taste test (self eval)".
Grilling skill invoked. Agent measured 77 verbs across 13 bundles (109 verb-bundle pairs; `handoff`, `findings`, `gates` shipped in 3-4 bundles each), mapped 15 workflows over five nodes with two node families (context: fact, question, decision, directive, evidence; change: spec section, task, slice, PR), drafted a nine-question grill order, and asked Q1: one SQLite work graph shared by wheypoint, specs, landing plans, milknado tasks, schema owned by easy-cheese-schemas, milknado depending on it. Recommendation was yes. User did not answer. No wheypoint saved. Later that day the user narrowed to the wheypoint CLI, which shipped.
The 09-26 sweep logged three conflicts from the thread: JSON-only output, nested noun-verb CLI, SQLite graph replacing the wheypoint store.

## 5. Schema and store position (agent recommendation, not decided)

Facts: 21 registered contract URIs. The execution loop middle is typed (mold-cook-handoff/approval, planner-request/result, curd-plan, curd-result, review-request/result, diagnosis, remediation-state, pr-plan, handoff-pointer, normalization-receipt). Missing: `spec` (MoldSpecDocument is doc-gen internal), `adr`, `research-report`, `eval-result`. WheypointRecord has `artifact_links` {path, digest?, revision_id?, covers_entry_ids}. `ArtifactRef` has {artifact_id, role, uri, digest, size, media_type, schema_uri}. Milknado `MikadoNode` (SQLite, int id, status/kind/flavor/pid/worktree) has opaque links `wiki_ref`, `github_ref`, `artifact_path`; edges parent/child only. Milknado does not import easy-cheese-schemas (Shape B 08-28 and seam ADR-006 unexecuted). Easy-cheese's only milknado code: a 92-line tool probe, no callers.

Position: shared schema, separate stores. Do not bolt milknado's engine onto the wheypoint type (mutable execution row vs append-only digest chain; ADR-006 sequence; Q1's coupling risk). Do: promote ArtifactLink to ArtifactRef; add `work-edge {from, to, kind}` with kinds depends_on, informs, supersedes, implements, blocks, checkpoints; register `spec` and `eval-result`; milknado adopts the package and links via `source_curd_ref` (ADR-001) plus `wheypoint_ref`. Keep the JSON store; a SQLite index can come later.

Diagrams (Graphviz, in `diagrams/` beside this file): `1-stores-and-packages`, `2-work-graph`, `3-execution-loop`.

## 6. New asks from the user (09-27 05:56), starting points

- **Scrutinize all schemas.** Start at `src/easy_cheese_schemas/_schema_catalog.py` (21 URIs), `contracts.py` (4,202 lines), seam ADRs 001-006, wiki `schema-similarity-and-consolidation-audit.md` (zero safe root merges found earlier).
- **Living spec / active idea with diagrams, no reprinting.** Candidates: typed markdown with stable section ids patched in place (MoldSpecDocument + tilth_write); the mold review canvas (`skills/mold/references/review-canvas.md`, `shared/html_report.py`, PRs #697, #711) as a rendered projection; wiki page. "Like our front-end" points at the canvas/design system.
- **Go over all CLIs.** 110 verbs today from `skills/*/references/commands.md` (cook 28, age 17, mold 11, cure 10, wheypoint 10, plate 6, affinage 5, melt 5, briesearch 4, easy-cheese-setup 4, press 4, hard-cheese 3, pasteurize 3). Thread direction: one nested `cheese <noun> <verb>` binary, JSON only, routing verbs owned by skills.

## 7. Defects noted, not fixed

- `ground-check` cannot resolve a `path:line` citation under a dot-directory other than `.cheese` (`ground_check.py:94`, from 09-21).
- Wiki `red-gate-environment-gotchas.md` describes an import that no longer exists (from 09-21).
- `.github/skill-budgets.json` still lists `python-authoring` and `skill-authoring`, which are not under `skills/`.
