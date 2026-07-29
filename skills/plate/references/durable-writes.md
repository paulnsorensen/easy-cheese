# Durable writes

Publication is forbidden until every promised artifact and every durable fact
discovered during implementation has been written and read back.

## Inventory

Build one list from upstream handoffs/specs, promised reports or generated
files, ADR/domain-model decisions, release notes, and implementation-time
architecture, convention, protocol, or gotcha knowledge. Classify each item as
required or optional and tracked or transient.

## Backend cascade

1. When the consumer repository exposes a hallouminate wiki, invoke the explicit
   user-visible `/wiki-ingest` handoff/capability. Do not duplicate its curation
   algorithm or hand-edit `.hallouminate/wiki`.
2. If hallouminate or `/wiki-ingest` is unavailable, write the tracked fallback
   from `skills/mold/references/adr.md`: `docs/adr/<slug>-NNN.md`. A cumulative
   domain model uses the repository's existing tracked domain-model path.
3. Other promised tracked artifacts go to their contractually named paths.
4. `.cheese/` reports are transient evidence. Keep them unstaged.

## Verification

Read back every required write from the same backend after writing. Compare the
target, essential contents, and expected revision. Emit one completion row per
item in the exact shape `{target, backend, verified}`. `verified` is true only
after successful read-back.

Halt before `just check`, staging, commit, push, or PR creation when a required
write is missing, a write call failed, or read-back cannot verify it. Optional
write failures are reported but never silently promoted to complete.

## Stack placement

Tracked knowledge shared by every PR belongs on the bottom/common branch or an
explicit wiring branch that all dependent PRs inherit. PR-specific artifacts
belong on the branch whose behavior requires them. The completion rows must name
that placement before the stack is submitted.

## `/hard-cheese` handoff

When `--hard` is active, pass the final inventory, completion rows, tracked
artifact diff, and quality-gate result into `/hard-cheese` before publication.
