# /cook — TDD Discipline

## Iron Law

**Do not write production code before you have a failing test.**

The RED step requires you to write a failing test.  
The RED step is mandatory.  
Do not perform the RED step "right after" implementation.  
If the test does not exist and does not fail, the Cook loop has not started.

---

## Red Flags

Stop if you think any of these statements:

- "The behavior is obvious from the spec; a test would just restate it."
- "I'll add tests in the press pass."
- "This is a small change; tests are overkill."
- "The existing tests already cover this implicitly."
- "The type system / linter makes a test redundant here."
- Do not treat the post-implementation taste-test as proof that you can skip the RED step.

Each statement is a rationalization.  
Name the rationalization.  
Stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The change is obvious; a test would just mirror the code." | A mirroring test still catches future regressions. It must fail when behavior changes. It does not have to surprise you today. | Write the test. |
| "I'll write the test in the press pass." | Press strengthens existing tests. It does not write the first test for new behavior. Behavior without a test has no harness. | Write the test first, before you write production code. |
| "This is a one-line fix; tests are overkill." | Change size does not predict the probability of regression. One-line fixes often have subtle edge cases. | Write the narrowest test that would have caught the original bug. |
| "The existing suite already covers this path." | Verify the coverage. Find the specific test that fails if the new behavior regresses. If you cannot name it, you imagined the coverage. | Name the specific test, or write a new test. |
| "The type system makes a runtime test redundant." | Types verify shape. Tests verify behavior. A function with the correct signature can still return the wrong value. | Write a test that asserts the return value, not only that the code compiles. |
| "The taste-test lenses will catch any issues." | Taste-test is a post-implementation smell check. It does not replace executable assertions. | Write the test first. |
| "We're under time pressure; I'll skip the test for this task." | Regressions cause the most harm under time pressure. The test is the least expensive available insurance. | Write the test. Never use time pressure as grounds to skip the RED step. |
