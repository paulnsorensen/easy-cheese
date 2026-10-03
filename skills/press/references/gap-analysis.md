# Press adversarial gap analysis

## Ownership boundary

Press is not a second first-coverage phase. Cook owns the implementation and its tests.

Press attacks the approved contract after Cook. Press writes only tests, fixtures, or test-only harness support.

Report a missing production implementation as a finding. Hand it to Cook as a correction.

## What Press may expose

| Gap type | Evidence | Action |
| --- | --- | --- |
| Defect | The approved seam fails on an adversarial input or transition | Report it as a finding with the failing test. Hand off to Cook as a correction. |
| Invalid evidence | The recorded run does not verify the attack outcome | Stop. |
| Production mutation | A production path changes during a Press interval | Stop. |
| Out-of-contract behavior | The approved spec omits a desired behavior | Record it under `## Review follow-ups`. Report `ok-with-concerns` on a GREEN pass. Do not implement it. |

## Evidence sequence

Complete these steps at each Press entry and after each Cook correction:

1. Run the same adversarial attack. Do not change its test or fixture digest.
2. Select `green`, `finding`, `invalid_evidence`, or `production_changed`.
3. For a finding, record the failing test and its digest.

A Cook correction can change production code to make the attack GREEN.

Do not rewrite or weaken the attack. Do not change its expected witness or the tests that it uses.

## Priority order

Press closes only adversarial gaps in the approved Cook contract:

1. Keep the production tree unchanged during the Press interval.
2. Attack approved boundaries, invalid inputs, state transitions, integrations, and error paths.
3. Verify assertion sensitivity. The attack must fail for an incorrect value, state, or error.

Cook owns first coverage. Do not create one hardening test for each changed behavior.

Do not add tests for unchanged or out-of-contract code.

## Routing

- GREEN hands off to `/age`.
- A finding hands off to Cook as a correction (`next: cook`).
- Invalid evidence and production changes stop.

Baseline failures do not become new Press findings when their tests and signatures match the Cook handoff.

New or changed failures block the route.

## When to fix or follow up

| Situation | Action |
| --- | --- |
| An adversarial test exposes a defect in Cook behavior | Report the finding with its failing test. Hand off to Cook as a correction. |
| The digest or production snapshot is invalid | Stop. Report the exact integrity failure. |
| The attack targets behavior outside the approved spec | Record it under `## Review follow-ups` for `/age`. Do not edit production code. |

## Hard rule — preserve the attack

Never weaken the attack to obtain GREEN. Never change the attack between replays.
