# Durable writes

Write every promised artifact. Read each artifact back. Do not publish before both steps finish.
Also write each durable fact that you find during implementation. Read each fact back.

## Inventory

Build one list of required artifacts. Include handoffs, specifications, promised reports, generated files, ADR decisions, domain-model decisions, and release notes.
Include architecture, convention, protocol, or gotcha knowledge that you find during implementation.
Classify each item as required or optional. Classify each item as tracked or transient.

When the repository has a hallouminate wiki, sweep `git status` for uncommitted `.hallouminate/wiki/` paths.
Add each non-gitignored path as a required tracked artifact. Wiki writes from earlier in the session ship with this publication.

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

Run these three calls in order for each tracked file:

1. **Fresh tagged read** — Read the target immediately before writing. Copy its tag and 1-based line numbers from that read.
   Never reuse a tag, a line number, or a file body captured earlier in the session.
2. **One stale-safe write** — Send one write with that fresh tag. Use the operation shape that the backend defines.
   A text replacement carries only the exact unique `old` string and its `new` replacement—never `start`/`end` line numbers.
   Line operations carry only integer `start` and `end` values from the fresh read.
   Mixing the two op shapes is a malformed write. It is a call-shape defect owned by this skill, not a backend outage.
3. **Diff read-back** — Re-read the written range or diff the file.
   Compare the target, essential contents, and expected revision. Then mark the row as `verified`.

A rejected write means the file drifted. Read the file again for a new tag. Then retry that section.
After a rejection, never retry with the stale tag. Also, never fall back to a shell redirect or a host editor.

## Verification

Read back every required write from the same backend. Compare the target, essential contents, and expected revision.
Emit one completion row per item in the exact shape `{target, backend, verified}`.
Set `verified` to true only after a successful read-back.

Halt before `just check`, staging, commit, push, or PR creation if a required write is missing.
Also halt if a write fails or a read-back cannot verify it.
Report optional write failures. Never mark them as complete.

## Stack placement

Put shared tracked knowledge on the bottom/common branch or an explicit wiring branch.
All dependent PRs must inherit that branch. Put PR-specific artifacts on the branch whose behavior requires them.
The completion rows must name that placement before you submit the stack.

## `/hard-cheese` handoff

When `--hard` is active, pass one JSON context into `/hard-cheese` before publication.
The context requires four fields:

| Field | Value |
| --- | --- |
| `artifacts` | The completion rows in the exact shape `{target, backend, verified}` |
| `inventory` | The final required and optional artifact list |
| `tracked_diff_digest` | The digest of the tracked artifact diff at the reviewed state |
| `gate` | The quality gate command and its result |

Halt when a field is missing. Halt when a row is unverified.
Compute `tracked_diff_digest` from the reviewed tracked tree. Do not reuse a digest from an earlier state.
