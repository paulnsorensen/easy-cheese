---
name: cure
description: Apply fixes from an /age report, finding list, or CI failure, then run the project's test/lint/build gates and hand a clean cure to /plate for commit/publication. Use when the user wants selected findings resolved. Do NOT use for review (route to /age), test authoring (route to /press), or direct publication (route to /plate).
license: MIT
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

## Inputs

Accept any of: a `/age` slug (`/cure <slug>` reads `.cheese/age/<slug>.md`), a pasted findings list, a CI failure summary, or a scoped instruction like "fix the high-severity age findings". `/age` may also hand off with a pre-locked selection by passing the chosen ids in a structured handoff context (see `references/selection.md#handoff-from-age` for the canonical format); when that context is present, skip rendering the selection list and go straight to apply.

Age reports older than this severity-rubric revision lack the `severity`, `location`, `fix-cost-now`, and `fix-cost-later` sub-fields on each finding. Tolerate the older shape: when a finding has no `severity` field, infer it from the section header (`## High-stake findings` → `high`, `## Medium-stake findings` → `medium`); when `fix-cost-now` is absent, the `cheap` selection verb resolves to the empty set per `references/selection.md`. Never reject a report for missing sub-fields; record any inference in the cure report under `### Notes`. Reports predating the per-finding `confidence:` label simply lack it; treat missing confidence as unspecified — no inference, no rejection.

When `/age` or `/affinage` hands off a pre-locked selection, adopt it. When called bare without a pre-locked selection, apply the recommended composite (`all-medium, cheap`) per `references/selection.md`, which also defines the gate conditions.

Optional flags:

- `--safe` — re-introduce the selection and terminal publication handoff gates.
- `--open-pr` — after a clean cure, allow terminal `/plate` publication when no PR exists.
- `--auto` — autonomous mode (propagated from `/cook --auto`). Bypasses the user-selection step. Must be paired with `--stake <floor>` to set the inclusion threshold; `/cook --auto` always passes `--stake medium+`. See `references/selection.md` for the auto-selection rules and `## Auto mode` below for the pass-cap and revert behaviour.
- `--stake <floor>` — used only with `--auto`. Severity floor: `blocker`, `high`, `medium+`, or `all`. Floor definitions and the `medium+` cheap-lows rule: `references/selection.md` § Auto-mode selection. Without `--auto` this flag is ignored.
- `--hard` — propagate the metacognitive-gate flag to terminal `/plate`; see `## --hard mode`.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Flow

1. **Load** — read the findings (markdown, not JSON sidecars).
2. **Select** — adopt any pre-locked handoff from `/age`/`/affinage`; otherwise apply the recommended composite. See `references/selection.md` for the default rule, recognized verbs, and gate conditions. To expand a user-supplied verb to finding ids:

   ```
   python3 shared/scripts/findings_cli.py parse-selection --report <path> --selection "<verb>"
   ```

   If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz findings_cli parse-selection ...` is the fallback.
3. **Apply** — fix one logical group at a time via `cheez-read` (re-confirm anchor location) and `cheez-write` (apply).
4. **Validate** — run the narrowest tests that prove each fix, then any relevant project-wide gates (lint, typecheck, build).
5. **Taste-test (behavioural fixes only)** — if this cure applied a *behavioural* fix (touched production logic or public surface), run the fresh-context taste-test before the handoff slug: dispatch the read-only `reviewer` phase-agent (named, no call-site model — its def pins `model: opus`) over the cure diff with the same lenses cook uses, or fall back to the inline self-check when no such reviewer sub-agent is available. *Mechanical* fixes — formatting, comment, import, no-logic rename — skip this and keep the current flow. Pipe any `revise` into a bounded corrective pass; a Locked-decision `halt` stops for a human. (A coder-nested cure cannot fan out; it defers the authoritative pass to the orchestrator.)
6. **Domain-model correction (diff-touched terms only)** — after the cook's fixes land, correct the project domain model (ubiquitous language) for terms **touched by the cook's diff** (bounded — diff-touched terms only, never a free rewrite). Resolve the store with `domain_model_target()` (`shared/scripts/paths.py`, read-probe cascade wiki → docs → XDG; an existing model always wins). For a diff-touched entry whose definition or `_Code_:` referent no longer matches the code, update it and write a one-line change note per edit (entry format: `**Term** — definition.` / `_Avoid_: syn1, syn2` / `_Code_: file:line (or NEW ENTITY)`). **HARD rule — flag, don't reverse:** if a correction would REVERSE a mold-decided canonical term (replace the term mold made authoritative, or contradict its definition), do not rewrite — flag it to the user (the term, mold's decision, the conflict) and leave the entry unchanged. mold DECIDES canonical terms at curdle; cure only APPLIES BOUNDED corrections and never overrules the authoritative writer.
7. **Re-review hand-off** — recommend `/age --scope <touched-path>` so review runs through the proper skill rather than reimplementing it inline. `/cure` does not re-grade its own work. If the user picks re-age, the resulting report can feed a fresh `/cure` invocation.
8. **Ship report** — what changed, checks run, deferred items, residual risks. Write the handoff slug at the top of `.cheese/cure/<slug>.md` (see `## Handoff slug` below) so the chain (and `/ultracook`) can read the outcome without re-parsing the full report.
9. **Plate / hand off** — on a clean cure, dispatch `/plate` per `## Handoff`.

