---
name: melt
description: >-
  Resolve content conflicts during Git merge, rebase, cherry-pick, pull, or branch integration.
  Use for CONFLICT, unmerged paths, or Git's "needs merge" diagnostic for an unmerged path.
  Trigger on fix merge conflicts, resolve rebase conflicts, cherry-pick conflict, and similar requests.
  Do not use for clean Git operations or review-only questions.
license: MIT
---

# /melt

Resolve the current conflict without rewriting a published branch.
Use the safe cascade: squash repair → summary → mergiraf → rerere → manual resolution → continuation.
Keep the original branch for recovery. Never push, reset, or force-push here.

Use the selected source-code backend for searches, bounded reads, and manual edits.
Follow [code-intelligence routing](../cheese/references/code-intelligence-routing.md): search, fresh read, stale-safe write.

## 1. Repair squash residue

Run this before resolving file conflicts:

```bash
python3 skills/melt/scripts/melt.pyz detect-squash-residue --apply
```

Use `--base <ref>` when the base is not `origin/main`.
Use `--branch <name>` when Git cannot identify the original branch.
The command previews by default without `--apply`.
It creates `<original-branch>-clean` and replays verified commits in order when safe.
Otherwise it merges the base into the original branch.
It preflights branch collisions before aborting an interrupted operation.
It never pushes or rewrites either branch.

If `application.state` is `confirmation-required`, keep the active operation intact.
Ask once whether to discard its staged resolution and abort it.
After explicit confirmation, rerun with `--apply --abort-operation`.
If confirmation is refused, continue the existing operation instead.
If `application.state` is `failed`, report `failed_step`, `error`, and `recovery_branch`; stop.
If it is `needs-resolution`, continue the cascade.
If it is `applied` without conflicts, check the operation state and proceed to handoff.
If it is `not-applied`, continue the existing conflict.

## 2. Diagnose and inspect

```bash
python3 skills/melt/scripts/melt.pyz conflict-summary
python3 skills/melt/scripts/melt.pyz operation
```

Read each summary hunk and the operation's `unmerged_paths` and `conflict_marker_files`.
Use `git log --merge --oneline` only when commit intent is unclear.
Do not accept a structural merge only because it has no markers.

## 3. Resolve structures

Preview mergiraf, then inspect its semantic result before applying it:

```bash
python3 skills/melt/scripts/melt.pyz batch-resolve
python3 skills/melt/scripts/melt.pyz batch-resolve --debug <path>
```

The debug command gives the merged output path, log path, and marker count.
Read that output with the selected backend. Confirm that both sides' intended edits remain.
Then apply clean resolutions and stage them:

```bash
python3 skills/melt/scripts/melt.pyz batch-resolve --apply
```

Melt text tools refuse binary files. Select a side for ordinary binaries and stage it.
For generated archives, resolve source files and rebuild the archive instead.

## 4. Resolve what remains

Run `operation` again. Its `rerere_enabled`, `configured_merge_tool`, and
`selected_manual_tool` fields define the available fallback.
When rerere is enabled, inspect `git rerere status` and `git rerere diff`.
If it is disabled, report the setting and skip that stage.
Do not change global Git configuration during this invocation.

For unresolved text, use the selected manual tool or edit after semantic inspection.
Prefer `git mergetool --tool=kdiff3 <path>` when `selected_manual_tool` is `kdiff3`.
Otherwise use the configured tool and report the substitution.
Stage each resolved path. Resolve lockfiles from their manifests, not their conflict text.

Read [conditional cascade stages](references/cascade-stages.md) only when selecting sides,
regenerating lockfiles, debugging mergiraf, or maintaining rerere data.
Its side-selection and lockfile commands require a judgment about intended content.

## 5. Continue once

```bash
python3 skills/melt/scripts/melt.pyz operation
python3 skills/melt/scripts/melt.pyz operation --continue
```

Run `--continue` only when status is `ready`.
It refuses unmerged paths and conflict markers, then continues without an interactive editor.
If it returns `blocked`, resolve the next conflict and repeat steps 2–5.
If it returns `failure`, report `failed_step` and stop.
Handoff only when status is `complete`.
Do not run a separate raw Git continuation command.

## Handoff

After completion, use the [shared handoff gate](../cheese/references/handoff-gate.md).
Fill the placeholders from the upstream invocation and propagated flags.

```yaml
handoff_gate:
  source_skill: /melt
  id: post-melt-next-step
  prompt: The Git operation is complete. What should happen next?
  recommended: rerun-upstream
  multi: false
  options:
    - id: rerun-upstream
      label: Re-run the upstream gate
      description: Run the invocation that found the conflict.
      dispatch: <upstream_invocation>
      context:
        upstream_invocation: <command>
        flags: [<propagated flags>]
    - id: plate-it
      label: Plate it
      description: Publish completed work through /plate.
      dispatch: /plate
      context:
        flags: [<propagated --hard, --open-pr>]
    - id: checkpoint-and-stop
      label: Checkpoint & stop
      description: Write a durable checkpoint, then pause the pipeline.
      dispatch: /wheypoint
    - id: stop
      label: Stop
      description: Leave the completed operation for inspection.
      dispatch: none
```

Omit `rerun-upstream` and recommend `stop` when its invocation is unknown.
Wait for the user's selection. Run a selected non-stop action immediately.
Melt never commits or pushes. `/plate` owns publication.

See the [generated command inventory](references/commands.md) for all Melt commands.
