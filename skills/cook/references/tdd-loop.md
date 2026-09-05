# The TDD loop: inner RED → implement → taste-test

Cook uses a sequential TDD discipline. Each phase must have a clear exit before the next phase starts.

Closed `not-applicable` work routes requested docs/refactor/test/appearance work through its non-behavior implementation and verification path. N/A never means that requested work is not necessary.

## Inner TDD — failing tests first

When a change adds or modifies behavior, write an inner failing test before implementation. This test is Cook's vertical loop.

For behavior changes, only the inner TDD loop can modify production code. Closed N/A work must use its declared non-behavior implementation path. It can edit only the requested surface.

If an inner test cannot fail for the expected reason, **stop and fix the test before implementing**. A test that passes against unimplemented code creates false-positive results.

## Implement — minimal green

For behavior work, make the smallest production change that makes the inner tests green.

For closed N/A work, make the requested docs/refactor/test/appearance change through its non-behavior path. Verify that path instead of replaying RED.

**Implement must:**

- Use existing dependencies and project patterns.
- Run the narrowest useful inner test.
- Run relevant wider gates: the project formatter, lint, type check, and build.
- Stop and ask if implementation identifies a design decision that the spec does not answer.

### Reviewable by construction

Write the change so the taste-test and `/age` pass on the first round. Each rule below maps to a lens or dimension that otherwise sends the work back. The evidence is in `.hallouminate/wiki/research/language-reviewability-evidence.md`.

- **Full-word identifiers.** No abbreviations or single letters outside a loop index or a conventional short name (`i`, `db`, `ctx`). Reviewers find defects about 19% faster with full words.
- **Local reasoning.** A reviewer must understand each changed function from its own body plus the signatures it calls. Do not add monkey-patching, side-effecting decorators, `__getattr__` or `__getattribute__` tricks, operator overloading, metaclass logic, or exception-based control flow that crosses a module boundary.
- **Let the type checker review.** Annotate every new parameter and return. Use a closed union or enum instead of a string tag. Make every `match` or `switch` over a closed union exhaustive with `assert_never` / `assertNever`; never rely on a silent default arm.
- **Canonical formatting.** Run the project formatter before handoff so the diff carries no formatting noise.
- **Stay under the comprehension ceiling.** Keep the semantics-altering surface under roughly 400 changed code lines. When the contract needs more, name the layer boundaries in the package report so `/plate` can recommend a stack.

These rules do not license speculative types, helpers, or abstractions. Scope and Simplify still apply.

Before handoff to Press, make every inner test and relevant gate GREEN.

For closed N/A work, complete the requested non-behavior verification and taste-test. Then, hand off directly to Age. N/A has no Test Contracts for Press to attack.

A corrective Cook (`correction = true`) applies only to the active Press corrective loop. It must not weaken, replace, or bypass an existing test.

If Cook reports partial or skipped work, **stop and resolve it before taste-test**.

## Taste-test — drift, readability, scope, simplify, plus three fresh-context lenses

After Cook says "I completed all the changes", run a taste test before Press. The taste-test is a **fresh-context review**.

For a non-trivial cooked diff, dispatch the review to a read-only reviewer that did not write the code. For a small diff, use the low-cost inline check.

**Cost gate — where it runs.**

Dispatch the fresh-context reviewer unless all four conditions are true:

- The diff changes one file.
- The diff adds no new public surface.
- The diff has <~40 changed lines.
- The diff has no risk flag.

If all four conditions are true, run the coder self-check. If one condition is false, route the review to 1 fresh opus reviewer.

### Risk flag

A risk flag is one of these override categories from the bundled age router:

- auth/secrets/crypto/tenant isolation
- payments/ledgers/irreversible effects
- concurrency/idempotency/ordering/retries
- schema/migration/protocol/public-API change
- production-destructive ops
- weak integration coverage around a global invariant

