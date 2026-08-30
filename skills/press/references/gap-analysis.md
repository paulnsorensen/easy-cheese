# Press adversarial gap analysis

## Ownership boundary

Press is not a second first-coverage phase. Cook owns the implementation and
the inner RED→GREEN loop. Press attacks the approved contract after Cook and
writes only tests, fixtures, or test-only harness support. A gap that needs
production implementation becomes an in-contract RED observation and a bounded
corrective Cook request.

## What Press may expose

| Gap type | Evidence | Action |
| --- | --- | --- |
| In-contract defect | The approved seam fails on an adversarial input or transition | Preserve the identical failing test and digest; route as `in_contract_red` |
| Invalid evidence | The attack's outcome cannot be verified from the recorded run | Stop without a repair action |
| Production mutation | Any production path changes during a Press-owned interval | Stop |
| Out-of-contract behavior | A desired behavior is not in the approved Test Contracts | Record a review follow-up; do not implement it |

## Evidence sequence

At every Press entry and post-Cook resume:

1. Run the same adversarial attack without changing its test or fixture digest.
2. Classify the outcome: `green`, `in_contract_red`, `invalid_evidence`, or
   `production_changed`.
3. For an in-contract RED, record the failing test and its digest in the
   attempt's candidate artifact before routing.

The failing-test digest is part of the evidence chain. A corrective Cook may
change production to make the attack GREEN, but it may not rewrite or weaken
the attack, its expected witness, or the tests it exercises.

## Priority order

Press closes only adversarial gaps in the approved Cook contract:

1. Production-tree immutability during the Press-owned interval.
2. Boundary, invalid-input, state-transition, integration, and error-path
   attacks that belong to the approved seam.
3. Assertion sensitivity: the attack must fail for the wrong value, state, or
   error, not merely because a command exited.

Cook owns first coverage. Do not manufacture one hardening test per changed
behavior, and do not add tests for untouched or out-of-contract code.

## Repair bound and readiness

The packaged boundary routes from the classified outcome and the completed
corrective count; the request has exactly these two fields:

```json
{
  "outcome": "in_contract_red",
  "repair_cycles": 0
}
```

`repair_cycles` counts the corrective Cook continuations already completed for
this slug: 0 for P1, 1 for P2, and 2 for P3. Each attempt has its own
`candidates/<slug>.attempt-N.json` and `.route.json` paths; never reuse or
overwrite an earlier attempt's artifact.

Invoke it from the project root, using the current attempt's route request:

```sh
python3 "skills/press/scripts/press.pyz" press-route \
  .cheese/press/outer-tdd-gates.attempt-1.route.json
```

The packaged boundary applies the count:

- GREEN returns `Dispatch("/age")`.
- An in-contract RED at `repair_cycles` 0 or 1 returns
  `Continue("press-corrective-cook")`.
- The third RED at `repair_cycles` 2 returns `Stop("third-red")`.
- Invalid evidence and production changes stop.

Only a valid GREEN result or a complete third-RED evidence chain is
review-ready. Invalid evidence or a production mutation is blocked. Existing
baseline-aware project-gate behavior remains compatible: failures identical to
the Cook handoff's recorded baseline do not become new Press findings, while
new or changed failures remain blocking.

## When to fix vs follow up

| Situation | Action |
| --- | --- |
| Approved adversarial test exposes a defect in cooked behavior | Preserve the RED evidence and request the fresh bounded corrective Cook |
| Evidence chain, digest, or production snapshot is invalid | Stop and report the exact integrity failure |
| Attack targets behavior outside approved contracts | Document it for `/age`; do not edit production or continue |

## Hard rule — preserve evidence

Never weaken the attack to obtain GREEN. Never reset a digest, change the
attack between replays, or turn a Press-owned continuation into a global Cook
dispatch.
