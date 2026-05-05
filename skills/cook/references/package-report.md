# Package-ready report

Before opening a PR or handing off to `/age`, cook produces a package-ready report.

## Output shape

```markdown
## Cook Report — <slug>

### Contract
- Behaviour: <one line>
- Non-goals: <list or "none">
- Quality gates: <commands>

### Files changed
- <path>: <one-line reason>

### Tests
- <command>: <pass | fail | skipped with reason>

### Risks
- <bullet — known unknown, deferred decision, or anything you'd want a reviewer to look at>

### Self-eval
- [x] Cut wrote failing tests before production changes.
- [x] Cook made tests pass without speculative behaviour.
- [x] Taste-test passed.
- [x] Quality gates pass.
- [x] All changed files are intentional.

### Next step
- /press <slug>   — harden tests and check coverage
- /age <slug>     — review the diff
- /cure <slug>    — apply selected age findings (after /age)
```

## Honesty rules

- **Never claim green on partial work.** If a test is skipped, list the command and the reason.
- **Never hide a failed gate.** If lint failed and you didn't fix it, the report says so and recommends a follow-up.
- **Never claim "ready for /age" if any taste-test lens returned `revise` and you didn't address it.** That's the cardinal sin.

## Stop conditions

Cook stops (does not produce a "ready" report) when:
- A spec decision was missing and the user has not answered.
- Tests cannot be made to fail for the expected reason.
- The two-round taste-test cap was hit and findings remain.
- A quality gate fails and the fix is outside the cooked contract.

In each case, the report says "blocked" with the precise reason.
