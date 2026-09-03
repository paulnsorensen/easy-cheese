---
name: affinage
description: >
  Triage a PR's review comments, CI failures, and merge conflicts through the /age lens.
  Use when the user asks to address PR feedback, fix CI, or resolve conflicts.
  Do not use for a diff without a PR. Use /age instead.
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

See `## Fresh-window review` for the entry rule.
See `## Merge-conflict resolution` for the conflict path.

## Inputs

```text
/affinage [<pr-ref>] [--auto --stake <floor>] [--plate] [--safe] [--open-pr] [--hard] [--full] [--include-outdated]
```

`<pr-ref>` accepts a PR number or a full GitHub PR URL.
If no reference exists, run `gh pr view --json number` on the current branch.

Flags:

- `--auto --stake <floor>` — Run without selection prompts.
  `<floor>` accepts `blocker`, `high`, `medium+`, or `all`.
  Use the same floor rules as `/cure`.
  Send `/cure --auto --stake <floor>` and post replies without prompts.
  See `references/auto-mode.md`.
- `--safe` — Add gates before cure selection and conflict resolution.
  This flag does not remove the default reply gate.
- `--open-pr` — Let terminal `/plate` open a new PR when no PR exists.
  Without this flag, `/plate` only updates an open PR.
- `--plate` — Run `--auto --stake medium+ --open-pr`.
  Grade claims, cure the selected findings, post replies, and run `/plate`.
  An explicit `--stake <floor>` replaces `medium+`.
- `--hard` — Pass the metacognitive gate flag to terminal `/plate`.
- `--full` — Show all low findings when at least 10 low findings exist.
- `--include-outdated` — Include outdated review threads.
- `--no-age` — Skip the fresh `/age` pass in standalone mode.
  This flag has no effect in chained mode.

