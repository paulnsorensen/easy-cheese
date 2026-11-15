# Gotcha: red-gate phase snapshotting halts on directory symlinks

The red-gate phase's tree snapshot walk halts when it hits a directory symlink. The main `easy-cheese` checkout carries several (pnpm `node_modules` links, `.venv/lib64`), so running `/cut` from the main checkout fails partway through snapshotting.

Run `/cut` from a clean dedicated worktree instead — this spec's Cut ran in `.worktrees/spec-format-enforcement` for that reason.
