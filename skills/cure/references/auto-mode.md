# Automatic mode for Cure

Read this file before `/cure --auto --stake <floor>`.
It defines worker exceptions, the puncture clause, and the empty selection case.

## Per-finding flow

- Skip the selection list and the handoff gate.
- Select every finding that meets the severity floor.
  Read `selection.md` § Auto-mode selection for floor definitions.
- Apply one finding at a time.
  Run the narrowest proving test after each fix.
  Revert a fix that breaks a passing test or project gate.
  Put it under `### Deferred` with the test name and failure summary.
  Continue with the remaining findings.
- After all findings, invoke `/age --scope <touched-paths> --auto`.
  Forward `--open-pr` when it is in scope.
  Skip the handoff gate.
- Let `/age --auto` enforce the two-pass cap.
  Cure does not track the pass count.

## Final publication

When Age returns `next: done`, dispatch `/plate` once.
It updates an open PR automatically.
With `--open-pr`, it applies the explicit layout and review rules before a new PR.
After publication, run § Post-PR learning write-back in `post-pr-writeback.md`.

A Cure worker from the Cook fan pathway does not invoke `/plate`.
The orchestrator owns commit and publication.

When `handoff_context.source_skill` is `/affinage`, do not invoke `/plate`.
Affinage posts its GitHub replies and owns final publication.

With `--auto --hard`, dispatch `/plate --hard` when Age returns `next: done`.
Do not invoke `/hard-cheese` directly.
`/plate` gives the completed artifact list to the metacognitive gate.
A failed hard gate stops publication.
In a non-TTY environment, report that `--hard` requires an interactive TTY.

When no finding meets the floor, write an empty Cure report.
Use `### Applied: (none — no findings meet <floor>)`.
Then continue to the automatic handoff.
Report `auto chain clean`.

## Cook fan pathway

Cook can dispatch Cure as a phase-only worker.
`/ultracook` is retired, but its no-chain contract remains in this pathway.
This case includes one curd and a curd in a wave.
Honor the no-chain and no-push override.

For one curd, apply the selected findings and write `.cheese/cure/<slug>.md`.
Put the handoff slug first and set `next: age`.
Then stop.
Do not invoke `/age --scope <touched-paths> --auto`.
The orchestrator reads the slug and dispatches Age.

For a wave curd, apply the findings and write the Cure slug.
Then stop.
Do not invoke `/plate` or change the remote.
The Cook fan pathway owns final commit and publication.

In both cases, suppress final `/plate` dispatch.
