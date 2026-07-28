---
name: cook
description: Implement an approved spec or focused unambiguous task through stale-safe source edits. Use when the user wants code written — "implement this", "cook this spec", "/cook .cheese/specs/<slug>.md", or "fix this bug" when the fix is clear; also when the user just says "go" or "ship it" with a spec or clear acceptance criteria in scope. Runs standalone on an unambiguous task — a spec helps but is not required. Do NOT use for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook

Do not use it for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).

## Inputs

Accept one of:

- A spec path. When explicit, read it verbatim wherever it points.
- A bare slug. Resolve it to the durable spec path with `SPEC=$(python3 shared/scripts/artifact_path.py specs <slug>)`, then read `"$SPEC"`. If you're on a host that only exposes the packaged helper, `python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>` is the fallback. The resolver anchors specs at the per-project durable corpus (see `../cheese/references/formatting.md` § Corpus location); this is the form `/ultracook` uses when chaining.
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.
- A clear, unambiguous task — single-file fix, named bug, well-scoped tweak — even without a spec.

Optional flags:

- `--auto` — autonomous mode. Skip every handoff gate, propagate the flag through `/press → /age → /cure`, and fix every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. See `## Auto mode` below.
- `--hard` — propagate through `/press → /age → /cure → /plate`; `/plate` fires `/hard-cheese` only after its final artifact-writing gate.
- `--open-pr` — propagate to terminal `/plate`. A new PR follows `/plate`'s explicit-choice and review-shape policy.
- `--resume <slug>` — resume a crashed **fan** run from its manifest at `.cheese/ultracook/<slug>/manifest.yaml`: read the latest completed phase and continue from the next incomplete one, mirroring old `/ultracook --resume` semantics.

### Standalone fast-path

`/cook` runs without `/mold` when the task is unambiguous. Treat a request as unambiguous when **all three** are present or trivially derivable:

1. **Inputs/outputs are clear.** "Tail returns wrong byte count when file ends without newline" ✓; "make tail better" ✗.
2. **Scope is bounded.** A named function, a single failing test, a specific call site, or a small region of one or two files.
3. **Verification is obvious.** A failing test that can be made to pass, or a runnable command whose output should change in a stated way.

When the fast-path applies, derive a slug from the task (e.g. `tail-trailing-newline`), treat **Contract** as a one-sentence restatement of the request, and proceed directly to **Cut** without a spec round-trip. Route to `/mold` only when one of the three checks fails — silent ambiguity is the cardinal sin.

## Flow

1. **Contract** — confirm behaviour, non-goals, likely scope, quality gates. For standalone fast-path tasks, the contract is the user's request restated in one sentence. If `.cheese/glossary/<slug>.md` exists, read it before implementation so naming follows the resolved canonical terms.
2. **Cut** — write failing tests for the changed behaviour. See `references/tdd-loop.md`.
3. **Implement** — make the cut tests pass with the smallest production change.
4. **Taste-test** — check spec drift, readability, scope, plus three fresh-context lenses (production path, wired callers, locked-decision). Dispatch the fresh-context `reviewer` for multi-file or public-surface diffs; keep the inline check otherwise. Two-round cap. Cost gate, reviewer-model pin, and the coder-nested degrade live in `references/tdd-loop.md`.
5. **Hand off** — produce the package-ready report (`references/package-report.md`), write the handoff slug (`## Handoff slug` below), and prompt the next step via the shared handoff gate (see `## Handoff` below). The default chain is `/press` → `/age` → `/cure`.

## Fan pathway

`/cook`'s single pathway routes a spec through one of three shapes, gated on whether the spec already carries a decomposition.

**(a) Curded spec.** If the spec already carries an embedded `curds:`/`waves:` block (produced by `/mold`'s curdle step, or a sibling curd's prior decomposition), skip straight to wave fan-out below — the decomposition is already locked, no fresh decompose pass runs.

**(b) Un-curded, small.** Ordinary single-coder Cut → Implement → Taste-test, unchanged from today's `/cook` (`## Flow` above). Sizing signal: `/mold`'s curd-count hint is advisory; otherwise use AC count and edit-site estimate. Per the spec's cook-gate row: "un-curded (curd block, else AC count and edit-site estimate) | single vs fan vs decompose-first; wave plan; transport".

