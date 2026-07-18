---
name: affinage
description: Triage a PR's review comments and failing CI (plus merge conflicts) through the /age lens, deciding which claims are worth acting on. Use when the user says "respond to PR comments", "handle review feedback", "affinage the PR", "/affinage <pr>", "fix the failing build", "resolve the conflicts and respond". Do NOT use for a bare diff with no PR (route to /age).
license: MIT
metadata: {dispatches-agents: true}
---

# /affinage

Use this skill when the user wants to act on external claims about a PR — review comments from humans or bots, plus failing CI checks and merge conflicts — and wants those claims graded through the same lens `/age` uses for fresh review, then handed to `/cure` for application.

`/affinage` always refines the claims that already exist on the PR (comments, CI failures, conflicts). Whether it *also* generates fresh `/age` findings depends on how it was reached:

- **Standalone** — the user typed `/affinage <pr>` directly, with no upstream `handoff_context`. The PR diff has not been reviewed in this session, so `/affinage` runs `/age` over it and folds the findings into the same report (unless `--no-age`).
- **Chained** — reached from `/cook` or `/cure` with a `handoff_context`. `/age` already ran in that chain, so `/affinage` skips the fresh pass to avoid double-grading and only refines existing claims.

See `## Fresh-window review` for the detection rule and `## Merge-conflict resolution` for the conflict path.

## Inputs

```text
/affinage [<pr-ref>] [--auto --stake <floor>] [--plate] [--safe] [--open-pr] [--hard] [--full] [--include-outdated]
```

`<pr-ref>` accepts a PR number, a full GitHub PR URL, or nothing (auto-detect via `gh pr view --json number` on the current branch).

Flags:

- `--auto --stake <floor>` — autonomous mode. `<floor>` is `blocker`, `high`, `medium+`, or `all` (same semantics as `/cure`). Skips the selection gate, dispatches `/cure --auto --stake <floor>`, posts all replies without prompting.
- `--safe` — also gate the cure-selection and merge-conflict-resolution steps (which otherwise run autonomously by default). Reply posting is **gated by default regardless of this flag** — only `--auto` posts without prompting. Use `--safe` when you also want to choose before anything is fixed or a conflict is resolved.
- `--open-pr` — allow affinage's terminal `/plate` to open a *new* PR when none exists (otherwise plate only updates the already-open one).
- `--plate` — one-shot publish combo, equivalent to `--auto --stake medium+ --open-pr`: autonomously triage, cure the recommended floor (medium-and-above plus cheap contained-fix lows), post every reply, then plate. Because it carries `--auto`, replies post without prompting. An explicit `--stake <floor>` overrides the `medium+` default.
- `--hard` — propagated metacognitive-gate flag. `/affinage` does not fire the gate; passes `--hard` forward to its terminal `/plate` at publication.
- `--full` — un-collapses `## Low` when ≥10 low-severity findings exist (mirrors `/age --full`).
- `--include-outdated` — include outdated review threads. Default skips them.
- `--no-age` — skip the standalone fresh `/age` pass. No effect when chained (the pass is already skipped). Use when you only want to triage existing comments, CI failures, and conflicts.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Flow

1. **Resolve PR.** From `<pr-ref>` or `gh pr view --json number` on the current branch. Resolve `<owner>/<repo>` from the git remote.
2. **Fetch PR status.** Call `python3 skills/affinage/scripts/affinage.pyz pr-status <pr>`. The script returns JSON with build status, per-check failure summaries (last ~10 lines of failed logs + parsed failed-test names), and merge state. Map the exit code:
   - **Exit 0** — proceed with grading.
   - **Exit 3** (`logs-expired`) — the build is failing but every failing check's log was unfetchable (typically expired GitHub Actions logs past the retention window), so there is nothing to ground a CI finding on. Write `status: halt: pr-status-logs-expired` and stop with the hint: *"CI is failing but the logs have expired — rerun the failed jobs (`gh run rerun <run-id> --failed`, where `<run-id>` is the `/actions/runs/<id>/` segment of the failing check's `url`, or read it from `gh pr checks`) and re-invoke `/affinage`."*
   - **Any other non-zero** (1 PR/gh API error, 2 missing gh binary) — write `status: halt: pr-status-unavailable` and stop.
   - **Merge conflicts.** If `merge.mergeable` is `CONFLICTING` or `merge.state` is `DIRTY`, the PR has unresolved conflicts. Resolve them before grading — see `## Merge-conflict resolution`.
