---
name: cure
description: This skill should be used when the user has an `/age` report (or any list of review findings, CI failures, or a "fix these" instruction) and wants the selected items resolved — phrases like "fix these findings", "/cure <slug>", "address the high-stake items", "act on the age report", "fix the failing CI", "apply the cleanup". Loads the report, gates on explicit user selection, applies focused fixes via cheez-write, runs the project's existing test/lint/build gates, and produces a shipping-ready summary. Use even when the user just says "fix it" if a review report or finding list is in scope. Default selection is empty — never apply everything implicitly. After `/age`; loops back to `/age --scope <touched-path>` for re-review or hands off to `/gh` to ship.
license: MIT
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

Do not use it to apply every suggestion automatically. The user chooses what to cure.

## Inputs

Accept any of: a `/age` slug (`/cure <slug>` reads `.cheese/age/<slug>.md`), a pasted findings list, a CI failure summary, or a scoped instruction like "fix the high-stake age findings".

If selection is ambiguous, render a numbered selection list per `references/selection.md` and ask what to apply. The default selection is empty.

## Flow

1. **Load** — read the findings (markdown, not JSON sidecars).
2. **Select** — gate on explicit user selection. See `references/selection.md` for the recognized verbs.
3. **Apply** — fix one logical group at a time via `cheez-read` (re-confirm anchor location) and `cheez-write` (apply).
4. **Validate** — run the narrowest tests that prove each fix, then any relevant project-wide gates (lint, typecheck, build).
5. **Re-review hand-off** — recommend `/age --scope <touched-path>` so review runs through the proper skill rather than reimplementing it inline. `/cure` does not re-grade its own work. If the user picks re-age, the resulting report can feed a fresh `/cure` invocation.
6. **Ship report** — what changed, checks run, deferred items, residual risks.
7. **Hand off** — prompt the next step via `AskUserQuestion` (see `## Handoff` below). Never auto-invoke.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Applying precise fixes | tilth edit | harness edit tools or patch application |
| Understanding findings | `/age` report plus code-review-graph: `get_minimal_context_tool`, `get_review_context_tool` | diff, touched files, tests, and `ripgrep` |
| CI and PR context | `gh` | local test output or user-provided logs |
| Diffs | `delta` | plain `git diff` |
| Conflict resolution | mergiraf | manual resolution with targeted tests |
| Search/navigation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |

If a preferred tool is missing, continue with the fallback. If a missing tool prevents safe application, stop and explain the blocker.

## Validation

Run the narrowest tests that prove the fix, then any relevant existing wider gates. If a gate is unavailable, record why. Do not declare ready when selected findings remain unresolved.

## Output

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

## Rules

- Nothing applies without explicit selection or approval.
- Keep fixes scoped to selected findings.
- Do not hide failed or skipped checks.
- Prefer PR-ready output, but do not open a PR unless the user asks.