`python3 skills/cook/scripts/cook.pyz age-route` consumes the flags.
See [`../../age/references/fan-out.md`](../../age/references/fan-out.md#router-call) for the exact tokens and the JSON shape.
The router ignores an unknown flag, so a spelling error removes a risk promotion.

**Who runs it.**

- **Top-level `/cook`**:
  - Resolve the fresh-context taste-test through `../../cheese/references/agent-resolution.md`.
  - Request a read-only `reviewer` at `powerful` / `high`.
  - Pass `{spec/contract, diff, inner-test list, any locked/user-approved decisions}`.
  - The reviewer returns the per-lens verdict below.
  - The reviewer does not return a full `/age` report.
  - A general worker can qualify only under the shared prompt-only read-only degradation.
- **Coder-nested `/cook`**:
  - If the active coder cannot dispatch, run the inline self-check.
  - Record `taste_test: deferred-to-orchestrator`.
  - The orchestrator must run the authoritative reviewer before it accepts the handoff.

**Lenses.**

The inline or dispatched taste-test returns `pass | revise | escalate` for each lens. The Locked-decision lens can also return `halt`.

| Lens | Question | Pass criterion |
| --- | --- | --- |
| Spec | Did the implementation drift from the spec? | Every behavior described in the spec is present; nothing extra. |
| Readability | Is the change as concise and clear as possible? | A reviewer can understand each changed function from its body and the signatures it calls, without external context. Identifiers are full words. No monkey-patching, side-effecting decorators, `__getattr__` tricks, operator overloading, or cross-module exception control flow. |
| Scope | Did Cook add more than asked? | The diff matches the spec's bullets; no speculative helpers. |
| Simplify | Does the diff reuse what exists, stay clean, and avoid wasted work? | See sub-checks below; all three must pass. |
| Production path | Does every spec acceptance criterion have a *production* path that exercises it? | The behavior is reachable from real callers, not only from tests that manufacture the state. |
| Wired callers | Does each new public function have a non-test caller? | A non-test caller exists, or the diff carries an explicit "wired in phase X" note. |
| Locked-decision | If the dispatch prompt carries a locked/user-approved decision, does the diff implement *that* decision? | The diff honors the locked decision, or the reviewer returns `halt` flagging the divergence. |

The last three lenses are fresh-context additions. They identify failures that the inline taste-test historically passed:

- A missing production path.
- Public functions with no non-test callers.
- A silently substituted design decision.

A `halt` from the Locked-decision lens stops the chain for a human decision. It is not a corrective Cook finding.

**Escalate-unverifiable.**

If available evidence cannot verify a lens claim, return `escalate` for that lens. Never return a guessed `pass` or `revise`.

This rule implements cross-cutting contract 1 in the spec: "a claim no evidence can settle returns escalate, never a guessed pass or fail".

The **Simplify** lens uses the same three sub-checks as `/simplify`:

- **Reuse**
  - New code must not duplicate an existing utility, helper, or component.
  - Inline logic must use an available project helper.
  - New code must not create a near-duplicate of an existing function.
- **Quality**
  - Do not add redundant state, such as a cached value that the code can derive.
  - Do not add parameters when code restructuring is appropriate.
  - Do not use copy-paste-with-variation.
  - Do not create a leaky abstraction that exposes internals across a slice boundary.
  - Do not use stringly-typed code when a constant, enum, or union exists.
- **Efficiency**
  - Avoid unnecessary work, including redundant compute, repeated reads, and N+1.
  - Use concurrency for independent operations.
  - Avoid recurring no-op state or store updates in loops or handlers.
  - Do not use pre-existence checks when the operation can handle the resulting error.
  - Do not use unbounded structures.
  - Do not leak listeners or timers.
  - Read a slice instead of a full file or dataset when a slice is sufficient.

Each lens returns `pass`, `revise`, or `escalate`. The Locked-decision lens can also return `halt`.

Send every `revise` finding into a bounded corrective Cook pass. Include the original spec, the Cook report, and the taste evidence.

## Two-round cap

```
best:    implement → taste-test (all pass) → press
worst:   implement → taste-test → implement → taste-test → implement (final)
```

After the second taste test, allow only one final corrective Cook pass.
Stop when the final pass cannot resolve all taste findings.
Report the result as **blocked**.
Do not continue to Press.

## Self-evaluation before handoff

Confirm every item that the package report asserts (`package-report.md` § Self-eval). Also confirm these two items:

- [ ] Spec or acceptance criteria are clear.
- [ ] The report documents every remaining risk and every skipped check.