3. **Fresh-window review.** If this is a standalone run and `--no-age` was not passed, run `/age` over the PR diff before grading and treat each finding as an additional input. See `## Fresh-window review`.
4. **Fetch comments.**
   - Inline threads: `gh api repos/<owner>/<repo>/pulls/<pr>/comments`. This REST endpoint returns individual review comments without thread-level resolution state, so the skill cannot filter on `isResolved` from this surface; it skips comments whose `position` is `null` (the diff has moved past the anchored line) unless `--include-outdated`.
   - Review bodies: `gh api repos/<owner>/<repo>/pulls/<pr>/reviews`. Filter to non-empty bodies. Dedupe against inline comments via `pull_request_review_id`.
5. **Skip already-replied threads.** A thread whose most recent comment is from the resolved GitHub handle (see §Rules) has already been responded to; skip it. The same resolved handle is rendered in the reply footer as `agent on behalf of <handle>`.
6. **Grade through the age lens.** For each input (comment, CI/build failure, OR fresh `/age` finding):
   - Classify dimension from the **code + claim** (or check type + failure summary, for CI items). See `../age/references/dimensions.md` for the dimension rubric.
   - **Build failures count, not just test failures.** A failing check is a finding whether the failure is a compile error, a lint/type-check failure, or a failing test — grade the `build.status: failing` checks from `affinage.pyz pr-status` and route them to `/cure` exactly like test failures. Tag CI-sourced items `[from-check:<job>]`.
   - **Fresh `/age` findings** (standalone runs) arrive already dimension-classified and severity-scored; fold them into the buckets below tagged `[from-age:<dimension>]`. Dedupe against comment-sourced items echoing the same defect — keep the comment-sourced one (it carries a reviewer to reply to).
   - Compute severity from base + location + compounding modifiers (same rubric as `/age`).
   - **Ignore reviewer-asserted urgency for severity computation.** Surface `CHANGES_REQUESTED` as metadata (`reviewer-asserted:` line) but do not let it modify computed severity.
   - Bucket into:
     - Standard severity sections (`## Blocker / ## High / ## Medium / ## Low`) when the claim is grounded in the diff and its fix is **contained** (`fix-cost-now: contained` — roughly a few lines or a localized refactor). Every such item still maps to a dimension and carries a `[<dimension>:<severity>]` tag — a style or quality nit maps to `deslop` (e.g. `[deslop:low]`). The new rule is to route these grounded, contained-fix nits to `/cure` (usually as `Low`) instead of `## Reviewer-rejected`, keeping the `[from-comment:<id>]` tag so `/cure`'s reply still reaches the reviewer; a valid cheap nit is cheaper to fix than to argue, so do not push back on it.
     - `## Needs-investigation` when the claim is plausible but requires evidence outside the diff (e.g., downstream caller in another repo).
     - `## Reviewer-rejected` only when the claim is **wrong or ungrounded** (the code is already correct, the reviewer misread it, or there is no real improvement) OR is valid but **a lot of follow-up work** (`fix-cost-now: moderate`/`sprawling` or `fix-cost-later: structural` — a refactor or scope expansion beyond this PR). Reject the wrong ones; defer the expensive ones.
