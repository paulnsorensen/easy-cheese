---
name: affinage
description: Use this skill to triage external claims about a PR — review comments AND CI failures — by running them through the /age lens. Phrases like "respond to PR comments", "handle review feedback", "affinage the PR", "/affinage <pr>", "address the reviewer comments", "grade the PR comments". Fetches inline + review-body comments via `gh` and CI failures via `scripts/pr-status.py`, grades each through the ten age dimensions, and writes a report at `.cheese/affinage/pr-<n>.md` with extra `## Needs-investigation` and `## Reviewer-rejected` sections. Hands off to `/cure` via `handoff_context`; on return, posts per-finding GitHub replies — fixes confirmed, reverts explained, push-backs delivered. Supports `--auto --stake <floor>` for the autonomous chain. Every reply carries an `agent on behalf of;` attribution. Do NOT use to generate fresh review findings — use `/age` instead. Before `/cure`; parallel to `/age`.
license: MIT
---

# /affinage

Use this skill when the user wants to act on external claims about a PR — review comments from humans or bots, plus failing CI checks — and wants those claims graded through the same lens `/age` uses for fresh review, then handed to `/cure` for application.

Do not use it to generate fresh review findings. That is `/age` (your code). `/affinage` only refines claims that already exist on the PR.

The metaphor: an *affineur* evaluates each wheel of cheese by sight / smell / sound and decides its fate. Here the wheels are review comments and CI failures.

## Inputs

```text
/affinage [<pr-ref>] [--auto --stake <floor>] [--hard] [--full] [--include-outdated]
```

`<pr-ref>` accepts a PR number, a full GitHub PR URL, or nothing (auto-detect via `gh pr view --json number` on the current branch).

Flags:

- `--auto --stake <floor>` — autonomous mode. `<floor>` is `blocker`, `high`, `medium+`, or `all` (same semantics as `/cure`). Skips the selection gate, dispatches `/cure --auto --stake <floor>`, posts all replies without prompting.
- `--hard` — propagated metacognitive-gate flag. `/affinage` does not fire the gate; passes `--hard` forward to `/cure` at handoff.
- `--full` — un-collapses `## Low` when ≥10 low-severity findings exist (mirrors `/age --full`).
- `--include-outdated` — include outdated review threads. Default skips them.

## Flow

1. **Resolve PR.** From `<pr-ref>` or `gh pr view --json number` on the current branch. Resolve `<owner>/<repo>` from the git remote.
2. **Fetch PR status.** Call `python3 skills/affinage/scripts/pr-status.py <pr>`. The script returns JSON with build status, per-check failure summaries (last ~10 lines of failed logs + parsed failed-test names), and merge state. If the script exits non-zero, write `status: halt: pr-status-unavailable` and stop.
3. **Fetch comments.**
   - Inline threads: `gh api repos/<owner>/<repo>/pulls/<pr>/comments`. This REST endpoint returns individual review comments without thread-level resolution state, so the skill cannot filter on `isResolved` from this surface; it skips comments whose `position` is `null` (the diff has moved past the anchored line) unless `--include-outdated`. For true unresolved-only filtering, switch to the GraphQL `pullRequest.reviewThreads { isResolved }` endpoint — documented as a future enhancement.
   - Review bodies: `gh api repos/<owner>/<repo>/pulls/<pr>/reviews`. Filter to non-empty bodies. Dedupe against inline comments via `pull_request_review_id`.
4. **Skip already-replied threads.** A thread whose most recent comment is from the resolved GitHub handle (env `RESPOND_GH_HANDLE` → `gh api user --jq .login` → `git config user.name`) has already been responded to; skip it. This keeps re-runs idempotent.
5. **Grade through the age lens.** For each input (comment OR CI failure):
   - Classify dimension from the **code + claim** (or check type + failure summary, for CI items). See `skills/age/references/dimensions.md` for the dimension rubric.
   - Compute severity from base + location + compounding modifiers (same rubric as `/age`).
   - **Ignore reviewer-asserted urgency for severity computation.** Surface `CHANGES_REQUESTED` as metadata (`reviewer-asserted:` line) but do not let it modify computed severity.
   - Bucket into:
     - Standard severity sections (`## Blocker / ## High / ## Medium / ## Low`) when the claim maps to a dimension and the diff grounds it.
     - `## Needs-investigation` when the claim is plausible but requires evidence outside the diff (e.g., downstream caller in another repo).
     - `## Reviewer-rejected` when the claim maps to no dimension, is ungrounded, or is pure style.
