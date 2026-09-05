# Quality gates — baseline-aware three-way policy

This document defines how `/cook`, `/press`, and `/cure` handle quality-gate failures against a baseline.
Every downstream skill links here instead of repeating these rules.

## Baseline capture ownership

The quality-debt snapshot supplies data to the bundled `baseline` classifier.
Fan mode records this snapshot once before any curd cooks.
Fan mode records it in the baseline artifact that `.cheese/cook/<slug>.md` names on its `baseline:` line.
The typed Cook handoff is the only live recovery record.
The retired `.cheese/ultracook/<slug>/manifest.yaml` is a lossless projection.
Never read that manifest to select the phase to execute.

If no baseline exists, bare Cook (no frame) lazily captures the same failure records from the pre-change tree.
The baseline capture and each current-gate run use the same worktree and toolchain.

Run the tested classifier through `python3 skills/cook/scripts/cook.pyz baseline`.
Do not classify failures by eye.

## Classification taxonomy

The tested bundled helper calculates each classification deterministically.
An agent does not classify failures by eye.

`FailureRecord = {suite, test_id, signature}`, where `signature` is the whitespace-normalized first line of the failure message.

- **identical** — The test and signature are the same as the baseline.
- **new** — The failure is not in the baseline.
- **changed** — The test is the same, but the signature is different. Treat this failure as `new`.
- **resolved** — The failure is in the baseline, but the test is now green. Record it for the summary. It is not a failure.

## Three-way gate policy

The handoff `baseline:` line points at the Cook comparison summary.
That summary holds the identical, new, changed, and resolved records.
It also holds every repair dispatch.

- **Identical, outside the cooked contract** — Record the failure in the baseline artifact. Continue under policy `never halt, never fix silently`.
- **New or changed** — The cook fixes the failure. Use no more than **2 fix rounds per gate**. Do a no-progress check after each round. The cook must halt when the same failure signature appears twice in sequence. Repair collateral damage outside the cooked contract when it blocks the gate. Record each repair in the report's Files-changed section. Use reason `collateral repair: <one line>`.
- **Halt** only when rounds exhaust, the no-progress check trips, or the fix is design-shaped. A design-shaped fix requires a decision outside the spec. Put the classification in the halt handoff. This ensures resume never re-asks.

## Baseline block shape

The baseline is optional and additive.
Statuses stay `ok` or `halt`.
The baseline introduces no new status value.

The handoff preamble accepts one physical line for each key.
Therefore `baseline:` holds one artifact reference, not a nested mapping.
Write `baseline: none` when Cook records no comparison.
Otherwise write one path, as this example shows:

```markdown
baseline: .cheese/cook/<slug>-baseline.yaml
```

Store the record itself in that artifact:

```yaml
captured_at: <UTC ISO-8601>
gates:
  - cmd: <gate command>
    failures: [{suite, test_id, signature}]
repair_dispatch:            # optional — present once a repair is dispatched
  slug: <pasteurize slug>
  branch: <repair worktree branch>
  run_branch: <originating run branch>
  pr: <PR number or URL>     # optional — present once plated
```

`run_branch` names the branch that recorded the debt.
`/plate` requires this field for its merge-time topology check.
Every consumer reads the artifact through the `baseline:` path.

## Loud, never hidden

Record identical-to-baseline failures visibly.
List them in the final summary.
State that the full suite is not green.
A concurrent repair can already be in progress.
See § Repair pathway.

## Repair pathway

Recording a debt does not fix it. This pathway applies when baseline capture records ≥1 identical-to-baseline failure. Both frames use the same repair pathway.

`cook/SKILL.md` links to this pathway instead of repeating it.

Use the frame's existing record point:

- fan mode: the pre-Seed write of the typed Cook handoff
- bare cook: the post-classify write of the typed Cook handoff

1. **Dedupe** — You must dedupe against a live `repair_dispatch`. A live `repair_dispatch` has an existing branch. Its handoff chain has not reached terminal `status: ok` or `status: halt`. Skip this dispatch when the baseline artifact already holds a live dispatch. Never dispatch a second repair for the same debt.
2. **Consent** — Set consent automatically under `--auto`. Otherwise, prompt once at record time with the failure count. Use [`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md). If the user declines, skip the repair. The debt stays recorded in both cases.
3. **Worktree** — Create a repair worktree with the shared primitive: `<skill>.pyz worktree create --slug repair-<run-slug> --base origin/main`. Do not use the cook's own tree. The repair worktree has an independent lifecycle. Exclude it from the run's worktree teardown. Bare `/cook` example: `python3 skills/cook/scripts/cook.pyz worktree create --slug repair-<slug> --base origin/main`.
4. **Dispatch** — Use the repair worktree to dispatch a concurrent `/pasteurize` in an isolated worktree. In the brief, identify the recorded failures as the symptom. Include `suite`, `test_id`, and `signature` for each entry. Add one explicit per-dispatch override to the brief. At Phase 6, chain forward with `/cook <repair-handoff-path> --auto --open-pr`.
Pass the canonical Pasteurize handoff path, not a bare slug.
Cook resolves a bare slug as a specification, so a bare slug breaks the repair chain. Do not use pasteurize's documented `/cook <repair-slug> --auto` for this dispatch. This instruction applies only to this dispatch brief. It does not change pasteurize's SKILL.md. It is more specific than the skill's generic default and governs this invocation. Therefore, the repair publishes its own PR by default. This instruction does not change `/pasteurize`'s own contract.
5. **Record** — Write `repair_dispatch: {slug, branch, run_branch}` into the baseline artifact. Use the typed Cook handoff in both frames. Add `pr` after `/plate` publishes one.

The run never waits for the repair. A failed, halted, or still-in-flight repair leaves the recorded debt unchanged. The repair never blocks the run's completion or publication.

Report the repair status in the final summary when known. Otherwise, use the `repair_dispatch` link and the pasteurize slug as the resume path.

### Merge-time topology

The repair worktree's own `/plate` step performs a mechanical file-overlap check at publication time. This check occurs before the ordinary New-PR topology policy.

Read `run_branch` from the baseline artifact.
Halt when that field is absent.
Verify that the branch still exists before you compare.
Compare the repair's changed files against that branch.

Count the changed lines from `git diff --numstat <merge-base>..<repair-branch>`.
Use the merge base of the repair branch and the run branch.
Count a rename as one changed file and count its changed lines.
Count a binary file as one changed file and 50 changed lines.

- **No shared files** (or the run branch is already gone).
  Plate the repair as an ordinary independent PR against `main`. This uses `/plate`'s existing New-PR flow. No run-diff comparison is necessary.
- **Shared files, repair ≤2 files and ≤50 changed lines** — Skip publication. Harvest the repair's commits onto the run branch with the bundled command:

  ```text
  python3 skills/cook/scripts/cook.pyz worktree harvest \
    --branch <repair-branch> --onto <run-branch> --repo <run-worktree>
  ```

  Resolve `<run-worktree>` from verified Git worktree state.
  Halt at topology when the command fails.
- **Shared files, repair over that threshold** — Restack the branches. The repair becomes the base PR. The run's PR(s) rebase on top through `/plate`'s existing stack machinery.

## Consumers

- `/cook` writes the `baseline:` block.
- `/press`, `/age`, and `/cure` honor the block. Apply `no re-halt, no re-flag of identical entries`.
- `/cheese --continue` treats the block as settled state, not an open question.
- `/cook`'s fan pathway validates the baseline artifact that the typed handoff names.
- `/plate` applies the repair pathway's merge-time topology check when it publishes a repair-worktree branch. See § Repair pathway, Merge-time topology.
