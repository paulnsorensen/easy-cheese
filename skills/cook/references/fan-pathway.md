# /cook — Fan pathway mechanics

Full mechanics for `/cook`'s wave-fan pathway: the existing-handoffs guard,
typed planner-to-Cook-to-Cure execution, mode selection, publication topology,
the optional milknado seam, worktree harvest, recovery, and resolution
provenance. `SKILL.md` keeps the three-shape gate and wave cap; this file owns
the executable pathway after that gate.

The semantic authority is always the canonical `PlannerResult` and its
validated `CurdPlan`. A handoff file records resumable evidence, but legacy
manifest state is not live workflow state and is never read to decide which
phase to execute.

## Existing handoffs guard

Before dispatching the planner for an un-curded big spec, check whether any of
`.cheese/cook/<slug>.md`, `.cheese/press/<slug>.md`,
`.cheese/age/<slug>.md`, or `.cheese/cure/<slug>.md` already exists. If any do,
stop — print only the ones present — and tell the user to either run
`/cheese --continue <slug>` to resume from the latest typed handoff or remove
the listed files to start fresh. Never wipe an existing handoff silently:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest typed handoff, or
remove the listed files to start fresh.
```

Read a handoff with
`python3 skills/cook/scripts/cook.pyz read-handoff-slug <path>`;
the matching `cook.pyz read-handoff-slug` command.

## Canonical planner → Cook → Cure steel thread

The live fan route has one typed path. Do not dispatch the legacy curd-block
decomposer as the semantic planner, hand raw mappings between phases, or
invent a preflight helper:

1. Build a `PlannerRequest` from the authored spec and dispatch the planner
   through `easy_cheese_schemas.plan`. The planner output is a
   `PlannerResultWriterView`; `plan` materializes it into one `PlannerResult`.
   If `PlannerResult.plan` is absent, stop before any worker dispatch and
   preserve the failure in the handoff.
2. Take `planner_result.plan`, call
   `easy_cheese_schemas.validate_curd_plan`, and use that returned `CurdPlan`
   for every subsequent operation. Validation is the preflight: it completes
   before the first Cook writer, reviewer, or diagnosis dispatch.
3. Schedule `CurdPlan.curds` in dependency-respecting topological waves. A
   blocked prerequisite produces a deterministic blocked `CurdResult` for its
   dependents; declaration order is never a substitute for the plan's
   dependency graph.
4. Call `easy_cheese_schemas.cook` with the validated plan. The host resolves
   every `ArtifactRef` with `resolve_artifact`, and finalizes exactly one
   `CurdResult` per selected curd through `normalize_agent_output`. Writer
   output is observation-only: the host owns identity, digests, provenance,
   dispositions, and coverage. Executor or normalization failure still yields
   a host-finalized blocked result rather than zero results.
5. A failed review is a host-controlled Review → Diagnosis transition. The
   diagnosis callback returns a `DiagnosisResultWriterView`; the canonical
   normalizer produces a `DiagnosisResult`. Only a confirmed result may cross
   into Cure. Bind it to the exact source plan and curd with
   `easy_cheese_schemas.bind_diagnosis(plan, curd, diagnosis_result)`.
6. Call `easy_cheese_schemas.cure` with the same validated `CurdPlan` and the
   complete tuple or mapping of `CureDiagnosisBinding` values. Cure validates
   each binding's plan reference, curd reference, digest, and confirmed
   disposition before dispatch, then repeats artifact resolution and
   host-owned `CurdResult` normalization. A diagnosis from another plan or
   curd is never accepted.

The direct `plan` → `cook` → `bind_diagnosis` → `cure` calls above are the
canonical steel thread. `run_workflow` is the typed convenience entrypoint
when a host needs one call, with `phase="cook"` or `phase="cure"` and the same
binding requirements; it is not a separate semantic path.

## Mode selection

Whether a validated plan wave-fans or stays in linear mode is deterministic,
not a deliberation. `src/easy_cheese/shared/fanout/mode.py` is the single source of truth:
`PARALLEL_THRESHOLD = 2`, and `select_mode(curds)` returns `"parallel"` when
`len(curds) >= PARALLEL_THRESHOLD` (2 or more curds), otherwise `"linear"`.
The same selector is exposed for the installed route as
`python3 skills/cook/scripts/cook.pyz mode --count <curd-count>`.
The count comes from the validated `CurdPlan`, never from a legacy phase file.

**No-plan fallback.** `select_mode_from_score(score)` is only a fallback for a
PR or fresh branch with no planner handoff. It returns `"linear"` at
`score <= DECOMPOSE_FIRST_THRESHOLD` (250) and `"decompose-first"` above it;
it never returns `"parallel"` without a validated plan and disjointness proof.

**Fast path.** When `/mold`'s curd-count hint = 1 and the blast radius is low
or medium, skip the decomposer spawn entirely and use the single-coder path:
the 1-curd spec runs in linear mode. The hint is trusted only to skip work,
never to pick parallel or bypass `validate_curd_plan`.

## Publication topology preflight

When the selected mode is `parallel`, `--open-pr` is present, and no PR exists,
run `/plate` in topology-preflight mode before the first planner or worker
dispatch. Apply `/plate`'s review-shape policy: preserve an explicit choice,
persist `single` without asking for one cohesive review unit. Ask once only when
stacked is recommended or shape is ambiguous; record `plate_layout` in the typed
handoff evidence, read it back, and do not ask twice. Do not use a legacy manifest to make this
decision. Existing PRs preserve their detected topology; runs without
`--open-pr` remain commit-only.

This decision completes before Phase 1 seed or any worker commit.

**Seed (coder).** After topology is fixed, prepare only files shared by two or
more curds; do not hide curd-owned behavior in the seed.

## Milknado seam

Before running any curd, probe which of three roles the available toolset
supports (`src/easy_cheese/shared/fanout/milknado.py::probe`, exposed as
`python3 skills/cook/scripts/cook.pyz milknado --tools "<available
tool names>"`):

