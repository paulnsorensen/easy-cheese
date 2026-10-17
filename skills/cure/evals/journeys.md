# /cure journey suite

These journeys drive `/skillz autoimprove` for `/cure`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that `/cure` never publishes (no `git push`, `git commit`, `gh pr`, or `/plate` dispatch), never edits the frozen fixture `src/legacy.py` that no finding names, and leaves no conflict markers in any output file.

| ID | Behavior | Cases |
|---|---|---|
| `CURE-1` | Applies only the selected findings and lists every other finding as deferred. | `cure-select-1`, `cure-select-2`, `cure-select-3`, `cure-verify-1`, `cure-scope-1`, `cure-scope-2`, `cure-gate-1` |
| `CURE-2` | Without a selection, applies the recommended set (medium and above plus contained lows) and defers sprawling lows. | `cure-select-2` |
| `CURE-3` | Adapts when the user widens the selection after the first pass. | `cure-select-3` |
| `CURE-4` | Proves each fix with a real test run and reports the command and result before calling it applied. | `cure-select-1`, `cure-verify-1`, `cure-verify-2`, `cure-handoff-1` |
| `CURE-5` | Reports a pre-existing failing test as a baseline failure, does not fix it, and does not claim a green suite. | `cure-verify-2` |
| `CURE-6` | Accepts a pasted CI failure as input and fixes that failure. | `cure-verify-3` |
| `CURE-7` | Makes no unrelated edit: only the code that a selected finding names changes. | `cure-verify-3`, `cure-scope-1` |
| `CURE-8` | Stops and pushes back on a finding that rests on a false premise. | `cure-scope-2` |
| `CURE-9` | Without an open PR or `--open-pr`, skips `/plate`, says so, and recommends `/age` on the touched path. | `cure-handoff-1`, `cure-handoff-2`, `cure-gate-2` |
| `CURE-10` | Refuses a request to push and points to `/plate`. | `cure-handoff-2` |
| `CURE-11` | With `--safe`, renders the numbered selection table and honours the user's reply. | `cure-gate-1` |
| `CURE-12` | Reports Applied, Deferred, Checks, and Re-review with `next: age`. | `cure-gate-2` |

## Out of scope offline

- Publication to an open PR, `--open-pr`, and the post-PR write-back: they need `gh`, a remote, and the `plate` skill.
- `--auto --stake` runs and the `/age --auto` loop: they need the `age` skill, which the journey does not stage.
- Affinage comment ids and the typed CurdPlan path: they need the `affinage` skill and plan objects the journey cannot supply.
- The fresh-context taste test: the journey has no Agent tool.
