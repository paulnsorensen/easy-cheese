---
name: cheese-factory
description: Parallelize an approved spec across 5+ independent behavioural curds into reviewable PRs, running the whole pipeline fanned out at once. Use when the user has such a spec — phrases like "/cheese-factory .cheese/specs/<slug>.md", "send through the factory", "parallelize this spec", "many curds", "fan out the implementation", "cheese-factory this". Runs inline and spawns full-peer general-purpose sub-agents per phase (decomposer, per-curd workers, wiring, post-merge review, PR planner), ending in 1–N reviewable PRs via `/pr-stack`. Use even when the user mentions `/fromagerie` — `/cheese-factory` is the portable harness-agnostic sibling. Supports `--hard` propagation and `--resume <slug>` to continue a crashed pipeline. Do NOT use for single coherent specs (`/cook`, `/ultracook`), fuzzy planning (`/mold`), review-only work (`/age`), or specs with fewer than 5 curds (`/ultracook`).
license: MIT
---

# /cheese-factory

## Inputs

Accept:

```text
/cheese-factory <spec-path-or-slug> [--hard] [--resume <slug>]
```

- A spec path. When explicit, read it verbatim wherever it points.
- A bare slug. Resolve it to the durable spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/cheese-factory.pyz artifact-path specs <slug>)`, then read `"$SPEC"`. The resolver anchors specs at the per-project durable corpus (see `shared/formatting.md` § Corpus location).
- `--hard` — propagate the `/hard-cheese` metacognitive gate flag through per-curd `/cook --hard --auto` and the Phase 6 `/cure --hard --auto --stake medium+`. The orchestrator does not fire the gate itself. See `skills/hard-cheese/SKILL.md`.
- `--resume <slug>` — read `.cheese/cheese-factory/<slug>/manifest.yaml`, find the latest phase marked complete, and continue from the next phase.

`/cheese-factory` does not accept fuzzy or open-ended asks — route those to `/mold` first. The orchestrator assumes the contract is locked.

`--auto` is **implicit**. After Phase 0 gate approval, the chain runs autonomously with no per-step handoff questions.

## When to use `/cheese-factory` vs alternatives

Use `/cheese-factory` only when the spec decomposes into 5+ file-disjoint behavioural curds. Fewer curds → `/ultracook`; single unambiguous task → `/cook`; on Anthropic Claude Code with bespoke agent files installed → `/fromagerie`.

## Decomposition contract — curds of behaviour

A curd is the smallest commit-worthy unit of behaviour.

The Phase 0 decomposer produces three artifact lists from the spec:

1. `seed[]` — foundational types / interfaces / enums that 2+ curds depend on.
2. `curds[]` — parallel units of behaviour, file-disjoint, one acceptance criterion each.
3. `wiring[]` — integration tasks with topological dependencies (barrels, registrations, routes, config).

### The five criteria

Five behavioural criteria govern every curd — see `references/decomposer-prompt.md` § The five criteria for the full list and the "token budgets are NOT a criterion" rationale. Curds that fail criterion 4 (file-disjoint) move their shared content to seed or wiring.

### Manifest format

The per-run manifest is written as YAML at `.cheese/cheese-factory/<slug>/manifest.yaml`.
YAML is the human/agent-facing syntax; the contract stays schema-shaped and is
documented in `references/manifest-schema.json`. Keep manifests in the JSON-compatible
subset of YAML: mappings, lists, strings, numbers, booleans, and nulls only; no anchors,
aliases, tags, or multi-document streams.

The PR plan follows the same convention — written as YAML at
`.cheese/cheese-factory/<slug>/pr-plan.yaml`, with its shape documented in
`references/pr-plan-schema.json`. `${CLAUDE_SKILL_DIR}/scripts/cheese-factory.pyz pr_plan_to_branches` reads either YAML
or JSON for backward compatibility, but YAML is the canonical format.

### Validation (Phase 0)

See `references/decomposer-prompt.md` § Validation for the six checks run by `${CLAUDE_SKILL_DIR}/scripts/cheese-factory.pyz validate_manifest` and `validate_decomposition`. If validation fails: re-run decomposer with violations highlighted. Max 2 retries before escalating to the user.

## Phases

Eight phases. The orchestrator walks them top-to-bottom and stops after the last entry or any halt.

| # | Phase | Shape |
|---|---|---|
| 0 | Pre-compile | Read spec, decompose via heavy general-purpose sub-agent, validate against the five criteria, user gate |
| 1 | Seed | Orchestrator inline edits via `/cheez-write` (or host edit tool if tilth MCP is unavailable), commit, push |
| 2 | Curds (fan-out) | N parallel general-purpose spawns; each runs the per-curd pipeline and commits |
| 3 | Merge curds (fan-in) | Cherry-pick curd commits → orchestrator branch; `/melt` on conflicts |
| 4 | Wiring (sequential within wave) | Integration files only; per-task general-purpose spawn with wiring-only prompt |
| 5 | Final merge wiring | Wiring commits → orchestrator branch; conflicts here = halt (decomposer error) |
| 6 | Post-merge review (fresh-context, ultracook-style) | Three sub-agent spawns: `/press --auto`, `/age --auto`, `/cure --auto --stake medium+`. Single pass. |
| 7 | PR plan + publish | Heavy PR planner sub-agent decides layout, orchestrator delegates publish via skill discovery (`/pr-stack`, `/gh`, fallbacks) |

### Optional: milknado curd-tracking backend

If milknado MCP is available (`mcp__milknado__milknado_todo_add` in toolset), persist the curd list to the milknado task graph during Phase 0 decomposition. Use `mcp__milknado__milknado_todo_add` per curd and `mcp__milknado__milknado_graph_summary` to surface the tracked curds alongside the manifest. This provides cross-session tracking of curd status across the factory run. If milknado is absent, proceed with the in-report curd decomposition (manifest YAML at `.cheese/cheese-factory/<slug>/manifest.yaml`) — the decomposition itself is unchanged. See [`../../shared/optional-plugins.md`](../../shared/optional-plugins.md) for the detect-and-degrade contract.

### Phase 0 — Pre-compile

Read the spec from the argument (or, if `--resume <slug>`, read the manifest and skip to the next incomplete phase).

Validate the spec has: Executive Summary, Problem Statement, User Stories, Acceptance Criteria, Quality Gates. Fail fast if any is missing.

**Hard worktree gate**: detect the host's worktree mechanism (Conductor, git worktrees, plain branches) and prompt if working on the default branch. Never skipped.

Spawn a heavy general-purpose **decomposer** sub-agent (prompt template at `references/decomposer-prompt.md`) with the spec text, the five criteria, the validation checks, and instructions to produce `seed[]`, `curds[]`, `wiring[]`, and a manifest scaffold.

The decomposer may invoke `/culture` or `/briesearch` internally if it needs to ground its decomposition against the codebase or external docs.

**Front-load permissions**: present the per-host permission manifest (git, the project's quality gate command, the host-specific spawn primitive) to the user. On approval, merge into the host's settings.

#### Gate — User Approval

Present the full plan:

```text
## Cheese-Factory Plan: <slug>

