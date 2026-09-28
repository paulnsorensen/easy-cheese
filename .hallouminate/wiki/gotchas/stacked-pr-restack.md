# Gotcha: restacking a long PR chain after its bottom PRs squash-merge

Recorded 2026-09-03 while restacking the r014 chain (#579 → #589, 11 branches) after #577/#578 merged to `main`.

## Symptoms

- The bottom PR shows `mergeable: CONFLICTING` because its branch still carries the pre-squash commits of the merged PRs.
- `gt log short` does not know the chain, and no local `gh stack` tracking exists (`$GIT_DIR/gh-stack` is per git-dir, so a fresh worktree sees none) even when the stack is linked on GitHub.

## What works

1. Rebase each branch bottom-up with `git rebase --onto <new parent tip> <old parent tip> <branch>`, where the bottom branch's old parent is the last merged commit of the old lineage. Record every local tip before a second cascade; `origin/<branch>` tips go stale after the first pass.
2. Generated archive refreshes can conflict on `skills/*/scripts/*.pyz`. Resolve source conflicts first, then run `just wedge-build` and `just check`. Commit the regenerated archives with their source changes. Wedge uses the pinned tool project; the retired short-path Shiv environment is not required. Do not treat a selected binary conflict side as verified output.
3. Adopt the rebased branches into `gh stack` with `gh stack init --base main <bottom> … <top>`; it finds the open PRs by branch name. Then `gh stack push` (per-branch `--force-with-lease`).

## Traps

- An untracked `uv.lock` in the worktree stops any pick that adds `uv.lock` with "untracked working tree files would be overwritten". It is not a merge conflict, so a conflict-driven loop spins forever. Move the file aside first.
- A rebase can succeed and still break at runtime when `main` changed a signature under the chain. #577 made `SpecFormatPolicy.requires_section` take a keyword-only `default_required`; the Grounding gate in #585 called the old one-argument form and raised `TypeError` on every spec. Run `tests/python/test_validate_spec.py` and `basedpyright` on any restacked mold branch.
- `mergiraf` resolves most Python conflicts; the ones it leaves are usually a `main` guard clause meeting a chain refactor of the same block (`validate_spec.py` test-contracts parsing) or a generated region (`skills/mold/references/curdle.md`). Verify a generated-region merge with `scripts/render_generated_regions.py --check`.
- CI `lint` and `type-check` jobs can go red before any project step runs when `extractions/setup-crate` (the `just` installer) hits a GitHub API rate limit. Read the job log before treating it as a code failure.

_Source: deployment reference correction for [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729) · Updated: 2026-09-28 · Supersedes: extensionless launcher references from the initial Wedge proposal._
