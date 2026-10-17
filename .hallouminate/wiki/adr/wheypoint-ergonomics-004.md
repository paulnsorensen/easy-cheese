# Additive schema evolution keeps old digests valid

<certain> Fields added to the wheypoint record in schema_version 3 are omitted from canonical bytes when they hold their default, so every v2 revision re-serializes byte-identically and its digests stay valid without migration.[^spec]

## ADR-004: Omit-default canonicalization for added fields [status: accepted]

- **Context:** <certain> Record and revision digests hash `attrs.asdict(recurse=True)` through `canonical_bytes` (`src/easy_cheese/skills/wheypoint/records.py:56-58,74-82`, `canonical.py:55-64`), which emits every key including `None` defaults. Adding `notes`, `tasks`, `parallel`, `quote`, or a `directives` ledger would change the recomputed digest of every existing revision, and the v3 runtime would report all seven stores in the corpus as `store-inconsistent`. A taste-test probe found this after the spec had promised "v2 digests unchanged". Only `schema_version` stamps a record, so an older runtime reading a newer store already misattributes canonical-form skew to the store: the installed bundle from 2026-08-29 and the repo bundle disagreed on the same bytes on 2026-09-05.
- **Decision:** Canonical serialization drops v3-added fields at their default. A v2 golden store and a v3 golden record with pinned digests are fixture tests, so any canonical-byte drift fails a test naming the required `schema_version` bump. `resolve` and `lint` report `runtime-behind` when a record's stamp exceeds the reader's instead of `store-inconsistent`.
- **Alternatives:** A `migrate` verb rewriting every v2 store to v3 with fresh digests and a chained receipt. Rejected: every store in the corpus would gain a revision it did not ask for.
- **Consequences:** The canonical form gains one rule; the ADR-004 kernel decision (canonical JSON + SHA-256) is unchanged. Future additive fields must follow the same rule or bump the version with a fixture update.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-ergonomics.md`, approved 2026-09-05 — forks `v3-digest-compat`, `skew-detection`; AC-16, AC-17, AC-24.
