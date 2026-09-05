# /cook — Fan pathway mechanics

This file defines the full mechanics for `/cook`'s wave-fan pathway.

It covers the existing-handoffs guard, typed Planner-to-Cook-to-Cure execution, mode selection, publication topology, and the optional milknado seam.

It also covers worktree harvest, recovery, and resolution provenance.

`SKILL.md` defines the three-shape gate and wave cap.

This file defines the executable pathway after that gate.

The canonical `PlannerResult` and its validated `CurdPlan` always provide semantic authority.

A handoff file records resumable evidence.

Legacy manifest state is not live workflow state.

Never read legacy manifest state to select the phase to execute.

## Existing handoffs guard

Before planner dispatch for an un-curded big spec, check these files:

- `.cheese/cook/<slug>.md`
- `.cheese/press/<slug>.md`
- `.cheese/age/<slug>.md`
- `.cheese/cure/<slug>.md`

If any file exists, stop and print only the files that exist.

Tell the user to run `/cheese --continue <slug>` to resume from the latest typed handoff.

Alternatively, tell the user to remove the listed files to start fresh.

Never silently remove an existing handoff:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest typed handoff, or
remove the listed files to start fresh.
```

Read a handoff with the phase and the slug, not with a path:

```text
python3 skills/cook/scripts/cook.pyz read-handoff-slug --phase <phase> --slug <slug>
```

The command exits with status 2 when either flag is absent.

## Canonical planner → Cook → Cure steel thread

The live fan route has one typed path.

Do not use the legacy curd-block decomposer as the semantic planner.

Do not pass raw mappings between phases.

Do not create a preflight helper.

1. Build a `PlannerRequest` from the authored spec.
   Select the request kind from the failure class, as `## Planner request kinds` defines.
   Dispatch the planner through `easy_cheese_schemas.plan`.
   The planner returns a `PlannerResultWriterView`.
   `plan` materializes this view into one `PlannerResult`.
   If `PlannerResult.plan` is absent, stop before any worker dispatch.
   Preserve the failure in the handoff.

2. Take `planner_result.plan`.
   Call `easy_cheese_schemas.validate_curd_plan`.
   Use the returned `CurdPlan` for every subsequent operation.
   Validation is the preflight.
   Complete validation before the first Cook writer, reviewer, or diagnosis dispatch.

3. Schedule `CurdPlan.curds` in topological waves that respect dependencies.
   A blocked prerequisite produces a deterministic blocked `CurdResult` for its dependents.
   Never use declaration order instead of the plan's dependency graph.

4. Call `easy_cheese_schemas.cook` with the validated plan.
   The host resolves every `ArtifactRef` with `resolve_artifact`.
   The host finalizes exactly one `CurdResult` for each selected curd through `normalize_agent_output`.
   Treat writer output only as an observation.
   The host owns identity, digests, provenance, dispositions, and coverage.
   Executor or normalization failure still produces a host-finalized blocked result.
   Never produce zero results for this failure.

5. A failed review starts a host-controlled Review → Diagnosis transition.
   The diagnosis callback returns a `DiagnosisResultWriterView`.
   The canonical normalizer produces a `DiagnosisResult`.
   Only a confirmed result can continue to Cure.
   Bind the result to the exact source plan and curd.
   Use `easy_cheese_schemas.bind_diagnosis(plan, curd, diagnosis_result)`.

6. Call `easy_cheese_schemas.cure` with the same validated `CurdPlan`.
   Supply the complete tuple or mapping of `CureDiagnosisBinding` values.
   Before dispatch, Cure validates each binding's plan reference, curd reference, digest, and confirmed disposition.
   Cure then repeats artifact resolution and host-owned `CurdResult` normalization.
   Never accept a diagnosis from another plan or curd.

The direct `plan` → `cook` → `bind_diagnosis` → `cure` calls define the canonical steel thread.

`run_workflow` is the typed convenience entrypoint when a host requires one call.

Use `phase="cook"` or `phase="cure"` with the same binding requirements.

`run_workflow` does not define a separate semantic path.

## Planner request kinds

Cook emits the validated request. Mold owns planning after a Cook failure.
Cook never plans on its own after a specification failure.

Select one `PlannerRequestKind` for each failure class:

| Failure class | `kind` | Required fields | Rejected when |
| --- | --- | --- | --- |
| The spec has no plan yet | `decompose` | `objective` | `source_plan_ref` is present |
| A deliberate replan of an approved plan | `replan` | `objective`, `source_plan_ref` | `source_plan_ref` is absent |
| A specification failure during execution | `remediate` | `objective`, `source_plan_ref`, at least one `evidence` entry | `source_plan_ref` or `evidence` is absent |

