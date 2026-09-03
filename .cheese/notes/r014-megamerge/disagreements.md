# R014 Megamerge Disagreements

This file collects every disagreement from the area reconciliation notes.

## Affinage

- `src/easy_cheese/skills/affinage/commands.py`: PR #581 added `_with_summary` for each command. Shared reconciliation added `derive_command` for the same purpose. The integration keeps `derive_command` because it removes duplicate local code.

## Age

- `skills/age/SKILL.md`: One path always passed `--next cure`. The output contract required `next: done` for clean reviews. The integration keeps the outcome-derived state because it matches the report contract.
- `skills/age/references/handoff-detail.md`: One path repeated the bundled command as a fallback. The integration removes the duplicate because both instructions ran the same command.
- `src/easy_cheese/skills/age/review_lock.py`: One path promised an unchanged tree but hashed only untracked paths. The integration also hashes untracked content because inline edits must invalidate the lock.

## Briesearch

- `src/easy_cheese/skills/briesearch/commands.py`: PR #581 added local `_with_summary` logic. PR #592 added shared `derive_command` logic. The integration keeps `derive_command` because it removes duplicate code and preserves required summaries.
- `skills/briesearch/SKILL.md`: One instruction required the selected provider tool. Fallback instructions allowed a compatible fetcher. The integration requires an explicit fallback provider and its retrieval tool. This choice preserves fallback support and manifest checks.

## Build

none

## Cheese

- `skills/cheese/SKILL.md`: PR #583 propagated `--auto` broadly. PR #589 made continuation optional. The integration keeps optional continuation because the validated handoff controls resume behavior.
- `skills/cheese/references/classification.md`: One router dispatched retired `/ultracook`. The compatibility skill redirects it. The integration keeps `/cook` because it is the active implementation path.
- `skills/cheese/SKILL.md`: Several sections repeated detailed reference rules. The integration keeps short router rules and reference-owned details to prevent drift.

## Cook

none

## Cure

none

## Docs

- `.github/workflows/docs.yml`: PR #592 watched the old `shared/**` path. Runtime code now uses `src/easy_cheese/shared/**`. The integration removes the dead filters because runtime code does not generate documentation.

## Easy-cheese-setup

none

## Hard-cheese

none

## Melt

- `skills/melt/SKILL.md`: One path named `cat` and `diff`. Its I/O rule requires the selected source backend. The integration keeps the backend rule because it provides one stale-safe inspection path.

## Mold

none

## Pasteurize

none

## Plate

none

## Press

none

## Schemas

- `tests/python/test_document_rules_compiler.py`: One path allowed hardened specifications without Grounding rows. PR #585 requires both probes for each hardened specification. The integration keeps the PR #585 rule because it records required evidence.
- `src/easy_cheese/skills/wheypoint/commands.py`: One path declared `checkpoint` outside the decorated command manifest. The validator requires one declaration method. The integration keeps the decorated manifest because it removes the duplicate declaration path.

## Shared

- `bundle_commands.py` and skill `commands.py`: PR #592 derived placeholder summaries. PR #581 required explicit summaries. The integration requires each summary in `derive_command` and removes local wrappers.
- `migrate.py`: The first migration path repeated publication persistence. The integration keeps `publish_canonical` because one path enforces route and replay checks.
- `publication.py`: The first request digest omitted route and schema identity. The integration keeps both fields because operations cannot replay across contracts.

## Wheypoint

- `skills/wheypoint/SKILL.md`: Older text made `commit` the only write path. Newer work made `checkpoint` the normal path. The integration keeps `checkpoint` for parent binding. It keeps `commit` for raw deltas and compaction proofs.
