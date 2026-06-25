---
name: melt
description: Resolve git merge, rebase, or cherry-pick conflicts via a structural-merge cascade — mergiraf (AST-aware auto-resolve) → git rerere (replay remembered fixes) → kdiff3 (manual fallback). Use when conflicts exist and the user wants them resolved — phrases like "melt the conflicts", "fix the merge conflicts", "resolve the rebase conflicts", "what's conflicting after the merge", "/melt", "fix the cherry-pick", or any prompt that surfaces `<<<<<<<` markers, `CONFLICT (...)` git output, or a half-finished merge state. First checks for squash-merge residue (rebase doomed by a squash-merged PR — abort and re-cherry-pick), then runs the cascade with helper scripts for batch resolution, ours/theirs picks, and lockfile regeneration. Use even when only one file is conflicting if the user wants the structural pass attempted before manual editing. Do NOT use for general git operations without conflicts. After `/cook` or `/cure` if a merge step blocked them; before retrying the gate that surfaced the conflict.
license: MIT
---

# /melt

Use this skill to resolve git merge, rebase, or cherry-pick conflicts using the structural cascade: **mergiraf → rerere → kdiff3**. Each tool handles what the previous could not.

## File IO delegation

`melt` orchestrates the resolution chain via bash and the helper scripts. For per-file inspection or manual edits, delegate to the `cheez-*` skills:

- **`/cheez-search`** — locate conflict markers or related symbols across the tree.
- **`/cheez-read`** — inspect conflicted files, view conflict hunks, list directory contents.
- **`/cheez-write`** — apply hash-anchored resolutions when bash flows are not enough.

The bash-driven flows below cover the bulk of resolution. Drop into the `cheez-*` skills only when you need to inspect or rewrite a specific file by hand.

## Cascade

| Stage | Tool | What it does | When it runs |
| --- | --- | --- | --- |
| 1 | `mergiraf` | Tree-sitter structural merge of base / ours / theirs. Independent additions merge cleanly even when text merge would conflict. Falls back to text merge on parse failure. | Automatically as a git merge driver, or via `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve`. |
| 2 | `git rerere` | Replays a previously recorded human resolution for the same conflict signature. | After mergiraf, especially during long rebases where conflicts recur. |
| 3 | `kdiff3` | Manual 3-way diff for what mergiraf and rerere could not resolve. | Launched via `git mergetool`. |

## Protocol

### 0. Squash-residue check

Run this before the conflict summary. If the branch was squash-merged into base, mergiraf cannot help — the right answer is to either merge base in (non-destructive) or abort and re-cherry-pick the unique commits (destructive).

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz detect-squash-residue
```

If the verdict is `SQUASH-MERGED`, surface both printed remedies to the user verbatim and stop the cascade. Neither remedy is auto-applied — the user picks one and copy-pastes. Flags:

- `--base` — base ref to compare against (default: `origin/main`).
- `--branch` — branch to check (default: current).
- `--json` — structured output for scripting.

Detection cascade (strongest first; later signals run only when needed):

- `tree-match` — walks commits on base looking for one whose tree equals the tree at some point on the branch. That commit is a squash-equivalent of branch commits up to that point. Works offline, through fork PRs and renames, and handles branches with commits past the squash (the case `local-synth` misses). Always runs first.
- `gh-api` — runs in parallel with tree-match. Enriches a tree-match verdict with PR metadata (number, URL, merge commit) when its SHAs correlate with the squash; supplies the verdict on its own when tree-match found nothing.
- `local-synth` — synthesizes a would-be squash commit from HEAD's tree and asks `git cherry` whether base contains an equivalent. Last-resort fallback that only runs when neither tree-match nor gh-api produced a verdict; cannot enumerate squashed vs unique commits.

Verdict semantics:

- `SQUASH-MERGED` (`method=tree-match` or `tree-match+gh`) — strongest signal; unique-commit list is the slice of branch commits after the matched squash point.
- `SQUASH-MERGED` (`method=gh-api`) — fallback when tree-match found nothing but the gh PR's SHAs overlap with branch commits.
- `SQUASH-MERGED` (`method=local-synth`) — detected offline only; cherry-pick list must be reviewed by hand.
- `not-detected` — proceed to the cascade.
- `not-applicable` — on the base branch.

The detector prints two remedies in order:

- **[A] merge** (non-destructive) — `git merge <base>`. Preserves all branch history; squashed commits collapse to a no-op merge, so only real conflicts surface. Prefer this when the branch has unique work or the unique-commit list is uncertain.
- **[B] reset-and-cherry-pick** (destructive) — `git reset --hard <base>` + `git cherry-pick <unique-shas>`. Rewrites the branch and requires force-push. Use when a clean linear history is wanted and the unique-commit list looks complete.

Default to suggesting [A] first; only suggest [B] when the user has stated a preference for a linear-history workflow or the unique-commit count is small and verified.

### 1. Diagnose

Run the summary script next; it replaces ad-hoc `grep -n '<<<<<<<'` parsers and is shaped for low-token output.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-summary
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
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve

# Apply clean resolutions and stage them
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve --apply

# Markdown output and mergiraf debug logs
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve --verbose
```

To inspect what mergiraf would produce for a single file without touching the working copy, use `--debug`:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve --debug <path>
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

Done = `git status` shows no `Unmerged paths` AND zero `<<<<<<<` markers remain.

For ours/theirs picks, lockfiles, mergiraf debugging, and maintenance, see [references/cascade-stages.md](references/cascade-stages.md).

## Scripts

| Script | Purpose | When |
| --- | --- | --- |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz detect-squash-residue` | Detect that the branch was squash-merged and emit both the merge and reset+cherry-pick remedies | **Run first** — short-circuits the cascade |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-summary` | Structured summary with line numbers and context | After residue check |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz batch-resolve` | Run `mergiraf merge` over every conflicted file | Supported languages |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-pick` | Choose ours / theirs per hunk | Shell, SQL, formats mergiraf does not parse |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz lockfile-resolve` | Take one side and regenerate the lockfile | `Cargo.lock`, `package-lock.json`, etc. |

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

After resolution finishes, prompt the next step via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Include the detected interrupted operation and upstream invocation in the context packet before asking. Default options:

- **Resume** — dispatch the exact continuation command for the current operation (`git merge --continue`, `git rebase --continue`, or `git cherry-pick --continue`). If the triggering skill invocation is known, return to that skill with the original context after the git operation succeeds; otherwise stop with the resumed git status.
- **Re-run gates** — dispatch the upstream skill invocation that originally surfaced the conflict so its quality gates run on the merged state.
- **Stop** — dispatch none; leave the working tree staged for the user to inspect.

`/melt` never resumes before the user selects. After a non-stop selection, run the selected continuation immediately.

## Rules

- Always run `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz detect-squash-residue` first; if positive, surface both remedies and stop the cascade.
- Always run `python3 ${CLAUDE_SKILL_DIR}/scripts/melt.pyz conflict-summary` before deciding the cascade order.
- Prefer structural resolution over manual edits when mergiraf supports the file type.
- Never weaken or hand-edit a lockfile in place — regenerate from the manifest.
- Flag unresolved files explicitly; do not claim a clean tree until `git status` agrees.
- Never auto-apply a squash-residue remedy — even the non-destructive merge path rewrites working state; the user copy-pastes their choice.
- Lead with the merge remedy unless the user has asked for a linear-history workflow; reset+cherry-pick rewrites the branch and requires force-push.
