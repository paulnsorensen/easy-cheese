# Quality gates — baseline-aware three-way policy

Single source of truth for how `/cook`, `/press`, `/cure`, and `/ultracook` treat quality-gate failures against a baseline. Every downstream skill links here instead of restating the rules.

## Baseline capture ownership

Baseline capture is frame-owned, not per-cook:

- **`/ultracook` run** — captures the broad-gate baseline once per run, before any curd cooks, and hands it down to curd cooks via dispatch. A curd never captures its own baseline.
- **Bare `/cook` (no frame)** — captures lazily, on the first red broad gate, from the pre-change tree (`git stash` or a clean worktree checkout), classifies the failures, then proceeds with the classified result.

Frame capture and the gate re-run happen in the same environment (same worktree, same toolchain) to minimize signature drift from environment-sensitive flakes.

## Classification taxonomy

Classification is deterministic and computed by the tested helper `src/fanout/baseline.py::classify()` — never agent-eyeballed.

`FailureRecord = {suite, test_id, signature}`, where `signature` is the first line of the failure message, whitespace-normalized.

- **identical** — same test, same signature as baseline.
- **new** — not in baseline.
- **changed** — same test, different signature. Treated as `new`.
- **resolved** — in baseline, now green. Recorded for the summary; not a failure.

## Three-way gate policy

- **Identical, outside the cooked contract** — record in the handoff's `baseline:` block, continue. Never halt, never fix silently.
- **New or changed** — the cook fixes it: up to **2 fix rounds per gate**, with a no-progress check. The same failure signature appearing twice consecutively halts early. Collateral repairs (files outside the cooked contract) are allowed freely; record each one in the report's Files-changed with reason `collateral repair: <one line>`.
- **Halt** only when: rounds exhaust, the no-progress check trips, or the fix is design-shaped (requires a decision outside the spec). The halt handoff carries the classification so resume never re-asks.

## Baseline block shape

Optional, additive. Statuses stay `ok`/`halt`; this introduces no new status enum.

```yaml
baseline:
  captured_at: <UTC ISO-8601>
  gates:
    - cmd: <gate command>
      failures: [{suite, test_id, signature}]
```

## Loud, never hidden

Identical-to-baseline failures are recorded loud: the final summary lists them and states the full suite is not green. Auto-fixing baseline failures is out of scope, deferred to issue #304.

## Consumers

- `/cook` writes the `baseline:` block.
- `/press`, `/age`, `/cure` honor it: no re-halt, no re-flag of identical entries.
- `/cheese --continue` treats it as settled state, not an open question.
- `/ultracook` validates it in the run manifest.
