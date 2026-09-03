# Package-ready report

Before Cook opens a PR or hands off to `/age`, Cook produces a package-ready report.

[`formatting.md`](../../cheese/references/formatting.md) defines the cross-cutting house style and citation format.

This file defines the package report structure.

`formatting.md` defines the voice rules and the footnote primitive.

[`quality-gates.md`](quality-gates.md) defines quality-gate failure handling, baseline classification, the three-way policy, and the `baseline:` block.

This file defines only how the report shows that policy.

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
- [x] A failing test existed before production changes.
- [x] Cook made tests pass without speculative behavior.
- [x] Taste-test passed.
- [x] Quality gates pass, or all remaining red is recorded baseline failure (see Baseline section).

### Next step
- /press <slug>   — harden tests and check coverage
- /age <slug>     — review the diff
- /cure <slug>    — apply selected age findings (after /age)
```

## Honesty rules

- **Never claim green on partial work.** If you skip a test, list the command and the reason.
- **Never hide a failed gate.**
  If lint fails, report the failure when you do not fix it.
  Recommend follow-up work.
- **Never claim "ready for /age" when an unresolved taste-test lens returns `revise`.**
  This claim is the cardinal sin.
- **When the Baseline section lists any recorded failures, state in the final summary that the full suite is not green.**
  The final summary lists those failures clearly, as [`quality-gates.md`](quality-gates.md) requires.

## Stop conditions

Cook stops and does not produce a "ready" report in these conditions:

- The specification requires a decision, and the user has not answered.
- Cook cannot make the tests fail for the expected reason.
- Cook reaches the two-round taste-test limit, and findings remain.
- A quality gate fails because of new or changed behavior, and the fix requires a design decision outside the specification.

Policy: identical-to-baseline failures are recorded, not a stop condition.

Record these failures as [`quality-gates.md`](quality-gates.md) specifies.

For each stop condition, the report says "blocked" and gives the precise reason.
