---
name: affinage
description: Triage a PR's review comments and failing CI (plus merge conflicts) through the /age lens, deciding which claims are worth acting on. Use when the user says "respond to PR comments", "handle review feedback", "affinage the PR", "/affinage <pr>", "fix the failing build", "resolve the conflicts and respond". Do NOT use for a bare diff with no PR (route to /age).
license: MIT
metadata: {dispatches-agents: true}
---

# /affinage

Act on external claims about a PR — review comments from humans or bots, plus failing CI checks and merge conflicts — grading them through the same lens `/age` uses for fresh review, then handing them to `/cure` for application.

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

- `--auto --stake <floor>` — autonomous mode; `<floor>` (`blocker`, `high`, `medium+`, `all`) matches `/cure`'s semantics. Skips selection, dispatches `/cure --auto --stake <floor>`, posts replies without prompting. Mechanics: `references/auto-mode.md`.
- `--safe` — also gates cure-selection and merge-conflict resolution (autonomous by default). Reply posting is **gated by default regardless** — only `--auto` skips it.
- `--open-pr` — let terminal `/plate` open a *new* PR when none exists (else it only updates the open one).
- `--plate` — one-shot publish combo = `--auto --stake medium+ --open-pr`: triage, cure the recommended floor, post every reply, then plate. An explicit `--stake <floor>` overrides `medium+`.
- `--hard` — propagated metacognitive-gate flag; forwarded to terminal `/plate`, not fired here.
- `--full` — un-collapses `## Low` when ≥10 low-severity findings exist (mirrors `/age --full`).
- `--include-outdated` — include outdated review threads (default: skip).
- `--no-age` — skip the standalone fresh `/age` pass; no effect when chained.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Flow

Exact CLI invocations, exit-code hints, and grading rationale for steps 2, 3, 6, and 9 below: `references/flow-details.md`.

1. **Resolve PR.** From `<pr-ref>` or `gh pr view --json number`; resolve `<owner>/<repo>` from the git remote.
2. **Fetch PR status.** `affinage.pyz pr-status <pr>`. Exit 3 halts `status: halt: pr-status-logs-expired`; any other non-zero halts `status: halt: pr-status-unavailable`. Conflicting/dirty merge state routes to `## Merge-conflict resolution` before grading. Exit-code detail: `references/flow-details.md`.
3. **Fresh-window review.** Standalone and `--no-age` not passed: score the PR diff, route it through `age_route.route(...)` sized with affinage's comment count and CI failure class, run `/age` with the returned `n`/`lenses`/`effort`, and fold each finding tagged `[from-age:<dimension>]`. See `## Fresh-window review`.
4. **Fetch comments.** Inline threads: `gh api repos/<owner>/<repo>/pulls/<pr>/comments` (REST; no thread-resolution state, so skip `position: null` comments unless `--include-outdated`). Review bodies: `gh api repos/<owner>/<repo>/pulls/<pr>/reviews`, filtered to non-empty bodies, deduped against inline comments via `pull_request_review_id`.
5. **Skip already-replied threads.** A thread last-commented by the resolved GitHub handle (§Rules) is already answered — skip it; the footer renders as `agent on behalf of <handle>`.
6. **Grade through the age lens.** Classify each input (comment, CI failure, or fresh `/age` finding) by dimension — code/claim, or check type/failure for CI — per `../age/references/dimensions.md`, and by severity (base + location + compounding, same rubric as `/age`); ignore reviewer-asserted urgency (`CHANGES_REQUESTED` is metadata, never a severity bump). Bucket into severity sections (contained fixes), `## Needs-investigation` (needs out-of-diff evidence), or `## Reviewer-rejected` (wrong/ungrounded, or a lot of follow-up work). Full bucketing criteria: `references/flow-details.md`.
7. **Write report** to `.cheese/affinage/pr-<n>.md`: four-line handoff slug, then the age-format body plus two extra sections. See `## Output`.
8. **Act or ask** — per §Handoff.
9. **Draft non-cure replies, then gate before posting** (whenever grading produced these items, with or without `/cure`). Never post blind — requires the reply-approval gate (§Handoff), or `--auto`. Draft per `references/flow-details.md`; post approved ones via `affinage.pyz post-reply`. CI-sourced (`from-check:<job>`) and fresh-review (`from-age:<dimension>`) findings get no reply.
10. **Post-cure reply posting** (only when `/cure` ran). Once `/cure` returns, read `.cheese/cure/pr-<n>.md`'s `### Applied`/`### Deferred` and post per-finding replies via `affinage.pyz post-reply`: **Applied** (`from-comment:<id>`) → `"Fixed — <applied summary>."`; **Deferred** (`from-comment:<id>`) → `"Attempted fix reverted — <reason>."`
11. **Plate** — once every approved reply is posted (steps 9–10) and the cure applied ≥1 fix, dispatch terminal `/plate [--open-pr] [--hard] [--safe]`; publication lands after every reply. After it lands, run the **§ Post-PR learnings write-back** (`../cure/SKILL.md` § Handoff) — affinage owns the write-back the chained `/cure` suppressed. Skip plate and write-back when no fix was applied.