## Preferred tools and fallbacks

Code search, reading, and editing all go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules.

Beyond `cheez-*` there are cure-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Understanding findings | `/age` report plus touched diff/test context | diff, touched files, tests |
| CI and PR context | `gh` | local test output or user-provided logs |
| Diffs | `delta` | plain `git diff` |
| Conflict resolution | mergiraf | manual resolution with targeted tests |
| Code navigation | `/cheez-search` `kind:symbol` then `kind:callers` | LSP, native AST search, or another semantic backend that answers the same question |
| Read before edit | `/cheez-read` ranged/outline (`paths: ["f#n-m"]`, `mode:stripped`) | Native bounded read with snapshot/line anchors, or LSP symbol read when it supplies a stale-safe edit path |

If a preferred tool is missing, continue with the fallback. If a missing tool prevents safe application, stop and explain the blocker.

## Validation

Run the narrowest tests that prove the fix, then any relevant existing wider gates. If a gate is unavailable, record why. Do not declare ready when selected findings remain unresolved.

Applied requires its proving test green (Iron Law — see `references/cure-discipline.md`).

**clean cure** — ≥1 fix applied, all gates green, no false-premise halt. To map the post-cure gate booleans to a readiness verdict (agent judges the booleans; the CLI maps them):

   ```
   python3 shared/scripts/gates_cli.py classify \
     --press-status <label> \
     [--hard-floor-met] [--has-open-level-1-or-2] [--has-open-level-3] [--has-open-level-4-or-5] [--any-spinning]
   ```

   If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz gates_cli classify ...` is the fallback.

## Handoff slug

Write the cure report to `.cheese/cure/<slug>.md` with a minimum handoff slug at the top so `/ultracook` and `/cheese --continue` can chain without re-parsing the full report:

```markdown
status: ok | halt: <one-line reason>
next: age | done
artifact: <path-if-any>
<one-line orientation: what cure applied or deferred>
```

`status: ok` when at least one finding applied cleanly (or no findings met the severity floor in `--auto` mode); `status: halt: <reason>` when every selected fix failed the revert/keep evaluation or a project-wide gate cannot be made green. `next:` is `age` whenever re-review should follow — that is the autonomous-chain default and the standard interactive recommendation. `next:` is `done` only when invoked interactively without `--auto` *and* the user explicitly opts out of re-review. Cure does not track which pass it is on; the two-cure-pass cap is enforced by `/age --auto`'s third invocation, not by cure.

## Output

Cross-cutting house style and citation form: [`../cheese/references/formatting.md`](../cheese/references/formatting.md).

The cure report body lives below the handoff slug in the same file at `.cheese/cure/<slug>.md`:

```markdown
## Cure Report

### Applied
- <finding>: <fix summary>

### Deferred
- <finding>: <reason>

### Checks
- <command>: <pass|fail|skipped with reason>