Read [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability rules.
It covers helper resolution, agent dispatch, GitHub operations, and handoff transitions.
Use the bundle or repository helper first.
Use `${CLAUDE_SKILL_DIR}` only as an optional host fallback.
The handoff blocks below define the portable contract.
The phrase "slash commands are host renderings, not the control model" defines the host rule.

## Flow

Read `references/flow-details.md` for exact commands, exit codes, and grading reasons.

1. **Resolve PR.** Use `<pr-ref>` or `gh pr view --json number`.
   Resolve `<owner>/<repo>` from the Git remote.
2. **Fetch PR status.** Run `affinage.pyz pr-status <pr>`.
   Exit 3 stops with `status: halt: pr-status-logs-expired`.
   Any other nonzero exit stops with `status: halt: pr-status-unavailable`.
   Route a conflicting or dirty merge state to `## Merge-conflict resolution`.
3. **Run fresh review.** Run this step only in standalone mode without `--no-age`.
   Score the PR diff and call `age_route.route(...)`.
   Include the comment count and CI failure class.
   Run `/age` with the returned `n`, `lenses`, and `effort` values.
   Tag each new finding with `[from-age:<dimension>]`.
4. **Fetch comments.** Fetch inline threads from `pulls/<pr>/comments`.
   Skip comments with `position: null` unless the user passes `--include-outdated`.
   Fetch review bodies from `pulls/<pr>/reviews`.
   Keep nonempty bodies and remove duplicates by `pull_request_review_id`.
5. **Skip answered threads.** Skip a thread when the resolved GitHub handle wrote its latest comment.
   Render the footer as `agent on behalf of <handle>`.
6. **Grade claims.** Classify each claim by the `/age` dimension and severity rules.
   Do not increase severity because a reviewer selected `CHANGES_REQUESTED`.
   Put contained fixes in severity sections.
   Put claims that need outside evidence in `## Needs-investigation`.
   Put wrong, unsupported, or large claims in `## Reviewer-rejected`.
7. **Write report.** Write `.cheese/affinage/pr-<n>.md`.
   Start with the four-line handoff slug.
   Add the `/age` report body and two affinage sections.
   See `## Output`.
8. **Act or ask.** Follow `## Handoff`.
9. **Handle non-cure replies.** Draft replies for rejected and investigation claims.
   Require the reply gate unless `--auto` is active.
   Post approved replies with `affinage.pyz post-reply`.
   Do not reply to CI or fresh-review findings.
10. **Handle cure replies.** Run this step only after `/cure`.
    Read `### Applied` and `### Deferred` from `.cheese/cure/pr-<n>.md`.
    Reply `Fixed — <applied summary>.` for applied comment findings.
    Reply `Attempted fix reverted — <reason>.` for deferred comment findings.
11. **Publish.** Run this step only after all approved replies post.
    Require `/cure` to apply at least one fix.
    Send terminal `/plate [--open-pr] [--hard] [--safe]`.
    Then run the post-PR learning write-back from `../cure/SKILL.md`.
    Skip publication and write-back when `/cure` applies no fix.

## Fresh-window review

Standalone mode calls the router with `entry="affinage"`.
Pass the PR reference and the router values to `/age`.
This prevents `/age` from calculating a smaller route with `entry="age"`.
Add each result to its severity section with `[from-age:<dimension>]`.
Send these findings to `/cure` like other findings.
Do not post GitHub replies for these findings.

Run the fresh review before you grade external claims.
This order lets you remove duplicate findings.
Use the same agent gate as the grading step.

## Merge-conflict resolution

When `pr-status` reports conflicts, send the PR to `/melt`.
`/melt` uses mergiraf, rerere, and kdiff3.
Do not resolve conflicts by hand.

Default and `--auto` modes run checkout and `/melt` before `/cure`.
`--safe` requires the handoff gate first.
If `/melt` fails, write `status: halt: merge-conflicts-need-human` and stop.
See `references/merge-conflict.md`.

## Sub-agent context gate

Keep dialogue, selection, approval state, and reply posting in the parent context.
Use a fresh read-only `reviewer` when any limit below is true:

- More than 10 inputs exist.
- The diff exceeds approximately 25 KB.
- Threads cover more than 5 files.

Resolve the reviewer through the shared agent resolver.
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
| PR status | `skills/affinage/scripts/affinage.pyz pr-status` | `gh pr checks` and `gh pr view` |
| GitHub fetch | `gh api` | none; stop the skill |
| Reply posting | `skills/affinage/scripts/affinage.pyz post-reply` | none; direct `gh api` calls omit attribution |
| Diff inspection | `delta` | `git diff --unified=3` |

## Output

Write the report to `.cheese/affinage/pr-<n>.md`.
Start with the four-line handoff slug.
Then add the `/age` report body and the `## PR status` section.
Use the severity, `## Needs-investigation`, and `## Reviewer-rejected` sections from `/age`.
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
Use `halt: <reason>` when `gh` or `pr-status` fails.
Set `next:` by the rules in `## Handoff`.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate.
`/affinage` runs parallel to `/age` and sends findings to `/cure`.

By default, affinage acts without a prompt.
Ask only when the selected fix is large, findings conflict, or `--safe` is active.

- **Severity findings exist.** Calculate the recommended `all-medium, cheap` selection.
  Without an ask reason, announce the selection and send `/cure` the locked `handoff_context`.
  Then show the reply gate before you post.
  With an ask reason, show the cure selection gate instead.
  Use the shared gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
  Preselect the composite and identify large rows.
  `--auto` skips both gates.
- **Only rejected or investigation claims exist.** Do not call `/cure`.
  Show the reply gate and wait for a selection.
  `--auto` skips this gate.

Post approved replies after the selection.
Run terminal `/plate [--open-pr] [--hard] [--safe]` only when `/cure` applies a fix.
Set `status: ok / next: done` when no action remains.

Set `next: cure` when at least one finding meets the `medium+` floor.
Set `next: done` when no severity finding exists.
Also set `next: done` when the selected findings are empty.

## Auto mode

Skip the selection gate.
Resolve merge conflicts through `/melt` first.
Stop with `status: halt: merge-conflicts-need-human` when conflicts remain.
Run the fresh `/age` pass in standalone mode.
Select each finding that meets `<floor>`.
`--plate` uses `--stake medium+ --open-pr`.
Send `/cure --auto --stake <floor>`.
Post replies for the original graded claims after the cure chain stops.
Then run terminal `/plate --open-pr [--hard]` after every reply posts.
Skip `/plate` when `/cure` applies no fix.
If no finding meets the floor, skip `/cure`.
Post only rejection and investigation replies.
Exit with `status: ok / next: done`.
See `references/auto-mode.md`.

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
- Never post a reply without approval, unless `--auto` is active.
- Post replies only through `skills/affinage/scripts/affinage.pyz post-reply`.
- End every reply with `agent on behalf of <handle>`.
- Resolve `<handle>` from `RESPOND_GH_HANDLE`, `gh api user --jq .login`, or `git config user.name`.
- Skip a thread when the resolved handle wrote its latest comment.
- Use GraphQL `reviewThreads` only when cross-session resolution state is necessary.
- Apply the voice rules in `../age/references/voice.md`.
- Use `certain`, `speculating`, or `don't know` for confidence.
- State that no findings exist when no claim needs grading.

## References

Use these affinage references:

- `references/flow-details.md`
- `references/merge-conflict.md`
- `references/report-template.md`
- `references/handoff-templates.md`
- `references/auto-mode.md`

Use `../age/references/sub-agent-gate.md` for the shared agent gate.
See the generated command inventory in [`references/commands.md`](references/commands.md).

## Agent resolution

Resolve each dispatch through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Triage review claims and CI evidence | reviewer | read-only, fresh context | powerful | high | compatible reviewer, then general |

The canonical affinage report includes the shared `agent_resolution` block.
