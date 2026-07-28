# Flow — full command and rationale detail

Read this when executing `## Flow` steps 2, 3, 6, or 9 — the exact CLI invocations, exit-code hints, and bucketing rationale the body's numbered list summarizes.

## Step 2 — Fetch PR status

Call `python3 skills/affinage/scripts/affinage.pyz pr-status <pr>`. The script returns JSON with build status, per-check failure summaries (last ~10 lines of failed logs + parsed failed-test names), and merge state.

- **Exit 3** (`logs-expired`) — the build is failing but every failing check's log was unfetchable (typically expired GitHub Actions logs past the retention window), so there is nothing to ground a CI finding on. Write `status: halt: pr-status-logs-expired` and stop with the hint: *"CI is failing but the logs have expired — rerun the failed jobs (`gh run rerun <run-id> --failed`, where `<run-id>` is the `/actions/runs/<id>/` segment of the failing check's `url`, or read it from `gh pr checks`) and re-invoke `/affinage`."*
- **Any other non-zero** (1 PR/gh API error, 2 missing gh binary) — write `status: halt: pr-status-unavailable` and stop.

## Step 3 — Fresh-window review

Compute the PR diff's `review_surface` score via the `review-surface` CLI (source: `src/fanout/review_surface_cli.py`, wrapping `src/fanout/review_surface.py::score()`) over the diff's git numstat rows. Run it through the `.pyz` bundle — the direct script imports `cli`/`git_utils` from `shared/scripts/`, which are only co-staged flat inside the bundle, so running it directly fails with `ModuleNotFoundError: No module named 'cli'`: `python3 skills/affinage/scripts/affinage.pyz review-surface --repo . <base>...HEAD` — the range must be the PR's full diff against its base branch (after `gh pr checkout <pr>`, `origin/<base>...HEAD`), never the CLI's bare `HEAD` default, which scores only the uncommitted delta. Grep the diff's **added lines outside `skills/**` and `.hallouminate/**`** for `age_route.OVERRIDE_FLAGS` risk flags — a missed token means no promoted lens, not a missing security lens — and call `age_route.route(score=<float>, risk_flags=[...], entry="affinage", comments=<unresolved-thread-count>, ci_class=<"failing"|"red"|"flaky"|None from pr-status>)` — the same router `/age` itself calls, but sized with affinage's comment count and CI failure class so a heavily-commented or red-CI PR gets the bigger fan-out even on a small diff. If the host only ships the bundle, `echo '{"score": <float>, "risk_flags": [...], "entry": "affinage", "comments": <n>, "ci_class": <"failing"|"red"|"flaky"|null>}' | python3 skills/affinage/scripts/affinage.pyz age-route` is the fallback for the router call (JSON on stdin, route JSON on stdout). Pass the returned `n`/`lenses`/`effort` into the `/age` dispatch (so `/age` uses affinage's sizing rather than recomputing from `entry="age"` defaults) and treat each finding as an additional input.

## Step 6 — Grading rationale

- **Build failures count, not just test failures.** A failing check is a finding whether the failure is a compile error, a lint/type-check failure, or a failing test — grade the `build.status: failing` checks from `affinage.pyz pr-status` and route them to `/cure` exactly like test failures. Tag CI-sourced items `[from-check:<job>]`.
- **Fresh `/age` findings** (standalone runs) arrive already dimension-classified and severity-scored; fold them into the buckets tagged `[from-age:<dimension>]`. Dedupe against comment-sourced items echoing the same defect — keep the comment-sourced one (it carries a reviewer to reply to).
- **Ignore reviewer-asserted urgency for severity computation.** Surface `CHANGES_REQUESTED` as metadata (`reviewer-asserted:` line) but do not let it modify computed severity.
- Bucket into:
  - Standard severity sections (`## Blocker / ## High / ## Medium / ## Low`) when the claim is grounded in the diff and its fix is **contained** (`fix-cost-now: contained` — roughly a few lines or a localized refactor). Every such item still maps to a dimension and carries a `[<dimension>:<severity>]` tag — a style or quality nit maps to `deslop` (e.g. `[deslop:low]`). The rule is to route these grounded, contained-fix nits to `/cure` (usually as `Low`) instead of `## Reviewer-rejected`, keeping the `[from-comment:<id>]` tag so `/cure`'s reply still reaches the reviewer; a valid cheap nit is cheaper to fix than to argue, so do not push back on it.
  - `## Needs-investigation` when the claim is plausible but requires evidence outside the diff (e.g., downstream caller in another repo).
  - `## Reviewer-rejected` only when the claim is **wrong or ungrounded** (the code is already correct, the reviewer misread it, or there is no real improvement) OR is valid but **a lot of follow-up work** (`fix-cost-now: moderate`/`sprawling` or `fix-cost-later: structural` — a refactor or scope expansion beyond this PR). Reject the wrong ones; defer the expensive ones.

## Step 9 — Reply drafting rules

Post each approved reply with `python3 skills/affinage/scripts/affinage.pyz post-reply` — never a direct `gh api` call, which would bypass the `agent on behalf of <handle>` attribution.
- **Reviewer-rejected items** → the pre-drafted push-back text from the affinage report.
- **Needs-investigation items** → do NOT post a bare acknowledgement. The reply must (a) name the specific evidence that would settle the claim — the regression test, throwaway prototype, or out-of-diff file to read — and (b) state that a follow-up will report the result. Before posting, **offer to run that investigation now**: a regression test via `/pasteurize`, or explore the out-of-diff evidence via `/briesearch`. If run, post a reply carrying the actual outcome; if the user declines, post the explicit `"Needs <named test/exploration> to confirm — will follow up with the result."` note — never a blind "investigating".
- **CI-sourced findings** (`from-check:<job>` tag) and **fresh-review findings** (`from-age:<dimension>` tag) → no reply (no reviewer to notify).
