# /affinage journey suite

These journeys drive `/skillz autoimprove` for `/affinage`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces three hard invariants: no reply post or thread resolve, no `git push` or `git commit`, and no edit to a fixture source file.
It also rejects a `status: ok` handoff when no `gh` exists in the sandbox.
The journeys serve recorded PR data through a fixture `bin/gh` stand-in, so the sandbox needs no network.

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
- The real `/cure`, `/melt`, and `/plate` chain: it edits code, needs git history, and publishes, so journeys stop at the report and the reply gate.
- Approved reply posting and thread resolution through `gh`: the journeys never approve them.