7. **Write report** to `.cheese/affinage/pr-<n>.md` with the four-line handoff slug at the top, then the age-format body plus the two extra sections. See `## Output` below.
8. **Act or ask** — per §Handoff.
9. **Draft non-cure replies, then gate before posting** (runs whenever grading produced these items, with or without `/cure`). **Never post blind** — posting requires the reply-approval gate (§Handoff) by default, or `--auto`. Draft each reply, then post approved ones via `python3 skills/affinage/scripts/affinage.pyz post-reply`:
   - **Reviewer-rejected items** → the pre-drafted push-back text from the affinage report.
   - **Needs-investigation items** → do NOT post a bare acknowledgement. The reply must (a) name the specific evidence that would settle the claim — the regression test, throwaway prototype, or out-of-diff file to read — and (b) state that a follow-up will report the result. Before posting, **offer to run that investigation now**: a regression test via `/pasteurize`, or explore the out-of-diff evidence via `/briesearch`. If run, post a reply carrying the actual outcome; if the user declines, post the explicit `"Needs <named test/exploration> to confirm — will follow up with the result."` note — never a blind "investigating".
   - **CI-sourced findings** (`from-check:<job>` tag) and **fresh-review findings** (`from-age:<dimension>` tag) → no reply (no reviewer to notify).

10. **Post-cure reply posting** (only when `/cure` ran). The chained `/cure` applies its fixes and runs its `/age --scope` loop but returns **without plating** (it owns no publication in the `/affinage` chain). When `/cure` returns, read `.cheese/cure/pr-<n>.md`'s `### Applied` / `### Deferred` sections and post per-finding replies via `python3 skills/affinage/scripts/affinage.pyz post-reply`:
    - **Applied** (with `from-comment:<id>` tag) → `"Fixed — <applied summary>."`
    - **Deferred** (with `from-comment:<id>` tag) → `"Attempted fix reverted — <reason>."`

11. **Plate** — the final writes above (steps 9–10) must land before publication. Once every approved reply is posted, and only when the cure applied ≥1 fix (there is something to publish), dispatch terminal `/plate [--open-pr] [--hard] [--safe]` to commit and publish cure's fixes to the PR. `/affinage` owns this dispatch; publication lands after all replies. After publication lands, run the **§ Post-PR learnings write-back** (`../cure/SKILL.md` § Handoff) — affinage owns terminal `/plate`, so it owns the write-back the chained `/cure` suppressed. Skip plate and write-back when no fix was applied — there is nothing to publish.

## Fresh-window review

Detection: standalone = no upstream `handoff_context`; chained = a `handoff_context` with `source_skill: /cook` or `/cure`. Behaviour:

- **Standalone** (and `--no-age` not passed): run `/age <pr-ref>` over the PR diff. Fold each returned finding into the affinage report's severity sections tagged `[from-age:<dimension>]`. They flow to `/cure` with every other selected finding and get **no** GitHub reply — there is no reviewer to notify, same as `[from-check:…]` items.
- **Chained**, or `--no-age`: skip the pass. Re-running `/age` on an already-reviewed diff double-grades.

Run the fresh `/age` before grading external claims so a comment that merely echoes an `/age` finding can be deduped. To keep the parent context lean, run the pass under the same sub-agent gate as grading (`## Sub-agent context gate`).

## Merge-conflict resolution

When `affinage.pyz pr-status` reports `merge.mergeable: CONFLICTING` or `merge.state: DIRTY`, the PR cannot merge until conflicts are resolved. `/affinage` does not resolve conflicts by hand — it routes to `/melt`, which runs the structural cascade (mergiraf → rerere → kdiff3).

1. Materialise the conflicts locally: `gh pr checkout <pr>`, then `git merge origin/<base>`. (`gh pr checkout` neither opens nor updates the PR, so it does not breach the no-`/gh` rule.)
2. Hand off to `/melt`. It first checks for squash-merge residue and stops with remedies if found — surface those verbatim and do not auto-apply.
3. After `/melt` resolves cleanly, the resolution commit is owned by `/melt` / `/cure`. `/plate` owns the verified commit and existing-PR update transaction.

- **Default and `--auto` mode**: run the checkout + `/melt` automatically before dispatching `/cure`, then re-run `affinage.pyz pr-status` to confirm `mergeable` cleared. If `/melt` cannot resolve (manual kdiff3 needed, or squash residue), write `status: halt: merge-conflicts-need-human` and stop.
- **`--safe` mode**: gate the checkout + `/melt` behind the handoff prompt — offer "Resolve merge conflicts" alongside the cure-selection options.