### Seed (sequential)
1. <description> — files: [<list>]

### Curds (parallel)
| # | Behaviour | Acceptance criterion | Files | Test target |
|---|---|---|---|---|

### Wiring DAG
| # | Type | File | Depends on |
|---|---|---|---|

### Review Pipeline
Per-curd: /cook → /press → /age (inline-degrade) → /cure
Post-merge: /press → /age → /cure (fresh-context sub-agents)

A. Approve — start execution
B. Modify — change the decomposition
C. Re-decompose — different boundaries
D. Pause — hold off
```

Use the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) for this approval step. All four options keep cheese-factory running internally (no skill transition) — they use `continue:` identifiers rather than `dispatch:` commands per the gate vocabulary:

- **Approve** — `continue: write-manifest-then-seed`: write `.cheese/cheese-factory/<slug>/manifest.yaml`, set `phase: gate_approved`, then proceed with Phase 1 (seed execution).
- **Modify** — `continue: ask-for-decomposition-change`: ask one targeted question for the requested decomposition change, then re-render the plan.
- **Re-decompose** — `continue: re-run-decomposer`: re-run the decomposer with the user's boundary instruction. Retry at most twice.
- **Pause** — `dispatch: none`: leave the manifest draft and report its path.

**Do NOT proceed without explicit approval.**

#### Compaction seam C1

Drop: full spec text, permission manifest, decomposition reasoning.
Keep: slug, spec summary (≤2K chars), manifest path, quality gate commands.

### Phase 1 — Seed (sequential, inline)

Seed items are minimal — only the shared types / protocols that curds cannot compile without. The orchestrator executes seed inline (a deliberate exception to the orchestrator's "never write code" rule because seed is always small).

For each seed item:

1. Implement the change. Prefer `/cheez-write` when tilth MCP is present; otherwise fall back to the host's native edit tool (per the `cheez-*` portability rule in `README.md`). The skill must not hard-fail when `/cheez-write` is unavailable.
2. Run quality gates (the project's `just check` or equivalent) — if gates fail, STOP.
3. Commit via `/commit` (if available) or `git commit` direct.

Push to branch — curds branch from HEAD.

Update manifest: `phase: seed_complete`, commit SHAs.

### Phase 2 — Curds (fan-out)

Spawn ALL curd workers in a single message via the host's fan-out primitive. If more than 5 curds, dispatch in waves of 5.

Each curd worker is a general-purpose sub-agent (full peer of the orchestrator — same model, full tools, full skills, full MCP) given the per-curd prompt at `references/curd-prompt.md`.

Collect results as curds complete. For failed curds: retry ONCE with error context. Mark `retry_count: 1`; do not retry twice.

Update manifest: curd statuses, worktree paths, branch names, commit SHAs.

#### Compaction seam C2

Drop: decomposer artifacts, curd dispatch prompts, curd return summaries.
Keep: slug, manifest path, quality gate commands, curd branch list.
Read from disk when needed: wiring DAG.

### Phase 3 — Merge curds (fan-in)

Cherry-pick curd commits onto the orchestrator branch in curd-id order:

For each curd (in order):

1. `git cherry-pick <curd_commit_sha>` — or, if the host fan-out used worktrees, merge the worktree branch.
2. On conflict: invoke `/melt` if available, else fall back to mergiraf → `git rerere` → manual.
3. If `/melt` cannot resolve: STOP, fall back to per-curd PRs in Phase 7.

After all curds merged: run quality gates. If failing, STOP and report — curds passed individually but conflict in aggregate (decomposer error).

### Phase 4 — Wiring (fan-out, sequential within wave)

Read wiring DAG from manifest. Dispatch wiring tasks in topological order, sequentially within each wave (concurrent commits to the same working directory race on git's `index.lock`).

Each wiring worker is a general-purpose sub-agent with the prompt template at `references/wiring-prompt.md`.

For failed wiring tasks: retry ONCE. If still failing, mark incomplete in manifest.

### Phase 5 — Final merge wiring

Cherry-pick the wiring commits onto the orchestrator branch.

If conflicts arise here: STOP. Wiring conflicts mean the decomposer's DAG was wrong (wiring touched implementation territory, or two wiring tasks shared a file outside the DAG). Do not auto-resolve.

#### Compaction seam C3

Drop: wiring DAG details, per-curd diffs, intermediate merger reports.
Keep: slug, spec path (for downstream skills), quality gates, list of all changed files, list of all commit SHAs (curds + seed + wiring).

### Phase 6 — Post-merge review (ultracook-style fresh-context)

Run the final review pipeline in fresh-context sub-agents.

Three sequential spawns:

1. `/press --auto` on the merged diff — writes `.cheese/press/<slug>.md`.
2. `/age --auto` on the merged diff — writes `.cheese/age/<slug>.md`.
3. `/cure --auto --stake medium+` on the age findings — writes `.cheese/cure/<slug>.md`.

Each spawn is a full-peer general-purpose sub-agent. Pass the no-chain-forward directive (same as `/ultracook`) so each spawn runs its phase only.

Single pass through — no two-cure-pass cap. Curds each had their own press/age/cure; this is integration-level review.

If any phase writes `status: halt: <reason>` in its slug, surface the halt and STOP. If `/cure` writes `next: done`, continue to Phase 7.

### Phase 7 — PR plan + publish

Spawn a heavy general-purpose **PR planner** sub-agent (prompt template at `references/pr-planner-prompt.md`) with the wiring DAG, the manifest, the merged diff, and the spec summary.

The planner emits one of four shapes:

| Shape | When | PR layout |
|---|---|---|
| `single` | Small total diff, tightly coupled | All commits in one PR. |
| `orthogonal_flat` | Curds touch disjoint slices, no seed/wiring coupling | N PRs each branching from main. |
| `stacked_linear` | Linear dependencies seed → curds → wiring | gt/gh stack. |
| `diamond_stack` | Seed and wiring exist; curds independent of each other | seed PR (base) → N parallel curd PRs → wiring PR. |

The planner writes its grouping to `.cheese/cheese-factory/<slug>/pr-plan.yaml` and returns control.

#### Skill discovery (orchestrator-side)

Before publishing PRs, the orchestrator detects which skills are available and picks the right delegate:

| Need | Prefer | Fallback |
|---|---|---|
| Stack publish | `/pr-stack` (Graphite `gt` or `gh stack`) | manual `gh pr create --base <prev-branch>` chain |
| Commits | `/commit` | `git commit` direct |
| PR publish | `/gh` | `gh pr create` direct |
| Merge conflicts | `/melt` | mergiraf → rerere → kdiff3 direct |

Detection: attempt to invoke the skill via the host's Skill tool; on unrecognised-skill error, fall back. Cache the result for the rest of the phase.

#### Publish

For each PR group in the plan:

1. Read group metadata from `pr-plan.yaml`.
2. Push the branch (use `${CLAUDE_SKILL_DIR}/scripts/cheese-factory.pyz pr_plan_to_branches` to convert `pr-plan.yaml` to branch-creation commands).
3. Create the PR (via `/gh` if available, else `gh pr create` direct).
4. For stacks: invoke `/pr-stack` with the ordered branch list.
5. Update manifest with PR numbers and URLs.

## Final report

```text
## Cheese-Factory Complete: <slug>

