# Cut pressure evaluation

This is the AC-12 pressure scenario for the `/cut` skill. It is deliberately
small: add one caller-visible behavior to an existing project with a runner,
a dirty worktree, and an optional Pasteurize reproduction. The evaluator asks
whether a fresh agent preserves the outer RED boundary before implementation,
not whether it can repeat the words “write a test.”

## Failing pre-skill baseline

Run the scenario with no Cut skill loaded. The captured baseline below is the
failure this skill must correct:

```text
baseline_verdict: fail
baseline_artifact: absent
baseline_handoff: absent
events:
- read-spec
- production-edit:first
- write-test
- run-tests-after-production-edit
- report-green
```

The first production edit precedes any durable outer RED evidence, so the run
cannot prove that the requested behavior failed before implementation. A test
added later is not a Cut receipt and does not repair this baseline.

## Corrected durable workflow

Run the same scenario with `/cut` active and with `auto = false` so the
synchronous boundary is observable. The expected durable trace is:

```text
corrected_verdict: pass
events:
- read-spec
- red-gate-contracts
- select-or-infer-contracts
- select-existing-runner
- write-test-only-tracer
- baseline-green
- declared-red-witness
- protected-test-digests
- red-gate-issue
- return-receipt-to-cook
- no-recursive-cook-dispatch
```

The corrected run has these durable assertions:

```text
production_edit_before_issue: false
production_edit_during_issue: false
initial_guard_receipt_refs: []
producer: cut
origin: generated-or-adopted
handoff:
status: ok
next: cook
artifact: .cheese/cut/<slug>.json
```

The `auto = true` variant replaces the final two events with one downstream
`dispatch-cook-with-receipt` event. It must still issue the receipt first and
must not invoke a second Cut/Cook cycle.

## Oracle-sensitivity mutations

The evaluator mutates or removes one oracle claim at a time. Every mutation is
expected to reject the workflow rather than silently pass on surrounding prose:

```text
oracle-sensitivity: required
mutation: remove expected witness -> reject
absence: remove baseline check -> reject
mutation: change production file -> reject
absence: remove protected test digest -> reject
absence: replace red-gate issue with raw receipt write -> reject
absence: use an unavailable runner without a harness decision -> reject
```

A mutation that leaves a run marked `pass` is an oracle failure. In particular,
removing the assertion witness or the protected test digest must be observable;
checking only that a test file exists is insufficient.

## AC-12 evidence record

The pressure artifact is complete only when it retains both verdicts and their
ordered traces:

1. `baseline_verdict: fail` is captured before the durable skill body is
   enabled;
2. `corrected_verdict: pass` follows with the skill active;
3. the corrected trace places baseline GREEN before declared RED and
   `red-gate-issue` after the failing witness;
4. the corrected trace contains no production edit and records the exact Cook
   handoff; and
5. each oracle-sensitivity mutation or absence case is rejected.

This reference is the durable scenario definition. The focused pressure test
must fail if either verdict, event order, handoff, or mutation resistance is
removed.
