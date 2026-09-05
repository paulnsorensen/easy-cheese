# Publication gateway invariants

`src/easy_cheese/shared/publication.py` is the trust boundary for every cross-phase `HandoffPointer`. The r014 shared and schemas reviews (`review-shared.md`, `edge-schemas-shared.md`, `hub-shared.md`) found six holes; the cure round closed them (commits `466ce044`, `b18b463b`, `732bcabf` and the `cure2-shared.md` set). Each fix is now an invariant that tests pin. The entity vocabulary lives in [domain-model](../domain-model.md).

## Pointers are `file` only

`resolve_artifact` in `src/easy_cheese_schemas/artifacts.py:89-105` understands `repo`, `file`, and `https`. The publication gateway rejects any scheme other than `file` before it fetches (`publication.py:484-489`), so a tampered pointer cannot make Cook or another acceptor trust remote content. Keep the artifact-root restriction and the scheme policy together.

## Reads are bounded before parsing

Every payload, receipt, or pointer read goes through one reader that takes at most `MAX_CONTRACT_BYTES + 1` bytes and rejects an oversized file before schema validation (`publication.py:456-459`). `Path.read_bytes()` on a caller-selected path is not allowed at this seam.

## Replay compares every identity field

`_validate_replay` compares `pointer.operation_id` with the request (`publication.py:93,117`). Before commit `466ce044` it skipped that field, so a replay under a different `operation_id` returned the wrong pointer. Any idempotency check on a pointer-like structure validates all identity fields.

## Receipts carry one legacy identity

`NormalizationReceipt` publishes two legacy source-identity URIs. The model now requires them to be equal and non-null (`src/easy_cheese_schemas/contracts.py:676-690`); the fix was equality validation, not field removal.

## Quote repair rejects ambiguity

The generous-writer repair normalizes stray whitespace, trailing commas, and structural curly quotes. It never treats a curly quote inside a value such as `don't` as a delimiter (`publication.py:140-142`); ambiguous input is rejected instead of guessed (commit `b18b463b`). A normalization pass must not mutate characters inside data values.

## One artifact resolver

`publication.py` once carried a weaker local `ArtifactRef` resolver beside the schema package's `resolve_artifact`. The gateway now calls only `resolve_artifact`; do not reintroduce a second resolver.

## Known platform gap

Durability uses `fcntl`, directory `fsync`, and hard links (`publication.py:28-30,397`). `pyproject.toml:15-22` declares OS-independent support. The corrupt-payload repair race is closed on POSIX by `_digest_lock`; a non-POSIX host still races. Route any change to the durability path through a portable adapter.

## Legacy migration is exact

`easy_cheese_schemas.compat` owns exactly one adapter per legacy source version with its sunset rule, and `shared/migrate.py` performs an exact lookup, converts, validates, and publishes through this gateway (see [legacy-adapter-lifecycle-004](../adr/legacy-adapter-lifecycle-004.md)). The conversion callback reads legacy keys without pre-validation, so malformed legacy input can raise `KeyError` instead of `UnsupportedLegacySourceError`; treat that as an open gap.

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `publication.py` and `artifacts.py` on 2026-09-04 · Updated: 2026-09-04 · Supersedes: review-time claims that the resolver accepted HTTPS pointers and that replay ignored `operation_id`_