**(c) Un-curded, big.** Dispatch the decomposer per `../cheese/references/decomposer.md` (the locked curd-block schema — do not use `../ultracook/references/decomposer-prompt.md`, which produces the incompatible legacy manifest schema) against the spec text to produce a `curd_block`-schema block (`curds[]`, `waves[]`, `decomposer{}`), then validate it with `src/fanout/curd_block.py::validate_curd_block`. Gate with the user by showing the wave plan — exact phrasing: "12 ACs -> 5 curds, 2 waves. Go?" — unless `--auto` is set. Above 2 waves, recommend `/cheese-factory` verbatim: "Recommend cheese-factory above 2 waves; user picks at the gate."

**Wave cap.** Waves are capped at `<=4` curds, enforced by `MAX_WAVE_SIZE` in `src/fanout/curd_block.py` — cited, not reimplemented here.

### Existing handoffs guard

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

### Mode selection

Whether a decomposed spec wave-fans or stays a single dispatch is a deterministic rule, not a deliberation. `src/fanout/mode.py` is the single source of truth: `PARALLEL_THRESHOLD = 2`, and `select_mode(curds)` returns `"parallel"` when `len(curds) >= PARALLEL_THRESHOLD`, else `"linear"`. The same check runs from the shell as `python3 skills/ultracook/scripts/ultracook.pyz mode --count <curd-count>` — `mode` is still one of the `.pyz`'s live subcommands (alongside `baseline`, `phase_decision`, `worktree`, `milknado`, `validate_decomposition`, `validate_manifest`, `manifest_update`, `wiring_topo_sort`) even though the skill that used to own the CLI is retired. There is one threshold in the tree: the selector, `validate_decomposition` (`python3 skills/ultracook/scripts/ultracook.pyz validate_decomposition <manifest>`, re-run on validation failure, max 2 retries — validates the manifest-level `seed[]`/`curds[]`/`wiring[]` shape, distinct from `curd_block.py`'s spec-level `curds`/`waves` schema above), and `/mold`'s curd-count hint all read it. A 1-curd spec runs the single-coder path — `select_mode` calls this linear mode (no wave-fan); 2 or more curds selects parallel mode and always wave-fans.

**No-curd-block fallback.** `select_mode_from_score(score)`, also in `src/fanout/mode.py`, is the fallback for a PR or fresh branch with no handoff — no curd block at all. It returns `"linear"` at `score <= DECOMPOSE_FIRST_THRESHOLD` (250) and `"decompose-first"` above it, and it never returns `"parallel"` for any input. The same check runs from the shell as `python3 skills/ultracook/scripts/ultracook.pyz mode --score <score>`. With no curd block there is no file-disjointness proof, so fanning coders is unsafe at any size — a large no-handoff branch triggers the decomposer, not blind parallelism. Curd count stays authoritative whenever a curd block exists: `PARALLEL_THRESHOLD` and `select_mode(curds)` above are unchanged, and the score fallback fires only when no curd block is present. The underlying principle: coders write, reviewers and debuggers read. File-disjointness exists to stop two writers colliding; read-only fan-out carries no such constraint, which is why the age ladder and the pasteurize policy need no curd block, and why `/cook` cannot fan without one.

**Fast-path.** When `/mold`'s curd-count hint = 1 and blast radius is low or medium, skip the decomposer spawn entirely and go straight to the single-coder path — the hint is trusted only to skip work in this indivisible case, never to pick parallel; the decomposer remains authoritative for hint >= 2 or absent.

### Publication topology preflight

When the selected mode is `parallel`, `--open-pr` is present, and no PR exists, dispatch `/plate` in topology-preflight mode against `.cheese/ultracook/<slug>/manifest.yaml` **before Phase 1 seed or any worker commit** — before **Seed (coder).** runs (`### Worktree harvest and teardown` below). Apply `/plate`'s review-shape policy: preserve an explicit user choice, persist `single` without asking for one cohesive review unit, or ask once when stacked is recommended or shape is ambiguous — do not ask twice. Read back `plate_layout: single | stacked` and re-run `validate_manifest`. Existing PRs preserve detected topology; runs without `--open-pr` do not preflight because their workers remain commit-only.

### Milknado seam

Before running any curd, probe which of three roles the available toolset supports (`src/fanout/milknado.py::probe`, exposed as `python3 skills/ultracook/scripts/ultracook.pyz milknado --tools "<available tool names>"`):

