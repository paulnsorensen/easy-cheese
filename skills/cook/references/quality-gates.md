# Quality gates — baseline-aware three-way policy

This document defines how `/cook`, `/press`, `/cure`, and `/ultracook` handle quality-gate failures against a baseline. Every downstream skill links here instead of repeating these rules.

## Baseline capture ownership

The quality-debt snapshot supplies data to the bundled `baseline` classifier. Fan mode records this snapshot once in the `baseline:` block of `.cheese/ultracook/<slug>/manifest.yaml` before any curd cooks.

If no baseline exists, bare Cook (no frame) lazily captures the same failure records from the pre-change tree. The baseline capture and each current-gate run use the same worktree and toolchain.

Run the tested classifier through `python3 skills/cook/scripts/cook.pyz baseline`. Do not classify failures by eye.

## Classification taxonomy

The tested bundled helper calculates each classification deterministically. An agent must not classify failures by eye.

`FailureRecord = {suite, test_id, signature}`, where `signature` is the whitespace-normalized first line of the failure message.

- **identical** — The test and signature are the same as the baseline.
- **new** — The failure is not in the baseline.
- **changed** — The test is the same, but the signature is different. Treat this failure as `new`.
- **resolved** — The failure is in the baseline, but the test is now green. Record it for the summary. It is not a failure.

## Three-way gate policy

The handoff `baseline:` block contains the Cook comparison summary. This summary includes identical, new, changed, and resolved records and all repair dispatches.

- **Identical, outside the cooked contract** — Record the failure in the handoff's `baseline:` block. Continue under policy `never halt, never fix silently`.
- **New or changed** — The cook fixes the failure. Use no more than **2 fix rounds per gate**. Do a no-progress check after each round. The cook must halt if the same failure signature appears twice consecutively. Collateral repairs outside the cooked contract are permitted. Record each repair in the report's Files-changed section. Use reason `collateral repair: <one line>`.
- **Halt** only if rounds exhaust, the no-progress check trips, or the fix is design-shaped. A design-shaped fix requires a decision outside the spec. Put the classification in the halt handoff. This ensures resume never re-asks.

## Baseline block shape

The block is optional and additive. Statuses stay `ok`/`halt`. This block introduces no new status enum.

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

Record identical-to-baseline failures visibly. List them in the final summary. State that the full suite is not green. A concurrent repair can already be in progress. See § Repair pathway.

## Repair pathway

Recording a debt does not fix it. This pathway applies when baseline capture records ≥1 identical-to-baseline failure. Both frames use the same repair pathway.

`cook/SKILL.md` and `ultracook/SKILL.md` link to this pathway instead of repeating it.

Use the frame's existing record point:

- ultracook: pre-Seed manifest write
- bare cook: post-classify handoff-slug write

1. **Dedupe** — You must dedupe against a live `repair_dispatch`. A live `repair_dispatch` has an existing branch. Its handoff chain has not reached terminal `status: ok` or `status: halt`. If the `baseline:` block already contains a live dispatch, skip this dispatch. Never dispatch a second repair for the same debt.
2. **Consent** — Set consent automatically under `--auto`. Otherwise, prompt once at record time with the failure count. Use [`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md). If the user declines, skip the repair. The debt stays recorded in both cases.
3. **Worktree** — Create a repair worktree with the shared primitive: `<skill>.pyz worktree create --slug repair-<run-slug> --base origin/main`. Do not use the cook's own tree. The repair worktree has an independent lifecycle. Exclude it from the run's worktree teardown. Bare `/cook` example: `python3 skills/cook/scripts/cook.pyz worktree create --slug repair-<slug> --base origin/main`.
4. **Dispatch** — Use the repair worktree to dispatch a concurrent `/pasteurize` in an isolated worktree. In the brief, identify the recorded failures as the symptom. Include `suite`, `test_id`, and `signature` for each entry. Add one explicit per-dispatch override to the brief. At Phase 6, chain forward with `/cook <repair-slug> --auto --open-pr`. Do not use pasteurize's documented `/cook <repair-slug> --auto` for this dispatch. This instruction applies only to this dispatch brief. It does not change pasteurize's SKILL.md. It is more specific than the skill's generic default and governs this invocation. Therefore, the repair publishes its own PR by default. `/pasteurize`'s own contract is unchanged.
5. **Record** — Write `repair_dispatch: {slug, branch}` into the `baseline:` block. Use the manifest for ultracook. Use the handoff slug for bare cook. Add `pr` once one is plated.

The run never waits for the repair. A failed, halted, or still-in-flight repair leaves the recorded debt unchanged. The repair never blocks the run's completion or publication.

Report the repair status in the final summary when known. Otherwise, use the `repair_dispatch` link and the pasteurize slug as the resume path.

### Merge-time topology

The repair worktree's own `/plate` step performs a mechanical file-overlap check at publication time. This check occurs before the ordinary New-PR topology policy.

If the originating run branch still exists, compare the repair's changed files against that branch.

- **No shared files** (or the run branch is already gone).
  Plate the repair as an ordinary independent PR against `main`. This uses `/plate`'s existing New-PR flow. No run-diff comparison is necessary.
- **Shared files, repair ≤2 files and ≤50 changed lines** — Skip publication. Harvest the repair's commits onto the run branch with the shared `worktree_harvest(branch, onto=run_branch)` primitive.
- **Shared files, repair over that threshold** — Restack the branches. The repair becomes the base PR. The run's PR(s) rebase on top through `/plate`'s existing stack machinery.

## Consumers

- `/cook` writes the `baseline:` block.
- `/press`, `/age`, and `/cure` honor the block. Apply `no re-halt, no re-flag of identical entries`.
- `/cheese --continue` treats the block as settled state, not an open question.
- `/cook`'s fan pathway validates the block in the run manifest.
- `/plate` applies the repair pathway's merge-time topology check when it publishes a repair-worktree branch. See § Repair pathway, Merge-time topology.