## Sub-agent context gate

`/affinage` keeps dialogue, selection, approval state, and reply posting in the parent context. When the parent context would balloon, resolve a fresh read-only `reviewer` through the shared agent resolver. A compatible reviewer is preferred; a general worker qualifies only with prompt-only no-write enforcement and `degraded: true`:

- Total input count (comments + CI failures) exceeds 10.
- Diff exceeds ~25 KB.
- Threads span more than 5 files.

The sub-agent returns a digest: graded findings table with dimension, severity, confidence, grounded-evidence cite, and pre-drafted push-back text for any `Reviewer-rejected` items. The parent owns the report write, selection gate, `/cure` dispatch, and reply posting.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in `../age/references/sub-agent-gate.md`.

## Preferred tools and fallbacks

Code search and reading go through `cheez-*` skills (`/cheez-search`, `/cheez-read`). Beyond `cheez-*` there are affinage-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR status (build + merge) | `skills/affinage/scripts/affinage.pyz pr-status` | manual `gh pr checks` + `gh pr view` |
| GitHub fetch | `gh api` | none (skill halts) |
| Reply posting | `skills/affinage/scripts/affinage.pyz post-reply` | none — direct `gh api` calls bypass the `agent on behalf of <handle>` attribution |
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

Per-finding `confidence:` uses the voice-kernel scale (`../age/references/voice.md` § Reasoning posture): `certain` — the defect is verified by direct evidence (diff/code read, command output); `speculating` — inferred from indirect signal. A `don't know` grading never ships as a severity row — route it to `## Needs-investigation`.

`status: ok` when grading completed; `status: halt: <reason>` when `gh` or `pr-status.py` failed in a way that blocks honest grading. `next:` is set per §Handoff — `cure` when ≥1 finding meets the `medium+` floor; `done` otherwise.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate · `/affinage` is parallel to `/age` and feeds `/cure`.

After the report lands, affinage acts by default and asks only on a genuine reason (a sprawling/structural fix in the recommended set, conflicting findings) or under `--safe` (Flow step 8). What it acts on depends on whether any severity-section finding exists.

**When at least one severity-section finding exists (any severity, including `Low`)** — compute the recommended composite (`all-medium, cheap`). With no reason to ask and no `--safe`: announce the one-line selection, dispatch `/cure` (below), then render the **reply-approval gate** before posting the non-cure replies (Flow step 9) and the cure-dependent replies (step 10) — never post blind. `--auto` posts without the gate (§Auto mode). On a reason to ask or `--safe`: render the cure-selection table inline (per `../cure/references/selection.md`) and ask via `../cheese/references/handoff-gate.md`, pre-selecting the recommended composite and flagging heavy rows. Lead with the recommended composite, then present the four severity-floor options below it, in the same most-inclusive-to-least order, so the gate is predictable across every run:

- The five severity-floor options (recommended `all-medium, cheap`, then `all`, `all-medium`, `all-high`, `all-blocker`) are exactly age's — see [`../age/SKILL.md`](../age/SKILL.md) § Selection gate for their labels and semantics.

Then offer the non-floor options last:

- **Pick findings to fix** — free-text reply using `/age`/`/cure` verbs (`1,3,5`, `all-blocker`, `all-medium`, `all-high`, `cheap`, `all`, `none`, `skip N`).
- **Resolve merge conflicts** *(offered only when the PR has conflicts)* — checkout + `/melt` per `## Merge-conflict resolution`, then re-render this gate.
- **Stop — leave the report for later** — equivalent to `none`.

The "present all four severity options on every run, empty-set-resolves-to-`none`" rule is age's — see [`../age/SKILL.md`](../age/SKILL.md) § Selection gate.

