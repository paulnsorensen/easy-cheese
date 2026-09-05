# Age review lock invariants

`src/easy_cheese/skills/age/review_lock.py` binds a review to the exact tree it examined. The r014 review of Age (`.cheese/notes/r014-megamerge/review-age.md`, cured in `cure2-age.md`) turned four security findings into standing invariants. Any change to the lock must keep all of them.

## Git side-channels are disabled before hashing

Git runs repository-configured commands during a diff: `textconv` filters, external diff drivers, hooks, and the filesystem monitor. An automated reviewer that shells out to `git diff` executes those commands with its own privileges. The lock passes `--no-ext-diff --no-textconv` (`review_lock.py:65`) and disables hooks and `core.fsmonitor` before any Git call. Every Git error fails closed; the only tolerated failure is "not a git repository".

## The digest covers the whole tree

A plain `git diff` compares the worktree to the index, so a re-staged change keeps the same digest. The original lock hashed `git diff HEAD` plus untracked files and excluded `.cheese`, so two clean commits collided. `tree_digest` (`review_lock.py:134-183`) now hashes `HEAD`, includes `.cheese`, and when `HEAD` is unborn hashes the index against the empty tree plus the worktree delta.

## Paths resolve to the top-level worktree

The lock resolves the top-level repository root before it digests or writes, so a nested-directory invocation cannot duplicate paths or let tracked files outside the directory escape the lock. It rejects any symlink component in the lock path and writes with `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` (`review_lock.py:276`), because a tracked `.cheese/age` symlink could otherwise redirect the write outside the repository.

## Freshness binds to the digest, not `HEAD`

A gate that compares only a recorded `HEAD` SHA accepts a changed-but-uncommitted tree. The same rule applies to the hard-cheese freshness check; see [hard-cheese-gate-contract](../architecture/hard-cheese-gate-contract.md). Compare one digest over `HEAD`, the working diff, the optional specification, and prior evidence.

## Age has no pass counter

Age starts a fresh context on every pass and cannot observe earlier passes. The two-pass cure cap is owned by the Cook phase table (`skills/cook/references/auto-mode.md:59-81`), not by Age or Cure; see [skill-review-round-r014](../decisions/skill-review-round-r014.md).

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `review_lock.py` on 2026-09-04 · Updated: 2026-09-04_
