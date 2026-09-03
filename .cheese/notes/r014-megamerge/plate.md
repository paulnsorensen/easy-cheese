# Plate reconciliation

## Summary

- The Plate instructions now use one coherent publication flow.
- The provider, topology, and durable-write rules use Simplified Technical English.
- The bundle rebuild includes all integrated command changes.

## Commits

- `86e87fc` — Ingest the Plate slice from PR #568.
- `bd33a0d` — Ingest the Plate slice from PR #581.
- `df3f07e` — Reconcile the Plate guidance and rebuild all skill bundles.

## Source PRs

- #568
- #581
- #592

## Disagreements

none

## Outward dependencies

- `this -> shared`: `easy_cheese.shared.bundle_commands` supplies `bundle_command`, `derive_command`, and `dispatch`. The contract did not change.
- `this -> age`: `/age` owns code-quality review. The contract did not change.
- `this -> gh`: `/gh` owns GitHub inspection and administration. The contract did not change.
- `this -> wiki-ingest`: `/wiki-ingest` owns durable wiki updates. The contract did not change.
- `this -> hard-cheese`: `/hard-cheese` receives final evidence for `--hard`. The contract did not change.
- `this -> cheese`: `ask-user-question.md` supplies topology question transport. The contract did not change.
- `this -> cook`: `quality-gates.md` supplies repair-worktree rules. The contract did not change.

## STE100 status

compliant

## Follow-ups

none
