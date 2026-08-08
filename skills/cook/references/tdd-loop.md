# The TDD loop: preflight → inner RED → implement → taste-test

Cook runs a sequential TDD discipline. The outer GateReceipt boundary must
complete before the inner implementation loop starts, and each phase has a
clear exit before the next starts.

## Preflight — canonical outer receipt

`GateReceipt` is the sole outer-oracle authority. Before any production
mutation, Cook must either receive a canonical receipt or synchronously invoke
Cut and consume the receipt Cut returns. A synchronous Cut invocation returns
to this preflight exactly once; it never recursively dispatches Cook.

The preflight verifies, in order:

1. The receipt loads canonically and names the same `spec_ref`, `work_id`, and
   sanitized `project_key` as the Cook invocation.
2. Every protected-file hash and the complete guard graph are valid. Guards
   retain matching work/spec/project identity, valid RED disposition, and the
   required transitive Cut ancestry.
3. For RED evidence, Cook executes
   `red-gate validate <receipt> --state red` before the first production edit.
   The active case and every transitive guard must pass replay and structural
   validation.

If the receipt is absent or invalid, invoke Cut before production, passing any
user or Pasteurize reproduction for normalization. Cut's issued evidence
`producer: cut` and adopted cases retain `origin: adopted`. Cook must not
hand-write, replace, or mutate the returned outer oracle or any receipt-owned
file.

Closed `not-applicable` receipts retain identity and structural validation,
skip only outer RED replay, then continue with the requested
docs/refactor/test/appearance work through the appropriate non-behavior
implementation and verification path. N/A never means no requested work. No
invalid receipt is allowed to fall through into inner TDD.

## Inner TDD — failing tests first

When the change adds or modifies behavior, write an inner failing test before
the implementation. This is Cook's vertical loop, not Cut's protected outer
tracer: Cut owns the outer RED evidence and Cook must never rewrite it.

For behavior changes, the inner TDD loop is the only stage allowed to mutate
production. Closed N/A work instead uses its declared non-behavior
implementation path after preflight; it may edit only the requested surface.
Both paths must never change receipt-protected files, the outer oracle, or their digests.

If an inner test cannot fail for the expected reason, **stop and fix the test
before implementing**. A test that passes against unimplemented code is a
false-positive factory.

## Implement — minimal green

For behavior work, implement the smallest production change that turns the
inner tests green. For closed N/A work, implement the requested
docs/refactor/test/appearance change through its non-behavior path and verify
that path instead of replaying RED.

**Implement must:**

- Use existing dependencies and project patterns.
- Run the narrowest useful inner test plus relevant wider gates (lint,
  typecheck, build).
- Preserve every protected assertion and outer receipt digest.
- Stop and ask if implementation reveals a design decision the spec did not
  answer.

Before handing off to Press, Cook runs
`red-gate validate <receipt> --state green` for an active RED receipt and
requires the active case and every transitive guard GREEN before handing off to
Press. For closed N/A, complete the requested non-behavior verification and
taste-test, then hand off directly to Age; N/A has no Test Contracts for Press
to attack.
A corrective Cook (`correction = true`) is scoped to the active Press RED
receipt and may not weaken, replace, or bypass any transitive guard.

If cook reports partial or skipped work, **stop and resolve before taste-test**.

## Taste-test — drift, readability, scope, simplify, plus three fresh-context lenses

After cook says "I completed all the changes", run a taste test before press. The taste-test is a **fresh-context review**: when the cooked diff is non-trivial it is dispatched to a read-only reviewer that did not write the code. Small diffs keep the cheap inline check.

**Cost gate — where it runs.** Dispatch the fresh-context reviewer unless all four hold: single file AND no new public surface AND <~40 changed lines AND no risk flag — then run the coder self-check instead. Any one term failing routes to 1 fresh opus reviewer.

**Risk flag** — one of the override categories in `src/fanout/age_route.py`'s `OVERRIDE_FLAGS` constant: auth/secrets/crypto/tenant isolation; payments/ledgers/irreversible effects; concurrency/idempotency/ordering/retries; schema/migration/protocol/public-API change; production-destructive ops; weak integration coverage around a global invariant. On a bundle-only host the same constant ships in the age bundle (`python3 ${CLAUDE_SKILL_DIR}/../age/scripts/age.pyz age-route` consumes the flags; see `skills/age/SKILL.md § Router call` for the exact vocabulary).

**Who runs it.**

- **Top-level `/cook`**: resolve the fresh-context taste-test through
  `../../cheese/references/agent-resolution.md`, requesting a read-only
  `reviewer` at `powerful` / `high`. Pass
  `{spec/contract, GateReceipt, diff, inner-test list, any locked/user-approved decisions}`;
  it returns the per-lens verdict below, not a full `/age` report. A general
  worker may qualify only under the shared prompt-only read-only degradation.
- **Coder-nested `/cook`**: when the active coder cannot dispatch, run the inline self-check and record `taste_test: deferred-to-orchestrator`; the orchestrator must resolve and run the authoritative reviewer before accepting the handoff.

**Lenses.** Inline or dispatched, the taste-test returns `pass | revise | escalate` per lens (`halt` for Locked-decision):

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

**Escalate-unverifiable.** When a lens cannot verify its claim from available evidence, it returns `escalate` for that lens, never a guessed `pass` or `revise` (cross-cutting contract 1 in the spec: "a claim no evidence can settle returns escalate, never a guessed pass or fail").

The **Simplify** lens runs three sub-checks (the same three axes `/simplify` uses):

- **Reuse** — new code does not duplicate an existing utility/helper/component; inline logic that has a project helper uses it; no near-duplicates of an existing function.
- **Quality** — no redundant state (cached value that can be derived), no parameter sprawl (added params instead of restructuring), no copy-paste-with-variation, no leaky abstraction (exposing internals across a slice boundary), no stringly-typed code where a constant/enum/union exists.
- **Efficiency** — no unnecessary work (redundant compute, repeated reads, N+1), no missed concurrency on independent ops, no recurring no-op state/store updates in loops or handlers, no pre-existence checks that should instead perform the operation and handle the resulting error, no unbounded structures or leaked listeners/timers, no full-file/dataset reads when a slice would do.

Each lens returns `pass`, `revise`, or `escalate` (`halt` for Locked-decision). Pipe every `revise` finding back into a bounded corrective cook pass with the original spec, the cook report, and the taste evidence.

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
