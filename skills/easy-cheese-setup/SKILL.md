---
name: easy-cheese-setup
description: Register and repair the durable cheese hallouminate corpus and the per-repo tenant. Use when the user says "set up cheese corpus", "repair hallouminate corpus", "register durable corpus", "my specs aren't searchable across sessions", "fix cheese-global drift", or invokes /easy-cheese-setup. Runs a detect → report → confirm → fix loop over two legs — a global durable-corpus registration/repair and a local per-repo tenant registration. Do NOT use for general hallouminate wiki authoring (that is the wiki skills) or for MCP server installation (that is scripts/install.sh).
license: MIT
---

# /easy-cheese-setup

Register the durable `cheese-durable` hallouminate corpus (so every project's XDG specs/research are semantically searchable across sessions) and, when asked, register the current repo as a hallouminate tenant. Idempotent and non-destructive: it detects, reports with evidence, asks before mutating, then fixes.

The engine ships as a self-contained bundle at `scripts/easy-cheese-setup.pyz`, with three `--apply`-gated subcommands (default is dry-run / report-only):

```
python3 <skill>/scripts/easy-cheese-setup.pyz global [--apply]   # durable-corpus registration/repair
python3 <skill>/scripts/easy-cheese-setup.pyz local  [--apply]   # per-repo tenant registration
python3 <skill>/scripts/easy-cheese-setup.pyz doctor [--apply]   # both legs
```

`install.sh` calls `global --apply` once at install time (guarded on hallouminate ∈ `--mcp`). This skill drives the interactive path.

## Flow

Run `doctor` (no `--apply`) first — it reports both legs' intended actions without touching anything. Show the report as evidence, confirm with the user, then apply the legs they approve.

### Global leg — durable corpus

- Ensures `paths.corpus_home()` exists on disk (guards hallouminate's abort-on-missing-path, hallouminate#101), then insert-or-replaces the marked `# >>> easy-cheese:cheese-durable … # <<<` `[[corpus]]` block in `~/.config/hallouminate/config.toml`, pointing at `corpus_home()`. Replace-in-place keeps it idempotent — a second `global --apply` leaves the file byte-identical.
- Repoints on drift: if the marked block points anywhere other than `corpus_home()`, `--apply` corrects it.
- **Legacy migration (interactive only).** A pre-existing unmarked `cheese-global → ~/.cheese` block is the stale state this work fixes. `migrate_legacy` removes it so the durable corpus collapses onto the marked `cheese-durable` block. It is deliberately NOT a CLI subcommand and NOT part of `install.sh`'s path — so the installer can never delete a user's config non-interactively. Invoke it here only after the user confirms the reported legacy block:

  ```bash
  python3 -c "import sys; sys.path.insert(0, '<skill>/scripts/easy-cheese-setup.pyz'); \
    import hallouminate_setup as h; print(h.migrate_legacy(apply=True))"
  ```

  A `cheese-global` block pointing anywhere other than `~/.cheese` is left untouched.

### Local leg — repo tenant

- Iff the repo has `.cheese/` artifacts and is not already a hallouminate tenant, runs `hallouminate init-repo <name> --path <main-root>`.
- Registers the **main repo root**, never a worktree — in a Conductor/worktree checkout this avoids stomping the tenant identity onto a throwaway worktree path.

## Rules

- Detect and report before mutating; every mutating leg is `--apply`-gated and confirmed.
- One source of truth for the durable root: the engine imports `paths.corpus_home()` — never hardcode `~/.cheese` or an XDG path.
- Non-destructive by default: `install.sh` touches only the marked block; legacy-block removal is interactive-only.
