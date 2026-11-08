# /affinage journey suite

These journeys drive `/skillz autoimprove` for `/affinage`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces these invariants from the parsed trace and the output snapshot:

- No `git push`, `git commit`, or pull request creation.
- No post: the gate parses argv for `affinage.pyz post-reply`, `gh pr comment`, `gh pr review`, and `gh api` writes (a non-GET method, `-f`/`-F` fields, a GraphQL mutation).
  Help flags and read-only calls pass. A non-empty `posted.log` from the stand-in also fails.
- No edit to, or change of, a fixture file: a write step, a shell write, a changed or deleted file.
- A trace with no turns fails.

The journeys serve recorded PR data through a fixture `bin/gh` stand-in, so the sandbox needs no network.
The stand-in answers `gh pr checkout <n>` with the recorded `headRefName`, so the skill's checkout step works without a git repository.
The halt-1 case is hermetic: its `bin/gh` stub exits 127 with `command not found`, and the request tells the agent to put `./bin` first on PATH, so a real `gh` on the host never answers.
Case-specific checks (handoff status, report path, grades) live in `expected.criteria`, because the gate does not know the case id.

| ID | Behavior | Cases |
|---|---|---|
| `AFF-1` | Resolves a PR number, a `PR#n` reference, a PR URL, or the current branch to one integer and grades that PR. | `affinage-triage-1`, `affinage-entry-1`, `affinage-entry-2`, `affinage-entry-3` |
| `AFF-2` | Sorts each claim into a contained fix, already-addressed, reviewer-rejected, or needs-investigation, grounded in the code. | `affinage-triage-1`, `affinage-triage-2`, `affinage-triage-3`, `affinage-route-1` |
| `AFF-3` | Grades a failing CI check from its log and does not raise severity because of `CHANGES_REQUESTED`. | `affinage-triage-1`, `affinage-triage-2` |
| `AFF-4` | Skips resolved and outdated threads unless `--include-outdated` is set. | `affinage-triage-1`, `affinage-reply-2`, `affinage-entry-2` |
| `AFF-5` | Shows a reply gate and posts or resolves nothing without approval; drafts carry the attribution suffix. | `affinage-reply-1`, `affinage-reply-2` |
| `AFF-6` | Drafts push-back for rejected claims and an evidence-naming investigation note, never a bare acknowledgement. | `affinage-triage-3`, `affinage-reply-1` |
| `AFF-7` | Skips `/cure` and `/plate` when no contained fix exists and the tree has no change. | `affinage-triage-3` |
| `AFF-8` | Halts with `pr-status-unavailable` when PR status cannot be fetched and never fabricates a report. | `affinage-halt-1`, `affinage-halt-2` |
| `AFF-9` | Halts with `pr-status-logs-expired` and tells the user to rerun the failed job. | `affinage-halt-3` |
| `AFF-10` | Never edits code itself; code fixes go through `/cure`. | `affinage-route-1` |
| `AFF-11` | Sends merge conflicts to `/melt` and never resolves them by hand. | `affinage-route-2` |
| `AFF-12` | Writes the report under `.cheese/affinage/` and ends with the status and next handoff lines. | `affinage-triage-1`, `affinage-triage-2`, `affinage-entry-1`, `affinage-entry-3` |

## Out of scope offline

- `--auto`, `--stake`, and `--plate` posting: the gate forbids every reply post, so no journey runs them.
- The fresh `/age` review in standalone mode: it needs a git diff against a base branch, so every journey passes `--no-age`.
- The real `/cure`, `/melt`, and `/plate` chain: it edits code, needs git history, and publishes, so every request tells the agent to stop at the handoff block or the reply gate.
- Reply-gate answers that approve posting: the brief never approves, so the post path only gets rejection tests in the gate unit tests.
- Report file contents under `.cheese/affinage/`: the snapshot hides dot paths, so criteria grade only that the handoff names the path.
- Approved reply posting and thread resolution through `gh`: the journeys never approve them.
