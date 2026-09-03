---
name: easy-cheese-setup
description: >
  Register and repair the durable cheese Hallouminate corpus and the repository tenant.
  Use this skill when the user requests durable corpus setup or repair.
  Also use it when the user requests repository tenant registration or invokes /easy-cheese-setup.
  Run a detect, report, confirm, and fix loop for each registration.
  Do not use this skill for general Hallouminate wiki work.
  Use the wiki skills for that work.
  Do not use this skill to install the MCP server.
  Use scripts/install.sh for that task.
license: MIT
---

# /easy-cheese-setup

Register the durable `cheese-durable` Hallouminate corpus. This corpus makes each project's XDG artifacts searchable across sessions.

Register the current repository as a Hallouminate tenant when the user requests it. The process is idempotent and does not delete data.

The engine is a self-contained bundle at `scripts/easy-cheese-setup.pyz`. It has three subcommands. Each subcommand requires `--apply` before it changes data. Without this option, each command only reports.

```
python3 <skill>/scripts/easy-cheese-setup.pyz global [--apply]   # durable-corpus registration/repair
python3 <skill>/scripts/easy-cheese-setup.pyz local  [--apply]   # per-repo tenant registration
python3 <skill>/scripts/easy-cheese-setup.pyz doctor [--apply]   # both legs
```

At installation, `install.sh` calls `global --apply` once when `--mcp` includes `hallouminate`. This skill controls the interactive path.

## Flow

Run `doctor` without `--apply` first. It reports the planned actions for both legs without changes. Show the report as evidence. Ask the user for confirmation. Apply only the approved legs.

### Global leg — durable corpus

- Create the directory from `paths.corpus_home()` if it does not exist. This action prevents Hallouminate issue #101. Insert or replace the marked `[[corpus]]` block in `~/.config/hallouminate/config.toml`. The block starts with `# >>> easy-cheese:cheese-durable` and ends with `# <<<`. Point the block at `corpus_home()`. A second `global --apply` leaves the file unchanged.
- If the marked block points elsewhere, use `--apply` to correct it.
- **Legacy migration requires user interaction.** An existing unmarked `cheese-global → ~/.cheese` block is stale. Show the report and get confirmation. Then use the explicit migration option. The installer never uses this option:

  ```bash
  python3 <skill>/scripts/easy-cheese-setup.pyz global --migrate-legacy --apply
  ```

  Leave a `cheese-global` block unchanged if it points anywhere except `~/.cheese`.

### Local leg — repo tenant

- Run `hallouminate init-repo <name> --path <main-root>` when the repository has `.cheese/` artifacts and no Hallouminate tenant.
- Always register the main repository root. Never register a worktree. This rule prevents a temporary worktree path from replacing the tenant identity.

## Rules

- Detect and report before you change data. Require `--apply` and user confirmation for each operation that changes data.
- Use the imported `paths.corpus_home()` as the single source for the durable root. Do not hardcode `~/.cheese` or an XDG path.
- Do not delete data by default. `install.sh` changes only the marked block. Remove a legacy block only after user confirmation.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
