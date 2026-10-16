---
name: affinage
description: >
  Triage a GitHub PR's review comments, CI failures, and merge conflicts through the /age lens.
  Use when the user says "address the PR feedback", "fix the review comments on PR 123",
  "fix CI on my PR", "resolve this PR's merge conflicts", or "/affinage".
  Do not use for a diff without a PR. Use /age instead.
  Do not use for local Git conflicts without a PR. Use /melt instead.
license: MIT
metadata: {dispatches-agents: true}
---

# /affinage

Act on existing claims about a PR.
Claims can come from reviewers, CI checks, or merge conflicts.
Grade each claim through the `/age` lens.
Send accepted claims to `/cure`.

`/affinage` always grades claims that exist on the PR.
Its entry path controls whether it also finds new `/age` findings:

- **Standalone** — The user starts `/affinage <pr>` without `handoff_context`.
  Run `/age` on the PR diff unless the user passes `--no-age`.
  Add the new findings to the same report.
- **Chained** — `/cook` or `/cure` supplies `handoff_context`.
  Skip the fresh review because `/age` already ran in this chain.

See `## Fresh review` for the entry rule.
See `## Merge-conflict resolution` for the conflict path.

## Phase entry

Run `python3 skills/affinage/scripts/affinage.pyz wheypoint-resolve --ref <slug>`.
`authoritative` uses the record; its `working_context` is the first batched `tilth_read`.
`not-found` proceeds cold; `legacy` shows its source and slug, then proceeds.
`gated`, `ambiguous`, and `error` stop and show the payload.
Show advisory `stale-commit` and `grounded-path-missing` findings.

## Inputs

```text
/affinage [<pr-ref>] [--auto --stake <floor>] [--plate] [--safe] [--open-pr] [--hard] [--full] [--include-outdated]
```

`<pr-ref>` accepts a PR number, a `PR#<n>` reference, or a full GitHub PR URL.
Extract the integer before you call `pr-status`.
The command accepts only the integer.
If no reference exists, run `gh pr view --json number` on the current branch.

Flags:

- `--auto --stake <floor>` — Run without selection prompts.
  `<floor>` accepts `blocker`, `high`, `medium+`, or `all`.
  Bare `--auto` uses the `medium+` default floor.
  Use the same floor rules as `/cure`.
  Send `/cure --auto --stake <floor>`.
  Post replies without prompts.
  See `references/auto-mode.md`.
- `--safe` — Add gates before cure selection and conflict resolution.
  This flag does not remove the default reply gate.
- `--open-pr` — Let terminal `/plate` open a new PR when no PR exists.
  Without this flag, `/plate` only updates an open PR.
- `--plate` — Run `--auto --stake medium+ --open-pr`.
  Grade the claims.
  Cure the selected findings.
  Post the replies.
  Then run `/plate`.
  An explicit `--stake <floor>` replaces `medium+`.
- `--hard` — Pass the metacognitive gate flag to terminal `/plate`.
- `--full` — Show all low findings when at least 10 low findings exist.
- `--include-outdated` — Include outdated review threads.
- `--no-age` — Skip the fresh review in standalone mode.
  This flag has no effect in chained mode.