- **`engine`** — both `milknado_todo_claim` and `milknado_node_verify` are present. milknado owns the DAG, per-node worktrees, and **verify-until-green** (it re-runs the project gates itself until they pass); `/cook` spawns the phase agent per claimed node instead of managing worktrees directly.
- **`tracker`** — only `milknado_todo_add` is present. milknado records curd status but doesn't run curds; `/cook` still owns native fan-out.
- **`none`** — no milknado tools. Native fan-out end to end: `/cook` owns worktrees itself, and **curds self-verify** by running the project gates once, in-worker.

This parity difference is deliberate: native curds self-verify (gates run once, in-worker); milknado, when present, does verify-until-green (re-runs gates until green). See [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md) for the detect-and-degrade contract — announce milknado's absence once and proceed; `none` is never a blocker.

### Phase-chain topology

| Stage | Chain | `phase_decision --table` |
| --- | --- | --- |
| Per curd | `coder(cook) → coder(press) → reviewer(age) → coder(cure) → reviewer(final age)` | `parallel-curd` |
| Post-merge, once, over the merged diff | `press → age → cure → age` | `parallel-postmerge` |

This is not the old 7-spawn linear `/ultracook` chain (`cook → press → age → cure → age → cure → age`, table `linear` in `src/fanout/phase_decision.py`) run verbatim — that table still backs the single-coder path's own `--auto` chain (`## Auto mode` below) — the fan pathway's own topology is the two tables above. The per-curd table can end early: a first age reporting `next: done` **clean-completes** the curd (`action=clean_complete`) and skips cure and the final age, because nothing has touched the tree since that review and the post-merge pass re-covers the merged diff anyway. The post-merge table never short-circuits on that signal — it is the last review before publication, so cure and final age always run, and only a final-age `next: done` is publishable; `next: cure` or a missing `next` halts.

### Deterministic phase loop

Between dispatches, `/cook`'s fan-pathway orchestrator decides the next action mechanically:

