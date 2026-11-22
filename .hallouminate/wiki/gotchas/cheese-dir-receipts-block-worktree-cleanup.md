# Gotcha: `.cheese/` receipts block worktree cleanup

Easy-cheese phases write receipts and reports into `<worktree>/.cheese/`, and nothing removes them.
The directory is git-ignored (`.gitignore:8`), so the files outlive the work.
A cleanup tool must then treat every worktree with a `.cheese/` directory as dirty.
Issue #869 tracks the fix. No lifecycle contract exists yet.

## Why it matters

The `.cheese/` directory mixes two kinds of output.
A cleanup tool cannot tell them apart without reading each file.

- Ephemeral output has no value after the PR merges. This covers review, publish, and scratch receipts from `age`, `plate`, `affinage`, `cure`, `press`, and loose PR bodies.
- Durable output is a spec, plan, research note, glossary, Mold record, or wheypoint record. A deleted worktree strands it.

The durable corpus is the right home for durable output. See [[index]] for the three storage lanes.

## Evidence

The issue measured one operator's machine on 2026-11-04.
229 of 541 remaining worktrees were held back by `.cheese/` alone.
147 of those 229 were already merged.
About 1,450 files were receipts or scratch, and about 760 looked durable.
Treat these counts as one sample. They are not a repo invariant.

## Current workaround

The operator's sweep tool copies `.cheese/` to a per-repo archive before it removes a receipts-only worktree.
The workaround lives outside this repo. The writer phases still own no cleanup.

## Proposed direction (not implemented)

The issue asks for three changes, and the triage label is `triage/needs-design`.

1. Write ephemeral output to a path that is safe to delete, such as a per-run directory.
2. Write durable output to the durable corpus, outside the worktree.
3. Document which `.cheese/` subdirectories a cleanup tool may delete without reading them.

Until the contract exists, do not delete a `.cheese/` subdirectory by name. Read it first.
