---
name: cook
description: This skill should be used when the user has an approved spec, pasted requirements, or a focused unambiguous implementation request and wants the code written — phrases like "implement this", "build this feature", "write the code", "cook this spec", "make it work", "/cook .cheese/specs/<slug>.md", "fix this bug" (when the bug has a clear fix). Runs a TDD-disciplined contract → cut → implement → taste-test → handoff loop with scoped edits via cheez-write. Supports `--auto` for the autonomous chain through `/press → /age → /cure` (see `## Auto mode`). Use even when the user just says "go" or "ship it" if a spec or clear acceptance criteria is in scope. `/cook` runs standalone when the task is unambiguous (clear inputs, expected outputs, verifiable result) — a spec is helpful but not required. If the request is genuinely fuzzy, route to `/mold` first; if it needs no writes, route to `/culture`. After `/mold` (optional); before `/press` → `/age` → `/cure`.
license: MIT
---

# /cook

Use this skill when the user has an approved spec, pasted requirements, a precise implementation request with acceptance criteria, or any unambiguous task that meets the standalone fast-path checks below.

Do not use it for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).

## Inputs

Accept one of:

- A spec path, usually `.cheese/specs/<slug>.md`.
- A bare slug whose spec lives at `.cheese/specs/<slug>.md` (cook resolves the path; this is the form `/ultracook` uses when chaining).
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.
- A clear, unambiguous task — single-file fix, named bug, well-scoped tweak — even without a spec.

Optional flags:

- `--auto` — autonomous mode. Skip every handoff gate, propagate the flag through `/press → /age → /cure`, and fix every medium-or-above finding across up to two cure passes. See `## Auto mode` below.
- `--hard` — propagate the `/hard-cheese` metacognitive gate flag through `/press → /age → /cure`. Cook does not fire the gate itself; it only passes the flag along. The gate fires at `/cure`'s share-for-review handoff or, under `--auto --hard`, at the end of cure's final auto pass. See `skills/hard-cheese/SKILL.md` and `skills/hard-cheese/references/composition.md`.

### Standalone fast-path

`/cook` runs without `/mold` when the task is unambiguous. Treat a request as unambiguous when **all three** are present or trivially derivable:

1. **Inputs/outputs are clear.** "Tail returns wrong byte count when file ends without newline" ✓; "make tail better" ✗.
2. **Scope is bounded.** A named function, a single failing test, a specific call site, or a small region of one or two files.
3. **Verification is obvious.** A failing test that can be made to pass, or a runnable command whose output should change in a stated way.

When the fast-path applies, derive the slug deterministically with `python3 shared/scripts/slugify.py from-task --task "<task text>" --json` and read the `slug` and `path` fields from the JSON (`path` is `.cheese/specs/<slug>.md`). The script enforces kebab-case, stopword dropping, the 5-word cap, and collision detection — never hand-roll the slug. Treat **Contract** as a one-sentence restatement of the request, and proceed directly to **Cut** without a spec round-trip. Route to `/mold` only when one of the three checks fails — silent ambiguity is the cardinal sin.

## Flow

1. **Contract** — confirm behaviour, non-goals, likely scope, quality gates. For standalone fast-path tasks, the contract is the user's request restated in one sentence.
2. **Cut** — write failing tests for the changed behaviour. See `references/tdd-loop.md`.
3. **Implement** — make the cut tests pass with the smallest production change.
4. **Taste-test** — check spec drift, readability, and scope creep. Two-round cap; details in `references/tdd-loop.md`.
5. **Hand off** — produce the package-ready report (`references/package-report.md`), then run `python3 skills/cook/scripts/self_eval_check.py --report .cheese/cook/<slug>.md --json` to scan for honesty-rule violations (skipped-claimed-pass, unverified-claim, scope-creep) and parse the JSON list for ids and lines. Non-empty list (exit 1) means stop and fix the report or the underlying work before handoff — do not eyeball the self-eval. (Drop `--json` for a one-line-per-violation human summary when running interactively.) Then write the handoff slug (`## Handoff slug` below) and prompt the next step via the shared handoff gate (see `## Handoff` below). The default chain is `/press` → `/age` → `/cure`.

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

Cross-cutting house style and citation form: [`../../shared/formatting.md`](../../shared/formatting.md). The authoritative cook-report shape lives in [`references/package-report.md`](references/package-report.md); the bullets below are a sketch of what that template requires.

Summarize:

- Files changed and why.
- Tests or checks run.
- Remaining risks or skipped checks.
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff slug

