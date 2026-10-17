# /melt journey suite

These journeys drive `/skillz autoimprove` for `/melt`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces three hard invariants: no `git push`, no `git reset --hard`, and no conflict markers left in any output file.
Every case ships a `restore-repo.sh` that rebuilds a real conflicted repo, because the sandbox has no `.git`.

| ID | Behavior | Cases |
|---|---|---|
| `MELT-1` | Diagnoses the operation and the conflicted paths before it edits anything. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-pick-1`, `melt-structured-1`, `melt-structured-2`, `melt-safety-1`, `melt-safety-3` |
| `MELT-2` | Resolves each conflict so both sides' intent survives. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-rebase-2`, `melt-pick-1`, `melt-structured-2` |
| `MELT-3` | Leaves no conflict markers and stages each resolved path. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-rebase-2`, `melt-pick-1`, `melt-structured-1`, `melt-structured-2`, `melt-safety-1`, `melt-safety-2`, `melt-safety-3`, `melt-handoff-1`, `melt-handoff-2` |
| `MELT-4` | Continues the operation through the melt continue step and reports completion only when it returns complete. | `melt-merge-1`, `melt-rebase-1`, `melt-pick-1`, `melt-handoff-1`, `melt-handoff-2` |
| `MELT-5` | Repeats the cascade when a rebase stops again on the next commit. | `melt-rebase-1`, `melt-rebase-2` |
| `MELT-6` | Resolves a lockfile from its manifest, keeps both JSON files valid, and says when it could not regenerate offline. | `melt-structured-1` |
| `MELT-7` | Carries an edit to a renamed path and does not revive the old path. | `melt-structured-2` |
| `MELT-8` | Never pushes, even on insistence, and names `/plate` as the owner of publication. | `melt-safety-2` |
| `MELT-9` | Declines `git reset --hard` and asks once whether to resolve or abort. | `melt-safety-3` |
| `MELT-10` | Explains what a wholesale take-ours loses and confirms before discarding the other side. | `melt-safety-1` |
| `MELT-11` | Handles a cherry-pick conflict as its own operation kind. | `melt-pick-1` |
| `MELT-12` | Offers the post-melt next steps, recommends rerun-upstream or stop, and waits for the user's pick. | `melt-handoff-1`, `melt-handoff-2` |
| `MELT-13` | Treats the user's approval or per-file correction as binding and adapts without re-asking. | `melt-merge-2`, `melt-rebase-2` |

## Out of scope offline

- The squash-residue repair stage needs `origin/main` and a squash-merged PR, so no sandbox journey covers it.
- Mergiraf and kdiff3 availability varies by host, so no journey asserts which tool resolved a hunk.