### Re-review
- Remaining risk:
- Suggested next step: `/age --scope <touched-path>` to verify the fixes, or `/plate` to commit/publish.
```

## Handoff

**Pipeline:** culture → mold → cook → press → age → **[cure]** → plate

After the cure report is rendered, cure decides whether to dispatch `/plate` or ask. On a **clean cure** (see Validation), the default carries work to an already-open PR without another gate. `--safe` re-introduces the handoff gate.

When the run was chained from `/affinage` (`handoff_context.source_skill: /affinage`), cure **never** dispatches `/plate` — it applies its fixes, runs the auto-mode `/age --scope` loop where applicable, and returns so `/affinage` can post its GitHub replies (final writes) before owning terminal `/plate`.

**Default (no `--safe`) — plate the work:**

- Detect an open PR with `gh pr view`. If one exists, dispatch `/plate` to run its final writing gate, validation, named-file commit, topology-aware update, and publication. Rule 11 authorizes the update. Propagate `--hard`; `/plate` gives `/hard-cheese` the final artifact state before publishing.
- If no open PR exists: with `--open-pr`, dispatch `/plate [--hard]`; explicit topology choices and obviously cohesive work proceed without asking, while stack-sized or ambiguous work asks before commit or branch-layout mutation. Without `--open-pr`, leave the remote untouched and finish with `no open PR — pass --open-pr or run /plate`.
- After `/plate`'s publication lands, run the **§ Post-PR learnings write-back** below.
- If the cure was not clean, do not dispatch `/plate`; mention the blocker and stop.

**`--safe` — ask via the shared handoff gate** in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md). Default options:

- **Re-review the touched code** *(recommended when fixes escaped the finding hunk)* — `/age --scope <touched-path>`.
- **Plate it — commit and open or update the PR** — `/plate [--hard]`.
- **Checkpoint & stop** — `/wheypoint`.
- **Stop** — dispatch none.

Pre-select **Plate it** only when all selected findings applied cleanly and gates passed. Never dispatch before selection; run the selected command immediately.

### Post-PR learnings write-back

After any path that **publishes to a PR** — the default `/plate` dispatch, an `--open-pr` new PR, the `--safe` **Plate it** selection, or the auto-mode terminal publication — record the session's *implementation-time* learnings to the wiki. This is the second wiki write moment; curdle owns the design-time write, this owns what only surfaces while building: constraints discovered in `/cook`, `/age` findings that changed the design, and any domain terms the diff introduced or redefined.

- **Candidates — upstream `durable_flags` + new-since-curdle ADRs.** Read `durable_flags:` from the upstream `/cook` and `/age` handoff slugs (`.cheese/cook/<slug>.md`, `.cheese/age/<slug>.md`); every non-`none` line is a write-back candidate alongside the new ADRs + domain-model deltas. Upstream phases record flags only — cure/plate/affinage remain the only wiki writers.
- **Writer — `/wiki-ingest`, detect-and-degrade.** When the hallouminate plugin is available, dispatch `/wiki-ingest` with the candidate list above; its dedup/route/merge/contradiction handling ensures only rationale *new since curdle* lands (say "new since curdle" in the dispatch so it does not re-add design-time ADRs). When hallouminate is absent, write `docs/adr/<slug>-NNN.md` + the domain-model file fallback and emit a **loud one-line note** that the write-back went to files, not the wiki — never a silent degrade. Detection and the degrade contract: [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md).
- **Every publication path.** Fires from the frame that dispatched terminal `/plate` — manual `cook→cure` and `--auto` alike — after publication lands.
- **Publication-owner exception.** When cure does not own terminal `/plate` — the `/ultracook` no-publish cases below, or the `/affinage` chain where affinage owns terminal `/plate` — cure does **not** write back; the skill that owns the `/plate` dispatch owns the write-back at its publish boundary.
- **Nothing to record** — all upstream `durable_flags` are `none` (or absent), no new ADR-worthy decision, and no domain-model delta — skip with a one-line "no post-PR learnings" note. Do not manufacture an entry.

`[TBD]` The write-back trigger lives at this cure boundary today; `/plate` (the dedicated commit/PR skill) now exists, so the deferred follow-up is to move the trigger onto `/plate` so publication and learnings-capture are wired at one seam (see the `post-pr-wiki-writeback` wiki page). Upstream `durable_flags` feed whichever skill owns this single publish-boundary write, so if the trigger moves to `/plate`, flag consumption moves with it.

## --hard mode

`/cure --hard` propagates `--hard` to `/plate` at the share-for-review boundary. `/plate` first completes and verifies every durable write, then gives `/hard-cheese` that final artifact inventory and proceeds only on pass. Re-review, checkpoint, and stop choices do not fire the gate. The mechanism lives in `skills/hard-cheese/SKILL.md`; composition details live in `../hard-cheese/references/composition.md`.

## Auto mode

When invoked with `--auto --stake <floor>`:

- Skip the selection-list rendering and the handoff gate.
- Auto-select every finding that meets the severity floor. Floor definitions: `references/selection.md` § Auto-mode selection.
- Apply findings one at a time. After each fix, run the narrowest test that proves it. If the fix breaks a previously-passing test or any project-wide gate, revert that single finding's edit and record it under `### Deferred` in the cure report with the test name and the failure summary. Continue with the remaining findings.
- After all selected findings are processed, skip the handoff gate and invoke `/age --scope <touched-paths> --auto` (forward `--open-pr` when it is in scope) so the chain can re-review.
- `/age --auto` enforces the two-pass cap. Cure does not need to track passes itself — it just keeps applying when invoked.
- **Terminal publication.** When the age child returns `next: done`, dispatch `/plate` once. It updates an existing PR automatically or, with `--open-pr`, applies the explicit-choice and review-shape policy before committing a new PR layout. After the publication lands, run the **§ Post-PR learnings write-back** in `## Handoff`.
- **Orchestrated sub-agent exception.** A phase-only `/ultracook` cure never invokes `/plate`; the orchestrator owns commit and publication.
- **`/affinage` chain exception.** When `handoff_context.source_skill` is `/affinage`, suppress this terminal `/plate` — affinage posts its GitHub replies (final writes) and then owns terminal `/plate`.

