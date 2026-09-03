---
name: easy-cheese-setup
description: >
  Register the durable `cheese-durable` Hallouminate corpus.
  Repair the durable corpus when its configuration changes.
  Register the repository tenant.
  Repair the repository tenant when its configuration changes.
  Use this skill when the user requests durable corpus setup or repair.
  Use it when the user requests repository tenant registration.
  Also use it when the user invokes /easy-cheese-setup.
  Use the wiki skills for general Hallouminate wiki work.
  Use scripts/install.sh to install the MCP server.
license: MIT
---

# /easy-cheese-setup

Register the durable `cheese-durable` Hallouminate corpus. The corpus makes each project's XDG artifacts searchable across sessions.

Register the current repository as a Hallouminate tenant when the user requests it. This process is idempotent. It does not delete data.

The engine is a self-contained bundle at `scripts/easy-cheese-setup.pyz`. It has three subcommands. Each subcommand changes data only with `--apply`. Without this option, each subcommand only reports.

```
python3 <skill>/scripts/easy-cheese-setup.pyz global [--apply]   # durable-corpus registration/repair
python3 <skill>/scripts/easy-cheese-setup.pyz local  [--apply]   # per-repo tenant registration
python3 <skill>/scripts/easy-cheese-setup.pyz doctor [--apply]   # both legs
```

At installation, `install.sh` calls `global --apply` when `--mcp` includes `hallouminate`. This skill controls the interactive process.

## Flow

Run `doctor` without `--apply` first. It reports the planned actions for both legs without changes. Show the report as evidence. Ask the user for confirmation. Apply only the approved legs.

### Global leg — durable corpus

- Create the directory from `paths.corpus_home()` if it does not exist. This action prevents Hallouminate issue #101.
- Insert or replace the marked `[[corpus]]` block in `~/.config/hallouminate/config.toml`. Use `# >>> easy-cheese:cheese-durable` and `# <<<` as the markers. Point the block at `corpus_home()`. A second `global --apply` leaves the file unchanged.
- Use `--apply` to correct a marked block that points elsewhere.
- **Legacy migration requires user interaction.** An unmarked `cheese-global → ~/.cheese` block is stale. Show the report. Ask the user for confirmation. Then use the explicit migration option. The installer never uses this option:

  ```bash
  python3 <skill>/scripts/easy-cheese-setup.pyz global --migrate-legacy --apply
  ```

  Leave a `cheese-global` block unchanged if it points anywhere except `~/.cheese`.

### Local leg — repo tenant

- Run `hallouminate init-repo <name> --path <main-root>` when both required conditions are true. The repository must have `.cheese/` artifacts. It must not have a Hallouminate tenant.
- Register the main repository root. Do not register a worktree. This rule prevents a temporary path from replacing the tenant identity.

## Rules

- Detect the current state. Report proposed changes. Ask the user for confirmation. Require `--apply` for each operation that changes data.
- Use the imported `paths.corpus_home()` as the only source for the durable root. Do not hardcode `~/.cheese` or an XDG path.
- Do not delete data by default. `install.sh` changes only the marked block. Remove a legacy block only after user confirmation.

See the generated bundle command inventory in [`references/commands.md`](references/commands.md).
