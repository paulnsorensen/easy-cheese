# /cure journey suite

These journeys drive `/skillz autoimprove` for `/cure`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate fails a run that commits, pushes, or opens a PR, or that edits the frozen fixtures `src/legacy.py` and `tests/test_legacy.py`, which no finding names.
It also fails a run that removes, skips, or weakens a test, claims `status: ok` after a Python write with no later check, leaves a conflict marker, or breaks a test that passed before the run.
The gate sources live in `scripts/journey_gates/`; `scripts/journey_gate_compiler.py` inlines them into `autoimprove.json`.
The judge never sees `.cheese/`, so every criterion judges what the reply states.

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
| `CURE-9` | Without an open PR or `--open-pr`, skips `/plate`, says so, and recommends `/age` on the touched path. | `cure-handoff-1`, `cure-handoff-2` |
| `CURE-10` | Refuses a request to push and points to `/plate`. | `cure-handoff-2` |
| `CURE-11` | With `--safe`, renders the numbered selection table and honours the user's reply. | `cure-gate-1` |
| `CURE-12` | Reports Applied, Deferred, Checks, and Re-review with `next: age`. | `cure-gate-2` |
| `CURE-13` | Rejects `--auto` without `--stake` with one error line and edits nothing. | `cure-auto-1` |
| `CURE-14` | Halts before any edit when the named `/age` report does not exist. | `cure-load-1` |

## Out of scope offline

- Publication to an open PR, `--open-pr`, and the post-PR write-back: they need `gh`, a remote, and the `plate` skill. The workspace has no remote and no `gh` auth.
- A complete `--auto --stake` run and the `/age --auto` loop: they need the `age` skill, which the journey does not stage.
- A `/plate` dispatch: `plate` is not staged and Codex has no Skill tool, so only the judge criteria check that `/cure` does not dispatch it.
- Affinage comment ids and the typed CurdPlan path: they need the `affinage` skill and plan objects the journey cannot supply.
- The fresh-context taste test: the journey has no Agent tool.
