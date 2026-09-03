---
name: melt
description: >-
  Resolve Git merge, rebase, or cherry-pick conflicts through a structural merge cascade.
  Run mergiraf first, Git rerere second, and kdiff3 last.
  Use this skill when conflicts exist or Git shows an incomplete operation.
  Trigger phrases include "melt the conflicts", "resolve the rebase conflicts", and "fix the cherry-pick".
  Do not use this skill for Git operations without conflicts.
  Use it after `/cook` or `/cure` when a merge step blocks progress.
license: MIT
---

# /melt

Use this skill to resolve Git conflicts with this cascade: **mergiraf → rerere → kdiff3**.
Each stage handles conflicts that remain after the prior stage.

## File IO routing

Use the selected source-code backend for conflict searches, bounded reads, and manual edits.
Follow the route in [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md).
Use this sequence for manual resolutions: search, fresh bounded read, stale-safe write.

## Cascade

| Stage | Tool | Purpose | Start condition |
| --- | --- | --- | --- |
| 1 | `mergiraf` | Merges syntax trees and preserves independent additions. It uses text merge after a parse failure. | Git starts it as a merge driver, or the user runs `batch-resolve`. |
| 2 | `git rerere` | Reuses a recorded human resolution for the same conflict signature. | Run it after mergiraf, especially during a rebase with repeated conflicts. |
| 3 | `kdiff3` | Provides a manual three-way diff for unresolved conflicts. | Start it with `git mergetool`. |

## Protocol

### 0. Check for squash residue

Run this check before the conflict summary.

```bash
python3 skills/melt/scripts/melt.pyz detect-squash-residue
```

If the verdict is `SQUASH-MERGED`, stop the cascade.
Show both printed remedies to the user without changes.
Do not apply either remedy automatically.
The user selects and copies one remedy.

Flags:

- `--base` — Sets the base ref. The default is `origin/main`.
- `--branch` — Sets the branch. The default is the current branch.
- `--json` — Produces structured output.

The detector checks these signals in order:

- `tree-match` — Searches base commits for a tree that matches a branch point.
  A match identifies the equivalent squash point.
  This check works offline and supports fork PRs, renames, and later branch commits.
- `gh-api` — Runs with `tree-match`.
  It adds the PR number, URL, and merge commit when its commit data matches.
  It can provide the verdict when `tree-match` finds no match.
- `local-synth` — Creates a possible squash commit from the `HEAD` tree.
  It uses `git cherry` to find an equivalent commit on the base.
  It runs only when the other signals provide no verdict.
  It cannot separate squashed commits from unique commits.

Verdicts:

- `SQUASH-MERGED` with `method=tree-match` or `tree-match+gh` — This is the strongest signal.
  The unique commit list contains branch commits after the squash point.
- `SQUASH-MERGED` with `method=gh-api` — The PR commit data overlaps with branch commits.
- `SQUASH-MERGED` with `method=local-synth` — The offline check found a match.
  Review the cherry-pick list manually.
- `not-detected` — Continue with the cascade.
- `not-applicable` — The current branch is the base branch.

The detector prints two remedies in this order:

- **[A] merge** — Run `git merge <base>`.
  This non-destructive remedy preserves branch history.
  Squashed commits become an empty merge, so only real conflicts remain.
  Prefer this remedy when the branch has unique work or the commit list is uncertain.
- **[B] reset-and-cherry-pick** — Run `git reset --hard <base>`, then run `git cherry-pick <unique-shas>`.
  This destructive remedy rewrites the branch and requires a force push.
  Use it when the user wants linear history and the unique commit list is complete.

Suggest remedy [A] first.
Suggest remedy [B] only when the user requests linear history or verifies a small commit list.

### 1. Diagnose

Run the summary command.

```bash
python3 skills/melt/scripts/melt.pyz conflict-summary
```

The default output contains one metadata line for each file and a small frame around each conflict.

Flags:

- `--json` — Produces structured output.
- `--verbose` — Produces a Markdown view.
- `--context N` — Sets the context line count. The default is `3`.

Use these commands for raw Git context:

```bash
git log --merge --oneline
git status
```

### 2. Resolve structures

Run a structural merge for each file type that mergiraf supports.

```bash
# Preview. Dry-run is the default.
python3 skills/melt/scripts/melt.pyz batch-resolve

# Apply clean resolutions and stage them.
python3 skills/melt/scripts/melt.pyz batch-resolve --apply

# Show Markdown output and mergiraf debug logs.
python3 skills/melt/scripts/melt.pyz batch-resolve --verbose
```

Use `--debug` to inspect one file without changes.

```bash
python3 skills/melt/scripts/melt.pyz batch-resolve --debug <path>
```

The command prints the merged output path, log path, and conflict marker count.
Inspect the merged output with the selected source-code backend.
Apply clean output with these commands.

```bash
cp <merged_path> <path>
git add <path>
```

### 3. Resolve remaining conflicts

Check rerere before you start the manual tool.

```bash
git rerere status
git rerere diff
```

If rerere applied a resolution, treat the conflict as resolved.
Otherwise, start the manual tool.

```bash
git mergetool
git mergetool <path>
```

Stage each manual resolution.
Then continue the interrupted operation.

```bash
git add <resolved-files>
git merge --continue
git rebase --continue
git cherry-pick --continue
```

Completion requires no `Unmerged paths` in `git status`.
Completion also requires no `<<<<<<<` markers.

For other procedures, see [references/cascade-stages.md](references/cascade-stages.md).
It covers side selection, lockfiles, mergiraf diagnostics, and maintenance.

## Scripts

See the generated command inventory in [`references/commands.md`](references/commands.md).

## Exclusions

- Do not push or open a PR. Hand the work to a `gh` skill.
- Do not run builds or tests. Return to `/cook` or run the project gates.
- Do not commit resolved files. Use a `commit` skill after staging.
- Do not review the merge architecture. Use `/age`.

## Gotchas

- Use `--stdout` or `-p` to preview `mergiraf solve`. Do not use `--output`.
- Mergiraf supports Markdown, but the repository can require a `.gitattributes` entry.
- A structural lockfile merge does not prove that the lockfile is valid.
  Regenerate each lockfile after you select one side.
- Each script handles zdiff3 base markers that start with `|||||||`.
- Mergiraf already ran as a driver when a supported file still has conflicts.

## Handoff

After resolution, use the shared gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
Add the interrupted operation and upstream invocation to the context packet.
Then ask the user to select one option:

- **Resume** — Run the exact continuation command for the current Git operation.
  Return to the upstream skill after the command succeeds.
  If the upstream invocation is unknown, stop after you report the Git status.
- **Re-run gates** — Run the upstream skill invocation that found the conflict.
- **Stop** — Run no command. Leave the working tree staged for inspection.

`/melt` waits for the user selection.
After a non-stop selection, run the selected command immediately.