**When no severity-section finding exists but `Reviewer-rejected` or `Needs-investigation` has items** — `/cure` has nothing to act on, so skip it. Posting is gated by default; render the **reply-approval gate** (below) and post nothing until the user chooses. Only `--auto` posts without this gate.

**Reply-approval gate** — the single gate both Handoff branches use before any `post-reply` call:

- **Post pushbacks only** *(recommended)* — post `Reviewer-rejected` drafts; hold `Needs-investigation` items for investigation.
- **Investigate now, then post** — for each `Needs-investigation` item, run the follow-up investigation (`/pasteurize` for a regression test, `/briesearch` to explore the out-of-diff evidence), then post a reply carrying the actual result.
- **Post all** — post every drafted push-back and the explicit `Needs-investigation` follow-up notes (naming the needed evidence) without running the investigation first.
- **Skip posting** — leave the report for later; post nothing.
- **Per-finding** — free-text pick of which drafts to post or investigate.

After the selection, post the approved replies via Flow step 9. Then — only when the cure applied ≥1 fix — dispatch terminal `/plate` (Flow step 11) so publication follows the replies; when no cure ran or no fix applied, there is nothing to plate. Exit with `status: ok / next: done` — see `## Auto mode` § "no findings meet the floor" for the auto path.

**Slug `next:` values.** Write `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low). Write `next: done` when no severity-section finding exists or all meeting items are empty-selection after floor resolution.

On a non-empty cure selection (auto-selected by default or chosen at the gate), immediately dispatch `/cure <slug> [--safe] [--open-pr] [--hard]` with locked context:

```yaml
handoff_context:
  source_skill: /affinage
  source_report: .cheese/affinage/pr-<n>.md
  selection: "<verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` re-confirms cited ids and goes straight to apply. Because the handoff carries `source_skill: /affinage`, `/cure` applies its fixes and runs its `/age --scope` loop but **suppresses its own terminal `/plate`** and returns — affinage owns publication. Propagate `--safe`, `--open-pr`, and `--hard` to `/cure` when in scope. On return, `/affinage` posts every reply (Flow steps 9–10) — its terminal final writes — and only then dispatches terminal `/plate [--open-pr] [--hard] [--safe]` (Flow step 11), so publication lands after every reply. Skip the plate dispatch when the cure applied no fix.

## Auto mode

When invoked with `--auto --stake <floor>` (or `--plate`, which enters this mode with `--stake medium+ --open-pr`):

- Skip the selection gate.
- If the PR has merge conflicts, resolve them via `/melt` first (see `## Merge-conflict resolution`). If `/melt` cannot resolve, halt with `status: halt: merge-conflicts-need-human` before any `/cure` dispatch.
- If standalone (and `--no-age` not passed), run the fresh `/age` pass so `[from-age:…]` findings join the floor-based auto-selection.
- Auto-select every finding (comment-sourced, CI-sourced, OR fresh-`/age`-sourced) that meets the floor — severity at or above the floor, plus cheap contained-fix lows when the floor is `medium+` (same floor semantics as `/cure`).
- Dispatch `/cure --auto --stake <floor>`.
- After `/cure --auto` and its downstream `/age --scope --auto` chain settle, post replies for the originally graded items only. Do NOT re-grade for findings discovered by `/age --scope`.
- Reviewer-rejected items: post the pre-drafted push-back.
- Needs-investigation items: post the explicit follow-up note naming the evidence that would settle the claim (`"Needs <named test/prototype> to confirm — will follow up with the result."`). Auto mode does not pause to run the spike; it posts the honest follow-up note, never a blind acknowledgement.
- After the cure chain settles and **all** replies are posted (previous two bullets), `/affinage` dispatches terminal `/plate --open-pr [--hard]` to publish cure's fixes — the final writes precede publication. `/cure` suppresses its own terminal `/plate` for the `/affinage` chain (keyed on `source_skill: /affinage`). Skip the dispatch when no fix was applied.

