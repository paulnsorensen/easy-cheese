---
name: press
description: Harden the test surface after `/cook` — map changed behavior to tests, find weak assertions and missing boundaries, and add focused hardening tests. Use when the user wants the tests strengthened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force.
license: MIT
---

# /press

Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## --hard propagation

`/press --hard` (propagated from `/cook --hard`) is pass-through only. Press runs no gate. Hand `--hard` forward to `/age` at the handoff so it eventually reaches `/cure`, which is the only pipeline skill that fires the metacognitive vibecheck. See `skills/hard-cheese/SKILL.md`.

## Flow

1. **Read** — load the spec or acceptance criteria and the cooked diff. If `.cheese/glossary/<slug>.md` exists, read it for naming consistency when hardening tests.
2. **Map** — for each changed behaviour, find the test(s) that cover it via `cheez-search`.
3. **Gap analysis** — identify weak assertions, missing boundaries, and uncovered integration seams. See `references/gap-analysis.md` for what counts as a gap and the priority order.
4. **Add focused tests** — observe red first when behaviour changes. Use `cheez-write` for precise edits.
5. **Corrective fixes** — only for defects the hardening tests expose. No new behaviour.
6. **Run checks** — narrowest useful tests, then relevant wider gates already in the project.
7. **Report** — write `.cheese/press/<slug>.md` (slug carried from `/cook`, or derived from branch/task) and print the path. Mark readiness: `ready for /age`, `follow-up recommended`, or `blocked`.
8. **Hand off** — in manual mode, prompt the next step via the shared handoff gate (see `## Handoff` below); in `--auto` mode, chain forward per `### Auto mode`.

## Preferred tools and fallbacks

Code search, reading, and editing all go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules. For coverage and test discovery, press uses `cheez-search` (callers via `kind: "callers"`) and `tilth_deps`.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

Beyond `cheez-*` there are press-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff review | `delta` | plain `git diff` |
| Affected execution flows + risk scoring | caller/dependency tracing from `/cheez-search` and `tilth_deps` | manual flow tracing from changed files |

If optional tools are missing, press a narrower surface and state the residual risk.

## Output

House style and citation form: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). This section owns the press-report shape.

Write to `.cheese/press/<slug>.md` with a minimum handoff slug at the top so `/ultracook` and `/cheese --continue` can chain without re-parsing the report. The full report shape:

```markdown
status: ok | halt: <one-line reason>
next: press | age | done
artifact: <path-if-any>
<one-line orientation: what press did — e.g., "added 4 boundary tests; no defects exposed">

# Press Report — <slug>

## Orientation
<one or two factual sentences about what press did this pass — the hardening added, the gaps closed, the readiness verdict. `/cheese --continue` surfaces the slug's orientation line to the user as "where you are", so press's orientation must describe press's own work, not duplicate cook's orientation.>

## Checks run
- <command>: <pass|fail|skipped with reason>

## Findings
| Severity | Category | Evidence | Recommendation |
| --- | --- | --- | --- |

## Coverage
- Spec coverage:
- Boundary coverage:
- Assertion strength:

## Readiness
<ready for /age | follow-up recommended | blocked>

## Next step
<ready for /age>:           /age <slug>           — review the cooked + pressed diff
<follow-up recommended>:    /age <slug>           — review-safe; documented follow-ups addressed after review
<blocked>:                  resolve blocking issues before proceeding
```

`status: ok` maps to readiness `ready for /age` or `follow-up recommended`; `status: halt: <reason>` maps to `blocked`. `next:` names the next runnable phase: `age` when review-safe, `press` when blocking issues must be resolved and the hardening phase rerun. Use `next: done` only for true terminal completion, not for a blocked-but-resumable halt. `/ultracook` still stops automatically on any `status: halt`; `next:` is the resume hint for `/cheese --continue`.

Then print:

```
Press report: .cheese/press/<slug>.md
Next step:    /age <slug>                          (when ready for /age or follow-up recommended)
              blocked — resolve before continuing  (when blocked)
```

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → ship

After the press report is on disk, ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md), following its **Standard forward-step menu**. Lead each option with the verb (what the user wants to *do* next); the skill command (with any in-scope `--hard` propagation) is the backing detail. Default options:

- **Review the diff** *(recommended when readiness is `ready for /age` or `follow-up recommended`)* — `/age <slug>`. For `follow-up recommended`, documented follow-ups can be addressed after review.
- **Ship it** — `/age <slug> --auto --open-pr`: run age → cure headless and open (or push) the PR at the end.
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause.
- **Stop** — dispatch none; defer review (use this if you want to harden manually before /age, even though the contract is review-safe).

Pre-select **Review the diff** when readiness is `ready for /age` or `follow-up recommended`. If the report is `blocked`, do not pre-select anything (and do not pre-select **Ship it**); the user decides whether to fix or escalate. After a non-stop selection, run the selected command immediately.

### Auto mode

When invoked with `--auto` (propagated from `/cook --auto`):

- Skip the handoff gate entirely.
- If readiness is `ready for /age` or `follow-up recommended`, invoke `/age <slug> --auto` directly (forward `--open-pr` when it is in scope).
- If readiness is `blocked`, stop the auto chain and surface the press report to the user. Blocked criteria: defined once in [`references/gap-analysis.md`](references/gap-analysis.md).

### When invoked from /ultracook

`/ultracook` spawns press as a fresh-context sub-agent and owns the chain itself. When the spawn prompt explicitly says "for THIS PHASE ONLY" and "do not chain forward to the next phase," honour the override: write `.cheese/press/<slug>.md` (with the handoff slug at the top) and stop. Do not invoke `/age <slug> --auto` from inside the sub-agent regardless of readiness. The orchestrator reads the handoff slug and either chains to age (when `status: ok` and `next: age`) or halts (when `status: halt`, regardless of `next:`). `next:` remains the resume hint for `/cheese --continue`.

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- **Every changed behaviour in the cooked diff leaves press with an executable hardening test that would fail if the change regressed.** If press cannot produce a stable hardening test for a changed behaviour (flaky seam, missing infrastructure, design decision required), readiness is `blocked` — never `ready for /age` or `follow-up recommended`.
- **Cap iteration at three attempts per gap.** Count test-edit + run cycles. On the third failed cycle on the same gap, mark readiness `blocked` with reason `spinning: <gap-description>` and surface the report. Do not loop indefinitely.
- Surface medium and high findings explicitly; summarize low findings.
- If the cooked diff or spec rests on a false premise (the contract is wrong, or the test surface is solving the wrong problem), stop and surface the premise before adding tests; do not harden the wrong angle.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the press report with the readiness verdict, flag residual risk as `certain | speculating | don't know`, agree when coverage is already sufficient without manufacturing tests.