1. **Parse the slug** — `python3 shared/scripts/read_handoff_slug.py --phase <phase> --slug <slug>` (the same helper `/age`'s own flow calls, e.g. `skills/age/SKILL.md`) → JSON `{status, next, artifact, orientation, halt_reason}`. Never infer success from a sub-agent's last line of stdout — read the file.
2. **Compute the verdict** — `python3 skills/ultracook/scripts/ultracook.pyz phase_decision --phase-index <i> --status <status> [--next <next>] --table parallel-curd|parallel-postmerge` (`src/fanout/phase_decision.py`) → JSON `{action, next_phase, exit_message}`. `action=halt` surfaces the reason and stops; `action=clean_complete` (per-curd table only) records the first age's review context as final and skips ahead; `action=spawn` dispatches `next_phase`.

### Worker exhaustion and aggregate-gate recovery

- **Worker exhaustion.** A curd worker that runs out of context or turns writes a partial `status: halt: <reason>` slug. Retry that curd **once** with the error folded into its context; if it halts again, mark it failed, keep harvesting the rest, and report the failed curd in the final summary — never silently drop it.
- **Aggregate-gate cross-curd conflict vs. drift.** After harvesting all curds, run the project gates over the merged tree. On failure, distinguish a **real cross-curd conflict** (curds passed individually but collide in aggregate — a decomposer error → halt and surface it) from **harmless drift** (a formatter or generated-file delta the post-merge cure pass can absorb → continue). Never auto-resolve a real conflict.

(ported from the retired `/ultracook`'s recovery-paths section, issue #194)

### Worktree harvest and teardown

- Give each curd its own worktree; when the host lacks a native worktree-isolated sub-agent primitive, create it first with `python3 skills/ultracook/scripts/ultracook.pyz worktree create --slug <id> --base <orchestrator-branch>` (returns `{path, branch}`).
- Harvest by cherry-picking each curd branch onto the orchestrator branch: `python3 skills/ultracook/scripts/ultracook.pyz worktree harvest --branch <curd-branch> --onto <orchestrator-branch>` — the parent and sub-agent share one `.git` object store, so this needs **no `git fetch`**. On conflict, invoke `/melt`; if it cannot resolve, fall back to per-curd PRs.
- Tear down every worktree after harvest: `python3 skills/ultracook/scripts/ultracook.pyz worktree teardown --path <worktree-path> --branch <curd-branch>`. `/cook`'s fan pathway owns teardown — worktrees leak otherwise. A completed run leaks nothing: no `worktree-agent-*` branch (the one exempt case is the repair pathway's own `worktree-agent-repair-*` branch, `skills/plate/SKILL.md`, which has an independent lifecycle) and no stray `.claude/worktrees/agent-*` directory.

**Wave-fan mechanics, in order** (baseline capture through publication; each step's literal `manifest_update set-phase` call is given so the phase-string writer/reader/schema round-trip stays exact):

- Capture the run's broad-gate baseline once, in the orchestrator's own tree, before Seed (see the dedicated baseline-capture section below).
- **Seed (coder).** Dispatch a `coder` for shared types/interfaces in an isolated worktree, commit via `/plate` in commit-only mode, then `manifest_update set-phase --manifest <path> --phase seed_complete`.
- Per curd (`### Worktree harvest and teardown`, `### Phase-chain topology` above): run the five sequential dispatches; mark each curd `running` then `completed`/`failed`; after all curds return, `manifest_update set-phase --manifest <path> --phase curds_complete`.
- Harvest and tear down every curd; `manifest_update set-phase --manifest <path> --phase merge_complete`.
- Run wiring tasks topo-sorted (`ultracook.pyz wiring_topo_sort`), dispatching a `coder` sequentially within each wave; `manifest_update set-phase --manifest <path> --phase wiring_complete` then immediately `manifest_update set-phase --manifest <path> --phase final_merge_complete` (wiring commits land directly on the orchestrator branch in this flow, so the two markers coincide).
- Run the post-merge integration pass (`### Phase-chain topology` above); `manifest_update set-phase --manifest <path> --phase post_review_complete`.
- `/cook` itself alone performs harvest and, at the very end, dispatches `/plate` — never mid-run; `manifest_update set-phase --manifest <path> --phase pr_publish_complete` after `/plate` verifies publication.

Every `set-phase` call above uses the same `manifest_update` CLI (`src/fanout/manifest_update.py`), atomic and re-validated against the schema: `manifest_update set-phase --manifest <path> --phase <phase-name>`, `manifest_update set-curd-status --manifest <path> --curd <id> --status running|completed|failed [--commit-sha <sha> --base-commit <sha> --reviewed-tree-oid <oid> --diff-hash sha256:<hex> --scope <path> ...]`, and `manifest_update set-wiring-status --manifest <path> --wiring <id> --status running|completed|failed [--commit-sha <sha>]`.

### --resume <slug>

`--resume <slug>` is the sanctioned re-entry into a crashed wave-fan run. It reads `.cheese/ultracook/<slug>/manifest.yaml` (path unchanged from the retired `/ultracook`) and continues from where the crash left off:

1. **Load the manifest.** If missing, fail fast: `"no manifest at .cheese/ultracook/<slug>/manifest.yaml — nothing to resume"`. Optionally re-check its shape with `python3 skills/ultracook/scripts/ultracook.pyz validate_manifest <path>`.
2. **Rebase guard.** For every non-null `commit_sha` recorded on a completed seed item, curd, or wiring row, run `git cat-file -e <sha>` (the schema permits `commit_sha: null` on a `completed` row — skip those). If any recorded SHA is gone, fail fast and name the missing SHA — resuming onto rewritten history would harvest the wrong tree. This guard is orchestrator prose, not new engine code; there is no auto-recovery.
3. **Restore continuity.** Read `phase_summary` and `carry_forward` from the manifest — the cross-seam continuity a resumed orchestrator reasons from, since a fresh spawn has no conversation history.
4. **Pick up at the next incomplete phase.** Read the `phase` field, one of the ordered enum in `skills/ultracook/references/manifest-schema.json`: `gate_approved -> seed_complete -> curds_complete -> merge_complete -> wiring_complete -> final_merge_complete -> post_review_complete -> pr_publish_complete`. Continue from the next incomplete phase, skipping every curd/wiring row already `completed`. Report `Resuming <slug> from phase <next-phase>`. If `phase` is already `pr_publish_complete`, the run is done — report and stop.

A bare re-run (no `--resume`) that finds an existing manifest stops and tells the user to pass `--resume <slug>` to continue or `rm -r .cheese/ultracook/<slug>/` to start fresh — never wipe an existing manifest silently.

### Resolution provenance and the output contract

Every phase and curd dispatch resolves against the typed-role table in the Agent resolution section below and the shared protocol in [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md):

| Work | Preferred types |
| --- | --- |
| Decompose the spec | planner, general |
| Cook, press, cure, seed, or wiring | coder |
| Every age pass | reviewer |
| Harvest and plate | parent |

The resolver filters for required capabilities/tools/permissions/isolation first, then picks minimum power and maximum specificity; a prompt-only read-only general fallback may continue with `degraded: true`, while a missing required tool or write permission halts. Typed-role shorthand, ported verbatim from the retired `/ultracook`'s Rules: planner/general for decomposition, coder for cook/press/cure/seed/wiring, reviewer for every age, and parent ownership for harvest and plate. Every phase's handoff slug and the fan pathway's own summary carry the resulting `agent_resolution` block, so role, fallback, and degradation stay visible rather than implicit.

A terminal age is **publishable only with `next: done`**; `next: cure` or a missing `next` halts as not publishable — this applies at the end of both the per-curd table and the post-merge table above, and to the single-coder `--auto` chain's own terminal age (`## Auto mode` below).

The fan pathway and the single-coder path keep the same behavioral output and final-summary shape (`## Handoff slug`, `## Output`); required `agent_resolution` provenance records the selected role, fallback, and topology regardless of which pathway ran.

## Baseline capture

Before any curd cooks — the fan pathway's curd fan-out alike — `/cook` captures the run's broad-gate baseline once, in the orchestrator's own tree, right after mode selection, before any curd cooks.

1. **Run the gates** — run the run's broad quality gates once, in the same environment (worktree, toolchain) the cooks will re-run them in.
2. **Classify** — pass the result through the tested helper, `src/fanout/baseline.py::classify()` via the ultracook `.pyz` (e.g. `python3 skills/ultracook/scripts/ultracook.pyz baseline` with the gate failures as JSON on stdin). Classification is never eyeballed by the agent. Full taxonomy and the three-way identical/new-or-changed/halt policy: [`references/quality-gates.md`](references/quality-gates.md).
3. **Hand it down** — record the classified result in `.cheese/ultracook/<slug>/manifest.yaml`'s `baseline:` block (shape: [`references/quality-gates.md`](references/quality-gates.md) § Baseline block shape) before Seed, then hand it down in every curd's `cook` dispatch via `../ultracook/references/curd-prompt.md`'s `{baseline}` field — a curd never captures its own baseline.
4. **Repair pathway** — when capture records ≥1 identical-to-baseline failure, dedupe against a live `repair_dispatch`, then follow the repair pathway ([`references/quality-gates.md`](references/quality-gates.md) § Repair pathway) to dispatch a concurrent `/pasteurize` in an isolated worktree via `ultracook.pyz worktree create --slug repair-<slug> --base origin/main`, excluded from this run's teardown.

The final summary reports baseline failures loud, never hidden — a run with an identical-to-baseline failure outside the cooked contract states the full suite is not green, even when every gate the curds touch is green.

For source changes, call the selected backend directly and follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md), including search → fresh bounded read → stale-safe write.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diffs | `delta` | plain `git diff` |
| GitHub context | `gh` | local git history or user-provided links |
| Merge assistance | mergiraf | manual conflict resolution with tests |
| Task commands | `just`, package scripts | direct documented commands |
| Code navigation | semantic symbol search, then caller search | LSP or bounded native search; report precision loss |
| Read before edit | fresh bounded read from the write backend family | another snapshot-capable bounded read; re-read if anchors are incompatible |

Falling back, mention any loss of precision that affects risk.

## Quality gates

Run existing project commands only — the most relevant tests for the touched area, plus lint/type/build if defined. Never remove, skip, or weaken unrelated tests to make the change pass.

Gate failures are baseline-aware. Policy, the classification taxonomy, and the `baseline:` block shape are the shared reference [`references/quality-gates.md`](references/quality-gates.md); every downstream phase links there instead of restating it.

- **Frame-owned (`/cook`'s fan pathway)** — the baseline arrives in the dispatch; a curd cook never captures its own.
- **Bare `/cook` (no frame)** — on the first red broad gate with no baseline yet, capture it lazily from the pre-change tree (`git stash` or a clean worktree checkout of the pre-cook state), then classify.
- **Identical, outside the cooked contract** — record in the handoff's `baseline:` block and continue; never halt, never fix silently.
- **New or changed** — fix it, capped at 2 rounds per gate; the same failure signature repeating twice consecutively halts early.
- **Halt** only when rounds exhaust, the no-progress check trips, or the fix is design-shaped — the halt handoff carries the classification so resume never re-asks.
- **Repair pathway** — when the capture records ≥1 identical-to-baseline failure, dedupe against a live `repair_dispatch`, then follow the repair pathway ([`references/quality-gates.md`](references/quality-gates.md) § Repair pathway) to dispatch a concurrent `/pasteurize` in an isolated worktree via `cook.pyz worktree create --slug repair-<slug> --base origin/main`.

## Output

House style and citations: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). Authoritative report shape: [`references/package-report.md`](references/package-report.md); the bullets below sketch it.

Summarize:

- Files changed and why.
- Tests or checks run.
- Remaining risks or skipped checks.
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff slug

Write a minimum-shape handoff slug to `.cheese/cook/<slug>.md` so downstream phases (and cook's own fan pathway, when it is orchestrating a wave) can resume or chain without re-reading the full package-ready report. The slug is prepended at the top of the same file the package-ready report lives in — there is no second file. Schema:

```markdown
status: ok | halt: <one-line reason>
next: mold | cook | press | age | done
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <block — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

`next:` names the next runnable phase: `press` for the standard chain, `age` if the user skips press, `cook` to rerun after resolving a blocker, `mold` when the spec needs another pass. Use `next: done` only for true terminal completion, never for a blocked-but-resumable or external-gate halt; `halt:` reasons follow the package-report stop conditions. The orientation line is one factual sentence about what the diff does, not a report summary. Omit `taste_test:` when the cost gate did not warrant a taste-test.

`durable_flags:` is a conservative durable-change gate. Default `none`; add one line per architecture, protocol, convention, or rationale delta the diff introduced (`<what changed> -> <target wiki page>`). Mechanical and test-only changes always record `durable_flags: none`. Cook records flags only — it never writes the wiki; the publish-boundary writer (cure/plate/affinage) reads upstream flags as its write-back candidate list.

`baseline:` is written only when the `## Quality gates` capture rule above ran and recorded at least one identical-to-baseline failure; omit it otherwise. Block shape: [`references/quality-gates.md`](references/quality-gates.md) § Baseline block shape.

## Handoff

**Pipeline:** culture → mold → **[cook]** → press → age → cure → plate

After the package-ready report is printed and the handoff slug is on disk, ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md), following its **Standard forward-step menu**. Lead each option with the verb (what the user wants to *do* next); the skill command (with any in-scope `--hard` propagation) is the backing detail. Default options:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Plate it** — `/press <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause.
- **Stop** — dispatch none; leave further hardening for later.

Pre-select **Harden tests before review** when the cooked diff added new behaviour or touched untested seams. A user who wants to skip the press pass and review immediately can reply with `other: /age <slug>` (the gate-specific alternative, kept off the buttons per the shared menu's tail rule). The user may also chain manually: pressing then age then cure happens via each step's own handoff gate. Never dispatch before selection; after a non-stop selection, run the selected command immediately.

When invoked with `--auto`, skip this gate entirely and proceed straight into the auto-mode chain (see `## Auto mode` below).

## Auto mode

`--auto` is the autonomous-pipeline switch. Use it when the user has signalled they want the whole chain to run forward without being asked between steps.

### What auto mode does

1. After the package-ready report, invoke `/press <slug> --auto`; append `--open-pr` so terminal `/plate` may publish a new PR.
2. `/press --auto` runs its hardening pass and, if readiness is `ready for /age` or `follow-up recommended`, invokes `/age <slug> --auto`. Both states mean the cooked contract is sound and every changed behaviour has a hardening test; documented follow-ups are review-safe. Only `blocked` stops auto — blocked criteria: defined once in [`../press/references/gap-analysis.md`](../press/references/gap-analysis.md).
3. `/age <slug> --auto` writes the report and invokes `/cure <slug> --auto --stake medium+`.
4. `/cure --auto --stake medium+` bypasses the selection gate, applies every finding of `blocker`, `high`, or `medium` severity plus every cheap (contained-fix) `Low`, then invokes `/age --scope <touched-paths> --auto` for verification.
5. The age → cure cycle is capped at **two cure passes total**. Pass 1 fixes the initial findings. Pass 2 fixes anything the re-age surfaces. After pass 2 the chain stops with a final summary, regardless of whether new findings remain.
6. `/cook` itself never invokes `/plate`. At the chain terminal, `/cure` dispatches `/plate` for an existing PR, and for a new PR only when `--open-pr` is in scope. `/plate` honors explicit topology, selects an obviously cohesive single without asking, and asks before mutation when stacked is recommended or shape is ambiguous, including under auto.

### Cap enforcement

The two-cure-pass cap is enforced by chain length, not by age — age boots in fresh context each pass and cannot count prior passes. Each age pass writes `next:` from what it observes on that one run (`next: cure` when a medium+ finding remains, `next: done` when none do); before the terminal position this drives an early stop, but the value itself is informational for cap purposes — the loop's fixed two-pass structure, not age's own `next:` value, is what terminates the chain. `/cook` does not pass a pass-ordinal hint to age: age has no need to know whether it is the first or second post-cure check, since the orchestrator owns the position.

### When auto mode stops early

- A quality gate fails **new** or **changed** against baseline (see [`references/quality-gates.md`](references/quality-gates.md)) and the 2 fix rounds exhaust, the no-progress check trips, or the fix is design-shaped. Identical-to-baseline failures outside the cooked contract are recorded and never stop auto.
- `/press` returns `blocked` (blocked criteria: [`../press/references/gap-analysis.md`](../press/references/gap-analysis.md)).
- A cure pass cannot apply any finding (every selected fix breaks tests on revert-or-keep evaluation).
- Two cure passes complete (success path).

In every early-stop case, surface the report from the failing skill and tell the user the cap reached or the blocker hit. Do not silently downgrade.

### No-chain isolation directive

Each phase's existing `--auto` contract chains forward in-session — `/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, and so on. When `/cook` is running as its own fan-pathway orchestrator (`## Fan pathway` above), that default is overridden for every per-curd or post-merge dispatch: each phase sub-agent runs only its own phase, writes its handoff slug, and stops — it never chains forward to the next phase itself, even though its own `--auto` contract documents that behavior. The fan-pathway orchestrator loop (`### Deterministic phase loop` under `## Fan pathway`) owns deciding and dispatching what runs next, exactly as the retired `/ultracook` orchestrator once did.

The override travels in the spawn prompt as an explicit no-chain directive, carried over verbatim from `/ultracook`'s original wording: "Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. `/cook`'s fan pathway is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with `status: halt: <reason>` and stop; do not silently timeout."

Each phase's own `SKILL.md` `## Auto mode` section honours this under its `### When invoked from /ultracook` heading (now: when invoked from `/cook`'s fan pathway) — see e.g. `skills/press/SKILL.md`, `skills/age/SKILL.md`, `skills/cure/SKILL.md`.