**`--auto --hard` puncture clause.** When age returns `next: done`, dispatch `/plate --hard` rather than firing `/hard-cheese` directly. `/plate`'s final writing gate makes the completed artifact inventory visible to the metacognitive check. A failed hard gate halts publication; a non-TTY environment reports that `--hard` needs an interactive TTY.

If no findings meet the floor, write an empty cure report with `### Applied: (none — no findings meet <floor>)` and skip straight to the auto handoff with a one-line "auto chain clean" note.

### When invoked from /ultracook (linear or a parallel-mode curd)

When an orchestrator spawns cure as a phase-only sub-agent and owns the chain itself, honour the no-chain / no-push override:

- **`/ultracook` linear mode** — the spawn prompt says "for THIS PHASE ONLY" and "do not chain forward to the next phase." Apply the auto-selected findings, write `.cheese/cure/<slug>.md` (handoff slug at the top, `next: age`), and stop. Do not invoke `/age --scope <touched-paths> --auto`. The orchestrator reads the cure slug and spawns the next age itself.
- **`/ultracook` parallel-mode curd worker** — apply findings, write the cure slug, and stop. Do not invoke `/plate` or touch the remote; parallel mode owns final commit and publication.

In both cases terminal `/plate` dispatch is suppressed — the orchestrator owns it.

## Rules

- Default to the recommended composite (`all-medium, cheap`), or the selection `/age` / `/affinage` locked in. `--safe` re-introduces the selection gate. A finding resting on a false premise, or a sprawling/structural fix, still pauses for a decision regardless of mode.
- Keep fixes scoped to selected (or auto-selected) findings.
- Do not hide failed or skipped checks. In auto mode, reverted findings go under `### Deferred`, never silently dropped.
- Publication contract — existing PR authorization, `--open-pr`, `--safe`, and never publishing an unclean cure: see `## Handoff`.
- If a selected finding rests on a false premise (the `/age` claim is wrong, or the diff already addresses it), stop and surface the premise before applying. Disagreeing with the report is allowed; silently working around it is not.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the cure report with what was applied, flag residual risk as `certain | speculating | don't know`, agree when the diff is fine without manufacturing follow-ups.
- **Verification before `status: ok`:** before writing `status: ok` in the handoff slug, (1) identify the gate command, (2) run it fresh in the same turn, (3) read the full output, (4) only then claim. Hedging words (`should`, `probably`, `I think`) are banned in completion claims — state what the gate output showed, not what you expect it to show.

## Discipline

Iron Law, Red Flags, and the fix-application Rationalization table live in
[`references/cure-discipline.md`](references/cure-discipline.md).
