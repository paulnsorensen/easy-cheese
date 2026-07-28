# /cook — Fan pathway mechanics

Full mechanics for `/cook`'s wave-fan pathway: the existing-handoffs guard, mode selection, publication-topology preflight, the milknado seam, phase-chain topology, the deterministic phase loop, worker-exhaustion/aggregate-gate recovery, worktree harvest and teardown, `--resume <slug>`, and resolution provenance. `SKILL.md`'s `## Fan pathway` keeps the three-shape gate (a/b/c) and the wave cap; this file is everything downstream of that gate.

## Existing handoffs guard

Before dispatching the decomposer for an un-curded big spec, check whether any of `.cheese/cook/<slug>.md`, `.cheese/press/<slug>.md`, `.cheese/age/<slug>.md`, `.cheese/cure/<slug>.md` already exist. If any do, stop — print only the ones present — and tell the user to either run `/cheese --continue <slug>` to resume from the latest phase or `rm` the listed files to start fresh. Never wipe an existing handoff silently:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest phase, or
`rm` the listed files to start fresh.
```

## Mode selection

Whether a decomposed spec wave-fans or stays a single dispatch is a deterministic rule, not a deliberation. `src/fanout/mode.py` is the single source of truth: `PARALLEL_THRESHOLD = 2`, and `select_mode(curds)` returns `"parallel"` when `len(curds) >= PARALLEL_THRESHOLD`, else `"linear"`. The same check runs from the shell as `python3 skills/ultracook/scripts/ultracook.pyz mode --count <curd-count>` — `mode` is still one of the `.pyz`'s live subcommands (alongside `baseline`, `phase_decision`, `worktree`, `milknado`, `validate_decomposition`, `validate_manifest`, `manifest_update`, `wiring_topo_sort`) even though the skill that used to own the CLI is retired. There is one threshold in the tree: the selector, `validate_decomposition` (`python3 skills/ultracook/scripts/ultracook.pyz validate_decomposition <manifest>`, re-run on validation failure, max 2 retries — validates the manifest-level `seed[]`/`curds[]`/`wiring[]` shape, distinct from `curd_block.py`'s spec-level `curds`/`waves` schema above), and `/mold`'s curd-count hint all read it. A 1-curd spec runs the single-coder path — `select_mode` calls this linear mode (no wave-fan); 2 or more curds selects parallel mode and always wave-fans.

**No-curd-block fallback.** `select_mode_from_score(score)`, also in `src/fanout/mode.py`, is the fallback for a PR or fresh branch with no handoff — no curd block at all. It returns `"linear"` at `score <= DECOMPOSE_FIRST_THRESHOLD` (250) and `"decompose-first"` above it, and it never returns `"parallel"` for any input. The same check runs from the shell as `python3 skills/ultracook/scripts/ultracook.pyz mode --score <score>`. With no curd block there is no file-disjointness proof, so fanning coders is unsafe at any size — a large no-handoff branch triggers the decomposer, not blind parallelism. Curd count stays authoritative whenever a curd block exists: `PARALLEL_THRESHOLD` and `select_mode(curds)` above are unchanged, and the score fallback fires only when no curd block is present. The underlying principle: coders write, reviewers and debuggers read. File-disjointness exists to stop two writers colliding; read-only fan-out carries no such constraint, which is why the age ladder and the pasteurize policy need no curd block, and why `/cook` cannot fan without one.

**Fast-path.** When `/mold`'s curd-count hint = 1 and blast radius is low or medium, skip the decomposer spawn entirely and go straight to the single-coder path — the hint is trusted only to skip work in this indivisible case, never to pick parallel; the decomposer remains authoritative for hint >= 2 or absent.

## Publication topology preflight

When the selected mode is `parallel`, `--open-pr` is present, and no PR exists, dispatch `/plate` in topology-preflight mode against `.cheese/ultracook/<slug>/manifest.yaml` **before Phase 1 seed or any worker commit** — before **Seed (coder).** runs (`## Worktree harvest and teardown` below). Apply `/plate`'s review-shape policy: preserve an explicit user choice, persist `single` without asking for one cohesive review unit, or ask once when stacked is recommended or shape is ambiguous — do not ask twice. Read back `plate_layout: single | stacked` and re-run `validate_manifest`. Existing PRs preserve detected topology; runs without `--open-pr` do not preflight because their workers remain commit-only.

## Milknado seam

Before running any curd, probe which of three roles the available toolset supports (`src/fanout/milknado.py::probe`, exposed as `python3 skills/ultracook/scripts/ultracook.pyz milknado --tools "<available tool names>"`):

- **`engine`** — both `milknado_todo_claim` and `milknado_node_verify` are present. milknado owns the DAG, per-node worktrees, and **verify-until-green** (it re-runs the project gates itself until they pass); `/cook` spawns the phase agent per claimed node instead of managing worktrees directly.
- **`tracker`** — only `milknado_todo_add` is present. milknado records curd status but doesn't run curds; `/cook` still owns native fan-out.
- **`none`** — no milknado tools. Native fan-out end to end: `/cook` owns worktrees itself, and **curds self-verify** by running the project gates once, in-worker.

