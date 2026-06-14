# /cook — TDD Discipline

See [`../../../shared/skill-authoring.md`](../../../shared/skill-authoring.md) for the
Iron Law / Red Flags / Rationalization-table template that governs this section.

---

## Iron Law

**No production code without a failing test first.**

The Cut step (write the failing test) is not optional and is never done
"right after" implementation. If the test does not exist and is not failing,
the Cook loop has not started.

---

## Red Flags

Stop if you notice yourself thinking any of these:

- "The behavior is obvious from the spec; a test would just restate it."
- "I'll add tests in the press pass."
- "This is a small change; tests are overkill."
- "The existing tests already cover this implicitly."
- "The type system / linter makes a test redundant here."
- Reaching for `taste_test: deferred-to-orchestrator` before writing a single
  test.

Each of these is a rationalization. Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The change is obvious; a test would just mirror the code." | A mirroring test still catches future regressions. Its job is to fail when behavior changes, not to surprise you today. | Write the test. |
| "I'll write the test in the press pass." | Press hardens existing tests; it does not write the first test for new behavior. A behavior with no test has no harness. | Write the test in Cut, before any production code. |
| "This is a one-line fix; tests are overkill." | The size of the change does not predict the probability of regression. One-line fixes often have subtle edge cases. | Write the narrowest test that would have caught the original bug. |
| "The existing suite already covers this path." | Verify it. Find the specific test that would fail if the new behavior regressed. If you cannot name it, coverage is imagined, not real. | Name the specific test, or write a new one. |
| "The type system makes a runtime test redundant." | Types verify shape; tests verify behavior. A function with the right signature can still return the wrong value. | Write a test that asserts the return value, not just that it compiles. |
| "The taste-test lenses will catch any issues." | Taste-test is a post-implementation smell check, not a substitute for executable assertions. | Write the test first. |
| "We're under time pressure; I'll skip cut for this task." | Time pressure is when regressions hurt most. The test is the cheapest insurance available. | Write the test. Time pressure is never grounds to skip Cut. |
