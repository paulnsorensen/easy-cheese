# Wheypoint transfer bundles

Wheypoint moves one record between people as a single canonical JSON bundle.
`wheypoint export` writes the bundle, and `wheypoint import` verifies it and writes a new record.
The code lives in `src/easy_cheese/shared/wheypoint/transfer.py`.
The decision record is [wheypoint-schema5-stack-001](../adr/wheypoint-schema5-stack-001.md), decision F-3.

## Bundle contents

A bundle holds exactly these keys: `bundle_version`, `origin`, `included`, `record`, `record_digest`, `projection`, `projection_digest`, and `bundle_digest`.
`origin` names the source project, work id, revision id, revision number, and the digest of the unfiltered source record.
`included` says whether operator directives and local references were kept.
`bundle_digest` covers the canonical bundle without that field.
A digest proves integrity, not authorship, because any holder can recompute every digest.

## Export omits private data by default

Export drops operator-scope directives unless `--include-operator` is set.
Export drops local references unless `--include-local` is set.
Local references are artifact links, edges, working-context items, and path-like words in free text.
A free-text word becomes `<local reference omitted>`.
The next action's `tasks` and `parallel` plan hold commands and worktree paths, so `--include-local` governs them too.
A default export drops both, and a `tasks` move becomes `hold`.
Export also scrubs machine-specific absolute paths outside the checkout, even when the file is gone.
A record that links repository paths needs `--workspace-root`, because only a checkout says which paths are local.
Export fails closed when `git check-ignore` fails (PR #784), so a Git failure cannot leak a local reference.

## Import treats the bundle as untrusted

Import bounds the bundle to 4 MiB and requires exact keys and strict types.
It checks the bundle, record, and projection digests.
Any mismatch refuses with `bundle-digest-mismatch` and writes nothing.
Import compares `origin.record_digest` with the record only when both `included` flags are true, because a filtered export changes the record (`transfer.py:332`).
`bundle_digest` has no key, so a holder can edit the origin digest and recompute `bundle_digest`.
The digests therefore catch damage and partial edits, not a deliberate forgery.
Import runs the same secret scan as a checkpoint and refuses a credential-like field with `secret-pattern`.
Import refuses a name that is not a lower-case identifier (`invalid-slug`) and a name that already holds a record (`import-exists`).

## What import writes

A valid import writes a genesis revision, not a copy of the history.
The genesis carries the orientation, next action, notes, working context, artifact links, and active entries.
It also carries one `forked_from` edge to `wheypoint:<origin-project>/<work_id>@<revision_id>`.
An absent origin project is external lineage, not a gate.
The importer skips a local link with `skipped-local-link` and a link it cannot digest with `skipped-unresolvable-link`.
An imported record resolves as `authoritative`.
A source whose decisions are newer than its notes imports with the notes-drift marker intact.