This parity difference is deliberate: native curds self-verify (gates run once, in-worker); milknado, when present, does verify-until-green (re-runs gates until green). See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md) for the detect-and-degrade contract — announce milknado's absence once and proceed; `none` is never a blocker.

## Phase-chain topology

| Stage | Chain | `phase_decision --table` |
| --- | --- | --- |
| Per curd | `coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)` | `parallel-curd` |
| Post-merge, once, over the merged diff | `press → age → cure → age` | `parallel-postmerge` |

This is not the old 7-spawn linear `/ultracook` chain (`cook → press → age → cure → age → cure → age`, table `linear` in `src/fanout/phase_decision.py`) run verbatim — that table still backs the single-coder path's own `--auto` chain (`../auto-mode.md`) — the fan pathway's own topology is the two tables above. The per-curd table can end early: a first age reporting `next: done` **clean-completes** the curd (`action=clean_complete`) and skips cure and the final age, because nothing has touched the tree since that review and the post-merge pass re-covers the merged diff anyway. The post-merge table never short-circuits on that signal — it is the last review before publication, so cure and final age always run, and only a final-age `next: done` is publishable; `next: cure` or a missing `next` halts.

## Deterministic phase loop

Between dispatches, `/cook`'s fan-pathway orchestrator decides the next action mechanically:

