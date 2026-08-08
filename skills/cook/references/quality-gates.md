# Quality gates — baseline-aware three-way policy

Single source of truth for how `/cook`, `/press`, `/cure`, and `/ultracook` treat quality-gate failures against a baseline. Every downstream skill links here instead of restating the rules.

## Baseline capture ownership

The protected outer RED has one pre-oracle baseline owner: `/cut`.

- **`/cut`** runs the broad project quality-gate commands on the exact tree
  before writing any protected RED oracle. It freezes each command's `id`,
  argv, project-relative cwd, and observed exit in the candidate's canonical
  `baseline_checks`; `red-gate issue` carries those entries into the
  `GateReceipt` and the Cut→Cook handoff.
- **`/cook`** never captures its own outer RED baseline, replaces it, or
  lazily recaptures it. GateReceipt preflight consumes Cut's frozen
  `baseline_checks` exactly; a current-gate run compares against that evidence.
- Receipt validation may replay baseline argv after the oracle exists. Cut
  therefore selects baseline argv that exclude protected RED-oracle paths or
  remain green when those paths are present; replay must not turn the
  intentional RED into a baseline failure.

The frozen baseline and every current-gate run use the same worktree and
toolchain. If the baseline cannot be captured before the oracle, Cut halts (or
must run the same commands against an exact frozen pre-oracle tree); it never
substitutes an empty baseline.

### Quality-debt comparison snapshot

This separate snapshot feeds `src/fanout/baseline.py::classify()`; it never
replaces the outer receipt. Fan mode records it once in
`.cheese/ultracook/<slug>/manifest.yaml`'s `baseline:` block before any curd
cooks. Bare Cook (no frame) with no baseline yet lazily captures the same
failure records from the pre-change tree. Run the tested classifier through
`python3 skills/ultracook/scripts/ultracook.pyz baseline`; do not classify by
eye.

## Classification taxonomy

Classification is deterministic and computed by the tested helper `src/fanout/baseline.py::classify()` — never agent-eyeballed.

`FailureRecord = {suite, test_id, signature}`, where `signature` is the first line of the failure message, whitespace-normalized.

### Intentional outer RED exclusion

Before classification, remove only the current failure record(s) that match a
receipt `RedCase`'s declared seam/case and expected witness. This narrow
exclusion is required because the protected oracle is intentionally failing
after the frozen baseline was captured; it is not inherited debt and must not
be dispatched to Pasteurize. Do not remove any other current failure, and do
not add the excluded case to the frozen baseline.

- **identical** — same test, same signature as baseline.
- **new** — not in baseline.
- **changed** — same test, different signature. Treated as `new`.
- **resolved** — in baseline, now green. Recorded for the summary; not a failure.

## Three-way gate policy

The canonical pre-Cut evidence lives in `GateReceipt.baseline_checks` and is
immutable. The handoff `baseline:` block is only the Cook comparison summary
(including identical/new/changed/resolved records and any repair dispatch);
it never replaces or truncates the receipt evidence.

- **Identical, outside the cooked contract** — record in the handoff's `baseline:` block, continue; never halt, never fix silently.
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
3. **Worktree** — create a repair worktree via the shared primitive: `<skill>.pyz worktree create --slug repair-<run-slug> --base origin/main`. Never the cook's own tree — an independent lifecycle, excluded from the run's worktree teardown. Bare `/cook` example: `python3 skills/cook/scripts/cook.pyz worktree create --slug repair-<slug> --base origin/main`.
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
- `/cook`'s fan pathway validates it in the run manifest.
- `/plate` applies the repair pathway's merge-time topology check when publishing a repair-worktree branch (§ Repair pathway, Merge-time topology).
