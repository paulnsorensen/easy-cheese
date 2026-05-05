# The TDD loop: cut → cook → taste-test

The cook skill runs a sequential TDD discipline. Each phase has a clear exit before the next starts.

## Cut — failing tests first

When the change adds or modifies behaviour, write the test before the implementation.

**Cut must report:**

- Test files added or changed.
- The spec requirement each test covers.
- The observed red failure for each new behaviour.
- Whether existing tests were touched and why (only allowed for related-fixture or shared-helper updates — never to weaken assertions).

If a test cannot be made to fail for the expected reason, **stop and fix the test before cooking**. A test that passes against unimplemented code is a false-positive factory.

## Cook — minimal green

Implement the smallest production change that turns the cut tests green.

**Cook must:**

- Use existing dependencies and project patterns.
- Run the narrowest useful test (the new cut tests) plus relevant wider gates (lint, typecheck, build).
- Preserve strong assertions written by cut.
- Stop and ask if implementation reveals a design decision the spec did not answer.

If cook reports partial or skipped work, **stop and resolve before taste-test**.

## Taste-test — drift / readability / scope

After cook says "I completed all the changes", run a taste test before press. This reduced workflow uses one inline taste-test step:

| Lens | Question | Pass criterion |
| --- | --- | --- |
| Spec | Did the implementation drift from the spec? | Every behaviour described in the spec is present; nothing extra. |
| Readability | Is the change as concise and clear as possible? | A reviewer can understand each changed file without external context. |
| Scope | Did cook add more than asked? | The diff matches the spec's bullets; no speculative helpers. |

Each lens returns `pass` or `revise`. Pipe every `revise` finding back into a bounded corrective cook pass with the original spec, the cook report, and the taste evidence.

## Two-round cap

```
best:    cook → taste-test (all pass) → press
worst:   cook → taste-test → cook → taste-test → cook (final)
```

After the second taste test, allow only one final corrective cook pass. If that final pass cannot fully resolve the taste findings, **stop and report blocked** instead of continuing to press.

## Why a cap

Without it, the loop has no termination — every taste pass can find something to nudge. The cap forces a "ship or escalate" decision instead of infinite refinement.

## Self-evaluation before handoff

```
- [ ] Spec or acceptance criteria are clear.
- [ ] Cut wrote failing tests before production changes.
- [ ] Cook made tests pass without speculative behaviour.
- [ ] Taste-test passed or completed the two-round corrective loop.
- [ ] Relevant quality gates pass.
- [ ] All changed files are intentional.
- [ ] Remaining risks or skipped checks are documented.
```