## Fresh-window review

Standalone runs (see intro) compute the `entry="affinage"` router call (Flow step 3) and run `/age <pr-ref>` over the PR diff, passing the router's `n`/`lenses`/`effort` so `/age` doesn't recompute a smaller `entry="age"` sizing from the diff alone. Fold each returned finding into the report's severity sections tagged `[from-age:<dimension>]` — they flow to `/cure` like any other finding but get no GitHub reply (no reviewer to notify, same as `[from-check:…]` items).

Run the fresh pass before grading external claims so an echoing comment can be deduped, under the same sub-agent gate as grading (`## Sub-agent context gate`) to keep the parent context lean.

## Merge-conflict resolution

When `pr-status` reports unresolved conflicts, `/affinage` routes to `/melt` (mergiraf → rerere → kdiff3) rather than resolving by hand. Default/`--auto` run checkout + `/melt` automatically before `/cure`; `--safe` gates it behind the handoff prompt. If `/melt` cannot resolve, write `status: halt: merge-conflicts-need-human` and stop. Full steps: `references/merge-conflict.md`.

## Sub-agent context gate

`/affinage` keeps dialogue, selection, approval state, and reply posting in the parent context. When the parent context would balloon — inputs exceed 10, diff exceeds ~25 KB, or threads span more than 5 files — resolve a fresh read-only `reviewer` through the shared agent resolver (a general worker qualifies only with `degraded: true`). The sub-agent returns a digest of graded findings (dimension, severity, confidence, evidence cite, pre-drafted push-back for `Reviewer-rejected` items); the parent owns the report write, selection gate, `/cure` dispatch, and reply posting. Digest size and selection detail: `../age/references/sub-agent-gate.md`.

## Preferred tools and fallbacks

