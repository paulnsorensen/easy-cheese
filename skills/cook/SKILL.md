---
name: cook
description: Implement an approved spec or focused unambiguous task, editing through cheez-write. Use when the user wants code written — "implement this", "cook this spec", "/cook .cheese/specs/<slug>.md", or "fix this bug" when the fix is clear; also when the user just says "go" or "ship it" with a spec or clear acceptance criteria in scope. Runs standalone on an unambiguous task — a spec helps but is not required. Do NOT use for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).
license: MIT
---

# /cook

Do not use it for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).

## Inputs

Accept one of:

- A spec path. When explicit, read it verbatim wherever it points.
- A bare slug. Resolve it to the durable spec path with `SPEC=$(python3 shared/scripts/artifact_path.py specs <slug>)`, then read `"$SPEC"`. If you're on a host that only exposes the packaged helper, `python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>` is the fallback. The resolver anchors specs at the per-project durable corpus (see `shared/formatting.md` § Corpus location); this is the form `/ultracook` uses when chaining.
- A pasted spec or issue.
- A focused implementation request with acceptance criteria.
- A clear, unambiguous task — single-file fix, named bug, well-scoped tweak — even without a spec.

Optional flags:

- `--auto` — autonomous mode. Skip every handoff gate, propagate the flag through `/press → /age → /cure`, and fix every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. See `## Auto mode` below.
- `--hard` — propagate the `/hard-cheese` metacognitive gate flag through `/press → /age → /cure`. Cook does not fire the gate itself; it only passes the flag along. The gate fires at `/cure`'s share-for-review handoff or, under `--auto --hard`, at the end of cure's final auto pass. See `skills/hard-cheese/SKILL.md` and `skills/hard-cheese/references/composition.md`.
- `--open-pr` — propagate to `/cure` so the chain's terminal cure pass may open a *new* PR when none exists. Without it the chain only pushes to an already-open PR (Rule 11) and otherwise leaves the remote untouched.

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

Edits go through `/cheez-write` (search and reads via the tools below).

Portability reference: [`../../shared/harness-portability.md`](../../shared/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diffs | `delta` | plain `git diff` |
| GitHub context | `gh` | local git history or user-provided links |
| Merge assistance | mergiraf | manual conflict resolution with tests |
| Task commands | `just`, package scripts | direct documented commands |
| Code navigation | `/cheez-search` `kind:symbol` then `kind:callers` | LSP, native AST search, or another semantic backend that answers the same question |
| Read before edit | `/cheez-read` ranged/outline (`paths: ["f#n-m"]`, `mode:stripped`) | Native bounded read with snapshot/line anchors, or LSP symbol read when it supplies a stale-safe edit path |

Falling back, mention any loss of precision that affects risk.

## Quality gates

Run existing project commands only — the most relevant tests for the touched area, plus lint/type/build if defined. Never remove, skip, or weaken unrelated tests to make the change pass.

## Output

House style and citations: [`../../shared/formatting.md`](../../shared/formatting.md). Authoritative report shape: [`references/package-report.md`](references/package-report.md); the bullets below sketch it.

Summarize:

- Files changed and why.
- Tests or checks run.
- Remaining risks or skipped checks.
- Suggested next skill: usually `/press` → `/age` → `/cure`.

## Handoff slug

Write a minimum-shape handoff slug to `.cheese/cook/<slug>.md` so downstream phases (and the `/ultracook` orchestrator) can resume or chain without re-reading the full package-ready report. The slug is prepended at the top of the same file the package-ready report lives in — there is no second file. Schema:

```markdown
status: ok | halt: <one-line reason>
next: mold | cook | press | age | done
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
<one-line orientation: what cook changed>
```

`next:` names the next runnable phase: `press` for the standard chain, `age` if the user skips press, `cook` to rerun after resolving a blocker, `mold` when the spec needs another pass. Use `next: done` only for true terminal completion, never for a blocked-but-resumable or external-gate halt; `halt:` reasons follow the package-report stop conditions. The orientation line is one factual sentence about what the diff does, not a report summary. Omit `taste_test:` when the cost gate did not warrant a taste-test.

## Handoff

**Pipeline:** culture → mold → **[cook]** → press → age → cure → ship

After the package-ready report is printed and the handoff slug is on disk, ask via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md), following its **Standard forward-step menu**. Lead each option with the verb (what the user wants to *do* next); the skill command (with any in-scope `--hard` propagation) is the backing detail. Default options:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Ship it** — `/press <slug> --auto --open-pr`: run press → age → cure headless and open (or push) the PR at the end.
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause.
- **Stop** — dispatch none; leave further hardening for later.

Pre-select **Harden tests before review** when the cooked diff added new behaviour or touched untested seams. A user who wants to skip the press pass and review immediately can reply with `other: /age <slug>` (the gate-specific alternative, kept off the buttons per the shared menu's tail rule). The user may also chain manually: pressing then age then cure happens via each step's own handoff gate. Never dispatch before selection; after a non-stop selection, run the selected command immediately.

When invoked with `--auto`, skip this gate entirely and proceed straight into the auto-mode chain (see `## Auto mode` below).

## Auto mode

`--auto` is the autonomous-pipeline switch. Use it when the user has signalled they want the whole chain to run forward without being asked between steps.

### What auto mode does

1. After cook's package-ready report, invoke `/press <slug> --auto` (append `--open-pr` when it is in scope so the terminal cure can open the PR).
2. `/press --auto` runs its hardening pass and, if readiness is `ready for /age` or `follow-up recommended`, invokes `/age <slug> --auto`. Both states mean the cooked contract is sound and every changed behaviour has a hardening test; documented follow-ups are review-safe. Only `blocked` stops auto — false premise, unfixable level-1/2 gap, a changed behaviour with no stable hardening test, or spinning wheels (three attempts at one gap without green).
3. `/age <slug> --auto` writes the report and invokes `/cure <slug> --auto --stake medium+`.
4. `/cure --auto --stake medium+` bypasses the selection gate, applies every finding of `blocker`, `high`, or `medium` severity plus every cheap (contained-fix) `Low`, then invokes `/age --scope <touched-paths> --auto` for verification.
5. The age → cure cycle is capped at **two cure passes total**. Pass 1 fixes the initial findings. Pass 2 fixes anything the re-age surfaces. After pass 2 the chain stops with a final summary, regardless of whether new findings remain.
6. `/cook` itself never invokes `/gh`. At the chain's terminal, `/cure`'s push contract takes over: the final cure pass pushes to an already-open PR (Rule 11), and opens a *new* PR only when `--open-pr` is in scope. A fresh branch with no PR and no `--open-pr` ends with the final age report and touches no remote, as before.

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

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface the premise before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the package-ready report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** before writing `status: ok` in the handoff slug, (1) identify the gate command, (2) run it fresh in the same turn, (3) read the full output, (4) only then claim. Hedging words (`should`, `probably`, `I think`) are banned in completion claims — state what the gate output showed, not what you expect it to show.

## Discipline

Iron Law, Red Flags, and the TDD Rationalization table live in
[`references/cook-discipline.md`](references/cook-discipline.md).
See [`../../shared/skill-authoring.md`](../../shared/skill-authoring.md) for the template these follow.
