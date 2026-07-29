# Package-ready report

Before opening a PR or handing off to `/age`, cook produces a package-ready report.

Cross-cutting house style and citation form: [`formatting.md`](../../cheese/references/formatting.md). This file owns the package-report shape; formatting.md owns the voice rules and the footnote primitive. Quality-gate failure handling (baseline classification, the three-way policy, the `baseline:` block) is owned by [`quality-gates.md`](quality-gates.md) — this file only shapes how that policy renders in the report.

## Output shape

```markdown
## Cook Report — <slug>

### Contract
- Behaviour: <one line>
- Non-goals: <list or "none">
- Quality gates: <commands>

### Files changed
- <path>: <one-line reason>
- <path>: collateral repair: <one-line reason> — for a repair outside the cooked contract, per the three-way policy in [`quality-gates.md`](quality-gates.md)

### Tests
- <command>: <pass | fail | skipped with reason>

### Risks
- <bullet — known unknown, deferred decision, or anything you'd want a reviewer to look at>

### Baseline (if any recorded)
- <suite>/<test_id>: <signature> — identical to baseline, outside the cooked contract, not fixed (see [`quality-gates.md`](quality-gates.md))

### Self-eval
- [x] Cut wrote failing tests before production changes.
- [x] Cook made tests pass without speculative behaviour.
- [x] Taste-test passed.
- [x] Quality gates pass, or all remaining red is recorded baseline failure (see Baseline section).

### Next step
- /press <slug>   — harden tests and check coverage
- /age <slug>     — review the diff
- /cure <slug>    — apply selected age findings (after /age)
```

## Honesty rules

- **Never claim green on partial work.** If a test is skipped, list the command and the reason.
- **Never hide a failed gate.** If lint failed and you didn't fix it, the report says so and recommends a follow-up.
- **Never claim "ready for /age" if any taste-test lens returned `revise` and you didn't address it.** That's the cardinal sin.
- **When the Baseline section lists any recorded failures, the final summary states plainly that the full suite is not green** and lists those failures — loud, never hidden, per [`quality-gates.md`](quality-gates.md).

## Stop conditions

Cook stops (does not produce a "ready" report) when:
- A spec decision was missing and the user has not answered.
- Tests cannot be made to fail for the expected reason.
- The two-round taste-test cap was hit and findings remain.
- A quality gate fails on new or changed behaviour and the fix requires a design decision outside the spec (identical-to-baseline failures are recorded, not a stop condition — see [`quality-gates.md`](quality-gates.md)).

In each case, the report says "blocked" with the precise reason.
