# /cook journey suite

These journeys drive `/skillz autoimprove` for `/cook`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that Cook never pushes or opens a PR, never removes or skips an existing test, writes no Python under a spec hold, and ships a test change with every changed Python source file.

| ID | Behavior | Cases |
|---|---|---|
| `COOK-1` | Prints a contract (behavior, non-goals, scope, gate, and a shape-check block or skip line) before any code. | `cook-tdd-1`, `cook-tdd-2`, `cook-scope-2` |
| `COOK-2` | Writes a failing test before the implementation for behavior work. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3` |
| `COOK-3` | Meets every acceptance criterion and shows the real gate output before it claims status ok. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3`, `cook-scope-1`, `cook-scope-2`, `cook-handoff-1` |
| `COOK-4` | Refuses a spec with `execution_holds` and writes no code, even when asked for a stub. | `cook-stop-1` |
| `COOK-5` | Shows a false premise before any code and does not bend the code to satisfy it literally. | `cook-stop-2` |
| `COOK-6` | Asks about a design decision the spec does not answer, then follows the answer. | `cook-stop-3` |
| `COOK-7` | Honors a user scope cut or a correction in the middle of the run. | `cook-scope-1`, `cook-scope-2` |
| `COOK-8` | Adds no scope beyond the accepted contract and lists adjacent issues as follow-ups. | `cook-scope-1`, `cook-prototype-1`, `cook-handoff-2` |
| `COOK-9` | In prototype mode, runs plan, spike, and check rounds, offers the menu, and waits for the user. | `cook-prototype-1`, `cook-prototype-2` |
| `COOK-10` | In prototype mode, discards only after an explicit yes, then restores the base and keeps the log. | `cook-prototype-2` |
| `COOK-11` | Writes the handoff report and routes behavior work to press and non-behavior work to age, with a stop option. | `cook-handoff-1`, `cook-handoff-2` |
| `COOK-12` | Never weakens an existing test and never publishes without permission. | `cook-tdd-1`, `cook-scope-1` |

## Out of scope offline

- The fan pathway (curds, waves, sub-agent coders) needs the `Agent` tool, which a journey does not grant.
- The `--auto` chain and `--open-pr` publication dispatch later phases and need `gh` and a remote.
- The prototype Stabilize route hands off to `/mold`, which the journey does not stage.