### Results
| Phase | Status | Detail |
|---|---|---|
| Seed | complete | 2 commits |
| Curds | 5/6 succeeded | Curd #4 failed after retry |
| Merge | complete | — |
| Wiring | 4/4 complete | — |
| Final merge | complete | — |
| Post-merge review | press: pass, age: 3 findings, cure: 3 applied |
| PR plan | diamond_stack | seed + 5 curds + wiring = 7 PRs |

### PRs
| PR | Title | Stack base |
|---|---|---|
| #101 | feat(orders): shared types | main |
| #102 | feat(orders): order entity | #101 |
| ... |

### Manual actions needed
- Curd #4 failed: {error_summary}

Manifest: .cheese/cheese-factory/<slug>/manifest.yaml
```

## Compaction strategy
At each seam, write a self-summary to the manifest before dropping:

Write `phase_summary` and `carry_forward` (shapes in `references/manifest-schema.json`) before dropping. On `--resume`, read `phase_summary` from the manifest — the only cross-seam continuity mechanism; do not rely on conversation history.

## Spawn primitive contract (host-agnostic)

The orchestrator never names a specific host primitive. Any primitive satisfying all five invariants is acceptable: (1) fresh context per spawn, (2) full-peer inheritance, (3) no chain-forward (passed in prompt), (4) returns control, (5) writes handoff slug. Host-by-host examples and the no-fan-out fallback (route to `/ultracook`) live in `references/spawn-primitive-reference.md`.

## Handoff slug schema

Every phase writes a handoff slug to `.cheese/<phase>/<slug>.md` (or, for per-curd workers, to `.cheese/cheese-factory/<slug>/curds/<curd-id>.md`) with the minimum shape:

```markdown
status: ok | halt: <one-line reason>
next: <phase-name | done>
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this phase did>
```

For phases that already write rich reports (`/age`, `/press`, `/cure`), the schema is prepended at the top of the same file.

## Quality gates

`/cheese-factory` runs the project's quality gate command (typically `just check` per `AGENTS.md`) at four points:

1. After seed (Phase 1).
2. Inside each curd worker (after its `/cure` step).
3. After curd merge (Phase 3, before wiring).
4. After Phase 6 `/cure`.

If any gate fails: STOP, report, do not silently fix.

## `--resume <slug>`

If the manifest references commits that no longer exist (rebased, deleted), fail fast — do not silently re-execute the phase. Otherwise continue from the phase after the latest one marked complete; report `Resuming <slug> from phase <N>`.

## Error recovery

| Failure | Recovery |
|---|---|
| No spec argument | STOP. Report `cheese-factory requires an approved spec; run /mold first if you need to shape one`. |
| Overlap / criterion violation in decomposer output | Re-run decomposer (max 2 retries) |
| Seed gate failure | STOP, report — do not dispatch curds |
| Curd fails | Retry once with error context, then mark failed |
| All curds fail | STOP, no merge/wiring |
| Curd merge conflict | `/melt`; if `/melt` fails, fall back to per-curd PRs |
| Wiring agent fails | Retry once, mark incomplete if still failing |
| Phase 5 conflicts | STOP — decomposer error, report to user |
| Phase 6 `/press` or `/age` halt | Surface halt, STOP |
| Phase 6 `/cure` cannot apply any finding | Surface report, STOP |
| `/pr-stack` not available, plan calls for stack | Fall back to manual `gh pr create --base` chain |
| `--resume` on missing manifest | Fail fast |

**Never proceed past Phase 0 gate without explicit user approval.**
**Never claim green on partial work.**

## What the orchestrator never does

**Does**: reads the spec once at Phase 0; reads per-phase handoff slugs (each ≤2KB); writes manifest updates after each phase; decides chain progression from slug `status` and `next` fields — never from sub-agent stdout.

**Never**:

- Read codebase files (sub-agents explore, orchestrator routes).
- Run build / test commands (per-curd workers and post-merge sub-agents handle verification).
- Write implementation code (cook agents and wiring agents implement; the orchestrator's only inline writes are the small seed items in Phase 1).
- Make decomposition decisions after Phase 0 (plan is locked at gate approval).
- Retry more than once (curds and wiring get one retry, then mark failed).
- Auto-resolve Phase 5 conflicts (wiring conflicts = decomposer error).
- Estimate sub-agent token usage (decomposition uses behavioural criteria, not token counts).
- Read full sub-agent reports — work from handoff slug digests only.

## Gotchas

- **`/age` nesting depth**: curd workers invoke `/age` which normally fans out to 6 review sub-agents (level 2, blocked). `/cheese-factory` requires `/age` to support an inline-degrade mode for sub-agent invocation — see `skills/age/SKILL.md` "Inline-degrade mode".
- **Context death after C2**: after C2 the orchestrator has no curd details. The wiring DAG must be self-contained on disk. If wiring references curd internals not captured in the manifest, wiring agents will fail.
- **Wiring race conditions**: wiring tasks commit to the same working directory. Phase 4 dispatches them sequentially (not in parallel) to avoid `git index.lock` races even when files differ.
- **bypassPermissions doesn't bypass Bash**: curd workers can Edit/Write freely but cannot `git push` or `gh pr create` without explicit Bash allowlist. The orchestrator must handle all push / PR operations.
- **Stale worktrees**: curd worktrees persist after Phase 3 merge. The orchestrator does NOT clean them up — recommend the user run `/worktree-sweep` (or host equivalent) after the pipeline completes.

## References

- `references/decomposer-prompt.md` — heavy decomposer sub-agent prompt template.
- `references/curd-prompt.md` — per-curd worker prompt template.
- `references/wiring-prompt.md` — per-wiring task prompt template.
- `references/pr-planner-prompt.md` — PR planner sub-agent prompt template.
- `references/manifest-schema.json` — JSON Schema for the manifest.
- `references/pr-plan-schema.json` — JSON Schema for the PR plan, `$ref`'d from `manifest-schema.json`.
- `references/spawn-primitive-reference.md` — host-by-host invocation examples plus the five invariants.
- `cheese-factory.pyz` subcommands (run via `${CLAUDE_SKILL_DIR}/scripts/`): `validate_manifest`, `validate_decomposition` (Phase 0), `validate_pr_plan`, `pr_plan_to_branches` (Phase 7).

## Rules

- Sub-agents are full peers, not diminutive workers. Do not downgrade the model, do not narrow `subagent_type`, do not restrict tools or MCP access.
- The chain is fixed at eight phases. Do not invent extra phases or skip phases (except via `--resume`).
- Read each phase's handoff slug after the sub-agent returns. Do not infer success from the sub-agent's last line — read the file.
- Surface halts verbatim. Do not paraphrase, do not soften, do not "retry" a halted phase silently.
- Never invoke `/gh` directly without confirming via the user-approved permission manifest from Phase 0.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the final report with what happened, flag residual risk as `certain | speculating | don't know`, do not manufacture follow-ups.
