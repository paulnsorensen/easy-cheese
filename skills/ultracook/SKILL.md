---
name: ultracook
description: Pipeline one approved high-blast-radius spec through fresh-context sub-agents in one of two modes the decomposer picks. Use when the user has such a spec — phrases like "/ultracook .cheese/specs/<slug>.md", "ultracook this", "run the full pipeline in isolation", "parallelize this spec", "fan out the implementation", "many curds", "send it through the cave", "pipeline with no contamination". Do NOT use for short focused changes, fuzzy planning, or review-only work.
license: MIT
metadata: {dispatches-agents: true}
---

# /ultracook

Use this skill when the user wants an approved high-blast-radius spec run forward without per-step approval, **and** wants each phase to reason in fresh context — blind to the previous phase's chain-of-thought. `/ultracook` carries two modes; the decomposer picks between them:

- **Linear mode** — for an indivisible spec: the deep `cook → press → age → cure → age → cure → age` chain, all `--auto`, each phase a fresh sub-agent. This is the sub-agent-transport sibling of `/cook --auto`.
- **Parallel mode** — for a decomposable spec: fan the spec out into independent behavioural curds; run typed `cook → press → age → cure → age` phase agents sequentially in each curd's worktree; harvest the curd branches; then run typed `press → age → cure → age` over the merged diff. The parent alone performs harvest and `/plate`. Ends in 1–N reviewable PRs. (This folds in the retired `/cheese-factory`.)

Do not use it for short focused changes (`/cook --auto` is cheaper and continuous), for fuzzy planning (`/mold`), or for review-only work (`/age`).

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Inputs

Accept one of:

- A spec path. When explicit, it points wherever the user wrote the spec.
- A bare slug whose spec lives in the per-project durable corpus (see `../cheese/references/formatting.md` § Corpus location).
- A pasted spec, with a slug supplied alongside.

`/ultracook` does not accept fuzzy or open-ended asks — those go to `/mold` first. The orchestrator assumes the contract is already locked.

Optional flags:

- `--open-pr` — allow publication when no PR exists. Linear mode resolves topology at terminal before its first commit. Parallel mode runs `/plate` topology preflight before seed, curd, or wiring commits: an explicit choice wins, obviously cohesive work persists `single` without asking, and a stack recommendation or ambiguous shape asks once. Phase-only cure sub-agents never publish.
- `--resume <slug>` — resume a crashed **parallel** run from its manifest at `.cheese/ultracook/<slug>/manifest.yaml`: read the latest completed phase and continue from the next incomplete one (see `## --resume <slug>`). Linear runs resume via `/cheese --continue <slug>` instead.

## Mode selection — the decomposer is the gate

Before the phase loop runs, the decomposer picks the mode. This is the one authoritative gate; the `/mold` curd-count hint is advisory only.

1. **Decompose** — resolve a fresh-context planner (or compatible general agent) through `../cheese/references/agent-resolution.md`, then dispatch `references/decomposer-prompt.md` to produce `seed[]`, `curds[]`, and `wiring[]` from the spec. Validate with `python3 skills/ultracook/scripts/ultracook.pyz validate_decomposition <manifest>` and re-run on validation failure (max 2 retries).
2. **Pick the mode** — `python3 skills/ultracook/scripts/ultracook.pyz mode --count <curd-count>` → `linear | parallel`. The canonical `PARALLEL_THRESHOLD` (2) lives in the engine: a decomposition of **2 or more** curds routes to **parallel mode**; **1** curd stays **linear**. There is one threshold in the tree — the selector, `validate_decomposition`, and the mold hint all read it.
3. **Probe the engine seam** — `python3 skills/ultracook/scripts/ultracook.pyz milknado --tools "<available tool names>"` → `engine | tracker | none`. This decides how parallel mode runs curds (see `## Parallel mode`); linear mode ignores it.
4. **Publication topology preflight** — when the selected mode is `parallel`, `--open-pr` is present, and no PR exists, dispatch `/plate` in topology-preflight mode against `.cheese/ultracook/<slug>/manifest.yaml` **before Phase 1 seed or any worker commit**. Apply `/plate`'s review-shape policy: preserve an explicit user choice, persist `single` without asking for one cohesive review unit, or ask once when stacked is recommended or shape is ambiguous. Read back `plate_layout: single | stacked` and re-run `validate_manifest`. Existing PRs preserve detected topology; runs without `--open-pr` do not preflight because their workers remain commit-only.

