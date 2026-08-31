# Durable writes

Publication is forbidden until every promised artifact and every durable fact
discovered during implementation has been written and read back.

## Inventory

Build one list from upstream handoffs/specs, promised reports or generated
files, ADR/domain-model decisions, release notes, and implementation-time
architecture, convention, protocol, or gotcha knowledge. Classify each item as
required or optional and tracked or transient.

When the repository has a hallouminate wiki, also sweep `git status` for
uncommitted `.hallouminate/wiki/` paths and add each (unless gitignored) as a
required tracked artifact — wiki writes from earlier in the session ship with
this publication, not after it.

## Backend cascade

1. When the consumer repository exposes a hallouminate wiki, invoke the explicit
   user-visible `/wiki-ingest` handoff/capability. Do not duplicate its curation
   algorithm or hand-edit `.hallouminate/wiki`.
2. If hallouminate or `/wiki-ingest` is unavailable, write the tracked fallback
   from `skills/mold/references/adr.md`: `docs/adr/<slug>-NNN.md`. A cumulative
   domain model uses the repository's existing tracked domain-model path.
3. Other promised tracked artifacts go to their contractually named paths.
4. `.cheese/` reports are transient evidence. Keep them unstaged.

## Canonical write sequence

Every tracked write runs these three calls, in this order, per file:

1. **Fresh tagged read** — read the target immediately before writing and copy
   its tag and its 1-based line numbers from that read. Never reuse a tag, a
   line number, or a file body captured earlier in the session.
2. **One stale-safe write** — send a single write carrying that fresh tag, with
   every op in the shape its backend defines. A text replacement carries only
   the exact unique `old` string and its `new` replacement — never `start`/`end`
   line numbers. Line ops carry only integer `start`/`end` copied from the fresh
   read. Mixing the two op shapes is a malformed write: a call-shape defect
   owned by this skill, not a backend outage.
3. **Diff read-back** — re-read the written range or diff the file, then compare
   target, essential contents, and expected revision before the row is
   `verified`.

A rejected write means the file drifted. Re-read for a new tag and retry that
section; never retry with the stale tag and never fall back to a shell redirect
or a host editor.

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
