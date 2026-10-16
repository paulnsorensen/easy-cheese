# Wheypoint schema 5 follow-up stack decisions

<certain> Issues #754-#761 and the /wheel port land as a linear stack of optional `since: 5` additions on top of PR #776, not as a schema 6 bump.[^spec]

## ADR-001: Stack shape, notes marker, bundle transport, and line pinning [status: accepted]

- **Context:** <certain> PR #776 already ships the entry lifecycle kernel: `supersede` transitions, active-only projection, a `stale-notes` checkpoint warning, and a fork that copies no entries (`src/easy_cheese/shared/wheypoint/fork.py`, `projection.py:_body` on #776). `revision_id` is an opaque hash; `WheypointRecord.revision_number` is the ordered counter. Optional `since: 5` fields at their default stay out of canonical bytes, so digests do not move ([[adr/wheypoint-ergonomics-004]]).
- **Decision:**
  - F-1: linear layers on #776 — L5 lifecycle (#754, #755), L6 owner/when and operator directives (#759, #760), L7 resolve prefix and list fallback (#761, in-stack because #776 rewrites `resolve.py`), L8 reference pinning and `## Local references` (#758), L9 export/import (#757). `/wheel` (#764) rebases as a sibling branch off #776.
  - F-2: notes drift shows as a projection marker from two stamps, `notes_revision_number` and `decisions_revision_number`.
  - F-3: export writes one canonical JSON bundle (record, projection, digests) without operator directives or local references by default; import verifies digests and writes a genesis that carries the bundle content plus a `forked_from` edge to `wheypoint:<origin-project>/<work_id>@<revision_id>`.
  - F-4: checkpoint pins bare `path:line` to `path:line@<sha>`; `path#symbol` stays as is; nothing rewrites references later.
- **Alternatives:** Notes split into current/history fields (rejected: larger contract change); full-history export under the same `work_id` (rejected: two writers could own one record); read-time re-anchoring via git blame (rejected: non-deterministic, needs the repository at read time); `/wheel` as the last layer (rejected: it would wait on five unrelated layers).
- **Consequences:** The JSON-schema goldens regenerate in each field layer, and the wheypoint command count goes from 10 to 12. #756 closes without code. The `easy-cheese-schemas` package still needs its 3.0.0 bump on #776.

## Later changes

- PR #783 adds `matched_by` (`exact`, `prefix`, or `substring`) to the `resolve` payload. Fuzzy matches stay dispatchable.
- PR #784 makes the projection's `git check-ignore` call fail closed: a Git failure raises `CheckIgnoreError` instead of emptying the ignored set.
- PR #785 refines F-3. Export omits `tasks` and `parallel` unless `--include-local` is set, and import runs the secret scan. See [wheypoint-transfer-bundles](../architecture/wheypoint-transfer-bundles.md).

## References

[^spec]: `~/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-schema5-stack.md`, taste-tested 2026-10-14 (round 2 pass) — forks F-1..F-4, AC-1..AC-22.