Helper resolution — including the `${CLAUDE_SKILL_DIR}` packaged-helper fallback — follows [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) § Helper resolution.

A 1-curd spec runs `## Flow` (linear mode) unchanged. A 2+-curd spec runs `## Parallel mode`.

## Flow (linear mode)

1. **Resolve slug** — derive `<slug>` from the input. If a spec path is given, the slug is the basename without `.md`; if a bare slug is given, confirm the spec exists at the durable path the spawned `/cook` resolves (`python3 shared/scripts/artifact_path.py specs <slug>`; if the host only exposes the packaged helper, `python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>` is the fallback; see `../cheese/references/formatting.md` § Corpus location).
2. **Guard against re-entry** — if any of `.cheese/{cook,press,age,cure}/<slug>.md` already exist, stop with a one-line list of the existing handoffs and tell the user to either run `/cheese --continue <slug>` to resume from the latest phase or `rm` the relevant files to start fresh.
3. **Phase loop** — for each phase in `cook, press, age, cure, age, cure, age`, resolve the phase role through `../cheese/references/agent-resolution.md`, spawn a fresh sub-agent (see `## Sub-agent contract` below), wait for it to return, then read each phase's handoff slug and compute the next action deterministically:
   1. **Parse the slug** — `python3 shared/scripts/read_handoff_slug.py --phase <phase> --slug <slug>` → JSON `{status, next, artifact, orientation, halt_reason}`. Do not infer success from the sub-agent's last line of stdout — read the file.
   2. **Compute the verdict** — `python3 skills/ultracook/scripts/ultracook.pyz phase_decision --phase-index <i> --status <status> [--next <next>]` → JSON `{action, next_phase, exit_message}` (if the host only exposes the packaged helper, `python3 ${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz phase_decision ...` is the fallback). `<i>` is the **0-based** position in the chain (0 = cook, 1 = press, … 6 = the final age) — one less than the spawn `#` in the "Phases and slug paths" table below.
   3. **Act on the verdict**:
      - `action=halt` → surface the `exit_message` (which contains the halt reason verbatim) and stop. Never push on a halt.
      - `action=stop_early` → age reported `next: done`; the diff is clean at the medium+ severity floor. Stop early with a clean summary.
      - `action=stop` → the terminal age reported `next: done`. Proceed to `/plate`. A terminal age that reports `next: cure` or omits `next` halts as not publishable.
      - `action=spawn` → spawn `next_phase` and continue.
4. **Terminal plate** — after the final non-halt stop, dispatch `/plate` for an existing PR. With `--open-pr`, dispatch `/plate` for a new PR; before its first commit it honors an explicit choice, proceeds with an obviously cohesive single PR, or asks when stacked is recommended or shape is ambiguous. A halt never commits or publishes.
5. **Final summary** — report phases, findings, final age path, and `/plate` outcome (or `review the diff, then /plate when ready`).

## Phases and slug paths

Every spawn uses the canonical `/<phase> <slug> --auto` form. Cook accepts a bare slug per its Inputs section; the other phases already resolve their paths from the slug.

| # | Phase invocation                          | Handoff slug                  |
|---|-------------------------------------------|-------------------------------|
| 1 | `/cook <slug> --auto`                     | `.cheese/cook/<slug>.md`      |
| 2 | `/press <slug> --auto`                    | `.cheese/press/<slug>.md`     |
| 3 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md`       |
| 4 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md`      |
| 5 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (overwritten) |
| 6 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md` (overwritten) |
| 7 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (final report) |

### Cap enforcement

The two-cure-pass cap is enforced by **chain length, not by age** — age boots in fresh context and cannot count prior passes. So:

- The chain table has exactly seven entries, with two cure spawns (#4 and #6) and three age spawns (#3, #5, #7).
- Each age spawn writes `next:` from what it observes on its own run: `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low), `next: done` when none do. Before the terminal position this drives early-stop; at the terminal position only `next: done` is publishable. `next: cure` or a missing `next` halts because the cure-pass cap is exhausted with unresolved review work.
- `/ultracook` does not pass a pass-ordinal hint to age. Age has no need to know whether it is age₁, age₂, or age₃; the orchestrator owns the position.

## No-chain isolation directive

Each phase's existing `--auto` contract chains forward in-session — `/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, etc. `/ultracook` overrides that behaviour: every spawn must run only its own phase, write the slug, and stop. The orchestrator owns the chain.

