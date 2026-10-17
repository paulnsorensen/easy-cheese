# ADR: WorkRecord continuity is worktree-scoped and pointer-free

Status: accepted (2026-07-26)
Spec: [Cross-skill work contract](../specs/cross-skill-work-contract.md)

## Context

`/cheese --continue` scans phase artifacts, while Wheypoint records can be misbound when concurrent work shares a cwd and recency acts as identity.[^1] Harness session identifiers are neither portable nor established as stable across `/clear`, and background agents may inherit the same process environment.

## Decision

One `WorkRecord` represents one user work item across conversations, phases, branches, and worktrees. A `WorkAttempt` represents one branch/worktree execution. Shared decisions and working context belong to the record; tentative branch-specific context belongs to an attempt.

The canonical record is `$XDG_DATA_HOME/cheese/<project>/work/<work-id>/index.md`. An optional portable snapshot may live at `.cheese/work/<work-id>/index.md`. Discovery inspects both, imports a valid local-only snapshot, and stops for explicit reconciliation when copies diverge.

Continuation derives `WorktreeKey` from the worktree-specific Git directory and selects by set cardinality only:

- zero active/paused worktree candidates: project picker;
- one: continue automatically;
- two or more: worktree picker.

No session key, foreground pointer, modification time, revision recency, or update order chooses work. Background activity can add a candidate but cannot replace a pointer because no pointer exists.

A WorkRecord may have at most one nonterminal WorkAttempt for a WorktreeKey. Joining from a new worktree creates an active attempt. Joining where an active, paused, or blocked attempt exists reuses it. A blocked attempt remains blocked until an explicit revision-checked lifecycle operation resolves it. Completed and abandoned attempts remain terminal; explicit `reopen_work` creates a new attempt while preserving history.

## Consequences

Concurrent work is clearest in separate worktrees. Multiple work items in one worktree remain supported but require selection after context loss. Harnesses share continuity when they share a user filesystem and XDG data root; remote synchronization remains outside the design.

[^1]: `skills/cheese/SKILL.md:89-114`; `skills/wheypoint/SKILL.md:74-85`; [Git worktree documentation](https://git-scm.com/docs/git-worktree.html); [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/).