6. **Write report** to `.cheese/affinage/pr-<n>.md` with the four-line handoff slug at the top, then the age-format body plus the two extra sections. See `## Output` below.
7. **Selection gate** (interactive mode). Render the cure-selection table inline using `/cure`'s verbs (`skills/cure/references/selection.md`). Ask via `shared/handoff-gate.md`. On non-empty selection, dispatch `/cure <slug>` with locked `handoff_context:`. On `none` / `Stop`, exit cleanly with the report path.
8. **Post-cure reply posting.** When `/cure` returns, read `.cheese/cure/pr-<n>.md`'s `### Applied` / `### Deferred` sections and post per-finding replies via `shared/post-reply.sh`:
   - **Applied** (with `from-comment:<id>` tag) → `"Fixed — <applied summary>."`
   - **Deferred** (with `from-comment:<id>` tag) → `"Attempted fix reverted — <reason>."`
   - **Reviewer-rejected items** → post the pre-drafted push-back text from the affinage report.
   - **Needs-investigation items** → post `"Human investigating — will follow up."`
   - **CI-sourced findings** (`from-check:<job>` tag) → no reply.

## Sub-agent context gate

`/affinage` keeps dialogue, selection, approval state, and reply posting in the parent context. Spawn a read-only grading sub-agent only when the parent context would balloon:

- Total input count (comments + CI failures) exceeds 10.
- Diff exceeds ~25 KB.
- Threads span more than 5 files.

The sub-agent returns a digest: graded findings table with dimension, severity, grounded-evidence cite, and pre-drafted push-back text for any `Reviewer-rejected` items. The parent owns the report write, selection gate, `/cure` dispatch, and reply posting.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in `skills/age/references/sub-agent-gate.md`.

## Preferred tools and fallbacks

Code search and reading go through cheez-* skills (`/cheez-search`, `/cheez-read`). Beyond cheez-* there are affinage-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR status (build + merge) | `skills/affinage/scripts/pr-status.py` | manual `gh pr checks` + `gh pr view` |
| GitHub fetch | `gh api` | none (skill halts) |
| Reply posting | `shared/post-reply.sh` | none — direct `gh api` calls bypass the `agent on behalf of;` attribution |
| Diff inspection | `delta` | `git diff --unified=3` |

## Output

Write to `.cheese/affinage/pr-<n>.md` with the four-line handoff slug at the top, then the age-style body with two extra sections:

```markdown
status: ok | halt: <one-line reason>
next: cure | done
artifact: <path-to-prior-cure-or-press-report-if-any>
<one-line orientation: what the PR does and what was graded>

# Affinage Report — PR #<n>

## Orientation
<one or two factual sentences about the PR and what was graded>

## PR status
- Build: passing | failing (N jobs)
- Merge: clean | conflicts
- Comments: K unresolved (M skipped as outdated)

## Blocker
- **[from-comment:<id>] [security:blocker]** alice on `src/auth.ts:42` — token parsed without validation.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural
  - reviewer-asserted: changes-requested
  - recommendation: validate `authorization` header; reject with 401 on missing.
- **[from-check:test-suite] [correctness:blocker]** CI job `test-suite` — 3 tests failing in `tests/auth.test.ts`.
  - location: contract · fix-cost-now: contained · fix-cost-later: structural
  - recommendation: re-run after fixing the missing null check.

## High
... (same shape)

## Medium
... (same shape)

## Low
... (same shape; collapsible per --full rules)

## Needs-investigation
- **[from-comment:<id>]** bob on `src/api/users.ts:108` — "might break analytics pipeline."
  - reason: claim plausible but pipeline lives in a different repo; diff cannot confirm.
  - suggested action: human reads `analytics-svc/consumers/users.ts`.

## Reviewer-rejected
- **[from-comment:<id>]** copilot on `src/utils/format.ts:18` — "rename `data` to `lineItems`."
  - reason: pure style; no dimension match.
  - draft reply: "Thanks — leaving `data` as-is; matches the adjacent format-helper pattern. Open to revisiting if the team standardises."

## Confidence
<certain | speculating | don't know> — <one-line justification>

## Next step
Selection prompt rendered inline — pick findings to cure or `none` to stop.
```

