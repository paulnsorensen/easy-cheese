## Summary

- This node reconciles the public authoring path around `checkpoint`.
- This node retains `commit` for raw deltas and compaction proofs.
- This node rebuilds all Python skill bundles after the cumulative merge.
- `just check` passes.

## Commits

- `78357af` (`fix(wheypoint): reconcile checkpoint contracts`)

## Source PRs

- #581
- #583
- #587
- #588
- #589
- #592

## Disagreements

- `skills/wheypoint/SKILL.md`: Older text makes `commit` the only write path. Newer work makes `checkpoint` the normal path. This reconciliation keeps `checkpoint` for parent binding. It keeps `commit` for caller-supplied raw deltas and compaction proofs.

## Outward dependencies

- `this -> schemas`: `easy_cheese_schemas` supplies all Wheypoint records, deltas, revisions, projections, status values, and compaction contracts.
- `this -> schemas`: `phase_contracts` supplies legacy status parsing and disposition.
- `this -> shared`: `paths.project_key`, `paths.project_corpus_root`, and `paths.git_toplevel` locate durable state and note mirrors.
- `this -> shared`: `bundle_commands` supplies the command manifest and dispatcher.
- `this -> shared`: The generated slug keeps the `parse_handoff_slug()` input shape unchanged.
- `other -> this`: The `cheese` area calls `resolve` and `lint` before resume dispatch.
- `this -> cook`: Wheypoint carries the baseline contract from `skills/cook/references/quality-gates.md`.
- `this -> build`: `src/easy_cheese/skills/wheypoint/commands.py` exports the static command manifest for bundle and documentation generation.

## STE100 status

compliant

## Follow-ups

none
