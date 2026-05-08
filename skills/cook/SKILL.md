---
name: cook
description: This skill should be used when the user has an approved spec, pasted requirements, or a focused unambiguous implementation request and wants the code written — phrases like "implement this", "build this feature", "write the code", "cook this spec", "make it work", "/cook .cheese/specs/<slug>.md", "fix this bug" (when the bug has a clear fix). Runs a TDD-disciplined contract → cut → implement → taste-test → handoff loop with scoped edits via cheez-write. Supports `--auto` to chain straight through `/press → /age → /cure` without per-step confirmation, fixing every medium-or-above finding across up to two `/age → /cure` passes. Use even when the user just says "go" or "ship it" if a spec or clear acceptance criteria is in scope. `/cook` runs standalone when the task is unambiguous (clear inputs, expected outputs, verifiable result) — a spec is helpful but not required. If the request is genuinely fuzzy, route to `/mold` first; if it needs no writes, route to `/culture`. After `/mold` (optional); before `/press` → `/age` → `/cure`.
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

Optional flag:

- `--auto` — autonomous mode. Skip every handoff `AskUserQuestion`, propagate the flag through `/press → /age → /cure`, and fix every medium-or-above finding across up to two cure passes. See `## Auto mode` below.

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

Use `cheez-search` to find existing patterns and `cheez-read` / `cheez-write` for precise edits.

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
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff

After the package-ready report is printed, ask via `AskUserQuestion` which downstream to run. Default options:

- **Run /press `<slug>`** *(recommended)* — harden tests before review.
- **Run /age `<slug>`** — review the diff now and skip the press pass.
- **Stop** — leave further hardening for later.

Pre-select `Run /press` when the cooked diff added new behaviour or touched untested seams. The user may also chain: pressing then age then cure happens via each step's own `AskUserQuestion`. Never auto-invoke; the user must select.

When invoked with `--auto`, skip this `AskUserQuestion` entirely and proceed straight into the auto-mode chain (see `## Auto mode` below).

## Auto mode

`--auto` is the autonomous-pipeline switch. Use it when the user has signalled they want the whole chain to run forward without being asked between steps.

### What auto mode does

1. After cook's package-ready report, invoke `/press <slug> --auto`.
2. `/press --auto` runs its hardening pass and, if readiness is `ready for /age`, invokes `/age <slug> --auto`. If readiness is `follow-up recommended` or `blocked`, auto mode stops and surfaces the press report to the user.
3. `/age <slug> --auto` writes the report and invokes `/cure <slug> --auto --stake medium+`.
4. `/cure --auto --stake medium+` bypasses the selection gate, applies every finding of `medium` or `high` stake, then invokes `/age --scope <touched-paths> --auto` for verification.
5. The age → cure cycle is capped at **two cure passes total**. Pass 1 fixes the initial findings. Pass 2 fixes anything the re-age surfaces. After pass 2 the chain stops with a final summary, regardless of whether new findings remain.
6. Auto mode never invokes `/gh`. Opening or updating a PR stays user-triggered.

### When auto mode stops early

- A quality gate (test, lint, type, build) fails and the failure cannot be attributed to a single revertable finding.
- `/press` returns `blocked` or `follow-up recommended`.
- A cure pass cannot apply any finding (every selected fix breaks tests on revert-or-keep evaluation).
- Two cure passes complete (success path).

In every early-stop case, surface the report from the failing skill and tell the user the cap reached or the blocker hit. Do not silently downgrade.

### Failure handling inside cure

When a cure-applied fix breaks a previously-passing test, revert that single finding, log it under the cure report's `### Deferred` section with the test name and reason, and continue with the remaining findings. Do not stop the whole pass for one bad fix.

### Final report

The last skill in the chain (cure or whichever stopped early) prints:

```
Auto-mode summary
Passes:        <1|2>
Findings fixed: <count by stake>
Deferred:       <count, with cure-report path>
Final age:      <path>
Next step:      review the diff, then /gh when ready
```

Auto mode is a propagated flag, not a separate skill — every downstream invocation passes `--auto` along so each step knows to skip its own handoff `AskUserQuestion`.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
