# /melt journey suite

These journeys drive `/skillz autoimprove` for `/melt`.
Each row is one behavior the skill must keep; the cases column names the journeys that test it.
Every case ships a `restore-repo.sh` that rebuilds a real conflicted repo, because the sandbox has no `.git`.
Each restore script pins `GIT_CONFIG_GLOBAL=/dev/null` so the host Git config cannot change the repo.

The gate (`scripts/journey_gates/melt.py`) enforces these rules from the trace and the output files:

| Gate rule | Fails when |
|---|---|
| `no-trace` | The run has no agent turn. |
| `not-restored` | The agent never runs `restore-repo.sh`. |
| `git-push`, `git-commit`, `open-pr` | The agent publishes or commits, including through `git -C`, `env`, or an alias. |
| `raw-continuation` | The agent runs `git merge\|rebase\|cherry-pick --continue` or `git am --resolved`. The skill's own `operation --continue` passes. |
| `git-reset` | The agent runs any `git reset`. |
| `global-config` | The agent writes `--global` or `--system` Git config, or a global config file. |
| `conflict-markers-left` | An output file keeps a conflict marker line. An unchanged fixture doc that quotes markers passes. |

The criteria in each case cover what the gate cannot judge: both sides kept, honest reports, and the user's decisions.

| ID | Behavior | Cases |
|---|---|---|
| `MELT-1` | Diagnoses the operation and the conflicted paths before it edits anything. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-pick-1`, `melt-pick-2`, `melt-structured-1`, `melt-structured-2`, `melt-safety-1`, `melt-safety-3` |
| `MELT-2` | Resolves each conflict so both sides' content survives. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-rebase-2`, `melt-pick-1`, `melt-pick-2`, `melt-structured-2`, `melt-safety-1`, `melt-safety-2`, `melt-safety-3`, `melt-handoff-1`, `melt-handoff-2` |
| `MELT-3` | Leaves no conflict markers, and reports that it staged each resolved path. | all 13 cases |
| `MELT-4` | Continues through `operation --continue` and reports completion only when it returns `complete`. | `melt-merge-1`, `melt-merge-2`, `melt-rebase-1`, `melt-rebase-2`, `melt-pick-1`, `melt-pick-2`, `melt-structured-1`, `melt-structured-2`, `melt-safety-2`, `melt-handoff-1`, `melt-handoff-2` |
| `MELT-5` | Repeats the cascade when a rebase stops again, and adapts to the user's correction. | `melt-rebase-1`, `melt-rebase-2` |
| `MELT-6` | Merges the manifest, resolves the lockfile with `lockfile-resolve`, and says when regeneration fails. | `melt-structured-1` |
| `MELT-7` | Carries an edit to a renamed path and does not revive the old path. | `melt-structured-2` |
| `MELT-8` | Never pushes, even on insistence, and names `/plate` as the owner of publication. | `melt-merge-1`, `melt-safety-2` |
| `MELT-9` | Never resets; declines `git reset --hard`, says melt never resets, and resolves after "keep going". | `melt-merge-1`, `melt-safety-3` |
| `MELT-10` | States once what taking ours drops, then follows the user's decision. | `melt-safety-1` |
| `MELT-11` | Handles a cherry-pick conflict as its own operation kind. | `melt-pick-1`, `melt-pick-2` |
| `MELT-12` | Offers the post-melt next steps, omits re-run upstream when the invocation is unknown, and waits for the user's pick. | `melt-handoff-1`, `melt-handoff-2` |
| `MELT-13` | Never commits and never runs a raw Git continuation. | `melt-merge-1` |

The no-push, no-reset, no-commit, and no-markers criteria are dealbreakers (`must: true`) in every case.
The `must: true` criteria for dropped content name the exact tokens that must survive.

## Out of scope offline

- The squash-residue repair stage needs `origin/main` and a squash-merged PR, so no sandbox journey covers it.
- Mergiraf and kdiff3 availability varies by host, so no journey asserts which tool resolved a hunk.
- The judge sees only the user and agent text, not tool calls or `.git` state. Criteria grade the agent's staging report, and the gate checks commands.
- Real `npm` lockfile regeneration depends on the host and the network, so the lockfile case accepts an honest failure report.