Every request also requires `contract_version` and `request_id`.
Publish the validated request, then name its typed pointer in `artifact:`.
Write `next: mold` with the `https://schemas.easy-cheese.dev/planner-request` payload schema.
Use `status: ok`, because `gated` and `halt` stop the chain.

## Mode selection

Select linear or wave-fan mode deterministically.

Do not use deliberation to select the mode.

`src/easy_cheese/shared/fanout/mode.py` is the single source of truth.

`PARALLEL_THRESHOLD = 2`.

`select_mode(curds)` returns `"parallel"` when `len(curds) >= PARALLEL_THRESHOLD`.

This condition means 2 or more curds.

Otherwise, `select_mode(curds)` returns `"linear"`.

The installed route exposes the same selector as `python3 skills/cook/scripts/cook.pyz mode --count <curd-count>`.

Get the count from the validated `CurdPlan`.

Never get the count from a legacy phase file.

**No-plan fallback.**

Use `select_mode_from_score(score)` only for a PR or fresh branch without a planner handoff.

It returns `"linear"` when `score <= DECOMPOSE_FIRST_THRESHOLD` (250).

It returns `"decompose-first"` above this threshold.

It never returns `"parallel"` without a validated plan and disjointness proof.

**Fast path.**

Use the fast path when `/mold`'s curd-count hint = 1 and the blast radius is low or medium.

Skip the decomposer spawn.

Use the single-coder path.

The 1-curd spec runs in linear mode.

Trust the hint only to skip work, never to pick parallel or bypass `validate_curd_plan`.

## Publication topology preflight

Run `/plate` in topology-preflight mode when the selected mode is `parallel`, the user supplied `--open-pr`, and no pull request exists.

Complete this decision before Phase 1 seed or any worker commit.

Apply `/plate`'s review-shape policy.

Preserve an explicit choice.

For one cohesive review unit, persist `single` without asking.

Ask only once when stacked is recommended or shape is ambiguous.

Record `plate_layout` in the typed handoff evidence.

Read `plate_layout` from that evidence.

Apply the policy `do not ask twice`.

Do not use a legacy manifest to make this decision.

Preserve the detected topology for existing PRs.

Keep runs without `--open-pr` commit-only.

Complete this decision before the Phase 1 seed or any worker commit.

**Seed (coder).**

After you fix the topology, prepare only files that two or more curds share.

Do not hide curd-owned behavior in the seed.

## Milknado seam

Before any curd runs, probe which role the available toolset supports.

Use `src/easy_cheese/shared/fanout/milknado.py::probe`.

The installed route exposes the probe as `python3 skills/cook/scripts/cook.pyz milknado --tools "<available tool names>"`.

The probe returns one of three roles:

- **`engine`** — Both `milknado_todo_claim` and `milknado_node_verify` are present.
  Milknado owns the DAG, per-node worktrees, and verify-until-green process.
  `/cook` dispatches the typed curd operation for each claimed node.
- **`tracker`** — Only `milknado_todo_add` is present.
  Milknado records typed curd status but does not run curds.
  `/cook` still owns native fan-out.
- **`none`** — No milknado tools are present.
  Native fan-out owns worktrees from start to finish.
  Native curds self-verify once in-worker.

This parity difference is deliberate.

Native curds self-verify once.

Milknado verifies until green when it is present.

Announce milknado's absence once.

Then proceed.

`none` never blocks the workflow.

`none` never changes the typed contract.

## Phase-chain topology

| Stage | Chain | Canonical handoff |
| --- | --- | --- |
| Planner | `planner-request → PlannerResult → validated CurdPlan` | `PlannerResult` |
| Per curd | `cook(CurdPlan) → reviewer(age) → confirmed diagnosis → cure(CurdPlan, bindings) → reviewer(final age)` | `CurdResult` + `CureDiagnosisBinding` |
| Post-merge | `press → age → cure → age` over the merged typed results | final `CurdResult` |
| Per curd, closed N/A | `coder(cook) → reviewer(age) → coder(cure) → reviewer(final age)` | `not-applicable-curd` |
| Post-merge, closed N/A | `age → cure → age` | `not-applicable-postmerge` |

Per-curd workers own incomplete implementation slices.

They never run Press while sibling curds remain unfinished.

After wiring and merge, the orchestrator runs one global Press → Age/Cure chain.

The per-curd chain can end early when a review returns a clean completion.

The host still records one normalized result.

The host also keeps the plan's dependency closure consistent.

A failed review never continues directly to Cure.

The host must materialize and confirm a diagnosis.

Then the host must bind the diagnosis to the exact curd.

Publish a terminal age only when it writes `next: done`.

**Projected dispatch count.**

The upper bound that `/cook` shows at the decompose gate depends on the disposition.

For RED-required, use 1 seed + 4 × curds + 4 post-merge = `5 + 4 × curds`.

