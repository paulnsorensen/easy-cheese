---
name: cure
description: Apply fixes from an /age report, finding list, or CI failure, then run the project's test/lint/build gates and, on a clean cure, push to the PR. Use when the user wants the selected items resolved — phrases like "fix these findings", "/cure <slug>", "address the high-severity items", "act on the age report", "fix the failing CI", "apply the cleanup". Adopts a locked selection from `/age` or `/affinage`; called bare it applies the recommended set unless `--safe`. After a clean cure it pushes to an already-open PR (Rule 11); `--open-pr` opens a new PR when none exists; `--safe` re-gates selection and push. Supports `--auto --stake <floor>` (from `/cook --auto`; `--stake` is a severity floor — `blocker`, `high`, `medium+`, or `all`). Use even when the user just says "fix it" if a review report or finding list is in scope. After `/age`; loops back to `/age --scope <touched-path>` or pushes to ship.
license: MIT
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

Do not use it to apply every suggestion automatically. The user chooses what to cure.

## Inputs

Accept any of: a `/age` slug (`/cure <slug>` reads `.cheese/age/<slug>.md`), a pasted findings list, a CI failure summary, or a scoped instruction like "fix the high-severity age findings". `/age` may also hand off with a pre-locked selection by passing the chosen ids in a structured handoff context (see `references/selection.md#handoff-from-age` for the canonical format); when that context is present, skip rendering the selection list and go straight to apply.

Age reports older than this severity-rubric revision lack the `severity`, `location`, `fix-cost-now`, and `fix-cost-later` sub-fields on each finding. Tolerate the older shape: when a finding has no `severity` field, infer it from the section header (`## High-stake findings` → `high`, `## Medium-stake findings` → `medium`); when `fix-cost-now` is absent, the `cheap` selection verb resolves to the empty set per `references/selection.md`. Never reject a report for missing sub-fields; record any inference in the cure report under `### Notes`.

When `/age` or `/affinage` hands off a pre-locked selection, adopt it. When called bare without a pre-locked selection, the default selection is the recommended composite (`all-medium, cheap`) — apply it unless `--safe` is passed or a recommended fix is sprawling/structural or findings conflict, in which case render a numbered selection list per `references/selection.md` and ask what to apply.

Optional flags:

- `--safe` — re-introduce the selection gate (when called bare) and the PR-push gate. Without it, cure applies the recommended set and, on a clean cure, pushes the PR; with it, cure asks before applying and before touching the remote.
- `--open-pr` — after a clean cure, allow cure to open a *new* PR when none exists. Without it cure only pushes to an already-open PR and otherwise leaves the remote untouched. Composes with both interactive and `--auto`.
- `--auto` — autonomous mode (propagated from `/cook --auto`). Bypasses the user-selection step. Must be paired with `--stake <floor>` to set the inclusion threshold; `/cook --auto` always passes `--stake medium+`. See `references/selection.md` for the auto-selection rules and `## Auto mode` below for the pass-cap and revert behaviour.
- `--stake <floor>` — used only with `--auto`. Despite the flag name (preserved across callers for stability), the floor is primarily a per-finding **severity** floor, not a dimension-bucket. Accepts `blocker`, `high` (blocker + high), `medium+` (blocker + high + medium **plus cheap contained-fix lows**), or `all`. The floors are severity thresholds; `medium+` is the one exception — it additionally unions the cheap lows (see `references/selection.md` § Auto-mode selection). Without `--auto` this flag is ignored.
- `--hard` — propagated metacognitive-gate flag (from `/cook --hard` or `/cheese --hard`). Cure is the *only* pipeline skill that fires the gate: when `--hard` is in scope, invoke `/hard-cheese <slug>` *before* the PR push (the share-for-review boundary) and proceed only on exit `0` — whether the push is the autonomous default or the `--safe` gate's **Open or update the PR** option. Under `--auto --hard`, see `## --hard mode` and the auto-mode puncture clause below.

## Flow

