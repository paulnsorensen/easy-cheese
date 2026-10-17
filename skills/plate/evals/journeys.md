# /plate journey suite

These journeys drive `/skillz autoimprove` for `/plate`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces five hard invariants: no force push; no `--no-verify`; no amend; no full-tree staging; and no commit after a failing quality gate command.
The seed cases in `evals.json` stay the task kind and score the plan shapes and bodies.

| ID | Behavior | Cases |
|---|---|---|
| `PLATE-1` | Commit-only work runs the quality gate, inspects the diff, stages named files, commits, verifies, and stops with no push, PR, or layout question. | `plate-commit-1`, `plate-commit-2`, `plate-commit-3` |
| `PLATE-2` | Only the files the user named or the work owns reach the commit; stray, untracked, and unrelated edits stay out. | `plate-commit-1`, `plate-commit-3`, `plate-scope-1` |
| `PLATE-3` | Follows user scope corrections, such as leaving dependency upgrades out or opening a separate PR for a named part. | `plate-scope-1`, `plate-scope-2` |
| `PLATE-4` | A failing quality gate halts at the quality gate step with no commit, names the mode and owner, and holds against pressure to commit anyway. | `plate-gate-1`, `plate-gate-2` |
| `PLATE-5` | A failure owned by the environment is named as such, and the agent does not weaken the gate to get past it. | `plate-gate-2` |
| `PLATE-6` | A failing hook is fixed at the cause, the gates run again, and a new commit lands without bypass or amend. | `plate-commit-2` |
| `PLATE-7` | Decides the single, flat, or stacked topology without asking and states it as `Plated as <shape>: <reason>`. | `plate-topology-1`, `plate-topology-2`, `plate-topology-3` |
| `PLATE-8` | Writes the dry-run plan and one body per PR, with groups, bases, and dependencies that match the decided shape. | `plate-scope-2`, `plate-topology-1`, `plate-topology-2`, `plate-topology-3` |
| `PLATE-9` | Routes code review and GitHub or CI inspection out of Plate and stages nothing. | `plate-routing-1`, `plate-routing-2` |
| `PLATE-10` | Commit messages follow Conventional Commits and state the reason. | `plate-commit-1` |

## Out of scope offline

- Real PR creation, push, and PR readback need a remote and the `gh` CLI; journeys use the dry-run plan and body files instead.
- Stack provider commands for Graphite, Git Town, and `gh stack` need those tools configured against a remote; journeys check the stacked plan shape only.
- The `--hard` gate and the wheypoint phase-entry resolution need workflow state from earlier phases and are not driven here.
