# Post-PR learning write-back for Cure

Read this file before any path publishes to a PR.
These paths include default `/plate`, `--open-pr`, safe **Plate it**, and automatic publication.

After publication, record implementation facts that became known after Curdle.
This operation is the second wiki write point.
Curdle owns the design write point.

Record constraints found during `/cook`.
Record `/age` findings that changed the design.
Record domain terms that the diff introduced or changed.

## Candidates

Read `durable_flags:` from `.cheese/cook/<slug>.md` and `.cheese/age/<slug>.md`.
Treat each non-`none` entry as a candidate.
Also include new ADRs and domain model changes.
Upstream phases record flags only.
Cure, Plate, and Affinage remain the wiki writers.

## Writer

When Hallouminate is available, dispatch `/wiki-ingest` with the candidate list.
Tell it to record only facts that are new since Curdle.
Its routing and conflict rules prevent duplicate design facts.

When Hallouminate is unavailable, write `docs/adr/<slug>-NNN.md` and the domain model fallback.
Report that the write-back used files instead of the wiki.
Do not hide this fallback.
Read [`optional-plugins.md`](../../cheese/references/optional-plugins.md) for detection and fallback rules.

## Ownership

Run this write-back after every publication path.
The frame that dispatches final `/plate` owns the write-back.

Cure does not write back when another skill owns final `/plate`.
This exception includes Cook fan workers that cannot publish.
It also includes an Affinage chain.
The final publication owner performs the write-back.

## Empty case

When all `durable_flags` are `none` or absent, check for new ADRs and domain changes.
When no candidate exists, report `no post-PR learnings`.
Do not create an entry.

## Deferred move

`[TBD]` The trigger currently exists at the Cure boundary.
A later change can move it to `/plate`.
That move keeps publication and fact capture at one boundary.
Move `durable_flags` consumption with the trigger.
See the `post-pr-wiki-writeback` wiki page.