- **`engine`** — both `milknado_todo_claim` and `milknado_node_verify` are
  present. Milknado owns the DAG, per-node worktrees, and verify-until-green;
  `/cook` dispatches the typed curd operation for each claimed node.
- **`tracker`** — only `milknado_todo_add` is present. Milknado records typed
  curd status but does not run curds; `/cook` still owns native fan-out.
- **`none`** — no milknado tools. Native fan-out owns worktrees end to end,
  and curds self-verify once in-worker.

This parity difference is deliberate: native curds self-verify once, while
milknado (when present) verifies until green. Announce milknado's absence once
and proceed; `none` is never a blocker and never changes the typed contract.

## Phase-chain topology

| Stage | Chain | Canonical handoff |
| --- | --- | --- |
| Planner | `planner-request → PlannerResult → validated CurdPlan` | `PlannerResult` |
| Per curd | `cook(CurdPlan) → reviewer(age) → confirmed diagnosis → cure(CurdPlan, bindings) → reviewer(final age)` | `CurdResult` + `CureDiagnosisBinding` |
| Post-merge | `press → age → cure → age` over the merged typed results | final `CurdResult` |
| Per curd, closed N/A | `coder(cook) → reviewer(age) → coder(cure) → reviewer(final age)` | `not-applicable-curd` |
| Post-merge, closed N/A | `age → cure → age` | `not-applicable-postmerge` |

Per-curd workers own incomplete implementation slices: they never run Press
while sibling curds remain unfinished. After wiring and merge, the
orchestrator runs the one global Press → Age/Cure chain.

The per-curd chain may end early when a review returns a clean completion, but
the host still records one normalized result and keeps the plan's dependency
closure consistent. A failed review never jumps directly to Cure: the host
must materialize and confirm a diagnosis, then bind it to the exact curd.
Only a terminal age with `next: done` is publishable.

**Projected dispatch count.** The upper bound `/cook` shows at the decompose gate is disposition-specific. RED-required: 1 seed + 4 × curds + 4 post-merge = `5 + 4 × curds`. Closed N/A: 1 seed + 4 × curds + 3 post-merge = `4 + 4 × curds`. A first-age `clean_complete` shortens a RED curd to 2 dispatches and an N/A curd to 2. Wiring dispatches are excluded because wiring rows live in the manifest, not the curd block.

