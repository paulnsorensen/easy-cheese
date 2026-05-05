---
name: cure
description: This skill should be used when the user has an `/age` report (or any list of review findings, CI failures, or a "fix these" instruction) and wants the selected items resolved — phrases like "fix these findings", "/cure <slug>", "address the high-stake items", "act on the age report", "fix the failing CI", "apply the cleanup". Loads the report, gates on explicit user selection, applies focused fixes via cheez-write, runs the project's existing test/lint/build gates, and produces a shipping-ready summary. Use even when the user just says "fix it" if a review report or finding list is in scope. Default selection is empty — never apply everything implicitly.
license: MIT
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

Do not use it to apply every suggestion automatically. The user chooses what to cure.

## Inputs

Accept a review report path, finding ids, pasted findings, CI failure summary, or a scoped instruction such as "fix high-stake age findings".

If selection is ambiguous, present a short numbered list and ask what to apply. The default selection is none.

## Flow

1. Load or restate the selected findings.
2. Ask for approval when the selection is not explicit.
3. Apply focused fixes, one logical group at a time.
4. Run relevant tests, lint, typecheck, or build commands already defined by the repo.
5. Re-review the touched area with `/age` principles.
6. Prepare shipping notes: what changed, checks run, risks, and PR readiness.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Applying precise fixes | tilth edit | harness edit tools or patch application |
| Understanding findings | `/age` report plus code review graph | diff, touched files, tests, and `ripgrep` |
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
- Suggested next step:
```

## Rules

- Nothing applies without explicit selection or approval.
- Keep fixes scoped to selected findings.
- Do not hide failed or skipped checks.
- Prefer PR-ready output, but do not open a PR unless the user asks.
