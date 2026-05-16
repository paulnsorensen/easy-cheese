---
name: melt
description: This skill should be used when a git merge, rebase, or cherry-pick has produced conflicts and the user wants them resolved — phrases like "melt the conflicts", "fix the merge conflicts", "resolve the rebase conflicts", "what's conflicting after the merge", "/melt", "fix the cherry-pick", or any prompt that surfaces `<<<<<<<` markers, `CONFLICT (...)` git output, or a half-finished merge state. First checks for squash-merge residue (rebase doomed by a squash-merged PR — abort and re-cherry-pick), then runs the structural-merge cascade — mergiraf (AST-aware auto-resolve) → git rerere (replay remembered fixes) → kdiff3 (manual fallback) — with helper scripts for batch resolution, ours/theirs picks, and lockfile regeneration. Use even when only one file is conflicting if the user wants the structural pass attempted before manual editing. Do NOT use for general git operations without conflicts. After `/cook` or `/cure` if a merge step blocked them; before retrying the gate that surfaced the conflict.
license: MIT
---

# /melt

Use this skill to resolve git merge, rebase, or cherry-pick conflicts using the structural cascade: **mergiraf → rerere → kdiff3**. Each tool handles what the previous could not.

Do not use it for general git operations without conflicts (those go to a `commit` or `gh` skill) or when no conflict markers are present.

## File IO delegation

`melt` orchestrates the resolution chain via bash and the helper scripts. For per-file inspection or manual edits, delegate to the cheez-* skills:

- **`/cheez-search`** — locate conflict markers or related symbols across the tree.
- **`/cheez-read`** — inspect conflicted files, view conflict hunks, list directory contents.
- **`/cheez-write`** — apply hash-anchored resolutions when bash flows are not enough.

The bash-driven flows below cover the bulk of resolution. Drop into the cheez-* skills only when you need to inspect or rewrite a specific file by hand.

## Resolution chain

| Stage | Tool | What it does | When it runs |
| --- | --- | --- | --- |
| 1 | `mergiraf` | Tree-sitter structural merge of base / ours / theirs. Independent additions merge cleanly even when text merge would conflict. Falls back to text merge on parse failure. | Automatically as a git merge driver, or via `batch-resolve.py`. |
| 2 | `git rerere` | Replays a previously recorded human resolution for the same conflict signature. | After mergiraf, especially during long rebases where conflicts recur. |
| 3 | `kdiff3` | Manual 3-way diff for what mergiraf and rerere could not resolve. | Launched via `git mergetool`. |

## Protocol

### 0. Squash-residue check

Run this before the conflict summary. If the branch was squash-merged into base, mergiraf cannot help — the right answer is to abort and re-cherry-pick the unique commits.

```bash
python3 skills/melt/scripts/detect-squash-residue.py
```

If the verdict is `SQUASH-MERGED`, surface the printed remedy to the user verbatim and stop the cascade. The remedy is destructive (`git reset --hard`) and must be copy-pasted by the user, not auto-applied. Flags:

- `--base` — base ref to compare against (default: `origin/main`).
- `--branch` — branch to check (default: current).
- `--json` — structured output for scripting.

Verdict semantics:

- `SQUASH-MERGED` (via `gh-api`) — PR found; cherry-pick list is exact.
- `SQUASH-MERGED` (via `local-synth`) — detected offline; cherry-pick list must be reviewed by hand.
- `not-detected` — proceed to the cascade.
- `not-applicable` — on the base branch.

### 1. Diagnose

Run the summary script next; it replaces ad-hoc `grep -n '<<<<<<<'` parsers and is shaped for low-token output.

```bash
python3 skills/melt/scripts/conflict-summary.py
```

Default output is terse: one metadata line per file plus minimally framed hunks. Flags:

- `--json` — structured output for scripting.
- `--verbose` — markdown view for humans.
- `--context N` — context lines around each hunk (default 3).

For raw git context:

```bash
git log --merge --oneline    # commits involved in the merge
git status                    # conflict / staging state
```

### 2. Structural resolution

For every file mergiraf supports, attempt structural merge:

```bash
# Preview (dry-run is the default)
python3 skills/melt/scripts/batch-resolve.py

# Apply clean resolutions and stage them
python3 skills/melt/scripts/batch-resolve.py --apply

# Markdown output and mergiraf debug logs
python3 skills/melt/scripts/batch-resolve.py --verbose
```

To inspect what mergiraf would produce for a single file without touching the working copy, use `--debug`:

```bash
python3 skills/melt/scripts/batch-resolve.py --debug <path>
```

The script extracts the three stages, runs mergiraf with `RUST_LOG=mergiraf=debug`, keeps the tempdir, and prints paths to the merged output, the log, and the conflict-marker count. Inspect with `cat`/`diff` against the printed paths. If the merged output is clean, apply it:

```bash
cp <merged_path> <path>
git add <path>
```

### 3. Remaining conflicts

After the structural pass, check rerere first:

```bash
git rerere status      # files with recorded resolutions
git rerere diff        # show what rerere would apply
```

If rerere already applied, the conflict is resolved. Otherwise drop into the manual tool:

