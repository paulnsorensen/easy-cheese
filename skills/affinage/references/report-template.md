# Affinage report template

Use this example for `.cheese/affinage/pr-<n>.md`.
Keep the four-line handoff slug from `SKILL.md` before these sections.
Downstream skills parse that slug.

```markdown
# Affinage Report — PR #<n>

## Orientation
<one or two facts about the PR and the graded claims>

## PR status
- Build: passing | failing (N jobs)
- Merge: clean | conflicts (resolved via /melt | needs human)
- Comments: K unresolved (M skipped as outdated)
- Fresh review: ran /age (N findings) | skipped (chained) | skipped (--no-age)

## Blocker
- **[from-comment:<id>] [security:blocker]** alice on `src/auth.ts:42` — The code parses a token without validation.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - reviewer-asserted: changes-requested
  - recommendation: Validate `authorization`. Return 401 when the header is absent.
- **[from-check:test-suite] [correctness:blocker]** CI job `test-suite` — Three tests fail in `tests/auth.test.ts`.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - recommendation: Add the absent null check. Then run the tests again.
- **[from-check:build] [correctness:blocker]** CI job `build` — `tsc` reports `src/auth.ts:42: 'token' is possibly undefined`.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - recommendation: Narrow `token` before use. The build cannot pass until this compiles.
- **[from-age:efficiency] [efficiency:high]** fresh review — `src/api/users.ts:88` fetches the user in each loop iteration.
  - location: hot path · fix-cost-now: contained · fix-cost-later: contained · confidence: speculating
  - recommendation: Move the fetch before the loop.

## High
... (use the same format)

## Medium
... (use the same format)

## Low
- **[from-comment:<id>] [deslop:low]** copilot on `src/utils/format.ts:18` — Rename `data` to `lineItems`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: Rename `data` to `lineItems`. Send this cheap fix to `/cure`.
... (use the same format; collapse it by the --full rules)

## Needs-investigation
- **[from-comment:<id>]** bob on `src/api/users.ts:108` — "This might break the analytics pipeline."
  - reason: The claim is plausible, but the pipeline is in another repository.
  - suggested action: Read `analytics-svc/consumers/users.ts`.

## Reviewer-rejected
- **[from-comment:<id>]** copilot on `src/auth.ts:30` — "This needs `await`."
  - reason: `parseToken` returns `string`, not `Promise`. See `src/auth.ts:12`.
  - draft reply: "`parseToken` returns `string` here. No promise exists, so I will keep the current code."
- **[from-comment:<id>]** dana on `src/api/users.ts:60` — "Extract a generic repository layer."
  - reason: The change needs six files in two slices. It exceeds this PR scope.
  - draft reply: "This cross-slice refactor exceeds this PR scope. I will record it as follow-up work."

## Confidence
<certain | speculating | don't know> — <one reason for the confidence>

## Next step
Send the recommended findings to `/cure`.
Hold prepared replies for the reply approval gate.
Post directly only in `--auto` mode.
Post replies before terminal `/plate` publishes fixes.
Show the cure selection gate when `--safe` is active or an ask reason exists.
```

Omit empty severity sections.
Omit `## Needs-investigation` and `## Reviewer-rejected` when they are empty.

Use the confidence scale from `../../age/references/voice.md`.
Use `certain` when direct evidence confirms the defect.
Use `speculating` when indirect evidence supports the defect.
Put a `don't know` claim in `## Needs-investigation`, not a severity section.