The override travels in the spawn prompt as the explicit no-chain directive: `Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. The /ultracook orchestrator is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with status: halt: <reason> and stop; do not silently timeout.`

Each phase's SKILL.md `## Auto mode` section honours this directive — see `skills/<phase>/SKILL.md` `### When invoked from /ultracook` for the per-phase contract amendment.

## Sub-agent contract

Resolve every dispatch against the local role table in `## Agent resolution` and the shared protocol in [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md). The resolver first filters for required capabilities, tools, permissions, and isolation, then selects minimum power and maximum specificity. A prompt-only read-only general fallback may continue with `degraded: true`; a missing required tool or write permission halts.

## Handoff slug schema

Every phase writes its handoff slug to `.cheese/<phase>/<slug>.md` with the following minimum shape (prepended as frontmatter or inline at the top of richer reports such as age and press):

```markdown
status: ok | halt: <one-line reason>
next: <phase-name | done>
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this phase did>
```

`status: ok`: phase finished cleanly, `next` names the next phase. `status: halt: <reason>`: the chain stops and surfaces the reason verbatim; for cook and press slugs `next` still names the runnable resume phase for `/cheese --continue` (age and cure halt slugs keep their finding-driven `next:` values — `cure | done` and `age | done`). `next: done` is terminal — age writes it when the diff is clean at the medium+ floor (early-stop).

For phases that already write rich reports (`/age`, `/press`, `/cure` once extended, `/cook` once extended), the slug schema is prepended at the top of the same file — there is no second file. The schema is the contract; the body is whatever the phase normally writes.

## When auto mode stops early

Beyond the halt and age `next: done` cases in Flow step 3, one more early-stop case is an error, not a clean stop:

- A phase's slug file is missing after the sub-agent returns (the sub-agent did not write its handoff). Before surfacing this as a hard stop, attempt a **re-dispatch** with the foreground-only directive reinforced in the prompt. Cap re-dispatches at **2** per phase. After the second failed re-dispatch with no slug, print: `"<phase> did not write handoff after 2 re-dispatch attempts — check sub-agent logs"` and stop. Track the attempt count per phase in the orchestrator loop; reset to 0 when advancing to a new phase.

In every early-stop case, surface the slug file path so the user can read the full report. The natural terminal case requires the final age slug to say `next: done`; table exhaustion alone never authorizes publication.

## Existing handoffs

