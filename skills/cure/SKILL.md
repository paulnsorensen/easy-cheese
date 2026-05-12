---
name: cure
description: This skill should be used when the user has an `/age` report (or any list of review findings, CI failures, or a "fix these" instruction) and wants the selected items resolved — phrases like "fix these findings", "/cure <slug>", "address the high-stake items", "act on the age report", "fix the failing CI", "apply the cleanup". Loads the report, gates on explicit user selection, applies focused fixes via cheez-write, runs the project's existing test/lint/build gates, and produces a shipping-ready summary. Supports `--auto --stake <floor>` (propagated from `/cook --auto`) for the autonomous chain (see `## Auto mode`). Use even when the user just says "fix it" if a review report or finding list is in scope. Default selection is empty — never apply everything implicitly. After `/age`; loops back to `/age --scope <touched-path>` for re-review or hands off to `/gh` to ship.
license: MIT
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

Do not use it to apply every suggestion automatically. The user chooses what to cure.

## Inputs

Accept any of: a `/age` slug (`/cure <slug>` reads `.cheese/age/<slug>.md`), a pasted findings list, a CI failure summary, or a scoped instruction like "fix the high-stake age findings". `/age` may also hand off with a pre-locked selection by passing the chosen ids inline in the dispatch (see `references/selection.md#handoff-from-age` for the canonical format); when that happens, skip rendering the selection list and go straight to apply.

If selection is ambiguous *and* not pre-locked from `/age`, render a numbered selection list per `references/selection.md` and ask what to apply. The default selection is empty.

Optional flags:

- `--auto` — autonomous mode (propagated from `/cook --auto`). Bypasses the user-selection step. Must be paired with `--stake <floor>` to set the inclusion threshold; `/cook --auto` always passes `--stake medium+`. See `references/selection.md` for the auto-selection rules and `## Auto mode` below for the pass-cap and revert behaviour.
- `--stake <floor>` — used only with `--auto`. Accepts `high`, `medium+` (medium or higher), or `all`. Without `--auto` this flag is ignored — interactive selection is the only sanctioned path.

## Flow

1. **Load** — read the findings (markdown, not JSON sidecars).
2. **Select** — if `/age` handed off a pre-locked selection, adopt it as-is (re-confirm the cited ids still exist in the report). Otherwise gate on explicit user selection. See `references/selection.md` for the recognized verbs.
3. **Apply** — fix one logical group at a time via `cheez-read` (re-confirm anchor location) and `cheez-write` (apply).
4. **Validate** — run the narrowest tests that prove each fix, then any relevant project-wide gates (lint, typecheck, build).
5. **Re-review hand-off** — recommend `/age --scope <touched-path>` so review runs through the proper skill rather than reimplementing it inline. `/cure` does not re-grade its own work. If the user picks re-age, the resulting report can feed a fresh `/cure` invocation.
6. **Ship report** — what changed, checks run, deferred items, residual risks. Write the handoff slug at the top of `.cheese/cure/<slug>.md` (see `## Handoff slug` below) so the chain (and `/ultracook`) can read the outcome without re-parsing the full report.
7. **Hand off** — prompt the next step via `AskUserQuestion` (see `## Handoff` below). Never auto-invoke.

## Preferred tools and fallbacks

Code search, reading, and editing all go through the cheez-* skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules.

Beyond cheez-* there are cure-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Understanding findings | `/age` report plus code-review-graph: `get_minimal_context_tool`, `get_review_context_tool` | diff, touched files, tests |
| CI and PR context | `gh` | local test output or user-provided logs |
| Diffs | `delta` | plain `git diff` |
| Conflict resolution | mergiraf | manual resolution with targeted tests |

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

`status: ok` when at least one finding applied cleanly (or no findings met the stake floor in `--auto` mode); `status: halt: <reason>` when every selected fix failed the revert/keep evaluation or a project-wide gate cannot be made green. `next:` is `age` whenever re-review should follow — that is the autonomous-chain default and the standard interactive recommendation. `next:` is `done` only when invoked interactively without `--auto` *and* the user explicitly opts out of re-review. Cure does not track which pass it is on; the two-cure-pass cap is enforced by `/age --auto`'s third invocation, not by cure.

## Output

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

After the cure report is rendered, ask via `AskUserQuestion` which downstream to run. Default options:

- **Run /age `--scope <touched-path>`** *(recommended when fixes were non-trivial)* — re-review the touched code through the proper skill.
- **Run /gh** — open or update the PR.
- **Stop** — sit on the changes for now.

Pre-select `Run /age` when any applied fix touched logic outside the original finding's hunk, when a corrective fix exposed adjacent risk, or when checks were skipped. Pre-select `Run /gh` when all selected findings applied cleanly and gates passed. Never auto-invoke.

### Auto mode

When invoked with `--auto --stake <floor>`:

- Skip the selection-list rendering and the `AskUserQuestion`.
- Auto-select every finding whose stake meets the floor (`high` only, `medium+` for medium or higher, or `all`).
- Apply findings one at a time. After each fix, run the narrowest test that proves it. If the fix breaks a previously-passing test or any project-wide gate, revert that single finding's edit and record it under `### Deferred` in the cure report with the test name and the failure summary. Continue with the remaining findings.
- After all selected findings are processed, skip the handoff `AskUserQuestion` and invoke `/age --scope <touched-paths> --auto` so the chain can re-review.
- `/age --auto` enforces the two-pass cap. Cure does not need to track passes itself — it just keeps applying when invoked.
- Never invoke `/gh` from auto mode. The chain ends with the final age report and the user opens a PR manually if they want.

If no findings meet the stake floor, write an empty cure report with `### Applied: (none — no findings at or above <floor>)` and skip straight to the auto handoff with a one-line "auto chain clean" note.

### When invoked from /ultracook

`/ultracook` spawns cure as a fresh-context sub-agent and owns the chain itself. When the spawn prompt explicitly says "for THIS PHASE ONLY" and "do not chain forward to the next phase," honour the override: apply the auto-selected findings, write `.cheese/cure/<slug>.md` (with the handoff slug at the top, `next: age`), and stop. Do not invoke `/age --scope <touched-paths> --auto` from inside the sub-agent. The orchestrator reads the cure slug and spawns the next age itself.

## Rules

- Nothing applies without explicit selection or approval. The only sanctioned bypass is `--auto --stake <floor>`, which substitutes a stake-based auto-selection for the user's selection and is meant for `/cook --auto` chains, not interactive use.
- Keep fixes scoped to selected (or auto-selected) findings.
- Do not hide failed or skipped checks. In auto mode, reverted findings go under `### Deferred`, never silently dropped.
- Prefer PR-ready output, but do not open a PR unless the user asks. Auto mode never opens a PR.
- If a selected finding rests on a false premise (the `/age` claim is wrong, or the diff already addresses it), stop and surface the premise before applying. Disagreeing with the report is allowed; silently working around it is not.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the cure report with what was applied, flag residual risk as `certain | speculating | don't know`, agree when the diff is fine without manufacturing follow-ups.
