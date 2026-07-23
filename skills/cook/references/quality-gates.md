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
  repair_dispatch:            # optional — present once a repair is dispatched
    slug: <pasteurize slug>
    branch: <repair worktree branch>
    pr: <PR number or URL>     # optional — present once plated
```

## Loud, never hidden

Identical-to-baseline failures are recorded loud: the final summary lists them and states the full suite is not green. A concurrent repair may already be in flight — see § Repair pathway.

## Repair pathway

Recording a debt is not fixing it. When a run's baseline capture records ≥1 identical-to-baseline failure, both frames follow the same repair pathway — expressed once here, linked from `cook/SKILL.md` and `ultracook/SKILL.md` rather than restated.

At the frame's existing record point (ultracook: pre-Seed manifest write; bare cook: post-classify handoff-slug write):

1. **Dedupe** — dedupe against a live `repair_dispatch`: if the `baseline:` block already carries one (its branch still exists and its handoff chain has not reached a terminal `status: ok` or `status: halt`), skip. Never dispatch a second repair for the same debt.
2. **Consent** — automatic under `--auto`; otherwise prompt once at record time ([`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md)) with the failure count. Decline skips the repair; the debt stays recorded either way.
3. **Worktree** — create a repair worktree via the shared primitive: `<skill>.pyz worktree create --slug repair-<run-slug> --base origin/main`. Never the cook's own tree — an independent lifecycle, excluded from the run's worktree teardown.
4. **Dispatch** — to dispatch a concurrent `/pasteurize` in an isolated worktree, brief it with the recorded failures (suite, test_id, signature per entry) as the symptom, plus one explicit per-dispatch override: chain forward at Phase 6 with `/cook <repair-slug> --auto --open-pr`, not pasteurize's own documented `/cook <repair-slug> --auto`. This is a dispatch-time instruction in the brief, not a change to pasteurize's SKILL.md — it is more specific than the skill's generic default and governs for this one invocation, so the repair publishes its own PR by default. `/pasteurize`'s own contract is unchanged.
5. **Record** — write `repair_dispatch: {slug, branch}` into the `baseline:` block (manifest for ultracook, handoff slug for bare cook); add `pr` once one is plated.

The run never waits on the repair: a failed, halted, or still-in-flight repair leaves the recorded debt untouched and never blocks the run's completion or publication. The final summary reports repair status when known; the `repair_dispatch` link and the pasteurize slug are the resume path otherwise.

### Merge-time topology

The repair worktree's own `/plate` step, at publication time, applies a mechanical file-overlap check before its ordinary New-PR topology policy: compare the repair's changed files against the originating run's branch, if that branch still exists.

- **No shared files** (or the run branch is already gone — merged or deleted) — plate the repair as an ordinary independent PR against `main`. This is `/plate`'s existing New-PR flow; no run-diff comparison needed.
- **Shared files, repair ≤2 files and ≤50 changed lines** — skip publication; harvest the repair's commits onto the run branch with the shared `worktree_harvest(branch, onto=run_branch)` primitive instead.
- **Shared files, repair over that threshold** — restack: the repair becomes the base PR, the run's PR(s) rebase on top, via `/plate`'s existing stack machinery.

## Consumers

- `/cook` writes the `baseline:` block.
- `/press`, `/age`, `/cure` honor it: no re-halt, no re-flag of identical entries.
- `/cheese --continue` treats it as settled state, not an open question.
- `/ultracook` validates it in the run manifest.
- `/plate` applies the repair pathway's merge-time topology check when publishing a repair-worktree branch (§ Repair pathway, Merge-time topology).