When any `.cheese/{cook,press,age,cure}/<slug>.md` exist (per Flow step 2), scan all four paths and print only the ones present:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest phase, or
`rm` the listed files to start fresh.
```

## Output

A short final summary, after the chain stops (success or early stop):

```
Ultracook summary — <slug>
Passes completed: <list of phase names that ran>
Findings:         <fixed count> applied, <count> deferred (cure-report path)
Final age:        .cheese/age/<slug>.md
Next step:        review the diff, then /plate when ready
```

If the chain stopped on a halt, replace "Next step" with the halt reason and the path of the phase that surfaced it.

## Parallel mode

Reached when the decomposer produces **2 or more** curds (`mode → parallel`). Parallel mode is **curd-light** — each curd runs its own review, then one integration pass reviews the merged diff. Behavioral output remains stable across modes, while required resolution provenance records the selected role, fallback, and topology. The per-run manifest lives at `.cheese/ultracook/<slug>/manifest.yaml`.

### Topology

1. **Seed (coder).** Resolve and dispatch a `coder` for shared types/interfaces in an isolated worktree. It runs project gates and returns a handoff; the parent invokes `/plate` in commit-only mode.

   After the seed commit, advance the manifest: `python3 skills/ultracook/scripts/ultracook.pyz manifest_update set-phase --manifest .cheese/ultracook/<slug>/manifest.yaml --phase seed_complete`.
2. **Per-curd fan-out.** Give each curd its **own worktree**, then make five top-level, fresh-context dispatches sequentially in that same worktree: `coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)`. Use `references/curd-prompt.md` and the `PARALLEL_CURD` phase table: `python3 skills/ultracook/scripts/ultracook.pyz phase_decision --phase-index <i> --status <status> [--next <next>] --table parallel-curd`. Before each age dispatch record and pass the review context: base commit SHA, reviewed tree OID, deterministic diff hash, and review scope. The first age never short-circuits the table, including on `next: done`; cure and final age always run. The final age must return `next: done`; `next: cure` or a missing value halts that curd as not publishable. After a clean final age, the parent invokes `/plate` in commit-only mode.
   - **Worktree floor (no native primitive).** When the host lacks a native worktree-isolated sub-agent primitive, the orchestrator first creates each curd's worktree with `python3 skills/ultracook/scripts/ultracook.pyz worktree create --slug <id> --base <orchestrator-branch>` (returns `{path, branch}`), then dispatches each phase agent into that path. Harvest (step 3) and teardown (step 4) proceed unchanged.

   As each curd dispatches, mark it running (`manifest_update set-curd-status --manifest <path> --curd <id> --status running`); after a clean final age, atomically record completion and its final review identity (`--status completed --commit-sha <sha> --base-commit <sha> --reviewed-tree-oid <oid> --diff-hash sha256:<hex> --scope <path>`; repeat `--scope` for multiple paths), or record `--status failed`. After **all** curds return, `manifest_update set-phase --manifest <path> --phase curds_complete`.
3. **Harvest (fan-in).** Cherry-pick each curd branch onto the orchestrator branch with `python3 skills/ultracook/scripts/ultracook.pyz worktree harvest --branch <curd-branch> --onto <orchestrator-branch>`. The parent and sub-agent share one `.git` object store, so this needs **no `git fetch`**. On conflict, invoke `/melt`; if it cannot resolve, fall back to per-curd PRs.

   After all curd branches are cherry-picked onto the orchestrator branch, `manifest_update set-phase --manifest <path> --phase merge_complete`.
4. **Teardown.** After harvesting each curd, `python3 skills/ultracook/scripts/ultracook.pyz worktree teardown --path <worktree-path> --branch <curd-branch>` removes the worktree and deletes its branch. The engine owns teardown — worktrees leak otherwise; a completed run leaves no `worktree-agent-*` branch or `.claude/worktrees/agent-*` dir.

Helper resolution — including the `${CLAUDE_SKILL_DIR}` packaged-helper fallback — follows [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) § Helper resolution.
5. **Wiring (coder).** Resolve a `coder` for each topo-sorted `wiring[]` integration task (`ultracook.pyz wiring_topo_sort`) and dispatch sequentially within each wave.

   Mark each wiring row as it runs (`manifest_update set-wiring-status --manifest <path> --wiring <id> --status running|completed|failed [--commit-sha <sha>]`). After the last wave, `manifest_update set-phase --manifest <path> --phase wiring_complete`, then immediately `manifest_update set-phase --manifest <path> --phase final_merge_complete`: wiring commits land directly on the orchestrator branch in this flow (no distinct wiring-merge action — the retired cheese-factory's separate Phase 5 final-merge is folded in), so the two markers coincide.
6. **Post-merge review.** Make four top-level, fresh-context dispatches on the orchestrator tree: `coder(press) → reviewer(age) → coder(cure) → reviewer(final age)`, using the `PARALLEL_POSTMERGE` table (`--table parallel-postmerge`). Before each age dispatch refresh `current_review` and pass its base commit SHA, reviewed tree OID, deterministic diff hash, and review scope in the prompt. The first age never short-circuits the table, including on `next: done`; cure and final age always run. Only a final-age `next: done` may advance; `next: cure` or a missing value halts as not publishable.

   After the final age returns clean, atomically record the final review packet in both `current_review` and `post_review.review_context`: `manifest_update set-post-review --manifest <path> --base-commit <sha> --reviewed-tree-oid <oid> --diff-hash sha256:<hex> --scope <path> [--press-slug <path> --age-slug <path> --cure-slug <path> --findings-applied <n> --findings-deferred <n>]` (repeat `--scope` for multiple paths). Only after that command succeeds, run `manifest_update set-phase --manifest <path> --phase post_review_complete`.
7. **PR plan + parent-owned plate.** Plan the layout (`references/pr-planner-prompt.md`) using the authoritative `manifest.plate_layout` and copy that value into `pr-plan.yaml`. The plan may document why the decomposition supports a stack, but it cannot override an explicit or previously verified choice. The parent dispatches `/plate`; it inventories and verifies all durable artifacts, verifies the manifest and plan selections agree, and reuses the preflight resolution — do not ask twice. It publishes through the ordinary or detected stack-provider path.

   After `/plate` verifies publication, run `manifest_update set-phase --manifest <path> --phase pr_publish_complete` (terminal).

### Manifest advancement + resume continuity

The per-run manifest at `.cheese/ultracook/<slug>/manifest.yaml` is advanced at every phase boundary via the `manifest_update` calls threaded through the topology above (`set-phase`, `set-curd-status`, `set-post-review`, `set-wiring-status` — all atomic writes that re-validate against `references/manifest-schema.json`). The `phase` field records the latest completed phase; per-curd and per-wiring `commit_sha`/`status` fields record what has already landed. `agent_resolution` records the shared resolver decision, while `current_review`, each curd's `review_context`, and `post_review.review_context` bind every age result to a base commit, reviewed tree, diff hash, and scope. At each boundary the orchestrator also refreshes `phase_summary` (a 2-3 sentence self-summary) and `carry_forward` directly in the manifest YAML — these two fields have no dedicated `manifest_update` subcommand, so after the in-place edit re-run `python3 ${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz validate_manifest <path>` to keep the write schema-valid. A fresh `--resume` orchestrator then recovers cross-seam continuity from the manifest rather than from conversation history it does not have.

Lifecycle validation is deliberate: a curd marked `completed` must carry its final `review_context`; `post_review_complete` and `pr_publish_complete` require both `current_review` and `post_review.review_context`. Earlier phases may omit review fields until the corresponding age pass has run.

### milknado engine seam (probe-and-use)

The `milknado` probe from **Mode selection** decides how curds run:

- **`engine`** (`milknado_todo_claim` + `milknado_node_verify` present) — milknado owns the DAG, per-node worktrees, and **verify-until-green**; the orchestrator spawns the agent per claimed node and lets milknado re-run the gates until they pass.
- **`tracker` / `none`** — **native fan-out**: the orchestrator owns worktrees (via the `worktree` helper), and **curds self-verify by running the project gates in-worker**. Parallel mode runs to completion with milknado entirely absent.

**This parity difference is intentional and critical:** native curds self-verify (gates run once, in-worker), while milknado, when present, does verify-until-green (re-runs gates until they pass). See [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md) for the detect-and-degrade contract; announce the absence once and proceed.

### Recovery paths (issue #194)

- **Worker exhaustion.** A curd worker that runs out of context or turns writes a partial `status: halt: <reason>` slug. Retry that curd **once** with the error folded into its context; if it halts again, mark it failed, keep harvesting the rest, and report the failed curd in the final summary. Never silently drop it.
- **Aggregate-gate failure.** After harvesting all curds, run the project gates over the merged tree. On failure, distinguish a **real cross-curd conflict** (the curds passed individually but collide in aggregate — a decomposer error → halt and surface it) from **harmless drift** (a formatter or generated-file delta the post-merge cure can absorb → continue). Do not auto-resolve a real conflict.

### Output contract

Parallel and linear modes keep the same behavioral handoff and final-summary fields (`## Handoff slug schema`, `## Output`). Required `agent_resolution` provenance intentionally makes the selected role, fallback, degradation, and topology visible.

## --resume <slug>

`--resume <slug>` is the sanctioned re-entry into a crashed **parallel** run. (Linear runs carry no manifest — resume those through `/cheese --continue <slug>`, which reads the per-phase handoff slugs.) It reads `.cheese/ultracook/<slug>/manifest.yaml` and continues from where the crash left off:

1. **Load the manifest.** Read `.cheese/ultracook/<slug>/manifest.yaml`. If it is missing, fail fast with `"no manifest at .cheese/ultracook/<slug>/manifest.yaml — nothing to resume"`. Optionally re-check its shape with `python3 ${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz validate_manifest <path>`.
   For `--open-pr` with no existing PR, also read `plate_layout`. If the phase is still `gate_approved` and the value is absent, run `/plate` topology preflight under the same explicit-choice/cohesive-single/stack-recommendation policy and persist the resolution before continuing. If any commit-bearing phase is already complete and the value is absent, halt: the before-commit resolution cannot be reconstructed retroactively. A recorded value is authoritative at terminal publication.
2. **Rebase guard — verify recorded commits still exist.** For every non-null `commit_sha` recorded on a completed seed item, curd, or wiring row, run `git cat-file -e <sha>` — the schema permits `commit_sha: null` on a `completed` row, so skip those rather than passing an empty SHA to `git cat-file`. If any recorded SHA is gone (a rebase or history rewrite dropped it), fail fast and name the missing SHA — resuming onto rewritten history would harvest the wrong tree. Do not auto-recover; this guard is orchestrator prose, not new engine code.
3. **Confirm curd files still match (optional).** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz manifest_update check-files --manifest <path> --root <repo-root>` to detect curd file lists that drifted since the crash; fold any misses into the resumed dispatch context (informational, not a blocker).
4. **Restore continuity.** Read `phase_summary` and `carry_forward` from the manifest — the cross-seam continuity mechanism. A resumed orchestrator reasons from these, never from conversation history (a fresh spawn has none).
5. **Pick up at the next incomplete phase.** Read the `phase` field — the latest completed phase, one of the ordered enum in `references/manifest-schema.json`: `gate_approved → seed_complete → curds_complete → merge_complete → wiring_complete → final_merge_complete → post_review_complete → pr_publish_complete`. Continue from the next incomplete phase in `## Parallel mode` § Topology, skipping every curd/wiring row already marked `completed`. Report `Resuming <slug> from phase <next-phase>`. If `phase` is already `pr_publish_complete`, the run is done — report and stop.

**Guard interaction.** A bare re-run (no `--resume`) that finds an existing `.cheese/ultracook/<slug>/manifest.yaml` stops and tells the user to pass `--resume <slug>` to continue or `rm -r .cheese/ultracook/<slug>/` to start fresh — the same never-wipe posture linear mode applies to its handoff slugs (Flow step 2). `--resume <slug>` is the one sanctioned re-entry, and it never wipes.

## Preferred tools and fallbacks

The orchestrator only needs:

| Need                              | Prefer                | Fallback                          |
|-----------------------------------|-----------------------|-----------------------------------|
| Spawning the per-phase worker     | `Agent()` / harness sub-agent primitive | none — without sub-agent spawn, the fresh-context property cannot be honoured |
| Reading the handoff slug          | `cheez-read` / host file read | host file read                    |
| Detecting existing handoffs       | host file glob / list | `cheez-read` `tilth_list` glob     |

If the host harness does not expose a sub-agent primitive at all, `/ultracook` is the wrong skill — recommend `/cook --auto` instead, which uses the same flag semantics in the parent's own context.

## Rules

- Resolve typed phase agents through the shared protocol: planner/general for decomposition, coder for cook/press/cure/seed/wiring, reviewer for every age, and parent ownership for harvest and plate. Use the minimum capable power and record `agent_resolution`; halt when required tools or write permissions are absent.
- In linear mode the chain is fixed: cook → press → age → cure → age → cure → age, all `--auto`, cure severity floor `medium+` (the `--stake` flag literal is preserved across callers). Parallel mode uses per-curd `cook → press → age → cure → age` and post-merge `press → age → cure → age`. A terminal age is publishable only with `next: done`; `next: cure` or missing `next` halts.
- Read each phase's handoff slug after the sub-agent returns. Do not infer success from the sub-agent's last line — read the file.
- Surface halts verbatim. Do not paraphrase, do not soften, do not "retry" a halted phase silently.
- In parallel mode, own worktree teardown: no `worktree-agent-*` branch or `.claude/worktrees/agent-*` dir may leak after a completed run. State the milknado parity difference (native self-verify vs milknado verify-until-green) when it applies.
- At the terminal, dispatch `/plate` for an existing PR (Rule 11). For a new PR, `--open-pr` is required: linear mode resolves topology before its first commit; parallel mode must have a verified `plate_layout` recorded before any seed, curd, or wiring commit. Explicit choices are authoritative, cohesive singles do not ask, stack recommendations and ambiguous shapes ask once, and no halt may commit or publish.
- Never wipe existing handoffs. Stop and tell the user to use `/cheese --continue` or `rm` by hand.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the final summary with what happened, flag residual risk as `certain | speculating | don't know`, do not manufacture follow-ups.

## Agent resolution

Resolve every phase through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Decompose the spec | planner, general | write (manifest only), fresh-context | powerful | high | compatible planner, then general |
| Cook, press, cure, seed, or wiring | coder | write, isolated-worktree | default | high | compatible coder, then general |
| Every age pass | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |
| Harvest and plate | parent | parent-owned repository state | powerful | high | no fallback; halt |

The manifest and every curd or phase output carry a consistent shared `agent_resolution` block. Resolution provenance intentionally records role and topology.
