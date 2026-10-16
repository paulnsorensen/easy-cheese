# Flow command and reason details

Use this file for `## Flow` steps 2, 5, 6, 7, 10, and 13.
It gives exact commands, exit codes, and grading rules.

## Step 2 — Fetch PR status

Run `python3 skills/affinage/scripts/affinage.pyz pr-status <pr>`.
The command returns JSON with build status, failed check summaries, failed test names, and merge state.
Each failed check summary includes approximately 10 final log lines.

- **`logs_expired: true`** in the JSON output means CI fails, but no failed check has usable logs.
  Write `status: halt: pr-status-logs-expired` and stop.
  Tell the user to rerun failed jobs with `gh run rerun <run-id> --failed`.
  Read `<run-id>` from the `/actions/runs/<id>/` URL segment or `gh pr checks`.
  Then tell the user to run `/affinage` again.
- **A nonzero exit** means the PR or GitHub status is unavailable.
  Exit 1 identifies a PR or API error.
  Exit 2 identifies a missing `gh` binary.
  Write `status: halt: pr-status-unavailable` and stop.

## Step 5 — Thread state

Read each thread's resolution state and node ID in one query:

```bash
gh api graphql -F owner=<owner> -F repo=<repo> -F pr=<n> -f query='
  query($owner:String!,$repo:String!,$pr:Int!){repository(owner:$owner,name:$repo){
    pullRequest(number:$pr){reviewThreads(first:100){nodes{
      id isResolved comments(first:100){nodes{databaseId author{login}}}}}}}}'
```

Match a REST comment to its thread by `databaseId`.
A thread is answered when it is resolved.
A thread is also answered when the handle wrote any comment after the root comment.
A bot acknowledgement after the handle's reply does not reopen the thread.

## Step 6 — Fresh review

Score the PR diff with the `review-surface` command.
Run `python3 skills/affinage/scripts/affinage.pyz review-surface --repo . <base>...HEAD`.
Use the complete PR range against its base branch.
Step 3 checks out the PR, so use `origin/<base>...HEAD`.
Do not use the bare `HEAD` default because it scores only uncommitted changes.

Build the evidence-bearing review context described in `../../age/references/fan-out.md`.
Include all changed paths, even when their workload weight is zero.
Use `entry="affinage"`, `comments=<unresolved-thread-count>`, and `ci_class=<"passing"|"failing"|"red"|"flaky"|null>` alongside `context`.
Take the unresolved thread count from step 5.
The router preserves comment-count and CI workload escalation.
Use normal review effort unless the user explicitly selects quick or deep.

Run `python3 skills/affinage/scripts/affinage.pyz age-route <request.json>`.
The command reads the contextual request and emits a deterministic subject plan.
Pass the complete plan and its evidence to `/age`, not the old dimension-lens tuple.
Then treat each `/age` finding as an additional claim.

## Step 7 — Grading rules

- Grade every failed check, including build, compile, lint, type, and test failures.
- Send failed checks to `/cure` like test failures.
- Tag each CI finding with `[from-check:<job>]`.
- Keep the existing dimension and severity for each fresh review finding.
- Tag each fresh review finding with `[from-age:<dimension>]`.
- Remove a duplicate fresh review finding when a reviewer reports the same defect.
- Keep the reviewer claim because it requires a reply.
- Record `CHANGES_REQUESTED` as `reviewer-asserted:` metadata.
- Do not use reviewer urgency to calculate severity.

Use these report sections:

- Put grounded claims with contained fixes in `## Blocker`, `## High`, `## Medium`, or `## Low`.
  Add a `[<dimension>:<severity>]` tag to each claim.
  Map style and quality claims to `deslop`.
  Add a `source: from-comment:<id>` line so `/cure` can reply.
  Prefer a cheap fix to push-back.
- Put plausible claims that need outside evidence in `## Needs-investigation`.
- Put wrong or unsupported claims in `## Reviewer-rejected`.
- Also put valid but large claims in `## Reviewer-rejected`.
  Large claims have `fix-cost-now: moderate` or `sprawling`.
  Structural later work is also large.
  Reject a wrong claim.
  Defer a large claim.
- Put a claim that the current head already fixes in `## Already-addressed`.
  Cite the fixing commit and the line that proves the fix.
  Do not draft a reply. Resolve the thread at step 13.

## Step 10 — Reply rules

Post approved replies with `python3 skills/affinage/scripts/affinage.pyz post-reply`.
Do not post with `gh api` because it omits the required attribution.

- Post the prepared push-back for `Reviewer-rejected` claims.
- Do not post a general acknowledgement for `Needs-investigation` claims.
- Name the exact evidence that can confirm each investigation claim.
- State that a follow-up will report the result.
- Offer to run the investigation before you post.
- Use `/pasteurize` for a regression test.
- Use `/briesearch` for evidence outside the diff.
- Post the actual result when the user accepts the investigation.
- Post the explicit follow-up note when the user declines.
- Do not reply to `[from-check:<job>]` or `[from-age:<dimension>]` findings.

## Step 13 — Resolve already-addressed threads

Resolve each approved `## Already-addressed` thread with its step 5 node ID:

```bash
gh api graphql -F id=<thread-node-id> -f query='
  mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}'
```

Confirm that the response shows `isResolved: true`.
Do not post a reply to a resolved thread.