```bash
git mergetool          # opens kdiff3 for each conflicted file
git mergetool <path>   # or just one file
```

After manual resolution, finish the interrupted operation:

```bash
git add <resolved-files>
git merge --continue        # or
git rebase --continue       # or
git cherry-pick --continue
```

### 4. Pick ours / theirs (mergiraf-unsupported files)

For shell, SQL, YAML, JSON, and other formats mergiraf does not parse, use `conflict-pick.py`:

```bash
# Take ours for every hunk
python3 skills/melt/scripts/conflict-pick.py hooks/session-start.sh --ours

# Take theirs for every hunk
python3 skills/melt/scripts/conflict-pick.py .gitignore --theirs

# Match by regex; matched hunks resolve, others remain
python3 skills/melt/scripts/conflict-pick.py config.yaml --grep "timeout" --ours
```

### 5. Lockfiles

Lockfile content has structure that text or AST merge cannot validate. Take one side and regenerate from the manifest:

```bash
# Auto-detect conflicted lockfiles, take theirs, regenerate, stage
python3 skills/melt/scripts/lockfile-resolve.py

# Preview
python3 skills/melt/scripts/lockfile-resolve.py --dry-run

# Take ours instead
python3 skills/melt/scripts/lockfile-resolve.py --strategy ours
```

Supports `Cargo.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `uv.lock`, `Gemfile.lock`, and `go.sum`.

### 6. Debug mergiraf

When mergiraf is not resolving something it should, use `--debug` for a single-file inspection (keeps the tempdir, captures `RUST_LOG=mergiraf=debug`):

```bash
python3 skills/melt/scripts/batch-resolve.py --debug <path>

mergiraf languages | grep <extension>   # is the type registered?
git check-attr merge -- <path>          # should show: merge: mergiraf
```

Common causes:

- Extension missing from `~/.gitattributes` — regenerate after upgrade.
- Parse failure on one of the three versions — mergiraf falls back silently.
- Very large files (>1MB) skip structural merge.

### 7. Maintenance

```bash
mergiraf languages --gitattributes > ~/.gitattributes   # after upgrade

git rerere status              # what is currently tracked
git rerere diff                # pending resolution diffs
git rerere forget <path>       # forget a bad resolution
git rerere gc                  # clean old entries
ls .git/rr-cache/              # browse the resolution database
```

## Scripts

| Script | Purpose | When |
| --- | --- | --- |
| `detect-squash-residue.py` | Detect that the branch was squash-merged and emit the abort+cherry-pick remedy | **Run first** — short-circuits the cascade |
| `conflict-summary.py` | Structured summary with line numbers and context | After residue check |
| `batch-resolve.py` | Run `mergiraf merge` over every conflicted file | Supported languages |
| `conflict-pick.py` | Choose ours / theirs per hunk | Shell, SQL, formats mergiraf does not parse |
| `lockfile-resolve.py` | Take one side and regenerate the lockfile | `Cargo.lock`, `package-lock.json`, etc. |

## Special cases

### Whitespace-only formatting changes

If one branch ran a formatter while the other modified content, mergiraf can produce more conflicts because AST positions shifted. Resolution: run the formatter on the merged result after resolving conflicts.

### Unrecoverable state

If conflict state is unrecoverable, abort and start over:

```bash
git merge --abort        # or
git rebase --abort       # or
git cherry-pick --abort
```

`/melt` surfaces abort as an option; the user decides.

## What this skill does NOT do

- Push or open PRs — hand off to a `gh` skill.
- Run builds or tests — re-enter `/cook` or run project gates.
- Commit resolved files outside `git add` staging — use a `commit` skill.
- Architectural review of merge results — use `/age`.
- Read, edit, or search files directly — delegate to `/cheez-read`, `/cheez-write`, `/cheez-search`.

## Gotchas

- `mergiraf solve` flag confusion: use `--stdout` / `-p` for preview, NOT `--output`.
- Markdown is supported by mergiraf but may need `.gitattributes` registration.
- Lockfile structural merge is not the same as a valid lockfile — always regenerate after taking a side.
- zdiff3 base markers (`|||||||`) are handled by every script in this skill.
- If you see conflicts in a supported file type, mergiraf-as-driver already ran — you are looking at the residue.

## Handoff

After resolution finishes, prompt the next step via `AskUserQuestion`. Default options:

- **Resume** — `git merge --continue` / `git rebase --continue` / `git cherry-pick --continue`, then return to whatever skill triggered the merge (`/cook`, `/cure`, etc.).
- **Re-run gates** — re-enter the upstream skill so its quality gates run on the merged state.
- **Stop** — leave the working tree staged for the user to inspect.

`/melt` never auto-resumes. The user picks.

## Rules

- Always run `detect-squash-residue.py` first; if positive, surface the remedy and stop the cascade.
- Always run `conflict-summary.py` before deciding the cascade order.
- Prefer structural resolution over manual edits when mergiraf supports the file type.
- Never weaken or hand-edit a lockfile in place — regenerate from the manifest.
- Surface unresolved files explicitly; do not claim a clean tree until `git status` agrees.
- Never auto-apply the squash-residue remedy — it is destructive (`git reset --hard`); the user copy-pastes it.
