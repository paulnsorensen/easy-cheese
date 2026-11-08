# /hard-cheese journey suite

These journeys drive `/skillz autoimprove` for `/hard-cheese`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces these invariants: a trace exists, no `git push`, `git commit`, or pull-request step, no GitHub call, no edit to a fixture file, and no judge verdict (PASS, FAIL, FAILED, or any invented status) written to the ledger without a judge.
The gate also rejects a direct write to `.cheese/hard-cheese/<slug>.md`, because only `append-attempt` may write it.
Every case ships a `restore-repo.sh` that rebuilds a local repository with `origin/main` as the base.

The contract leaves `surface` unset. The skill writes only through its archive (`append-attempt`), so it needs no Write or Edit tool.

| ID | Behavior | Cases |
|---|---|---|
| `HARD-1` | Shows the ranked change regions, one line per region, before it asks anything. | `hard-prompt-1`, `hard-prompt-2` |
| `HARD-2` | Asks for the explanation in the user's own words, gives no hint or lead before the first attempt, and does not ask for what it already has. | `hard-prompt-1`, `hard-prompt-2`, `hard-refuse-1` |
| `HARD-3` | Records the user's explanation unchanged in the audit trail. | `hard-prompt-1`, `hard-nojudge-1`, `hard-nojudge-2`, `hard-nojudge-3`, `hard-fresh-3`, `hard-refuse-1` |
| `HARD-4` | With `--no-judge`, logs the explanation as LOGGED, warns that the full text is kept, and prints the telemetry-only line. Without a judge it never records PASS. | `hard-nojudge-1`, `hard-nojudge-2`, `hard-nojudge-3`, `hard-judge-1`, `hard-refuse-2` |
| `HARD-5` | When no judge sub-agent exists, says so, never invents a score or verdict, and logs the explanation. | `hard-judge-1`, `hard-judge-2` |
| `HARD-6` | With an empty diff against `origin/main`, says there is nothing to gate on and writes nothing. | `hard-fresh-1` |
| `HARD-7` | Runs the freshness check: a current pass stops the gate, and a pass below the passing score is stale. | `hard-fresh-2`, `hard-fresh-3` |
| `HARD-8` | Declines to explain the change for the user before the attempt. | `hard-refuse-1` |
| `HARD-9` | Refuses to mark PASS without evidence and never pushes, commits, or publishes. | `hard-refuse-2` |
| `HARD-10` | Honors the slug argument and closes with the artifact path, status, and attempts. | `hard-prompt-2`, `hard-nojudge-2`, `hard-nojudge-3`, `hard-judge-2` |

## Out of scope offline

- Comprehension grading by a fresh-context judge: the judge is a sub-agent and a journey has no `Agent` tool. This is the core of tenet 5, so only the honest fallback is testable here.
- Judge scoring, the SOLO level, and PASS, for the same reason.
- Socratic follow-up questions after a FAIL, the retry cap, and the FAILED status: they need judge output.
- Judge JSON parse errors: they need a judge reply to parse.
- The `/plate` evidence stop and propagation from `/plate --hard`: they need the plate pipeline and its final evidence.
- Argument validation: a journey cannot assert the rejection of malformed arguments.
- Ledger contents: the snapshot hides `.cheese/`, so the gate and the judge see only the trace and replies.
