---
name: cook
description: This skill should be used when the user has an approved spec, pasted requirements, or a focused unambiguous implementation request and wants the code written — phrases like "implement this", "build this feature", "write the code", "cook this spec", "make it work", "/cook .cheese/specs/<slug>.md", "fix this bug" (when the bug has a clear fix). Runs a TDD-disciplined contract → cut → implement → taste-test → handoff loop with scoped edits via cheez-write. Use even when the user just says "go" or "ship it" if a spec or clear acceptance criteria is in scope. `/cook` runs standalone when the task is unambiguous (clear inputs, expected outputs, verifiable result) — a spec is helpful but not required. If the request is genuinely fuzzy, route to `/mold` first; if it needs no writes, route to `/culture`. After `/mold` (optional); before `/press` → `/age` → `/cure`.
license: MIT
---

# /cook

Use this skill when the user has an approved spec, pasted requirements, a precise implementation request with acceptance criteria, or any unambiguous task that meets the standalone fast-path checks below.

Do not use it for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).

## Inputs

Accept one of:

- A spec path, usually `.cheese/specs/<slug>.md`.
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.
- A clear, unambiguous task — single-file fix, named bug, well-scoped tweak — even without a spec.

### Standalone fast-path

`/cook` runs without `/mold` when the task is unambiguous. Treat a request as unambiguous when **all three** are present or trivially derivable:

1. **Inputs/outputs are clear.** "Tail returns wrong byte count when file ends without newline" ✓; "make tail better" ✗.
2. **Scope is bounded.** A named function, a single failing test, a specific call site, or a small region of one or two files.
3. **Verification is obvious.** A failing test that can be made to pass, or a runnable command whose output should change in a stated way.

When the fast-path applies, derive a slug from the task (e.g. `tail-trailing-newline`), treat **Contract** as a one-sentence restatement of the request, and proceed directly to **Cut** without a spec round-trip. Route to `/mold` only when one of the three checks fails — silent ambiguity is the cardinal sin.

## Flow

1. **Contract** — confirm behaviour, non-goals, likely scope, quality gates. For standalone fast-path tasks, the contract is the user's request restated in one sentence.
2. **Cut** — write failing tests for the changed behaviour. See `references/tdd-loop.md`.
3. **Implement** — make the cut tests pass with the smallest production change.
4. **Taste-test** — check spec drift, readability, and scope creep. Two-round cap; details in `references/tdd-loop.md`.
5. **Hand off** — produce the package-ready report (`references/package-report.md`) and prompt the next step via `AskUserQuestion` (see `## Handoff` below). The default chain is `/press` → `/age` → `/cure`.

Code search, reading, and editing all go through the cheez-* skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules and out-of-scope fallbacks.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
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
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff

After the package-ready report is printed, ask via `AskUserQuestion` which downstream to run. Default options:

- **Run /press `<slug>`** *(recommended)* — harden tests before review.
- **Run /age `<slug>`** — review the diff now and skip the press pass.
- **Stop** — leave further hardening for later.

Pre-select `Run /press` when the cooked diff added new behaviour or touched untested seams. The user may also chain: pressing then age then cure happens via each step's own `AskUserQuestion`. Never auto-invoke; the user must select.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface the premise before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the package-ready report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