Call source-code search/read backends per [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Affinage-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR status (build + merge) | `skills/affinage/scripts/affinage.pyz pr-status` | manual `gh pr checks` + `gh pr view` |
| GitHub fetch | `gh api` | none (skill halts) |
| Reply posting | `skills/affinage/scripts/affinage.pyz post-reply` | none — direct `gh api` calls bypass the `agent on behalf of <handle>` attribution |
| Diff inspection | `delta` | `git diff --unified=3` |

## Output

Write to `.cheese/affinage/pr-<n>.md`: the four-line handoff slug, then the age-style body plus two extra sections (`## PR status` and the same severity / `## Needs-investigation` / `## Reviewer-rejected` shape `/age` uses). Full annotated template: `references/report-template.md`.

```markdown
status: ok | halt: <one-line reason>
next: cure | done
artifact: <path-to-prior-cure-or-press-report-if-any>
<one-line orientation: what the PR does and what was graded>
```

Empty severity sections are omitted; so are `## Needs-investigation`/`## Reviewer-rejected` when empty. `status: ok` when grading completed; `halt: <reason>` when `gh`/`pr-status` failed. `next:` per `## Handoff` § Slug `next:` values.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate · `/affinage` is parallel to `/age` and feeds `/cure`.

Default: affinage acts without asking, and asks only for a genuine reason (a sprawling/structural fix in the recommended set, conflicting findings) or under `--safe` (Flow step 8).

- **Severity-section findings exist (any severity, including `Low`)** — compute the recommended composite (`all-medium, cheap`). No reason to ask and no `--safe`: announce the selection, dispatch `/cure` with the locked `handoff_context` (shape: `references/handoff-templates.md` § Cure dispatch context), then render the **reply-approval gate** before posting (Flow steps 9–10) — never post blind. A reason to ask, or `--safe`: render the **cure-selection gate** per `../cheese/references/handoff-gate.md` instead, pre-selecting the composite and flagging heavy rows. `--auto` skips both gates (`## Auto mode`).
- **No severity-section findings, but `Reviewer-rejected`/`Needs-investigation` items exist** — nothing for `/cure` to act on; render the reply-approval gate and post nothing until chosen. Only `--auto` skips it.

After the selection, post approved replies (Flow step 9–10), then — only when the cure applied ≥1 fix — dispatch terminal `/plate [--open-pr] [--hard] [--safe]` (Flow step 11); publication lands after every reply. Exit `status: ok / next: done` when there is nothing to act on.

**Slug `next:` values.** `cure` when ≥1 finding meets the `medium+` floor; `done` when no severity-section finding exists or all meeting items resolve to an empty selection.

## Auto mode

Skips the selection gate. Resolves merge conflicts via `/melt` first (halt `status: halt: merge-conflicts-need-human` if unresolved). If standalone, runs the fresh `/age` pass. Auto-selects every finding meeting `<floor>` (`--plate` enters this mode at `--stake medium+ --open-pr`) and dispatches `/cure --auto --stake <floor>`; once its chain settles, posts replies for the originally graded items only, then dispatches terminal `/plate --open-pr [--hard]` once every reply posts (skipped if no fix applied). If no findings meet the floor: skip `/cure`, post rejection/investigation replies only, exit `status: ok / next: done`. Full mechanics: `references/auto-mode.md`.

## --hard mode

`/affinage` passes `--hard` to its terminal `/plate`, which fires `/hard-cheese` after verifying the final artifact state. `/cure` never dispatches plate in this chain, so the gate fires once — at affinage's publication boundary.

## Rules

- Grading is code-grounded, not reviewer-asserted — see Flow step 6.
- Prefer fixing over pushing back. A grounded nit with a contained fix goes to `/cure` as `Low`; reserve `## Reviewer-rejected` for claims that are wrong, ungrounded, or a lot of work (Flow step 6, `../age/references/voice.md`).
- Never auto-apply fixes itself — code fixes go through `/cure`, merge conflicts through `/melt` (`## Merge-conflict resolution`).
- Never post a reply without approval — see the reply-approval gate (`## Handoff`, `references/handoff-templates.md`).
- Every posted reply ends with the literal `agent on behalf of <handle>` attribution via `skills/affinage/scripts/affinage.pyz post-reply`, where `<handle>` is resolved from `RESPOND_GH_HANDLE` → `gh api user --jq .login` → `git config user.name`. Never call `gh api` directly to post.
- Idempotent re-runs rely on the latest-comment-from-self heuristic (Flow step 5) — the REST `/comments` endpoint exposes no thread resolution state; use GraphQL `reviewThreads` if cross-session resolution state is ever needed.
- Apply the shared voice kernel (`../age/references/voice.md`): name confidence as `certain | speculating | don't know`; agree when no findings warrant grading.

## References

Affinage-local, each also routed inline above: `references/flow-details.md`, `references/merge-conflict.md`, `references/report-template.md`, `references/handoff-templates.md`, `references/auto-mode.md`. `sub-agent-gate.md` is `../age/references/sub-agent-gate.md` (shared, not affinage-local).

Scripts: `skills/affinage/scripts/affinage.pyz post-reply` (reply posting), `pr-status` (PR status fetcher).

## Agent resolution

Resolve each dispatch through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Triage review claims and CI evidence | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |

The canonical affinage report carries the shared `agent_resolution` block.
