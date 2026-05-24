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
2. **Fetch PR status.** Call `python3 ${CLAUDE_SKILL_DIR}/scripts/affinage.pyz pr-status <pr>`. The script returns JSON with build status, per-check failure summaries (last ~10 lines of failed logs + parsed failed-test names), and merge state. Map the exit code:
   - **Exit 0** — proceed with grading.
   - **Exit 3** (`logs-expired`) — the build is failing but every failing check's log was unfetchable (typically expired GitHub Actions logs past the retention window), so there is nothing to ground a CI finding on. Write `status: halt: pr-status-logs-expired` and stop with the hint: *"CI is failing but the logs have expired — rerun the failed jobs (`gh run rerun <run-id> --failed`, where `<run-id>` is the `/actions/runs/<id>/` segment of the failing check's `url`, or read it from `gh pr checks`) and re-invoke `/affinage`."* Affineurs often run a few days after a PR opens, so this is routine, not an edge case.
   - **Any other non-zero** (1 PR/gh API error, 2 missing gh binary) — write `status: halt: pr-status-unavailable` and stop.
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
7. **Selection gate** (interactive mode). Branch on what graded out:
   - **At least one `Blocker` / `High` / `Medium` finding.** Render the cure-selection table inline using `/cure`'s verbs (`skills/cure/references/selection.md`). Ask via `shared/handoff-gate.md`. On non-empty selection, **first run step 8** to post any drafted push-backs / investigating notes — they don't depend on cure's outcome, so they must reach GitHub even if `/cure` later halts or the session is interrupted — then dispatch `/cure <slug>` with locked `handoff_context:` and post the cure-dependent replies (step 9) when `/cure` returns. On `none` / `Stop`, run step 8 for any drafted push-backs / investigating notes, then exit with the report path.
   - **No medium-or-above findings, but `Reviewer-rejected` or `Needs-investigation` has items.** Skip `/cure` dispatch entirely — there is nothing to apply. Render a small gate that lets the user pick `post all`, `post pushbacks only`, `skip posting`, or per-finding choices. On the selection, run step 8 to post the chosen replies. Exit with `status: ok / next: done`. This mirrors the documented auto-mode "no findings meet the floor" branch (see `### Auto mode`) so interactive and auto behave the same.
   - **Nothing graded into any section.** Exit cleanly with the report path; there is nothing to post or cure.
8. **Post non-cure replies** (runs whenever grading produced these items, with or without `/cure`). Post via `shared/post-reply.sh`:
   - **Reviewer-rejected items** → post the pre-drafted push-back text from the affinage report.
   - **Needs-investigation items** → post `"Human investigating — will follow up."`
   - **CI-sourced findings** (`from-check:<job>` tag) → no reply.

   Decoupling this from `/cure` is deliberate: drafted push-backs and investigating notes must reach GitHub even when no medium-or-above finding exists and `/cure` never runs — otherwise the drafted reply is write-only, useful to the human reading the report but invisible to the reviewer waiting on GitHub.
9. **Post-cure reply posting** (only when `/cure` ran). When `/cure` returns, read `.cheese/cure/pr-<n>.md`'s `### Applied` / `### Deferred` sections and post per-finding replies via `shared/post-reply.sh`:
   - **Applied** (with `from-comment:<id>` tag) → `"Fixed — <applied summary>."`
   - **Deferred** (with `from-comment:<id>` tag) → `"Attempted fix reverted — <reason>."`

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
| PR status (build + merge) | `${CLAUDE_SKILL_DIR}/scripts/affinage.pyz pr-status` | manual `gh pr checks` + `gh pr view` |
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

After the report lands, the gate depends on whether any medium-or-above finding exists (Flow step 7).

**When at least one `Blocker` / `High` / `Medium` finding exists** — render the cure-selection table inline (per `skills/cure/references/selection.md`) and ask via `shared/handoff-gate.md`. Options:

- **Pick findings to fix** — free-text reply using `/age`/`/cure` verbs (`1,3,5`, `all-blocker`, `all-high`, `cheap`, `all`, `none`, `skip N`).
- **Fix every blocker** — equivalent to `all-blocker`.
- **Fix blockers and high-severity findings** *(recommended when at least one blocker or high-severity finding exists)* — equivalent to `all-high`.
- **Stop — leave the report for later** — equivalent to `none`.

**When no medium-or-above finding exists but `Reviewer-rejected` or `Needs-investigation` has items** — `/cure` has nothing to act on, so skip it and render a reply-only gate instead:

- **Post all** *(recommended)* — post every drafted push-back and human-investigating note.
- **Post pushbacks only** — post `Reviewer-rejected` drafts; skip `Needs-investigation` notices.
- **Skip posting** — leave the report for later; post nothing.
- **Per-finding** — free-text pick of which drafts to post.

On the selection, post via Flow step 8 and exit with `status: ok / next: done`. This mirrors the documented auto-mode "no findings meet the floor" branch (see `### Auto mode`).

On a non-empty cure selection, immediately dispatch `/cure <slug>` with locked context:

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

The whole cure chain (cure → `/age --scope --auto` → up to the two-cure-pass cap) must run in the parent affinage context so the post-cure reply step still has the original graded findings (slug, ids, `from-comment:<id>` tags, drafted push-back text) in memory. Same in-session-memory contract as `/age --auto`'s two-pass cap. Spawning the cure chain in a sub-agent silently breaks reply posting — do not.

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
- `${CLAUDE_SKILL_DIR}/scripts/affinage.pyz pr-status` — PR status fetcher.
