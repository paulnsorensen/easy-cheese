# The TDD loop: cut → implement → taste-test

The cook skill runs a sequential TDD discipline. Each phase has a clear exit before the next starts.

## Cut — failing tests first

When the change adds or modifies behaviour, write the test before the implementation.

**Cut must report:**

- Test files added or changed.
- The spec requirement each test covers.
- The observed red failure for each new behaviour.
- Whether existing tests were touched and why (only allowed for related-fixture or shared-helper updates — never to weaken assertions).

If a test cannot be made to fail for the expected reason, **stop and fix the test before cooking**. A test that passes against unimplemented code is a false-positive factory.

## Implement — minimal green

Implement the smallest production change that turns the cut tests green.

**Implement must:**

- Use existing dependencies and project patterns.
- Run the narrowest useful test (the new cut tests) plus relevant wider gates (lint, typecheck, build).
- Preserve strong assertions written by cut.
- Stop and ask if implementation reveals a design decision the spec did not answer.

If cook reports partial or skipped work, **stop and resolve before taste-test**.

## Taste-test — drift, readability, scope, simplify, plus three fresh-context lenses

After cook says "I completed all the changes", run a taste test before press. The taste-test is a **fresh-context review**: when the cooked diff is non-trivial it is dispatched to a read-only reviewer that did not write the code. Small diffs keep the cheap inline check.

**Cost gate — where it runs.** Dispatch the fresh-context taste-test only when the cooked diff **touches more than one file OR adds public surface** (a new exported/public function, type, or CLI seam). Single-file, no-public-surface fixes keep the inline self-check — the dispatch is not worth its latency there.

**Who runs it.**

- **Top-level `/cook`**: resolve the fresh-context taste-test through `../../cheese/references/agent-resolution.md`, requesting a read-only `reviewer` at `powerful` / `high`. Pass `{spec/contract, diff, cut-test list, any locked/user-approved decisions}`; it returns the per-lens verdict below, not a full `/age` report. A general worker may qualify only under the shared prompt-only read-only degradation.
- **Coder-nested `/cook`**: when the active coder cannot dispatch, run the inline self-check and record `taste_test: deferred-to-orchestrator`; the orchestrator must resolve and run the authoritative reviewer before accepting the handoff.

**Lenses.** Inline or dispatched, the taste-test returns `pass | revise` per lens (`halt` for Locked-decision):

| Lens | Question | Pass criterion |
| --- | --- | --- |
| Spec | Did the implementation drift from the spec? | Every behaviour described in the spec is present; nothing extra. |
| Readability | Is the change as concise and clear as possible? | A reviewer can understand each changed file without external context. |
| Scope | Did cook add more than asked? | The diff matches the spec's bullets; no speculative helpers. |
| Simplify | Does the diff reuse what exists, stay clean, and avoid wasted work? | See sub-checks below; all three must pass. |
| Production path | Does every spec acceptance criterion have a *production* path that exercises it? | The behaviour is reachable from real callers, not only from tests that manufacture the state. |
| Wired callers | Does each new public function have a non-test caller? | A non-test caller exists, or the diff carries an explicit "wired in phase X" note. |
| Locked-decision | If the dispatch prompt carries a locked/user-approved decision, does the diff implement *that* decision? | The diff honours the locked decision, or the reviewer returns `halt` flagging the divergence. |

The last three lenses are the fresh-context additions — they encode the failures the inline taste-test historically passed: a missing production path, public functions with zero non-test callers, and a silently-substituted design decision. A `halt` from the Locked-decision lens stops the chain for a human decision; it is not a corrective-cook finding.

The **Simplify** lens runs three sub-checks (the same three axes `/simplify` uses):

- **Reuse** — new code does not duplicate an existing utility/helper/component; inline logic that has a project helper uses it; no near-duplicates of an existing function.
- **Quality** — no redundant state (cached value that can be derived), no parameter sprawl (added params instead of restructuring), no copy-paste-with-variation, no leaky abstraction (exposing internals across a slice boundary), no stringly-typed code where a constant/enum/union exists.
- **Efficiency** — no unnecessary work (redundant compute, repeated reads, N+1), no missed concurrency on independent ops, no recurring no-op state/store updates in loops or handlers, no pre-existence checks that should instead perform the operation and handle the resulting error, no unbounded structures or leaked listeners/timers, no full-file/dataset reads when a slice would do.

Each lens returns `pass` or `revise` (`halt` for Locked-decision). Pipe every `revise` finding back into a bounded corrective cook pass with the original spec, the cook report, and the taste evidence.

## Two-round cap

```
best:    implement → taste-test (all pass) → press
worst:   implement → taste-test → implement → taste-test → implement (final)
```

After the second taste test, allow only one final corrective cook pass. If that final pass cannot fully resolve the taste findings, **stop and report blocked** instead of continuing to press.

## Self-evaluation before handoff

Confirm every item the package report asserts (`package-report.md` § Self-eval),
plus two it does not surface:

- [ ] Spec or acceptance criteria are clear.
- [ ] Remaining risks or skipped checks are documented.
