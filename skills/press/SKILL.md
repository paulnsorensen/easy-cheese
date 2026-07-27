---
name: press
description: Harden the test surface after `/cook` — map changed behavior to tests, find weak assertions and missing boundaries, and add focused hardening tests. Use when the user wants the tests strengthened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force.
license: MIT
---

# /press

Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## --hard propagation

`/press --hard` (propagated from `/cook --hard`) is pass-through only. Press runs no gate. Hand `--hard` forward to `/age` at the handoff so it eventually reaches `/cure`, which is the only pipeline skill that fires the metacognitive vibecheck. See `skills/hard-cheese/SKILL.md`.

## Baseline-aware gates

When the inherited cook envelope carries `payload.baseline`, press re-runs the gates but does not re-flag failures identical to that recorded baseline; only new or changed failures affect readiness.

## Flow

1. **Read** — load the spec or acceptance criteria and the cooked diff. If `.cheese/glossary/<slug>.md` exists, read it for naming consistency when hardening tests.
2. **Map** — for each changed behaviour, find the test(s) that cover it through semantic caller search.
3. **Gap analysis** — identify weak assertions, missing boundaries, and uncovered integration seams. See `references/gap-analysis.md` for what counts as a gap and the priority order.
4. **Add focused tests** — observe red first when behaviour changes. Apply precise stale-safe edits.
5. **Corrective fixes** — only for defects the hardening tests expose. No new behaviour.
6. **Run checks** — narrowest useful tests, then relevant wider gates already in the project. When the handoff carries `payload.baseline`, classify gate failures against it per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md): identical failures do not affect readiness; only new or changed failures do.
7. **Report** — build the press body, commit the versioned `press` envelope through `handoff-commit`, and print its returned path. Mark readiness as `ready for /age`, `follow-up recommended`, or `blocked`.
8. **Hand off** — in manual mode, prompt the next step via the shared [handoff gate](../cheese/references/handoff-gate.md) (see `## Handoff` below); in `--auto` mode, chain forward per `## Auto mode`.

## Preferred tools and fallbacks

Call source-code search, read, and edit backends directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). For coverage and test discovery, use semantic caller search plus `tilth_deps` when available.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

Beyond source-code routing there are press-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff review | `delta` | plain `git diff` |
| Affected execution flows + risk scoring | semantic caller/dependency tracing and `tilth_deps` | manual flow tracing from changed files; note the precision loss |

If optional tools are missing, press a narrower surface and state the residual risk.

## Output

House style and citation form: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). This section owns the press-report shape.

Build the report body below, then commit it through the shared runtime with `phase: press`. Put a propagated quality-gate baseline in `payload.baseline` and use the artifact path returned by `handoff-commit`.

```markdown
# Press Report — <slug>

## Orientation
<one or two factual sentences about the hardening added, gaps closed, and readiness verdict.>

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

Commit `status: ok` for `ready for /age` or `follow-up recommended`; commit `status: halt` with a non-empty reason for `blocked`. Set `next_phase: age` when review-safe, `press` when the phase must rerun, or `done` only for terminal completion. When `payload.baseline` is present, identical recorded failures do not change readiness; only new or changed failures do.

Print `Press report: <path>` using the artifact returned by `handoff-commit`, followed by the readiness next step.

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → plate

After committing the press report, call `handoff-resolve`; when manual choice is still required, use the shared [handoff gate](../cheese/references/handoff-gate.md). Lead each option with the verb. Default options:

- **Review the diff** *(recommended when readiness is `ready for /age` or `follow-up recommended`)* — `/age <slug>`. For `follow-up recommended`, documented follow-ups can be addressed after review.
- **Plate it** — `/age <slug> --auto --open-pr`: run age → cure, then `/plate` resolves topology and publishes.
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause.
- **Stop** — dispatch none; defer review (use this if you want to harden manually before /age, even though the contract is review-safe).

Pre-select **Review the diff** when ready. If blocked, do not pre-select **Plate it**. Run a non-stop selection immediately.

## Auto mode

When invoked with `--auto` (propagated from `/cook --auto`):

- Skip the handoff gate entirely.
- If readiness is `ready for /age` or `follow-up recommended`, invoke `/age <slug> --auto` directly (forward `--open-pr` when it is in scope).
- If readiness is `blocked`, stop the auto chain and surface the press report to the user. Blocked criteria: defined once in [`references/gap-analysis.md`](references/gap-analysis.md).

### Within cook's own fan pathway

When `/cook`'s fan pathway spawns press phase-only, commit the versioned press envelope, return its artifact path, and stop. Set `next_phase: age` for review-safe work or commit `status: halt` with a non-empty reason when blocked. The parent calls `handoff-resolve` and owns dispatch.

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- **Every changed behaviour in the cooked diff leaves press with an executable hardening test that would fail if the change regressed.** If press cannot produce a stable hardening test for a changed behaviour (flaky seam, missing infrastructure, design decision required), readiness is `blocked` — never `ready for /age` or `follow-up recommended`.
- **Cap iteration at three attempts per gap.** Count test-edit + run cycles. On the third failed cycle on the same gap, mark readiness `blocked` with reason `spinning: <gap-description>` and surface the report. Do not loop indefinitely.
- Surface medium and high findings explicitly; summarize low findings.
- If the cooked diff or spec rests on a false premise (the contract is wrong, or the test surface is solving the wrong problem), stop and surface the premise before adding tests; do not harden the wrong angle.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the press report with the readiness verdict, flag residual risk as `certain | speculating | don't know`, agree when coverage is already sufficient without manufacturing tests.

## Work continuity

Follow the executable [cross-skill work contract](../cheese/references/work-contract.md) before phase work. A meaningful direct invocation ensures one WorkRecord; a nested invocation joins the inherited work ID. Emitting phases commit their versioned envelope and report body through `handoff-commit`, then act only on `handoff-resolve`. Never write or route from a legacy line-based handoff header.
