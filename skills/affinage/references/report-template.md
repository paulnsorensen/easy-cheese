# Affinage report — full annotated template

Read this when writing `.cheese/affinage/pr-<n>.md` — the worked example for every section below the four-line handoff slug (which stays in `SKILL.md` § Output, since downstream skills parse it directly).

```markdown
# Affinage Report — PR #<n>

## Orientation
<one or two factual sentences about the PR and what was graded>

## PR status
- Build: passing | failing (N jobs)
- Merge: clean | conflicts (resolved via /melt | needs human)
- Comments: K unresolved (M skipped as outdated)
- Fresh review: ran /age (N findings) | skipped (chained) | skipped (--no-age)

## Blocker
- **[from-comment:<id>] [security:blocker]** alice on `src/auth.ts:42` — token parsed without validation.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - reviewer-asserted: changes-requested
  - recommendation: validate `authorization` header; reject with 401 on missing.
- **[from-check:test-suite] [correctness:blocker]** CI job `test-suite` — 3 tests failing in `tests/auth.test.ts`.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - recommendation: re-run after fixing the missing null check.
- **[from-check:build] [correctness:blocker]** CI job `build` — `tsc` fails: `src/auth.ts:42: 'token' is possibly undefined`.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural · confidence: certain
  - recommendation: narrow `token` before use; build is red until this compiles.
- **[from-age:efficiency] [efficiency:high]** fresh review — `src/api/users.ts:88` re-fetches the user inside the loop body.
  - location: hot path · fix-cost-now: contained · fix-cost-later: contained · confidence: speculating
  - recommendation: hoist the fetch above the loop.

## High
... (same shape)

## Medium
... (same shape)

## Low
- **[from-comment:<id>] [deslop:low]** copilot on `src/utils/format.ts:18` — rename `data` to `lineItems` for clarity.
  - location: class · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: rename `data` → `lineItems`. Valid cheap nit — fixed via `/cure`, not pushed back.
... (same shape; collapsible per --full rules)

## Needs-investigation
- **[from-comment:<id>]** bob on `src/api/users.ts:108` — "might break analytics pipeline."
  - reason: claim plausible but pipeline lives in a different repo; diff cannot confirm.
  - suggested action: human reads `analytics-svc/consumers/users.ts`.

## Reviewer-rejected
- **[from-comment:<id>]** copilot on `src/auth.ts:30` — "missing `await`; this promise is unhandled."
  - reason: wrong — `parseToken` is synchronous (returns `string`, not a `Promise`, see `src/auth.ts:12`); there is nothing to await.
  - draft reply: "`parseToken` is synchronous here (returns `string`, `src/auth.ts:12`), so there's no promise to await. Leaving as-is."
- **[from-comment:<id>]** dana on `src/api/users.ts:60` — "extract this into a generic repository layer."
  - reason: valid but large — fix-cost-now: sprawling (6 files across 2 slices); scope expansion beyond this PR.
  - draft reply: "Agreed this would be cleaner, but it's a cross-slice refactor beyond this PR's scope — filing a follow-up rather than growing this change."

## Confidence
<certain | speculating | don't know> — <one-line justification>

## Next step
Auto-fixing the recommended set via `/cure`; drafted replies are held for the reply-approval gate before posting (`--auto` posts directly). Replies post before terminal `/plate` publishes cure's fixes. On a reason to ask / `--safe`, the cure-selection prompt renders inline — pick findings to cure or `none` to stop.
```

Empty severity sections are omitted entirely. `## Needs-investigation` and `## Reviewer-rejected` are omitted when no items land there.

Per-finding `confidence:` uses the voice-kernel scale (`../../age/references/voice.md` § Reasoning posture): `certain` — the defect is verified by direct evidence (diff/code read, command output); `speculating` — inferred from indirect signal. A `don't know` grading never ships as a severity row — route it to `## Needs-investigation`.
