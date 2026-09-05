# /cook — Auto mode chain mechanics

This file defines the full mechanics for `--auto`, the autonomous pipeline switch.

It defines the per-step chain, two-cure-pass cap enforcement, early-stop conditions, no-chain isolation for the fan pathway, and the final-report template.

`SKILL.md`'s `## Auto mode` contains the one-paragraph summary and the publishable-gate rule. This file defines all behavior after that summary.

## Cook entry preflight

`--auto` uses the same `cook(spec_ref, correction = false)` contract as manual Cook.

For behavior work, Cook runs the inner RED → GREEN loop against the spec's test contracts.

A closed `not-applicable` disposition routes the requested non-behavior change through its own verification path.

After inner TDD completes, Cook requires all inner tests and relevant gates to be GREEN before it invokes `/press`.

When `correction = true`, Cook limits the scope to the active Press corrective loop.

Cook cannot weaken or bypass existing tests.

## What auto mode does

1. After Cook completes the inner implementation and green gates, Cook writes the package-ready report.
   Cook then invokes `/press <slug> --auto`.
   Cook appends `--open-pr` only when the user supplied that flag.
   `--open-pr` is publication permission, and auto mode never creates it.
   Without that flag, the chain stays commit-only.
   Cook also forwards `--hard` when the user supplied it.

2. `/press --auto` runs its hardening pass.
   It invokes `/age <slug> --auto` when readiness is `ready for /age` or `follow-up recommended`.
   Both states mean that the cooked contract is sound.
   Both states also mean that every changed behavior has a hardening test.
   Documented follow-ups are review-safe.
   Only `blocked` stops auto.
   [`../../press/references/gap-analysis.md`](../../press/references/gap-analysis.md) defines the blocked criteria once.

3. `/age <slug> --auto` writes the report.
   It then invokes `/cure <slug> --auto --stake medium+`.
   Every Age dispatch carries the pipeline slug, `--auto`, and any user-supplied `--hard`.

4. `/cure --auto --stake medium+` bypasses the selection gate.
   It applies every finding with `blocker`, `high`, or `medium` severity.
   It also applies every cheap `Low` finding that has a contained fix.
   It then invokes `/age <slug> --scope <touched-paths> --auto` for verification.
   The scoped call keeps the pipeline slug, because Age needs it for its lock and its report path.
   Never dispatch `/age --scope <touched-paths> --auto` without the slug.
   The call also forwards `--hard` when the user supplied it.

5. The age → cure cycle has a maximum of **two cure passes total**.
   Pass 1 fixes the initial findings.
   Pass 2 fixes all findings that the second age pass identifies.
   After pass 2, the chain stops and writes a final summary.
   The chain stops even if new findings remain.

6. In the linear chain, `/cook` never invokes `/plate`.
   At the chain terminal, `/cure` dispatches `/plate` for an existing pull request.
   For a new pull request, `/cure` dispatches `/plate` only when the user supplied `--open-pr`.
   In the fan pathway, the Cook orchestrator owns its own terminal `/plate` dispatch.
   `/plate` honors explicit topology.
   It selects an obviously cohesive single without asking.
   It asks before mutation when it recommends stacked or when the shape is ambiguous.
   This requirement also applies under auto.

## Cap enforcement

The chain length enforces the two-cure-pass cap. Age does not enforce the cap.

Age starts in a fresh context for each pass. Therefore, age cannot count prior passes.

Each age pass writes `next:` from the conditions that it observes during that run.

Age writes `next: cure` when a medium+ finding remains.

Age writes `next: done` when no medium+ finding remains.

Before the terminal position, `next: done` causes an early stop.

For cap enforcement, the `next:` value is informational.

The fixed two-pass loop structure terminates the chain. Age's own `next:` value does not enforce the cap.

`/cook` does not pass a pass-ordinal hint to age.

Age does not need to know whether it performs the first or second post-cure check.

The orchestrator owns the pass position.

## When auto mode stops early

- A quality gate fails **new** or **changed** against baseline, as defined in [`quality-gates.md`](quality-gates.md).
  Auto mode stops when the two fix rounds end.
  Auto mode also stops when the no-progress check trips.
  Auto mode also stops when the fix requires a design decision.
  Record Identical-to-baseline failures outside the cooked contract.
  These failures never stop auto mode.

- `/press` returns `blocked`.
  See the blocked criteria in [`../../press/references/gap-analysis.md`](../../press/references/gap-analysis.md).

- A cure pass cannot apply any finding.
  This condition occurs when every selected fix breaks tests during revert-or-keep evaluation.

- Two cure passes complete.
  This condition is the success path.

For every early stop, show the report from the skill that failed.

Tell the user whether the chain reached the cap or encountered a blocker.

Do not silently downgrade.

## No-chain isolation directive

By default, each phase's existing `--auto` contract chains forward in the same session.

`/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, and so on.

When `/cook` runs as its fan-pathway orchestrator, `fan-pathway.md` overrides this default.

The override applies to every per-curd or post-merge dispatch.

Each phase sub-agent runs only its own phase.

Each phase sub-agent writes its handoff slug and stops.

It never chains forward to the next phase, although its own `--auto` contract documents that behavior.

The fan-pathway orchestrator loop decides and dispatches the next phase.

`fan-pathway.md`'s `## Deterministic phase loop` defines this loop.

The retired `/ultracook` orchestrator previously owned the same responsibility.

The spawn prompt carries the override as an explicit no-chain directive.

The directive uses `/ultracook`'s original wording verbatim:

"Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. `/cook`'s fan pathway is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with `status: halt: <reason>` and stop; do not silently timeout."

Each phase applies the directive from its own `## Auto mode` section.

See [`../../press/SKILL.md`](../../press/SKILL.md), [`../../age/SKILL.md`](../../age/SKILL.md), and [`../../cure/references/auto-mode.md`](../../cure/references/auto-mode.md).

## Failure handling inside cure

See `skills/cure/SKILL.md` `## Auto mode` for cure's revert-or-defer behavior for each finding.

Cook does not duplicate this contract.

Cure owns the contract.

## Final report

The skill that ends the chain prints the following summary.

On the success path, the final `/age --auto` prints it after the chain reaches the two-cure-pass cap.

On an early stop, the skill that identifies the blocker prints it.

```
Auto-mode summary
Passes:        <1|2>
Findings fixed: <count by severity>
Deferred:       <count, with cure-report path>
Final age:      <path>
Next step:      review the diff, then /plate when ready
```
