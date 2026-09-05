# Flow command and reason details

Use this file for `## Flow` steps 2, 3, 6, and 9.
It gives exact commands, exit codes, and grading rules.

## Step 2 — Fetch PR status

Run `python3 skills/affinage/scripts/affinage.pyz pr-status <pr>`.
The command returns JSON with build status, failed check summaries, failed test names, and merge state.
Each failed check summary includes approximately 10 final log lines.

- **Exit 3** means `logs-expired`.
  CI fails, but no failed check has usable logs.
  Write `status: halt: pr-status-logs-expired` and stop.
  Tell the user to rerun failed jobs with `gh run rerun <run-id> --failed`.
  Read `<run-id>` from the `/actions/runs/<id>/` URL segment or `gh pr checks`.
  Then tell the user to run `/affinage` again.
- **Any other nonzero exit** means the PR or GitHub status is unavailable.
  Exit 1 identifies a PR or API error.
  Exit 2 identifies a missing `gh` binary.
  Write `status: halt: pr-status-unavailable` and stop.

## Step 3 — Fresh review

Score the PR diff with the `review-surface` command.
Run `python3 skills/affinage/scripts/affinage.pyz review-surface --repo . <base>...HEAD`.
Use the complete PR range against its base branch.
After checkout, use `origin/<base>...HEAD`.
Do not use the bare `HEAD` default because it scores only uncommitted changes.

Search added lines outside `skills/**` and `.hallouminate/**` for `age_route.OVERRIDE_FLAGS`.
A missed token prevents lens promotion.
It does not remove the security lens.

Call `age_route.route(score=<float>, ...)` with these values:

- `score=<float>`
- `risk_flags=[...]`
- `entry="affinage"`
- `comments=<unresolved-thread-count>`
- `ci_class=<"failing"|"red"|"flaky"|None>`

This route includes comment count and CI class.
It can increase fan-out for a small PR with many comments or red CI.

If only the bundle exists, pipe JSON to `affinage.pyz age-route`.
The command reads JSON from standard input and writes route JSON to standard output.
Pass the returned `n`, `lenses`, and `effort` to `/age`.
Then treat each `/age` finding as an additional claim.

## Step 6 — Grading rules

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

## Step 9 — Reply rules

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
