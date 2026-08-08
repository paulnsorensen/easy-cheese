# Press adversarial gap analysis

## Ownership boundary

Press is not a second first-coverage phase. Cut owns the protected outer
oracle; Cook owns the implementation and the inner RED→GREEN loop. Press
attacks the approved contract after Cook and writes only tests, fixtures, or
test-only harness support. A gap that needs production implementation becomes
an in-contract RED evidence receipt and a bounded corrective Cook request.

## What Press may expose

| Gap type | Evidence | Action |
| --- | --- | --- |
| In-contract defect | The approved seam fails on an adversarial input or transition | Preserve the identical failing test and digest; issue through `red-gate issue` as `producer: press` |
| Invalid evidence | Receipt is stale, malformed, witness-inconsistent, unchained, or has incomplete guards | Stop without a repair action |
| Production mutation | Any production path changes during a Press-owned interval | Stop without gated evidence |
| Out-of-contract behavior | A desired behavior is not in the approved Test Contracts | Record a review follow-up; do not implement it |

## Evidence sequence

At every Press entry and post-Cook resume:

1. Replay the original Cut receipt GREEN with `red-gate validate`.
2. Verify all protected oracle digests and capture every production-path digest.
3. Run the same adversarial attack without changing its test or fixture digest.
4. Compare the production snapshot at the next `Continue`, `Dispatch`, or
   `Stop` boundary. Any difference is `production_changed`.
5. For an in-contract RED, issue canonical evidence only through
   `red-gate issue`; guard the original Cut receipt and every prior Press
   receipt.

The failing-test digest is part of the evidence chain. A corrective Cook may
change production to make the attack GREEN, but it may not rewrite or weaken
the attack, its expected witness, its protected oracle, or its prior guards.

## Priority order

Press closes only adversarial gaps in the approved Cook contract:

1. Receipt and guard integrity.
2. Protected oracle and production-tree immutability.
3. Boundary, invalid-input, state-transition, integration, and error-path
   attacks that belong to the approved seam.
4. Assertion sensitivity: the attack must fail for the wrong value, state, or
   error, not merely because a command exited.

Cut/Cook own first coverage. Do not manufacture one hardening test per changed
behavior, and do not add tests for untouched or out-of-contract code.

## Repair bound and readiness

The packaged boundary derives repair state and production integrity from the
named canonical receipt plus the current one-use phase token; the request
cannot provide a repair counter or production verdict:

```json
{
  "outcome": "in_contract_red",
  "current_receipt": ".cheese/press/outer-tdd-gates.attempt-1.json",
  "phase_token_ref": ".cheese/press/outer-tdd-gates.attempt-1.phase.json",
  "phase_token_sha256": "<64 lowercase hex characters>"
}
```

The current receipt is always the receipt for the observation being routed:
P1 uses `.attempt-1.json`, P2 uses `.attempt-2.json`, and P3 uses
`.attempt-3.json`. Each attempt has its own `.plan.json`, `.phase.json`, and
`candidates/<slug>.attempt-N.json` paths; never reuse or overwrite an earlier
attempt's artifact.
Every new phase plan must repeat the exact `production_paths` bound by the
current receipt's phase token. The route boundary rejects narrower, broader,
or otherwise different roots before deriving production changes.

Invoke it from the project root, using the current attempt's route request:

```sh
python3 "${CLAUDE_SKILL_DIR}/scripts/press.pyz" press-route \
  .cheese/press/outer-tdd-gates.attempt-1.route.json
```

The boundary replays the current receipt, resolves every transitive
`guard_receipt_refs`, requires canonical encoding for the current phase token,
requires its `production_paths` to equal those bound by the current receipt,
and reconciles the authoritative journal with all immutable matching Press
receipts. It rejects missing, malformed, cyclic, symlinked, escaping, stale,
reused, journal-divergent, cross-work/spec/project, or production-mutating
evidence.
The current Press RED is the observation being routed, so it is excluded from
`completed_cycles`; the original Cut receipt yields `completed_cycles=0` for
P1, and the first and second earlier Press receipts yield
`completed_cycles=1` and `2` for P2 and P3.

The packaged boundary then applies that derived count:

- GREEN returns `Dispatch("/age")`.
- An in-contract RED at `completed_cycles=0` or `1` returns
  `Continue("press-corrective-cook")`.
- The third RED at `completed_cycles=2` returns
  `Stop("third-red", gated_evidence=True)` before issuing another receipt.
- Invalid evidence and production changes stop with `gated_evidence=False`.

Only a valid GREEN result or a complete gated third-RED evidence chain is
review-ready. Invalid evidence or a production mutation is blocked. Existing
baseline-aware project-gate behavior remains compatible: failures identical to
the Cook handoff's recorded baseline do not become new Press findings, while
new or changed failures remain blocking.

## When to fix vs follow up

| Situation | Action |
| --- | --- |
| Approved adversarial test exposes a defect in cooked behavior | Preserve the RED receipt and request the fresh bounded corrective Cook |
| Evidence chain, digest, or production snapshot is invalid | Stop and report the exact integrity failure |
| Attack targets behavior outside approved contracts | Document it for `/age`; do not edit production or continue |

## Hard rule — preserve evidence

Never weaken the attack to obtain GREEN. Never hand-write a receipt, bypass
`red-gate issue`, drop a guard, reset a digest, change the attack between
replays, or turn a Press-owned continuation into a global Cook dispatch.
