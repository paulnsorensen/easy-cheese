# Press adversarial gap analysis

## Ownership boundary

Press is not a second first-coverage phase. Cook owns the implementation and the inner RED→GREEN loop.

Press attacks the approved contract after Cook. Press writes only tests, fixtures, or test-only harness support.

Treat a missing production implementation as an in-contract RED. Request a bounded corrective Cook continuation.

## What Press may expose

| Gap type | Evidence | Action |
| --- | --- | --- |
| In-contract defect | The approved seam fails on an adversarial input or transition | Preserve the same failing test and digest. Route as `in_contract_red`. |
| Invalid evidence | The recorded run does not verify the attack outcome | Stop without a repair action. |
| Production mutation | A production path changes during a Press interval | Stop. |
| Out-of-contract behavior | The approved Test Contracts omit a desired behavior | Record it under `## Review follow-ups`. Report `ok-with-concerns` on a GREEN pass. Do not implement it. |

## Evidence sequence

Complete these steps at each Press entry and after each Cook continuation:

1. Run the same adversarial attack. Do not change its test or fixture digest.
2. Select `green`, `in_contract_red`, `invalid_evidence`, or `production_changed`.
3. For an in-contract RED, record the failed test and its digest before you select a route.

The failed-test digest is part of the evidence chain. A corrective Cook continuation can change production code to make the attack GREEN.

Do not rewrite or weaken the attack. Do not change its expected witness or the tests that it uses.

## Priority order

Press closes only adversarial gaps in the approved Cook contract:

1. Keep the production tree unchanged during the Press interval.
2. Attack approved boundaries, invalid inputs, state transitions, integrations, and error paths.
3. Verify assertion sensitivity. The attack must fail for an incorrect value, state, or error.

Cook owns first coverage. Do not create one hardening test for each changed behavior.

Do not add tests for unchanged or out-of-contract code.

## Repair bound and readiness

The packaged boundary uses the classified outcome and completed corrective count. The request contains only these fields:

```json
{
  "outcome": "in_contract_red",
  "repair_cycles": 0
}
```

`repair_cycles` counts completed corrective Cook continuations for this slug. Use 0 for attempt 1, 1 for attempt 2, and 2 for attempt 3.

Each attempt uses separate candidate and route paths. Never reuse or overwrite an earlier attempt artifact.

Run this command from the project root. Use the route request for the current attempt:

```sh
python3 "skills/press/scripts/press.pyz" press-route \
  .cheese/press/outer-tdd-gates.attempt-1.route.json
```

The packaged boundary applies these rules:

- GREEN returns `Dispatch("/age")`.
- An in-contract RED at `repair_cycles` 0 or 1 returns `Continue("press-corrective-cook")`.
- The third RED at `repair_cycles` 2 returns `Stop("third-red")`.
- Invalid evidence and production changes stop.

A valid GREEN result is ready for review. Press dispatches Age after that result.

A complete third-RED evidence chain is ready for terminal reporting. Press does not dispatch Age after that result.

Invalid evidence blocks the route. A production mutation also blocks the route.

Baseline failures do not become new Press findings when their tests and signatures match the Cook handoff.

New or changed failures block the route.

## When to fix or follow up

| Situation | Action |
| --- | --- |
| An approved adversarial test exposes a defect in Cook behavior | Preserve the RED evidence. Request a bounded corrective Cook continuation. |
| The evidence chain, digest, or production snapshot is invalid | Stop. Report the exact integrity failure. |
| The attack targets behavior outside approved contracts | Record it under `## Review follow-ups` for `/age`. Do not edit production code. Do not continue. |

## Hard rule — preserve evidence

Never weaken the attack to obtain GREEN. Never reset a digest or change the attack between replays.

Never turn a Press continuation into a global Cook dispatch.
