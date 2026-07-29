---
name: cook
description: Implement an approved spec or focused unambiguous task through stale-safe source edits. Use when the user wants code written — "implement this", "cook this spec", "/cook .cheese/specs/<slug>.md", or "fix this bug" when the fix is clear; also when the user just says "go" or "ship it" with a spec or clear acceptance criteria in scope. Runs standalone on an unambiguous task — a spec helps but is not required. Do NOT use for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook

## Inputs

Accept one of:

- A spec path. When explicit, read it verbatim wherever it points.
- A bare slug. Resolve it to the durable spec path with `SPEC=$(python3 shared/scripts/artifact_path.py specs <slug>)`, then read `"$SPEC"`. If you're on a host that only exposes the packaged helper, `python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>` is the fallback. The resolver anchors specs at the per-project durable corpus (see `../cheese/references/formatting.md` § Corpus location); this is the form `/ultracook` uses when chaining.
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.
- A clear, unambiguous task — single-file fix, named bug, well-scoped tweak — even without a spec.

Optional flags:
- `--auto` — autonomous mode: skip every handoff gate and chain `/press → /age → /cure` (see `## Auto mode` below; full selection/cap rules in `references/auto-mode.md`).
- `--hard` — propagate through `/press → /age → /cure → /plate`; `/plate` fires `/hard-cheese` after its final artifact-writing gate.
- `--open-pr` — propagate to terminal `/plate`, which follows its explicit-choice and review-shape policy for a new PR.
- `--resume <slug>` — resume a crashed **fan** run from its manifest (full mechanics: `references/fan-pathway.md` § --resume).

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

Read [`references/fan-pathway.md`](references/fan-pathway.md) before orchestrating a wave-fan run — it owns the existing-handoffs guard, mode selection, the publication-topology preflight, the milknado seam, phase-chain topology, the deterministic phase loop, worker-exhaustion/aggregate-gate recovery, worktree harvest and teardown, `--resume <slug>`, and resolution provenance.

A terminal age is **publishable only with `next: done`**; `next: cure` or a missing `next` halts — this applies to both fan-pathway tables ([`references/fan-pathway.md`](references/fan-pathway.md)) and the single-coder `--auto` chain's terminal age (`## Auto mode` below).

## Baseline capture

Before any curd cooks, `/cook` captures the run's broad-gate baseline once, in the orchestrator's own tree, right after mode selection. Full capture steps, classification, hand-down, and the repair pathway: [`references/quality-gates.md`](references/quality-gates.md).

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

## Output

House style and citations: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). Authoritative report shape: [`references/package-report.md`](references/package-report.md); the bullets below sketch it:

- Files changed and why.
- Tests or checks run.
- Remaining risks or skipped checks.
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff slug

Write a minimum-shape handoff slug at the top of `.cheese/cook/<slug>.md` — same file as the report, no second file — so downstream phases (and cook's own fan pathway when orchestrating a wave) can resume or chain without re-reading it. Schema:

```markdown
status: ok | halt: <one-line reason>
next: mold | cook | press | age | done
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <block — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

`next:` names the next runnable phase — `press` (standard chain), `age` (press skipped), `cook` (rerun after a blocker), `mold` (spec needs another pass) — or `done` only for true terminal completion, never a blocked-but-resumable halt; `halt:` reasons follow the package-report stop conditions. The orientation line is one factual sentence. Omit `taste_test:` when the cost gate didn't warrant one.

`durable_flags:` is a conservative gate, default `none`. Add one line per architecture/protocol/convention/rationale delta (`<what changed> -> <target wiki page>`); mechanical and test-only changes stay `none`. Cook records flags only — the publish-boundary writer (cure/plate/affinage) reads them as its write-back candidates.

`baseline:` is written only when the `## Quality gates` capture rule above ran and recorded at least one identical-to-baseline failure; omit it otherwise. Block shape: [`references/quality-gates.md`](references/quality-gates.md) § Baseline block shape.

## Handoff

**Pipeline:** culture → mold → **[cook]** → press → age → cure → plate

After the package-ready report and handoff slug are on disk, ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) (its **Standard forward-step menu**): lead each option with the verb, backed by the skill command (with any in-scope `--hard`):

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Plate it** — `/press <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause.
- **Stop** — dispatch none; leave further hardening for later.

Pre-select **Harden tests before review** when the diff added new behaviour or touched untested seams. To skip straight to review, reply `other: /age <slug>`; manual chaining works via each step's own gate. Never dispatch before selection; run the selected command immediately.

When invoked with `--auto`, skip this gate entirely and proceed straight into the auto-mode chain (see `## Auto mode` below).

## Auto mode

`--auto` is the autonomous-pipeline switch: skip every gate and chain forward without asking between steps. It runs `/press --auto → /age --auto → /cure --auto --stake medium+`, capped at **two cure passes total** — pass 1 fixes the initial findings, pass 2 fixes anything the re-age surfaces, then the chain stops regardless of remaining findings. `/cook` itself never invokes `/plate`; `/cure` dispatches it at the chain terminal (existing PR always, new PR only with `--open-pr`).

Auto mode stops early when: a quality gate fails new or changed against baseline and the fix rounds exhaust, the no-progress check trips, or the fix is design-shaped; `/press` returns `blocked`; a cure pass cannot apply any finding; or two cure passes complete (success path). Every early stop surfaces the failing skill's report and states the cap reached or the blocker hit — never a silent downgrade.

Read [`references/auto-mode.md`](references/auto-mode.md) before running or dispatching auto mode — it owns the full per-step chain, cap-enforcement mechanics, the fan-pathway no-chain isolation directive (a spawned phase sub-agent never chains forward on its own; the orchestrator drives), cure's per-finding failure handling, and the final-report template.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface it before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (`../age/references/voice.md`): lead the report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** identify the gate command, run it fresh this turn, read the full output, only then claim. Hedging words (`should`, `probably`, `I think`) are banned — state what the gate output showed.

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