Write a minimum-shape handoff slug to `.cheese/cook/<slug>.md` so downstream phases (and the `/ultracook` orchestrator) can resume or chain without re-reading the full package-ready report. The slug is prepended at the top of the same file the package-ready report lives in — there is no second file. Schema:

```markdown
status: ok | halt: <one-line reason>
next: press | age | done
artifact: <path-to-richer-report-if-any>
<one-line orientation: what cook changed>
```

`status: ok` when cook finished cleanly. `status: halt: <reason>` when cook stopped per the package-report stop conditions (missing spec decision, blocked test, taste-test cap hit, quality gate fail outside scope). `next:` is `press` for the standard chain, `age` if the user opts to skip press, or `done` if the package-report status itself is `blocked`. The orientation line is a single factual sentence about what the diff does — not a summary of the report.

## Handoff

**Pipeline:** culture → mold → **[cook]** → press → age → cure → ship

After the package-ready report is printed and the handoff slug is on disk, ask via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command (with any in-scope `--hard` propagation) is the backing detail. Default options:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Review the diff now (skip the press pass)** — `/age <slug>`.
- **Stop** — dispatch none; leave further hardening for later.

Pre-select **Harden tests before review** when the cooked diff added new behaviour or touched untested seams. The user may also chain: pressing then age then cure happens via each step's own handoff gate. Never dispatch before selection; after a non-stop selection, run the selected command immediately.

When invoked with `--auto`, skip this gate entirely and proceed straight into the auto-mode chain (see `## Auto mode` below).

## Auto mode

`--auto` is the autonomous-pipeline switch. Use it when the user has signalled they want the whole chain to run forward without being asked between steps.

### What auto mode does

1. After cook's package-ready report, invoke `/press <slug> --auto`.
2. `/press --auto` runs its hardening pass and, if readiness is `ready for /age` or `follow-up recommended`, invokes `/age <slug> --auto`. Both states mean the cooked contract is sound and every changed behaviour has a hardening test; documented follow-ups are review-safe. Only `blocked` stops auto — false premise, unfixable level-1/2 gap, a changed behaviour with no stable hardening test, or spinning wheels (three attempts at one gap without green).
3. `/age <slug> --auto` writes the report and invokes `/cure <slug> --auto --stake medium+`.
4. `/cure --auto --stake medium+` bypasses the selection gate, applies every finding of `blocker`, `high`, or `medium` severity, then invokes `/age --scope <touched-paths> --auto` for verification.
5. The age → cure cycle is capped at **two cure passes total**. Pass 1 fixes the initial findings. Pass 2 fixes anything the re-age surfaces. After pass 2 the chain stops with a final summary, regardless of whether new findings remain.
6. Auto mode never invokes `/gh`. Opening or updating a PR stays user-triggered.

### When auto mode stops early

- A quality gate (test, lint, type, build) fails and the failure cannot be attributed to a single revertible finding.
- `/press` returns `blocked` (false premise, unfixable level-1/2 gap, missing hardening test, or spinning wheels at three attempts).
- A cure pass cannot apply any finding (every selected fix breaks tests on revert-or-keep evaluation).
- Two cure passes complete (success path).

In every early-stop case, surface the report from the failing skill and tell the user the cap reached or the blocker hit. Do not silently downgrade.

### When invoked from /ultracook

`/ultracook` spawns each phase as a fresh-context sub-agent and owns the chain itself. When the spawn prompt explicitly says "for THIS PHASE ONLY" and "do not chain forward to the next phase," honour the override: write `.cheese/cook/<slug>.md` and stop. Do not invoke `/press <slug> --auto` from inside the sub-agent. The orchestrator reads the handoff slug and decides whether to spawn the next phase. Without this override, sub-agent #1 would run the entire pipeline inside its own context and `/ultracook`'s per-phase isolation guarantee would be silently broken.

### Failure handling inside cure

See `skills/cure/SKILL.md` `### Auto mode` for cure's per-finding revert/defer behaviour. Cook does not duplicate the contract — cure owns it.

### Final report

The skill that ends the chain prints the summary below. On the success path that is the final `/age --auto` (after the two-cure-pass cap is reached); on an early stop it is the skill that surfaced the blocker.

```
Auto-mode summary
Passes:        <1|2>
Findings fixed: <count by severity>
Deferred:       <count, with cure-report path>
Final age:      <path>
Next step:      review the diff, then /gh when ready
```

Auto mode is a propagated flag, not a separate skill — every downstream invocation passes `--auto` along so each step knows to skip its own handoff gate.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface the premise before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the package-ready report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