For closed N/A, use 1 seed + 4 × curds + 3 post-merge = `4 + 4 × curds`.

A first-age `clean_complete` shortens a RED curd to 2 dispatches.

A first-age `clean_complete` shortens an N/A curd to 2 dispatches.

Exclude wiring dispatches.

Wiring rows exist in the manifest, not the curd block.

## Recovery and aggregate gates

- **Worker exhaustion.**
  A worker can run out of context or turns.
  The worker writes a partial typed handoff with `status: needs-context: <gap>`.
  The orchestrator re-dispatches that curd once.
  Fold the gap into the context.
  Set `--retry-count 1`.
  A second `needs-context` at that phase halts.
  The router caps the loop itself.
  The host finalizes the blocked `CurdResult`.
  The host continues to harvest the other results.
  The host reports the curd.

- **Aggregate-gate conflict.**
  After you harvest all wave results, run the project gates over the merged tree.
  Distinguish a real cross-curd conflict from harmless generated drift.
  A real cross-curd conflict occurs when curds pass individually but collide in aggregate.
  The post-merge Cure can absorb harmless generated drift.
  Never automatically resolve a real conflict.

- **Compute the verdict** —
  Normalize each typed `CurdResult`.
  A halted result stops the workflow.
  A clean first review finalizes that curd without Cure.
  After wiring and merge, the project gates must pass before the global post-merge chain.

## Worktree harvest and teardown

- Give each curd its own worktree.
  First create the worktree when the host has no native worktree-isolated sub-agent primitive.
  Use `python3 skills/cook/scripts/cook.pyz worktree create --slug <id> --base <orchestrator-branch>`.
  The command returns `{path, branch}`.

- Run the disposition-specific sequential chain for each curd.
  Persist one normalized `CurdResult` for each curd.
  Per-curd workers never run Press.

- After every curd returns, harvest its commits.
  Then tear down each curd worktree.

- Harvest with `python3 skills/cook/scripts/cook.pyz worktree harvest --branch <curd-branch> --onto <orchestrator-branch>`.
  On conflict, invoke `/melt`.
  If `/melt` cannot resolve the conflict, use per-curd PRs.
  The worktrees share one object store.
  Therefore, this operation does not require `git fetch`.

- Tear down with `python3 skills/cook/scripts/cook.pyz worktree teardown --path <worktree-path> --branch <curd-branch>`.
  A completed run leaves no `worktree-agent-*` branch.
  It also leaves no stray worker directory.

- Run wiring in dependency order.
  Then run the one global `press → age → cure → age` integration pass.

- `/cook` alone performs harvest.
  The Cook fan orchestrator owns the terminal `/plate` dispatch.
  Terminal Cure owns publication only in the linear chain.
  Never dispatch `/plate` during the run.

After each wave, persist the typed `PlannerResult`, `CurdResult` values, diagnosis bindings, and gate evidence in the handoff artifact.

These records support recovery and publication provenance.

They do not create a second workflow state machine.

## --resume <slug>

`--resume <slug>` re-enters a crashed wave-fan run.

It loads the latest typed handoff from `.cheese/cook/<slug>.md` and its referenced artifacts.

Fail fast if the handoff is missing, malformed, stale, or unresolved.

Also fail fast if its referenced `PlannerResult` or `CurdPlan` has these conditions.

Use `resolve_artifact` to resolve the references.

Run `validate_curd_plan` again before selecting the next dependency wave.

Verify that every retained commit or artifact reference still exists.

Resume only curds whose typed result is incomplete.

Never infer progress from an old phase name.

A bare re-run has no `--resume`.

If a bare re-run finds an existing handoff, stop.

Tell the user to resume or remove the handoff.

Never silently remove typed evidence.

## Resolution provenance and the output contract

Resolve every planner, curd, review, diagnosis, and Cure dispatch against the typed-role table in `SKILL.md`'s `## Agent resolution` section.

Also use the shared protocol in [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md):

| Work | Preferred types |
| --- | --- |
| Plan the spec | planner, general |
| Cook, press, cure, seed, or wiring | coder |
| Every age pass | reviewer |
| Harvest and plate | parent |

The resolver first filters required capabilities, tools, permissions, and isolation.

Then the resolver selects minimum power and maximum specificity.

A prompt-only, read-only general fallback can continue with `degraded: true`.

A missing required tool or write permission halts the workflow.

Every handoff and final summary includes the resulting `agent_resolution` block.

This block keeps the role, fallback, and degradation visible.

The fan pathway and single-coder path use the same final-summary shape.

`SKILL.md` defines this shape in `## Handoff slug` and `## Output`.

Publish a terminal age only when it writes `next: done`.

Do not publish a terminal age that writes `next: cure`.

Do not publish a terminal age that omits `next`.
