# Gap analysis

After cook produces green changes, press identifies where the test surface is weak before review.

## What counts as a gap

| Gap type | Symptom | Example |
| --- | --- | --- |
| Spec uncovered | A spec bullet has no executable test | "Returns 401 on missing token" with no test for that path |
| Weak assertion | Test passes for the wrong reason | `expect(result).toBeTruthy()` instead of `expect(result).toEqual(expected)` |
| Missing boundary | Edge case not exercised | empty input, null, max-length, off-by-one, concurrent access |
| Integration seam | Cooked code crosses a boundary that is mocked or untested | filesystem write, subprocess, network call, time-dependent logic |
| Error path | Happy path tested, failure path not | What happens when the dependency throws? |

## Mapping changed behaviour to tests

For each function or module touched by the cooked diff:

1. Find existing tests via `cheez-search`:
   ```
   tilth_search(query: "<changed-symbol>", kind: "callers", scope: "**/*.test.*")
   ```
2. Read the test bodies to verify they actually exercise the new behaviour, not just the symbol's existence.
3. List any spec bullet without a corresponding test.

## Priority order

Address gaps in this order — stop when the time-budget runs out:

1. **Spec compliance:** every promised behaviour has executable coverage.
2. **Assertion strength:** tests fail for wrong values, wrong errors, or wrong state.
3. **Boundary behaviour:** empty, missing, malformed, minimal, maximum.
4. **Integration seams:** filesystem, subprocess, network, time, dependency failure when in scope.
5. **Happy path regression:** the primary user path still passes.

Higher-priority gaps block; lower-priority gaps become follow-ups.

## When to fix vs follow-up

| Situation | Action |
| --- | --- |
| Hardening test exposes a bug in cooked code | Fix it now (corrective fix only — no new behaviour). |
| Hardening test exposes a bug outside cooked scope | Document it in the press report; do not fix. |
| Coverage gap is in code that cook did not touch | Document it in the press report; do not add tests. |

## Hard rule — never weaken assertions

If a hardening test reveals that an existing test passes for the wrong reason, **strengthen the existing test**. Do not delete it, do not loosen its assertion, do not skip it. If you must skip it temporarily, the press report says exactly which test and why, and recommends a follow-up issue.