Empty severity sections are omitted entirely. `## Needs-investigation` and `## Reviewer-rejected` are omitted when no items land there.

`status: ok` when grading completed; `status: halt: <reason>` when `gh` or `pr-status.py` failed in a way that blocks honest grading. `next: cure` when at least one medium-or-above severity finding exists; `next: done` when none do.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → ship · `/affinage` is parallel to `/age` and feeds the same `/cure`.

After the report lands, render the cure-selection table inline (per `skills/cure/references/selection.md`) and ask via `shared/handoff-gate.md`. Options:

- **Pick findings to fix** — free-text reply using `/age`/`/cure` verbs (`1,3,5`, `all-blocker`, `all-high`, `cheap`, `all`, `none`, `skip N`).
- **Fix every blocker** — equivalent to `all-blocker`.
- **Fix blockers and high-severity findings** *(recommended when at least one blocker or high-severity finding exists)* — equivalent to `all-high`.
- **Stop — leave the report for later** — equivalent to `none`.

On non-empty selection, immediately dispatch `/cure <slug>` with locked context:

```yaml
handoff_context:
  source_skill: /affinage
  source_report: .cheese/affinage/pr-<n>.md
  selection: "<verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` re-confirms cited ids and goes straight to apply. `/affinage` resumes when `/cure` returns to post replies.

### Auto mode

When invoked with `--auto --stake <floor>`:

- Skip the selection gate.
- Auto-select every finding (comment-sourced OR CI-sourced) whose severity meets the floor.
- Dispatch `/cure --auto --stake <floor>`.
- After `/cure --auto` and its downstream `/age --scope --auto` chain settle, post replies for the originally graded items only. Do NOT re-grade for findings discovered by `/age --scope`.
- Reviewer-rejected items: post the pre-drafted push-back.
- Needs-investigation items: post the human-investigating reply.
- Never invoke `/gh`.

If no findings meet the floor, skip the `/cure` dispatch, post replies for `Reviewer-rejected` + `Needs-investigation` items only, and exit with `status: ok / next: done / "no findings at or above <floor>"`.

### --hard mode

`/affinage` does not fire the `/hard-cheese` gate. It propagates `--hard` forward to `/cure` so the gate can fire at the share-for-review boundary inside `/cure --hard`. See `skills/cure/SKILL.md` `--hard mode`.

## Rules

- Grading is code-grounded, not reviewer-asserted. `CHANGES_REQUESTED` is metadata, not a severity bump.
- Never auto-apply fixes from `/affinage` itself. Fixes go through `/cure`.
- Every posted reply ends with the literal `agent on behalf of;` attribution via `shared/post-reply.sh`. Never call `gh api` directly to post.
- Idempotent re-runs: skip threads where the latest comment is from the resolved handle. The REST `/comments` endpoint does not expose thread resolution, so honest idempotency relies on the latest-comment-from-self heuristic; switch to GraphQL `reviewThreads` if cross-session resolution-state visibility becomes required.
- CI-sourced findings get no reply (no reviewer to notify).
- Do not invoke `/gh`. Opening or updating the PR stays user-triggered.
- Apply the shared voice kernel (`skills/age/references/voice.md`): name confidence as `certain | speculating | don't know`; agree when no findings warrant grading.

## References

- `skills/age/SKILL.md` — review pipeline, dimensions, sub-agent gate, report shape.
- `skills/age/references/dimensions.md` — per-dimension rubrics and severity computation.
- `skills/cure/SKILL.md` — apply pipeline, `--auto --stake` floors, handoff context shape.
- `skills/cure/references/selection.md` — selection verbs and composition.
- `shared/handoff-gate.md` — gate primitives.
- `shared/post-reply.sh` — reply posting with `agent on behalf of;` attribution.
- `skills/affinage/scripts/pr-status.py` — PR status fetcher.