1. **Load** — read the findings (markdown, not JSON sidecars).
2. **Select** — if `/age` or `/affinage` handed off a structured pre-locked selection, adopt it as-is after re-confirming the cited ids still exist in the report. Otherwise default to the recommended composite (`all-medium, cheap`); gate on explicit user selection only under `--safe` or when a recommended fix is sprawling/structural or findings conflict. See `references/selection.md` for the recognized verbs.
3. **Apply** — fix one logical group at a time via `cheez-read` (re-confirm anchor location) and `cheez-write` (apply).
4. **Validate** — run the narrowest tests that prove each fix, then any relevant project-wide gates (lint, typecheck, build).
5. **Taste-test (behavioural fixes only)** — if this cure applied a *behavioural* fix (touched production logic or public surface), run the fresh-context taste-test before the handoff slug: dispatch the read-only `reviewer` phase-agent (named, no call-site model — its def pins `model: opus`) over the cure diff with the same lenses cook uses (drift / scope / production-path / wired-callers / locked-decision). *Mechanical* fixes — formatting, comment, import, no-logic rename — skip this and keep the current flow. Pipe any `revise` into a bounded corrective pass; a Locked-decision `halt` stops for a human. (Mirrors cook's taste-test, which cure lacked before; a coder-nested cure cannot fan out and defers the authoritative pass to the orchestrator, as in cook.)
6. **Re-review hand-off** — recommend `/age --scope <touched-path>` so review runs through the proper skill rather than reimplementing it inline. `/cure` does not re-grade its own work. If the user picks re-age, the resulting report can feed a fresh `/cure` invocation.
7. **Ship report** — what changed, checks run, deferred items, residual risks. Write the handoff slug at the top of `.cheese/cure/<slug>.md` (see `## Handoff slug` below) so the chain (and `/ultracook`) can read the outcome without re-parsing the full report.
8. **Push / hand off** — on a clean cure (≥1 fix applied, gates green, no false-premise halt), push to the PR by default (see `## Handoff` below): if an open PR exists for the branch, dispatch `/gh` to commit + push to it; if none exists, open one only with `--open-pr`. Under `--safe`, ask via the shared handoff gate before touching the remote. If the cure was not clean, surface the blocker instead of pushing.

## Preferred tools and fallbacks

Code search, reading, and editing all go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules.

Beyond `cheez-*` there are cure-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Understanding findings | `/age` report plus code-review-graph: `get_minimal_context_tool`, `get_review_context_tool` | diff, touched files, tests |
| CI and PR context | `gh` | local test output or user-provided logs |
| Diffs | `delta` | plain `git diff` |
| Conflict resolution | mergiraf | manual resolution with targeted tests |

**Freshness:** before the first code-review-graph query in a run, call `build_or_update_graph_tool`. See [`/cheez-search`](../cheez-search/SKILL.md#when-code-review-graph-beats-tilth-if-your-harness-has-it) for the full freshness contract and when semantic search beats tilth.

If a preferred tool is missing, continue with the fallback. If a missing tool prevents safe application, stop and explain the blocker.

## Validation

Run the narrowest tests that prove the fix, then any relevant existing wider gates. If a gate is unavailable, record why. Do not declare ready when selected findings remain unresolved.

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

Cross-cutting house style and citation form: [`../../shared/formatting.md`](../../shared/formatting.md). This section owns the cure-report shape; formatting.md owns the voice rules and the footnote primitive.

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
- Suggested next step: `/age --scope <touched-path>` to verify the fixes, or `/gh` to ship.
```

## Handoff

**Pipeline:** culture → mold → cook → press → age → **[cure]** → ship

After the cure report is rendered, cure decides whether to *push* or *ask*. The default is to push: on a clean cure (≥1 fix applied, gates green, no false-premise halt) carry the work to the PR without a gate. `--safe` re-introduces the handoff gate below.

**Default (no `--safe`) — push to the PR:**

- Detect an open PR for the branch (`gh pr view`). If one exists, dispatch `/gh` to commit + push the cure's changes to it — no gate. Rule 11 authorizes pushing to an already-open PR ("the existing PR is the authorization"). When `--hard` is in scope, fire `/hard-cheese <slug>` *before* the push (the share-for-review boundary) and proceed only on exit `0`.
- If no open PR exists: with `--open-pr`, dispatch `/gh` to open a new PR (same `--hard` gate first); without `--open-pr`, leave the remote untouched and finish with the ship report plus a one-line note (`no open PR — pass --open-pr or run /gh to open one`).
- Announce the push in one line. If applied fixes touched logic outside a finding's hunk, exposed adjacent risk, or checks were skipped, add a one-line recommendation to re-run `/age --scope <touched-path>` before merge — but still push (the PR is the review surface).
- If the cure was not clean (every selected fix reverted, a project-wide gate cannot go green, or a finding rests on a false premise), do not push — surface the blocker and stop.

**`--safe` — ask via the shared handoff gate** in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command is the backing detail. Default options:

- **Re-review the touched code** *(recommended when fixes were non-trivial)* — `/age --scope <touched-path>`, runs review through the proper skill. Propagates `--hard` when in scope.
- **Open or update the PR** — `/gh`. When `--hard` is in scope, this option first dispatches `/hard-cheese <slug>` and proceeds to `/gh` only if the gate exits `0`.
- **Stop** — dispatch none; sit on the changes for now.

Pre-select **Re-review the touched code** when any applied fix touched logic outside the original finding's hunk, when a corrective fix exposed adjacent risk, or when checks were skipped. Pre-select **Open or update the PR** when all selected findings applied cleanly and gates passed. Never dispatch before selection; after a non-stop selection, run the selected command immediately.

## --hard mode

`/cure --hard` is the gate-firing path for the `/hard-cheese` metacognitive vibecheck. The flag propagates up the pipeline (`/cheese → /mold → /cook → /press → /age → /cure`); cure is the only step that actually fires the gate. The contract:

- **Interactive `/cure --hard`:** the gate fires at the share-for-review boundary — the PR push. In the default (no `--safe`) path, fire `/hard-cheese <slug>` *before* the autonomous push and proceed only on exit `0`. Under `--safe`, fire it when the user selects the share-for-review option (the **Open or update the PR** label, which dispatches `/gh`). Either way, proceed only on exit `0`. If the gate exits non-zero (`FAILED` status — cap exhausted), surface the artifact path and abort the push; the user must improve their understanding before sharing for review.
- **Not sharing for review** (no open PR and no `--open-pr`, or under `--safe` picking **Re-review the touched code** / **Stop**) does *not* fire the gate. Re-review and pausing do not put code in front of readers.
- **Auto-mode puncture** — see the clause in `### Auto mode` below. The auto-mode puncture is the single sanctioned point at which `--hard` overrides `--auto`'s skip-handoff semantics.

The gate's mechanism (SOLO-graded fresh-context judge, Socratic retry, fail-open on judge error) lives in `skills/hard-cheese/SKILL.md`. The full composition matrix lives in `skills/hard-cheese/references/composition.md`.

### Auto mode

When invoked with `--auto --stake <floor>`:

- Skip the selection-list rendering and the handoff gate.
- Auto-select every finding that meets the floor (`blocker` only; `high` for blocker + high; `medium+` for blocker + high + medium **plus cheap contained-fix lows**; or `all`).
- Apply findings one at a time. After each fix, run the narrowest test that proves it. If the fix breaks a previously-passing test or any project-wide gate, revert that single finding's edit and record it under `### Deferred` in the cure report with the test name and the failure summary. Continue with the remaining findings.
- After all selected findings are processed, skip the handoff gate and invoke `/age --scope <touched-paths> --auto` (forward `--open-pr` when it is in scope) so the chain can re-review.
- `/age --auto` enforces the two-pass cap. Cure does not need to track passes itself — it just keeps applying when invoked.
- **Terminal PR push.** The PR push fires once, from the cure frame whose `/age --auto` child returned `next: done` (chain-clean or two-cure-pass cap reached) — the same terminal hook as the `--hard` puncture below. At that terminal, push to an already-open PR via `/gh` (Rule 11); open a new PR only when `--open-pr` is in scope. Mid-chain cure passes (age child returned `next: cure`) never push. A cook chain on a fresh branch with no PR and no `--open-pr` ends with the final age report and touches no remote, as before.
- **Orchestrated sub-agent exception (no push).** When cure runs as a phase-only sub-agent of an orchestrator that owns publishing — `/ultracook` (see below) or a `/cheese-factory` curd worker (spawn prompt carries `invoked-from: cheese-factory-curd` / forbids `/gh` and chaining forward) — it never performs the terminal push, even at `next: done`. The orchestrator owns the remote (cheese-factory publishes in its Phase 7 via `/pr-stack` / `/gh`). Such a sub-agent applies its findings, writes its cure slug, and stops; touching the remote from inside a curd would violate the orchestrator contract.

**`--auto --hard` puncture clause.** When `--hard` is also in scope, the chain pauses *once*, at the natural terminal point: after cure invokes `/age --auto` and the returned age slug shows `next: done` (chain-clean *or* two-cure-pass cap reached), invoke `/hard-cheese <slug>` *before returning to the caller*. This is the only sanctioned puncture of `--auto`'s skip-handoff semantics. Concretely:

- The trigger is **age's `next: done`** read from the age slug cure just invoked, not cure's own slug-writing step. Cure cannot tell on its own which pass is final (the cap is enforced inside `/age --auto`, the chain-clean signal is also issued by age) — reading age's handoff is the only honest signal.
- The puncture fires from the cure frame whose age-child returned `next: done`. That is cure pass 1 if findings cleared early, cure pass 2 if the cap is reached. Never between passes — punching the gate into every cure call would defeat its signal.
- On `PASS`: perform the terminal PR push (push to an already-open PR; open a new one only with `--open-pr`), then exit with `"gate passed → pushed for review"` (or `"gate passed → no open PR"` when nothing was pushed).
- On `FAILED`: chain exits non-zero with the artifact path; do **not** push.
- On `ERROR`: chain exits `0` with a warning (the fail-open divergence documented in `skills/hard-cheese/SKILL.md`).
- A non-TTY environment aborts with `"--hard requires an interactive TTY; remove --hard or run interactively"` — the puncture requires a human in the loop.

If no findings meet the floor, write an empty cure report with `### Applied: (none — no findings meet <floor>)` and skip straight to the auto handoff with a one-line "auto chain clean" note.

### When invoked from /ultracook or a /cheese-factory curd

When an orchestrator spawns cure as a phase-only sub-agent and owns the chain itself, honour the no-chain / no-push override:

- **`/ultracook`** — the spawn prompt says "for THIS PHASE ONLY" and "do not chain forward to the next phase." Apply the auto-selected findings, write `.cheese/cure/<slug>.md` (handoff slug at the top, `next: age`), and stop. Do not invoke `/age --scope <touched-paths> --auto`. The orchestrator reads the cure slug and spawns the next age itself.
- **`/cheese-factory` curd worker** — the spawn prompt carries `invoked-from: cheese-factory-curd` (or forbids `/gh` / PR-related skills). Apply the auto-selected findings, write the cure slug, and stop — no re-review chain and **no terminal PR push**. Publishing is owned by the factory's Phase 7 (`/pr-stack` / `/gh`); a curd must never touch the remote.

In both cases the terminal PR push (above) is suppressed — the orchestrator, not the sub-agent, owns the remote.

## Rules

- Default to the recommended composite (`all-medium, cheap`), or the selection `/age` / `/affinage` locked in. `--safe` re-introduces the selection gate. A finding resting on a false premise, or a sprawling/structural fix, still pauses for a decision regardless of mode.
- Keep fixes scoped to selected (or auto-selected) findings.
- Do not hide failed or skipped checks. In auto mode, reverted findings go under `### Deferred`, never silently dropped.
- On a clean cure, push to an already-open PR by default (Rule 11 — the existing PR is the authorization). Open a *new* PR only with `--open-pr`. `--safe` re-gates the push. Never push when the cure was not clean.
- If a selected finding rests on a false premise (the `/age` claim is wrong, or the diff already addresses it), stop and surface the premise before applying. Disagreeing with the report is allowed; silently working around it is not.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the cure report with what was applied, flag residual risk as `certain | speculating | don't know`, agree when the diff is fine without manufacturing follow-ups.