### Failure handling inside cure

See `skills/cure/SKILL.md` `## Auto mode` for cure's per-finding revert/defer behaviour. Cook does not duplicate the contract — cure owns it.

### Final report

The skill that ends the chain prints the summary below. On the success path that is the final `/age --auto` (after the two-cure-pass cap is reached); on an early stop it is the skill that surfaced the blocker.

```
Auto-mode summary
Passes:        <1|2>
Findings fixed: <count by severity>
Deferred:       <count, with cure-report path>
Final age:      <path>
Next step:      review the diff, then /plate when ready
```

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface the premise before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the package-ready report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** before writing `status: ok` in the handoff slug, (1) identify the gate command, (2) run it fresh in the same turn, (3) read the full output, (4) only then claim. Hedging words (`should`, `probably`, `I think`) are banned in completion claims — state what the gate output showed, not what you expect it to show.

## Discipline

Iron Law, Red Flags, and the TDD Rationalization table live in
[`references/cook-discipline.md`](references/cook-discipline.md).

## Agent resolution

Resolve implementation and taste-test dispatches through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Implement the contract | coder | write, isolated-worktree | default | high | compatible coder, then general |
| Fresh-context taste-test | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |
| Decompose the spec | planner, general | write (manifest only), fresh-context | powerful | high | compatible planner, then general |
| Harvest and plate | parent | parent-owned repository state | powerful | high | no fallback; halt |

The canonical cook handoff and package report carry the shared `agent_resolution` block.
