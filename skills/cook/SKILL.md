---
name: cook
description: This skill should be used when the user has an approved spec, pasted requirements, or a focused implementation request and wants the code written — phrases like "implement this", "build this feature", "write the code", "cook this spec", "make it work", "/cook .cheese/specs/<slug>.md", "fix this bug" (when the bug has a clear fix). Runs a TDD-disciplined cut → cook → taste-test → press handoff loop with scoped edits via cheez-write. Use even when the user just says "go" or "ship it" if a spec or clear acceptance criteria is in scope. If the request is fuzzy, route to `/mold` first; if it needs no writes, route to `/culture`.
license: MIT
---

# /cook

Use this skill when the user has an approved spec, pasted requirements, or a precise implementation request with acceptance criteria.

Do not use it for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).

## Inputs

Accept one of:

- A spec path, usually `.cheese/specs/<slug>.md`.
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.

If the request is ambiguous, ask for the missing acceptance criteria or route to `/mold`.

## Flow

1. Confirm the contract: behavior, non-goals, likely scope, and quality gates.
2. Inspect relevant code and tests before editing.
3. Add or update a failing test first when behavior changes.
4. Implement the smallest scoped production change.
5. Run the narrowest useful test, then relevant wider checks.
6. Refine for readability without expanding scope.
7. Hand off to `/press` for test hardening, then `/age` for review when appropriate.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Semantic navigation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise edits | tilth edit | harness edit tools or patch application |
| Code search | `sg`, ripgrep | language/package search commands |
| Diffs | `delta` | plain `git diff` |
| GitHub context | `gh` | local git history or user-provided links |
| Merge assistance | mergiraf | manual conflict resolution with tests |
| Task commands | `just`, package scripts | direct documented commands |

When a preferred tool is unavailable, continue with the fallback and mention any loss of precision if it affects risk.

## Quality gates

Use existing project commands only. Run the most relevant tests for the touched area, plus lint/type/build commands if the repository already defines them. Never remove, skip, or weaken unrelated tests to make the change pass.

## Output

Summarize:

- Files changed and why.
- Tests or checks run.
- Remaining risks or skipped checks.
- Suggested next skill: usually `/press`, then `/age`.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