The whole cure chain (cure → `/age --scope --auto` → up to the two-cure-pass cap) must run in the parent affinage context so the post-cure reply step still has the original graded findings (slug, ids, `from-comment:<id>` tags, drafted push-back text) in memory. Spawning the cure chain in a sub-agent breaks reply posting — do not.

If no findings meet the floor, skip the `/cure` dispatch, post replies for `Reviewer-rejected` + `Needs-investigation` items only, and exit with `status: ok / next: done`.

## --hard mode

`/affinage` passes `--hard` to its own terminal `/plate` (dispatched after replies), which fires `/hard-cheese` after verifying the final artifact state. `/cure` does not dispatch plate in the `/affinage` chain, so the gate fires once — at affinage's publication boundary.

## Rules

- Grading is code-grounded, not reviewer-asserted. `CHANGES_REQUESTED` is metadata, not a severity bump.
- Prefer fixing over pushing back. A valid, grounded nit whose fix is contained (`fix-cost-now: contained` — a few lines or a localized refactor) goes to `/cure` as a `Low` finding tagged `[from-comment:<id>]`; do not draft a push-back for it. Reserve `## Reviewer-rejected` for claims that are wrong/ungrounded or whose fix is a lot of work (`moderate`/`sprawling`/`structural`). See `../age/references/voice.md`.
- Never auto-apply fixes from `/affinage` itself. Code fixes go through `/cure`; merge conflicts go through `/melt`.
- Never post a GitHub reply without approval. Reply posting is gated by default (§Handoff reply-approval gate); only `--auto` posts autonomously. A `Needs-investigation` reply must name the follow-up test or exploration and offer to run it (`/pasteurize` or `/briesearch`) before posting — never a blind acknowledgement.
- Fresh `/age` runs only on standalone invocations (no upstream `handoff_context`) and only when `--no-age` is absent. Chained runs never re-review the diff.
- Merge conflicts are resolved through `/melt`, not by hand. `gh pr checkout` to materialise conflicts is allowed — it neither opens nor updates the PR. After resolution, affinage's terminal `/plate` owns the verified commit and push.
- `/affinage` owns terminal publication. The chained `/cure` suppresses its own `/plate` (keyed on `source_skill: /affinage`); after a clean cure, `/affinage` posts every reply and *then* dispatches `/plate` to update the existing PR — or, with `--open-pr`, apply the explicit-choice and review-shape policy before publishing a new PR. Replies always precede plate: no final write lands after publication.
- Every posted reply ends with the literal `agent on behalf of <handle>` attribution via `skills/affinage/scripts/affinage.pyz post-reply`, where `<handle>` is resolved from `RESPOND_GH_HANDLE` → `gh api user --jq .login` → `git config user.name`. Never call `gh api` directly to post.
- Idempotent re-runs: skip threads where the latest comment is from the resolved handle. The REST `/comments` endpoint does not expose thread resolution, so honest idempotency relies on the latest-comment-from-self heuristic; switch to GraphQL `reviewThreads` if cross-session resolution-state visibility becomes required.
- CI-sourced findings get no reply (no reviewer to notify).
- Apply the shared voice kernel (`../age/references/voice.md`): name confidence as `certain | speculating | don't know`; agree when no findings warrant grading.

## References

- `skills/age/SKILL.md` — review pipeline, dimensions, sub-agent gate, report shape.
- `../age/references/dimensions.md` — per-dimension rubrics and severity computation.
- `skills/cure/SKILL.md` — apply pipeline, `--auto --stake` floors, handoff context shape.
- `../cure/references/selection.md` — selection verbs and composition.
- `skills/melt/SKILL.md` — merge-conflict resolution cascade (mergiraf → rerere → kdiff3).
- `../cheese/references/handoff-gate.md` — gate primitives.
- `python3 skills/affinage/scripts/affinage.pyz post-reply` — reply posting with `agent on behalf of <handle>` attribution.
- `python3 skills/affinage/scripts/affinage.pyz pr-status` — PR status fetcher.

## Agent resolution

Resolve each dispatch through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Triage review claims and CI evidence | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |

The canonical affinage report carries the shared `agent_resolution` block.
