# Gotcha: broad gates dirty the red-gate frozen tree after phase entry

`red-gate begin` freezes the entire project tree outside the plan's `production_paths` (only `.git`, `.cheese`, and cache dirs are excluded). Anything that mutates other paths between `begin` and a later `validate`/`issue` breaks the receipt with "oracle dependency changed since phase entry":

- `just check` / `just docs-build` — rebuilds `tools/skill-overlap/target/` (Rust incremental) and creates a pnpm `node_modules/` (whose directory symlinks also independently halt snapshotting — see [red-gate-worktree-symlinks](./red-gate-worktree-symlinks.md)).
- Harness side effects — e.g. Claude's `.claude/scheduled_tasks.lock` appears when a wakeup is scheduled mid-phase. If it wasn't in the frozen snapshot, deleting it restores validity.
- `scripts/build_pyz.py <skill> --update-locks` — writes `requirements/bundles/<skill>.txt`. The lock pins the skill wheel's SHA-256, so ANY source change under that skill's package requires the lock update; include `requirements/bundles/<skill>.txt` in the Cut plan's `production_paths` whenever `skills/<skill>` or `src/easy_cheese/skills/<skill>` is a production root.

Sequencing that works: run broad gates BEFORE `red-gate begin` or AFTER the final GREEN validation — never between. If the tree gets dirtied mid-chain, the recovery is a clean re-cut: stash production edits + move the protected oracle aside → archive the old phase token/receipt (issuance is append-only; same `--out` path is rejected) → `begin` on the current tree → restore oracle, re-prove RED, re-`issue` → unstash → validate GREEN. (Used twice in the PR #330 salvage, 2026-08.)