## Recovery and aggregate gates

- **Worker exhaustion.** A worker that runs out of context or turns writes a
  partial typed handoff with `status: needs-context: <gap>`. The orchestrator
  re-dispatches that curd once with the gap folded into context and
  `--retry-count 1`; a second `needs-context` at that phase halts (the router
  caps the loop itself), and the host finalizes its blocked `CurdResult`,
  keeps harvesting the rest, and reports the curd.
- **Aggregate-gate conflict.** After all waves are harvested, run the project
  gates over the merged tree. Distinguish a real cross-curd conflict (curds
  passed individually but collide in aggregate) from harmless generated drift
  the post-merge Cure can absorb. Never auto-resolve a real conflict.
- **Compute the verdict** — normalize each typed `CurdResult`; a halted result stops, while a clean first review finalizes that curd without Cure. After wiring and merge, the project gates must pass before the global post-merge chain.

## Worktree harvest and teardown

- Give each curd its own worktree; when the host lacks a native worktree-isolated sub-agent primitive, create it first with `python3 skills/cook/scripts/cook.pyz worktree create --slug <id> --base <orchestrator-branch>` (returns `{path, branch}`).
- Per curd, run the disposition-specific sequential chain and persist one
  normalized `CurdResult`; per-curd workers never run Press.
- After every curd returns, harvest commits and tear down each curd worktree.
- Harvest with `python3 skills/cook/scripts/cook.pyz worktree harvest
  --branch <curd-branch> --onto <orchestrator-branch>`. On conflict, invoke
  `/melt`; if it cannot resolve, fall back to per-curd PRs.
  The worktrees share one object store, so this needs no `git fetch`.
- Tear down with `python3 skills/cook/scripts/cook.pyz worktree
  teardown --path <worktree-path> --branch <curd-branch>`. A completed run
  leaves no `worktree-agent-*` branch or stray worker directory.
- Run wiring in dependency order, then run
  the one global `press → age → cure → age` integration pass.
- `/cook` alone performs harvest and dispatches `/plate` at the end, never
  mid-run.

After each wave, persist the typed `PlannerResult`, `CurdResult` values,
diagnosis bindings, and gate evidence in the handoff artifact. These records
are for recovery and publication provenance; they do not become a second
workflow state machine.

## --resume <slug>

`--resume <slug>` re-enters a crashed wave-fan run by loading the latest typed
handoff (`.cheese/cook/<slug>.md` and its referenced artifacts). If the
handoff or its referenced `PlannerResult`/`CurdPlan` is missing, malformed,
stale, or cannot be resolved by `resolve_artifact`, fail fast. Re-run
`validate_curd_plan` before selecting the next dependency wave, and verify
every retained commit or artifact reference still exists. Resume only curds
whose typed result is incomplete; never infer progress from an old phase name.

A bare re-run (no `--resume`) that finds an existing handoff stops and tells
the user to resume or remove it; it never silently wipes typed evidence.

## Resolution provenance and the output contract

Every planner, curd, review, diagnosis, and Cure dispatch resolves against the
typed-role table in `SKILL.md`'s `## Agent resolution` section and the shared
protocol in [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md):

| Work | Preferred types |
| --- | --- |
| Plan the spec | planner, general |
| Cook, press, cure, seed, or wiring | coder |
| Every age pass | reviewer |
| Harvest and plate | parent |

The resolver filters required capabilities, tools, permissions, and isolation
first, then picks minimum power and maximum specificity. A prompt-only
read-only general fallback may continue with `degraded: true`; a missing
required tool or write permission halts. Every handoff and final summary
carries the resulting `agent_resolution` block so role, fallback, and
degradation stay visible.

The fan pathway and single-coder path keep the same final-summary shape
(`SKILL.md`'s `## Handoff slug`, `## Output`). A terminal age is publishable
only with `next: done`; `next: cure` or a missing `next` is not publishable.