Read [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability rules.
It covers helper resolution, agent dispatch, GitHub operations, and handoff transitions.
Use the bundle or repository helper first.
Do not use the `${CLAUDE_SKILL_DIR}` environment variable in an invocation path.
The handoff blocks below define the portable contract.
The rule "slash commands are host renderings, not the control model" applies here.

## Flow

Read `references/flow-details.md` for exact commands, exit codes, and grading reasons.

1. **Resolve PR.** Use `<pr-ref>` or `gh pr view --json number`.
   Normalize a `PR#<n>` reference or a PR URL to its integer.
   Resolve `<owner>/<repo>` from the Git remote.
2. **Fetch PR status.** Run `python3 skills/affinage/scripts/affinage.pyz pr-status <pr>`.
   A `logs_expired: true` field stops with `status: halt: pr-status-logs-expired`.
   A nonzero exit stops with `status: halt: pr-status-unavailable`.
   Route a conflicting or dirty merge state to `## Merge-conflict resolution`.
3. **Check out the PR.** Run `gh pr checkout <pr>`.
   The fresh review and `/cure` read the PR head from the working tree.
   With `--safe`, ask before the checkout.
   A failed checkout stops with `status: halt: pr-checkout-failed`.
4. **Fetch comments.** Fetch inline threads from `pulls/<pr>/comments`.
   Skip comments with `position: null` unless the user passes `--include-outdated`.
   Fetch review bodies from `pulls/<pr>/reviews`.
   Keep each nonempty body.
   Remove duplicates by `pull_request_review_id`.
5. **Skip answered threads.** Read thread resolution state from GraphQL `reviewThreads`.
   Skip a thread that GitHub marks resolved.
   Skip a thread when the resolved GitHub handle replied after its root comment.
6. **Run fresh review.** Run this step only in standalone mode without `--no-age`.
   Build contextual review input and call the bundled `age-route` command.
   Include the unresolved thread count from step 5 and the CI failure class.
   Run `/age` with the complete subject plan and its evidence.
   Tag each new finding with `[from-age:<dimension>]`.
7. **Grade claims.** Classify each claim by the `/age` dimension and severity rules.
   Do not increase severity because a reviewer selected `CHANGES_REQUESTED`.
   Put contained fixes in severity sections.
   Put claims that need outside evidence in `## Needs-investigation`.
   Put wrong, unsupported, or large claims in `## Reviewer-rejected`.
   Put claims that the current head already fixes in `## Already-addressed`.
8. **Write report.** Write `.cheese/affinage/pr-<n>.md`.
   Start with the four-line handoff slug.
   Add the `/age` report body and the affinage sections.
   See `## Output`.
9. **Act or ask.** Follow `## Handoff`.
10. **Draft non-cure replies.** Draft replies for rejected and investigation claims.
    Do not reply to CI or fresh-review findings.
11. **Draft cure replies.** Run this step only after `/cure`.
    Read `### Applied` and `### Deferred` from `.cheese/cure/pr-<n>.md`.
    Draft `Fixed — <applied summary>.` for applied comment findings.
    Draft `Attempted fix reverted — <reason>.` for deferred comment findings.
12. **Re-review the cure diff.** Run this step only after a `/cure` run without `--auto`.
    `/cure --auto` runs its own scoped `/age` chain.
    Run the `/age <slug> --scope <touched-path>` command that `.cheese/cure/pr-<n>.md` recommends.
    Start each `reviewer` worker prompt with the line `Review mode: severity-report`.
    Use the `/age` findings, not its handoff gate.
    Send the new findings to one more `/cure` by the `## Handoff` rules.
    Do not re-review that second `/cure`.
    Do not draft replies for these findings.
    Report each finding that remains as a residual.
13. **Post replies.** Show one reply gate that lists every drafted reply and every already-addressed thread.
    Skip the gate only when `--auto` is active.
    Post approved replies with `python3 skills/affinage/scripts/affinage.pyz post-reply`.
    Resolve each approved already-addressed thread without a reply.
14. **Publish.** Run this step only after all approved replies post.
    Publish when `/cure` applies at least one fix.
    Also publish when `/melt` resolved a merge conflict.
    Send terminal `/plate [--open-pr] [--hard] [--safe]`.
    Then run the post-PR learning write-back from `../cure/SKILL.md`.
    Skip publication and write-back when the working tree has no change.

## Fresh review

Standalone mode calls the router with `entry="affinage"`.
Pass the PR reference and the router values to `/age`.
This prevents `/age` from calculating a smaller route with `entry="age"`.
Add each result to its severity section with `[from-age:<dimension>]`.
Send these findings to `/cure` like other findings.
Do not post GitHub replies for these findings.

Run the fresh review before you grade external claims.
This order lets you remove duplicate findings.
Use the same agent gate as the grading step.
Start each `reviewer` worker prompt with the line `Review mode: severity-report`.

## Merge-conflict resolution

When `pr-status` reports conflicts, send the PR to `/melt`.
`/melt` uses mergiraf, rerere, and kdiff3.
Do not resolve conflicts by hand.

Default and `--auto` modes run checkout and `/melt` before `/cure`.
`--safe` requires the handoff gate first.
If `/melt` fails, write `status: halt: merge-conflicts-need-human` and stop.
`/melt` leaves the resolution uncommitted.
Terminal `/plate` commits and pushes that resolution.
See `references/merge-conflict.md`.

## Sub-agent context gate

Keep dialogue, selection, approval state, and reply posting in the parent context.
Use a fresh read-only `reviewer` when any limit below is true:

- More than 10 inputs exist.
- The diff exceeds approximately 25 KB.
- Threads cover more than 5 files.

Resolve the reviewer through the shared agent resolver.
Start the reviewer prompt with the line `Review mode: severity-report`.
Without that line, the `reviewer` agent returns `blocked: missing-contract`.
Use a general worker only with `degraded: true`.
The reviewer returns a compact digest of graded findings.
Each finding includes its dimension, severity, confidence, evidence, and draft push-back.
The parent writes the report, controls selection, calls `/cure`, and posts replies.
See `../age/references/sub-agent-gate.md` for digest limits.

## Preferred tools and fallbacks

Use [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) for source code operations.
Use these affinage tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR status | `python3 skills/affinage/scripts/affinage.pyz pr-status` | `gh pr checks` and `gh pr view` |
| GitHub fetch | `gh api` | none; stop the skill |
| Reply posting | `python3 skills/affinage/scripts/affinage.pyz post-reply` | none; direct `gh api` calls omit attribution |

## Output

Write the report to `.cheese/affinage/pr-<n>.md`.
Start with the four-line handoff slug.
Then add the `/age` report body and the `## PR status` section.
Use the severity sections from `/age`.
Add the `## Needs-investigation` and `## Reviewer-rejected` sections from `/affinage`.
See `references/report-template.md`.

```markdown
status: <canonical status field>
next: cure | done
artifact: <path-to-prior-cure-or-press-report-if-any>
<one-line orientation: what the PR does and what was graded>
```

Use the canonical `status:` grammar from the [handback contract](../cheese/references/handback-contract.md).
Only `next:` and the extra keyed lines are phase-specific.
Omit empty sections.
Use `status: ok` after grading completes.
Use `status: halt: <reason>` when `gh` or `pr-status` fails.
Set `next:` by the rules in `## Handoff`.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate.
`/affinage` runs parallel to `/age` and sends findings to `/cure`.

By default, affinage acts without a prompt.
Ask only when the selected fix is large, findings conflict, or `--safe` is active.

- **Severity findings exist.** Calculate the recommended `all-medium, cheap` selection.
  Without an ask reason, announce the selection.
  Then send `/cure` the locked `handoff_context`.
  Then show one reply gate for every drafted reply.
  That gate covers the applied, deferred, push-back, and investigation replies.
  With an ask reason, show the cure selection gate instead.
  Use the shared gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
  Preselect the composite and identify large rows.
  `--auto` skips both gates.
- **Only rejected or investigation claims exist.** Do not call `/cure`.
  Show the reply gate.
  Then wait for a selection.
  `--auto` skips this gate.

Then follow Flow steps 10 through 14.
Set `status: ok / next: done` when no action remains.

Set `next: cure` when at least one finding meets the `medium+` floor.
Set `next: done` when no severity finding exists.
Also set `next: done` when the selected findings are empty.

## Auto mode

Read `references/auto-mode.md` when `--auto` or `--plate` is active.
It defines the selection, cure chain, reply, and publication steps.

## --hard mode

Pass `--hard` to terminal `/plate`.
`/plate` runs `/hard-cheese` after it verifies the final artifact.
`/cure` does not call `/plate` in this chain.
The gate therefore runs once at the publication boundary.

## Rules

- Ground each grade in code evidence.
- Prefer a contained fix to push-back.
- Send a valid, contained quality fix to `/cure` as `Low`.
- Reserve `## Reviewer-rejected` for wrong, unsupported, or large claims.
- Never apply code fixes in affinage.
- Send code fixes to `/cure` and merge conflicts to `/melt`.
- Never post a reply or resolve a thread without approval, unless `--auto` is active.
- Post replies only through `python3 skills/affinage/scripts/affinage.pyz post-reply`.
- End every reply with `agent on behalf of <handle>`.
- Resolve `<handle>` from `RESPOND_GH_HANDLE`, `gh api user --jq .login`, or `git config user.name`.
- Use GraphQL only to read `reviewThreads` state and to resolve already-addressed threads.
- Apply the voice rules in `../age/references/voice.md`.
- Use `certain`, `speculating`, or `don't know` for confidence.
- State that no findings exist when no claim needs grading.

## References

Read each affinage reference when its trigger applies:

- `references/flow-details.md` — read when you run Flow steps 2, 5, 6, 7, 10, or 13.
- `references/merge-conflict.md` — read when `pr-status` reports a conflicting or dirty merge state.
- `references/report-template.md` — read when you write the report at Flow step 8.
- `references/handoff-templates.md` — read when you render the cure selection gate or the reply gate.
- `references/auto-mode.md` — read when `--auto` or `--plate` is active.
- [`references/commands.md`](references/commands.md) — read when you need the exact flags of a bundled command.
  The file is the generated command inventory.

Use `../age/references/sub-agent-gate.md` for the shared agent gate.

## Agent resolution

Resolve each dispatch through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Triage review claims and CI evidence | reviewer | read-only, fresh context | powerful | high | compatible reviewer, then general |

The canonical affinage report includes the shared `agent_resolution` block.
