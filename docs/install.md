# Install

easy-cheese skills can be installed three ways. Pick the one that matches your harness.

## `gh skill` (recommended)

Requires [GitHub CLI](https://cli.github.com) v2.90.0+ with the `gh skill` command.

```bash
# Browse and pick
gh skill install paulnsorensen/easy-cheese

# Install one skill
gh skill install paulnsorensen/easy-cheese cook

# Install every skill in one shot
for s in age briesearch cheese cheese-factory cheez-read cheez-search \
         cheez-write cook culture cure hard-cheese melt mold press ultracook; do
  gh skill install paulnsorensen/easy-cheese "$s"
done
```

### Pin to a release or commit

```bash
gh skill install paulnsorensen/easy-cheese cook@v1.2.0
gh skill install paulnsorensen/easy-cheese cook@abc123def
```

### Choose agent and scope

```bash
# User-wide (recommended for personal toolkits)
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope user

# Committed into the current project repo
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope project
```

Supported `--agent` values include `claude-code`, `github-copilot`, `cursor`, `codex`, and `gemini-cli`. Omit `--agent` to auto-detect.

### Preview before install

```bash
gh skill preview paulnsorensen/easy-cheese cook
```

### Keep up to date

```bash
gh skill update --all
```

## Claude Code plugin

Once a `.claude-plugin/plugin.json` ships, install with:

```bash
/plugin install paulnsorensen/easy-cheese
```

## Manual copy

```bash
# Per-user
mkdir -p ~/.claude/skills
cp -r skills/age ~/.claude/skills/

# Per-project
mkdir -p .claude/skills
cp -r skills/cook .claude/skills/
```

## Bootstrap script (tools + MCP servers)

The repo ships an `install.sh` that handles the surrounding ecosystem — CLI tools (`ripgrep`, `jq`, `fd`, `ast-grep`, `mergiraf`, `tilth`, etc.) and MCP servers (`tilth`, `context7`, `tavily`, `code-review-graph`).

```bash
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh | bash
```

Flags:

| Flag | Purpose |
| --- | --- |
| `--tools <list>` | Comma-separated CLI tools (`gh`, `ripgrep`, `fd`, `jq`, `ast-grep`, `git-delta`, `just`, `mergiraf`, `tilth`) |
| `--mcp <list>` | MCP servers to register (`tilth`, `context7`, `tavily`, `code-review-graph`, `none`) |
| `--skip-mcp` / `--skip-tools` | Run one half only |
| `--harness <list>` | Harness to register MCP servers with (`auto`, `claude-code`, `cursor`, `codex`, `gemini`, `vscode`, `zed`, `copilot`) |
| `--no-edit` | Register tilth without the `--edit` capability |
| `--dry-run` | Print what would happen without changing anything |

See `scripts/install.sh --help` for the full reference.
