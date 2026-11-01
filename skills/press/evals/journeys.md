# /press journey suite

These journeys drive `/skillz autoimprove` for `/press`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that every changed or added code file is a test file, that no production fixture changes, that no existing test is removed or skipped, and that Press never pushes or opens a PR.

| ID | Behavior | Cases |
|---|---|---|
| `PRESS-1` | Reads the Cook handoff and attacks the contract with new tests only. | `press-finding-1`, `press-finding-2`, `press-green-1` |
| `PRESS-2` | Backs every classification with a real test run and names the evidence, not a guess. | `press-finding-1`, `press-finding-2`, `press-finding-3`, `press-green-1` |
| `PRESS-3` | Reports a finding with its failing test and routes it to Cook as a correction (`ok-with-concerns`, next cook). | `press-finding-1`, `press-finding-2`, `press-flags-2`, `press-refusal-1` |
| `PRESS-4` | Replays the same attack unchanged after a Cook correction and reclassifies. | `press-finding-3` |
| `PRESS-5` | Reports GREEN as status ok with next age and the `/age <slug>` start. | `press-green-1`, `press-green-2`, `press-flags-1`, `press-input-2` |
| `PRESS-6` | Records an out-of-contract concern under Review follow-ups, leaves it to Age, and does not fix it. | `press-green-2` |
| `PRESS-7` | Forwards only the flags the user supplied to Age and never publishes or adds `--open-pr`. | `press-flags-1`, `press-flags-2` |
| `PRESS-8` | Refuses to edit production code, even on a direct request, and routes the fix to Cook. | `press-refusal-1` |
| `PRESS-9` | Stops at the correction cap with `halt: correction-cap` and next done on a third finding for the same attack. | `press-refusal-2` |
| `PRESS-10` | Stops when no Cook handoff exists for the slug and invents no artifact. | `press-input-1` |
| `PRESS-11` | Treats a failure that matches the Cook baseline artifact as known debt, not as a finding. | `press-input-2` |

## Out of scope offline

- The `--auto` chain dispatches `/age`, which a journey does not stage.
- The Wheypoint-backed phase entry (`authoritative`, `gated`, `ambiguous`) needs a durable record that a journey cannot seed.
- The Press handoff writer rejects the `press` to `cook` route in the current archive, so a journey cannot require the artifact write for a finding; the cases judge the stated status and next value.
