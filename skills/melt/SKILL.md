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
| 2 | `git rerere` | Reuses a recorded human resolution for the same conflict signature. | Run it after mergiraf when `rerere.enabled` is `true`. |
| 3 | `kdiff3` | Provides a manual three-way diff for unresolved conflicts. | Start it with `git mergetool --tool=kdiff3`. |

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

Run this preflight first.
It reports whether the host enables each remaining stage.

```bash
git config --get rerere.enabled
git config --get merge.tool
```

Git records and replays a resolution only when `rerere.enabled` is `true`.
Report the absent setting to the user and name the fix: `git config --global rerere.enabled true`.
Then skip the rerere stage for this invocation.

Check rerere when the host enables it.

```bash
git rerere status
git rerere diff
```

If rerere applied a resolution, treat the conflict as resolved.
Otherwise, name the manual tool explicitly.
The explicit flag makes the stage independent of the host `merge.tool` value.

```bash
git mergetool --tool=kdiff3
git mergetool --tool=kdiff3 <path>
```

Drop the flag when kdiff3 is absent from the host.
Git then starts the tool that `merge.tool` names.
Report the substitution to the user.

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

- Do not push or open a PR directly. The `plate-it` gate option hands publication to `/plate`.
- Do not run builds or tests. Return to `/cook` or run the project gates.
- Do not commit resolved files. Stage them, then hand the commit to `/plate`.
- Do not review the merge architecture. Use `/age`.

## Gotchas

- Use `--stdout` or `-p` to preview `mergiraf solve`. Do not use `--output`.
- Mergiraf supports Markdown, but the repository can require a `.gitattributes` entry.
- A structural lockfile merge does not prove that the lockfile is valid.
  Regenerate each lockfile after you select one side.
- `conflict-pick` and `conflict-summary` handle zdiff3 base markers that start with `|||||||`.
  `detect-squash-residue` reads no conflict markers.
  `lockfile-resolve` reads the index stages.
- Mergiraf already ran as a driver when a supported file still has conflicts.

## Handoff

After resolution, build one structured gate record.
Follow the shared contract in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
Fill each placeholder from the current Git state before you render the gate.

```yaml
handoff_gate:
  source_skill: /melt
  id: post-melt-next-step
  prompt: The conflicts are resolved. What should happen next?
  recommended: resume-operation
  multi: false
  options:
    - id: resume-operation
      label: Resume the Git operation
      description: Run the continuation command, then return to the upstream skill.
      continue: run-continuation-then-return
      context:
        operation: <merge|rebase|cherry-pick>
        continuation: git <operation> --continue
        upstream_invocation: <command|none>
    - id: rerun-upstream
      label: Re-run the upstream gate
      description: Run the upstream skill invocation that found the conflict.
      dispatch: <upstream_invocation>
      context:
        upstream_invocation: <command>
        flags: [<propagated flags>]
    - id: plate-it
      label: Plate it
      description: Finish the Git operation, then publish through /plate.
      dispatch: /plate
      context:
        operation: <merge|rebase|cherry-pick>
        continuation: git <operation> --continue
        flags: [<propagated --hard, --open-pr>]
    - id: checkpoint-and-stop
      label: Checkpoint & stop
      description: Write a durable checkpoint, then pause the pipeline.
      dispatch: /wheypoint
      context:
        operation: <merge|rebase|cherry-pick>
    - id: stop
      label: Stop
      description: Leave the resolved files staged for inspection.
      dispatch: none
      context:
        reason: leave the resolved files staged
```

Apply these rules to the gate:

- Omit `rerun-upstream` when the upstream invocation is unknown.
- Set `recommended` to `stop` when the upstream invocation is unknown.
- Propagate in-scope `--hard` and `--open-pr` to `plate-it`.
- Run the continuation command first for `plate-it`.
  Dispatch `/plate` only after `git status` reports no unmerged paths and no interrupted operation.
  Report the failure and stop when the continuation command fails.
- Do not commit or push in `/melt`. `/plate` owns every durable write.

`/melt` waits for the user selection.
After a non-stop selection, run the selected action immediately.