1. **Parse the slug** — `python3 shared/scripts/read_handoff_slug.py --phase <phase> --slug <slug>` (the same helper `/age`'s own flow calls, e.g. `skills/age/SKILL.md`) → JSON `{status, next, artifact, orientation, halt_reason}`. Never infer success from a sub-agent's last line of stdout — read the file.
2. **Compute the verdict** — `python3 skills/ultracook/scripts/ultracook.pyz phase_decision --phase-index <i> --status <status> [--next <next>] --table parallel-curd|parallel-postmerge` (`src/fanout/phase_decision.py`) → JSON `{action, next_phase, exit_message}`. `action=halt` surfaces the reason and stops; `action=clean_complete` (per-curd table only) records the first age's review context as final and skips ahead; `action=spawn` dispatches `next_phase`.

## Worker exhaustion and aggregate-gate recovery

- **Worker exhaustion.** A curd worker that runs out of context or turns writes a partial `status: halt: <reason>` slug. Retry that curd **once** with the error folded into its context; if it halts again, mark it failed, keep harvesting the rest, and report the failed curd in the final summary — never silently drop it.
- **Aggregate-gate cross-curd conflict vs. drift.** After harvesting all curds, run the project gates over the merged tree. On failure, distinguish a **real cross-curd conflict** (curds passed individually but collide in aggregate — a decomposer error → halt and surface it) from **harmless drift** (a formatter or generated-file delta the post-merge cure pass can absorb → continue). Never auto-resolve a real conflict.

(ported from the retired `/ultracook`'s recovery-paths section, issue #194)

## Worktree harvest and teardown

- Give each curd its own worktree; when the host lacks a native worktree-isolated sub-agent primitive, create it first with `python3 skills/ultracook/scripts/ultracook.pyz worktree create --slug <id> --base <orchestrator-branch>` (returns `{path, branch}`).
- Harvest by cherry-picking each curd branch onto the orchestrator branch: `python3 skills/ultracook/scripts/ultracook.pyz worktree harvest --branch <curd-branch> --onto <orchestrator-branch>` — the parent and sub-agent share one `.git` object store, so this needs **no `git fetch`**. On conflict, invoke `/melt`; if it cannot resolve, fall back to per-curd PRs.
- Tear down every worktree after harvest: `python3 skills/ultracook/scripts/ultracook.pyz worktree teardown --path <worktree-path> --branch <curd-branch>`. `/cook`'s fan pathway owns teardown — worktrees leak otherwise. A completed run leaks nothing: no `worktree-agent-*` branch (the one exempt case is the repair pathway's own `worktree-agent-repair-*` branch, `skills/plate/SKILL.md`, which has an independent lifecycle) and no stray `.claude/worktrees/agent-*` directory.

**Wave-fan mechanics, in order** (baseline capture through publication; each step's literal `manifest_update set-phase` call is given so the phase-string writer/reader/schema round-trip stays exact):

- Capture the run's broad-gate baseline once, in the orchestrator's own tree, before Seed (see `SKILL.md`'s `## Baseline capture` and [`quality-gates.md`](quality-gates.md)).
- **Seed (coder).** Dispatch a `coder` for shared types/interfaces in an isolated worktree, commit via `/plate` in commit-only mode, then `manifest_update set-phase --manifest <path> --phase seed_complete`.
- Per curd (`## Worktree harvest and teardown`, `## Phase-chain topology` above): run the five sequential dispatches; mark each curd `running` then `completed`/`failed`; after all curds return, `manifest_update set-phase --manifest <path> --phase curds_complete`.
- Harvest and tear down every curd; `manifest_update set-phase --manifest <path> --phase merge_complete`.
- Run wiring tasks topo-sorted (`ultracook.pyz wiring_topo_sort`), dispatching a `coder` sequentially within each wave; `manifest_update set-phase --manifest <path> --phase wiring_complete` then immediately `manifest_update set-phase --manifest <path> --phase final_merge_complete` (wiring commits land directly on the orchestrator branch in this flow, so the two markers coincide).
- Run the post-merge integration pass (`## Phase-chain topology` above); `manifest_update set-phase --manifest <path> --phase post_review_complete`.
- `/cook` itself alone performs harvest and, at the very end, dispatches `/plate` — never mid-run; `manifest_update set-phase --manifest <path> --phase pr_publish_complete` after `/plate` verifies publication.

Every `set-phase` call above uses the same `manifest_update` CLI (`src/fanout/manifest_update.py`), atomic and re-validated against the schema: `manifest_update set-phase --manifest <path> --phase <phase-name>`, `manifest_update set-curd-status --manifest <path> --curd <id> --status running|completed|failed [--commit-sha <sha> --base-commit <sha> --reviewed-tree-oid <oid> --diff-hash sha256:<hex> --scope <path> ...]`, and `manifest_update set-wiring-status --manifest <path> --wiring <id> --status running|completed|failed [--commit-sha <sha>]`.

## --resume <slug>

`--resume <slug>` is the sanctioned re-entry into a crashed wave-fan run. It reads `.cheese/ultracook/<slug>/manifest.yaml` (path unchanged from the retired `/ultracook`) and continues from where the crash left off:

1. **Load the manifest.** If missing, fail fast: `"no manifest at .cheese/ultracook/<slug>/manifest.yaml — nothing to resume"`. Optionally re-check its shape with `python3 skills/ultracook/scripts/ultracook.pyz validate_manifest <path>`.
2. **Rebase guard.** For every non-null `commit_sha` recorded on a completed seed item, curd, or wiring row, run `git cat-file -e <sha>` (the schema permits `commit_sha: null` on a `completed` row — skip those). If any recorded SHA is gone, fail fast and name the missing SHA — resuming onto rewritten history would harvest the wrong tree. This guard is orchestrator prose, not new engine code; there is no auto-recovery.
3. **Restore continuity.** Read `phase_summary` and `carry_forward` from the manifest — the cross-seam continuity a resumed orchestrator reasons from, since a fresh spawn has no conversation history.
4. **Pick up at the next incomplete phase.** Read the `phase` field, one of the ordered enum in `skills/ultracook/references/manifest-schema.json`: `gate_approved -> seed_complete -> curds_complete -> merge_complete -> wiring_complete -> final_merge_complete -> post_review_complete -> pr_publish_complete`. Continue from the next incomplete phase, skipping every curd/wiring row already `completed`. Report `Resuming <slug> from phase <next-phase>`. If `phase` is already `pr_publish_complete`, the run is done — report and stop.

A bare re-run (no `--resume`) that finds an existing manifest stops and tells the user to pass `--resume <slug>` to continue or `rm -r .cheese/ultracook/<slug>/` to start fresh — never wipe an existing manifest silently.

## Resolution provenance and the output contract

Every phase and curd dispatch resolves against the typed-role table in `SKILL.md`'s `## Agent resolution` section and the shared protocol in [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md):

| Work | Preferred types |
| --- | --- |
| Decompose the spec | planner, general |
| Cook, press, cure, seed, or wiring | coder |
| Every age pass | reviewer |
| Harvest and plate | parent |

The resolver filters for required capabilities/tools/permissions/isolation first, then picks minimum power and maximum specificity; a prompt-only read-only general fallback may continue with `degraded: true`, while a missing required tool or write permission halts. Typed-role shorthand, ported verbatim from the retired `/ultracook`'s Rules: planner/general for decomposition, coder for cook/press/cure/seed/wiring, reviewer for every age, and parent ownership for harvest and plate. Every phase's handoff slug and the fan pathway's own summary carry the resulting `agent_resolution` block, so role, fallback, and degradation stay visible rather than implicit.

A terminal age is **publishable only with `next: done`**; `next: cure` or a missing `next` halts as not publishable — this applies at the end of both the per-curd table and the post-merge table above, and to the single-coder `--auto` chain's own terminal age (`../auto-mode.md`).

The fan pathway and the single-coder path keep the same behavioral output and final-summary shape (`SKILL.md`'s `## Handoff slug`, `## Output`); required `agent_resolution` provenance records the selected role, fallback, and topology regardless of which pathway ran.
