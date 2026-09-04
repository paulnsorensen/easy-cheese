# Schemas to Wheypoint edge review

## State

broken

## Evidence

- Schemas export `CompactionRecord`, `WheypointDelta`, and `WheypointRevision` at `src/easy_cheese_schemas/__init__.py:88-109`.
- `CompactionRecord` requires the revision, record digest, and entry ledger at `src/easy_cheese_schemas/wheypoint.py:419-449`.
- The prior compaction identifier defaults to null, and the source session list defaults to empty.
- `WheypointRevision` carries parent identifiers, parent digests, compaction data, and session data at `src/easy_cheese_schemas/wheypoint.py:672-706`.
- Schemas call no Wheypoint module, command, or note path under `src/easy_cheese_schemas`.
- Wheypoint imports schema records in `records.py:30-38`, `commit.py:49-64`, `lineage.py:9`, and `lint.py:25-31`.
- The `commit` command structures raw input as `WheypointDelta` at `src/easy_cheese/skills/wheypoint/wheypoint.py:167-178`.
- Invalid shapes return `invalid-delta`, and semantic refusals return `commit-refused` at `wheypoint.py:167-178,223-245`.
- The `checkpoint` command rejects compaction fields and binds a normal delta at `wheypoint.py:181-220`.
- Commit checks the current revision, record digest, and entry ledger at `commit.py:406-458`.
- Commit derives the prior compaction identifier from stored lineage at `commit.py:546-608`.
- `lineage.walk` checks missing parents, cycles, and parent digests at `lineage.py:58-124`.
- `lint_work` checks the stored lineage and compaction claims at `lint.py:193-256,353-452`.
- Storage emits `record.json`, revision JSON, and projection Markdown at `storage.py:1-23,261-319`.
- The command surface contains `checkpoint`, `commit`, `resolve`, `show`, and `lint` at `commands.py:15-57`.
- Projection fields emit the status, move, artifact, identifiers, digests, durability, version, and orientation at `projection.py:38-95`.
- The Wheypoint skill requires rehydration before compaction at `skills/wheypoint/SKILL.md:50-67`.
- The delta reference matches the compaction field names and defaults at `skills/wheypoint/references/delta-contract.md:67-68,96-105`.
- Schema tests cover shape and defaults at `tests/schemas/python/test_wheypoint_conformance.py:391-402,611-643`.
- Runtime tests cover commit and lint behavior at `tests/wheypoint/python/test_commit.py:571-710` and `test_lint.py:297-408`.
- The focused command passed all 164 selected tests.
- Behavioral probes returned no lint codes for each invalid record described below.

## Findings

### Blocker

- **Lineage accepts an impossible root or a foreign parent.** The schema permits a later revision without a parent. The schema test accepts this state at `tests/schemas/python/test_wheypoint_conformance.py:382-389`. The walker compares neither work identifiers nor revision numbers at `src/easy_cheese/skills/wheypoint/lineage.py:68-124`. Probes accepted revision two without a parent. They also accepted a revision gap with a foreign parent. **Fix:** Require revision one when the parent is null. Require later revisions to name a parent. Require each parent to use the same work identifier and the previous revision number. Add schema and lint tests for each refusal.

### High

- **Lint accepts an incomplete compaction proof.** The schema requires `rehydrated_record_digest` and `reconciled_entry_ids` at `src/easy_cheese_schemas/wheypoint.py:419-449`. Commit validates both fields at `src/easy_cheese/skills/wheypoint/commit.py:433-458`. Lint checks neither field at `src/easy_cheese/skills/wheypoint/lint.py:399-452`. Probes accepted a false record digest and an empty ledger over one protected entry. **Fix:** Compare the digest with the parent receipt's `record_digest`. Derive the parent entry set from preserved identifiers and applied transitions. Require the compaction ledger to include that complete set. Add negative lint tests for both fields.
- **Lint accepts a prior compaction that points forward or to itself.** Schema stores the prior identifier at `src/easy_cheese_schemas/wheypoint.py:431-445`. Lint checks only map membership and compaction presence at `src/easy_cheese/skills/wheypoint/lint.py:415-451`. A self-reference probe returned no lint codes. **Fix:** Track each position in the current-first lineage. Require every prior compaction to occur later in that sequence. Add self-reference and descendant-reference tests.
- **Wheypoint prose omits the schema value `cut`.** Schemas define `NextMove.CUT` at `src/easy_cheese_schemas/wheypoint.py:86-101`. The delta reference includes `cut` at `skills/wheypoint/references/delta-contract.md:47-49`. The skill omits it at `skills/wheypoint/SKILL.md:79-82,163-180`. A test requires the omission at `tests/python/test_wheypoint_skill_contract.py:173-185`. **Fix:** Add `cut` to the Wheypoint and Cheese dispatch contracts. Replace the omission assertion with an end-to-end round-trip test.

### Medium

none

### Low

none

## STE100 status

compliant

The schemas area has no `SKILL.md` file.
The Wheypoint skill and reference prose meet the STE100 form rules.

## Follow-ups

- Enforce revision ancestry invariants in the schemas and the lineage walker.
- Validate stored compaction digests, entry ledgers, and prior ordering in lint.
- Add `cut` to the Wheypoint and Cheese dispatch contracts.
- Replace the `cut` omission assertion with an end-to-end round-trip test.
