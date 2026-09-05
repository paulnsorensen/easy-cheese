# Classification reference

Intent shapes for `/cheese`, with the signals that drive each one and the disambiguation rules that resolve ambiguity.

## Clarity check (implementation intents)

For a `cook` intent, classification feeds Cook's fast-path check.
This check drives the three-tier escalation in `skills/cheese/SKILL.md`.
A `mold` intent skips this check and reaches `/mold`'s user mode.

Use `clarify` only for the tier-3 path.
Use it when the fast-path check fails before and after tier 2.
Also use it when intent confidence stays below `medium` after the silent Culture pass.

Every other intent bypasses the clarity check and dispatches directly.
The `ultracook` compatibility invocation resolves to `/cook` without the clarity check.

## Shape index

| Intent | Pre-step | Target |
| --- | --- | --- |
| clarify | one host-routed question | re-enter `/cheese` |
| research | — | `/briesearch` |
| rubber-duck | — | `/culture` (only when the user explicitly opted out of writes) |
| mold | optional `/briesearch` | `/mold` → `/cook` |
| cook | — | `/cook --auto` (default — propagates through `/press → /age → /cure`) |
| debug | — | `/pasteurize --auto` (default) → `/cook --auto` |
| affinage | — | `/affinage` |
| age | — | `/age` |
| age-then-cure | — | `/age` → `/cure` |
| ultracook (retired) | — | `/cook` (compatibility redirect) |
| plate | — | `/plate` |

## Signal table

### clarify

Use when classification confidence falls below `medium`, or critical facts are missing.

| Signal | Example |
| --- | --- |
| `$ARGUMENTS` is empty or a single word | `/cheese`, `/cheese help` |
| Pronoun-only reference with no recent context | "fix it", "review that" |
| Two strong but conflicting signals | spec path **and** PR url in one prompt |
| Mentioned file/spec/slug does not exist | path that fails a bounded file read |

Ask one question. Re-enter `/cheese` with the answer.

### research (`/briesearch`)

External-evidence questions where the answer is not in the working tree.

| Signal | Example |
| --- | --- |
| Names a library / framework / API / CLI | "what does the Stripe SDK do for idempotency keys" |
| Comparison or recommendation question | "best rate limiter library", "compare X vs Y" |
| Asks about current vendor state | "is library X still maintained" |
| "Before I implement…" framing | "before I implement, what's the right approach" |

Defer to `/briesearch` even when the user did not say "research" — the router's job is to recognise the shape.

### rubber-duck (`/culture`)

The user has explicitly requested discussion without production writes, code, or pull requests.
This path is narrow.
For all other cases, `/culture` runs silently during step 1 of `/cheese`.

| Signal | Example |
| --- | --- |
| "no writes" / "just thinking" / "rubber duck this" / "let's just talk about X" | "let's rubber-duck whether to split this slice — don't write anything" |
| Explicit "discuss only" framing | "I want to think about this with you before we touch code" |

If the user dropped a debug or implementation signal *and* asked for discussion only, the rubber-duck signal wins — they opted out of writes. If the conversation later reveals real work, `/culture` itself recommends `/mold` or `/cook`.

`/culture` is otherwise the agent's internal-thinking skill — invoked silently by `/cheese` (and other workflow skills) to model the problem before dispatching. Never route to it as a user-facing target unless the rubber-duck signal is present.

### mold (`/mold`)

Fuzzy idea or multi-module feature where a spec is the right next artifact.

| Signal | Example |
| --- | --- |
| Feature description without acceptance criteria | "add dark mode", "support webhooks" |
| Touches more than one module or introduces a new public seam | "a new authn flow across web + worker" |
| Asks for a spec, plan, or design doc | "shape this into a spec", "design X" |
| Issue reference whose body is itself a fuzzy idea | `#87` with "we should support…" body |

Optional pre-step: route `/briesearch` first when the user calls out external evidence as missing.

### cook (`/cook`)

Clear, scoped implementation request that passes Cook's standalone fast-path check.

`/cook` owns that check. Read it at [`../../cook/SKILL.md`](../../cook/SKILL.md) section Standalone fast-path.
Do not restate the check here. The signals below only recognize the shape.

| Signal | Example |
| --- | --- |
| Spec path under `.cheese/specs/` | `.cheese/specs/dark-mode.md` |
| Single-file fix with named function or test | "make `tail` count bytes correctly when no trailing newline" |
| A request that passes Cook's standalone fast-path check | the check in `skills/cook/SKILL.md` |

Downgrade to `mold` when any part of Cook's check is borderline.

Before a tier-1 `cook` dispatch, run the specification discovery check in `skills/cheese/references/escalation.md`.
Reuse a matching specification instead of writing a duplicate.

### debug (`/pasteurize --auto` → `/cook --auto`)

Symptom-driven work with no confirmed cause. The user expects a code-level fix.

| Signal | Example |
| --- | --- |
| Stack trace pasted in `$ARGUMENTS` | `TypeError: ...` block |
| Failing test name or output | "test_foo_handles_empty fails on main" |
| Reproduction steps without a stated cause | "open page, click X, see 500" |
| "Why is X broken" / "what's wrong with Y" framing | — |
| Visual / behavioural bug with a clear repro | "flash of white between two clips" with a file path |

Route to `/pasteurize` to identify the cause, add a regression test, and apply the minimum fix.
`/pasteurize` then hands off through `/cook`, `/press`, `/age`, and `/cure`.
When the cause and a single-file fix are clear, route directly to `/cook`.
Route a debug signal to `/culture` only when the user requests no writes.

### affinage (`/affinage`)

Requests about the review feedback that a pull request already carries.
Match this shape before the generic pull request rules below.

| Signal | Example |
| --- | --- |
| Asks to answer or act on review comments | "respond to the PR comments", "handle the review feedback" |
| Names failing CI on an open pull request | "fix the failing build on PR#142" |
| Names merge conflicts on an open pull request | "resolve the conflicts and reply" |

`/affinage` triages the existing comments, the failing checks, and the conflicts.
It accepts a pull request number or a full GitHub pull request URL.
It uses the current branch when the input names no pull request.
Route to `/age` instead when the user wants a fresh review of the diff.

### age (`/age`)

Review-only requests against a diff, branch, PR, or scoped path.
A pull request reference with no review-feedback signal belongs here, not to `affinage`.

| Signal | Example |
| --- | --- |
| PR reference (`PR#142`, GitHub PR URL) | — |
| File path or glob with review verb | "review `src/auth/**`", "check `login.ts`" |
| "Is this safe to merge" / "find bugs" / "review this" | — |
| Commit ref / branch range | `main..HEAD`, `<sha>...HEAD` |

`/age` writes a report; it does not fix. `/cheese` does not pre-bind `/cure` unless the user asked for fixes.

### age-then-cure (`/age` → `/cure`)

Review request that explicitly asks for fixes too.

| Signal | Example |
| --- | --- |
| "Review and fix" / "find and fix" | — |
| Existing `.cheese/age/<slug>.md` plus "act on the findings" | `/cure` may be the direct target if the report is fresh |
| CI failure with multiple unrelated findings | route to `/age` first to scope, then `/cure` |

If a fresh `.cheese/age/<slug>.md` already exists and the user only wants fixes, target `/cure <slug>` directly without re-running `/age`.

### plate (`/plate`)

Use for staging and committing, opening or updating an ordinary PR, or creating, syncing, or submitting a PR stack. A direct new-PR request routes here; `/plate` owns the explicit-choice and review-shape topology policy.

## Disambiguation rules

When two intents are plausible, apply in order:

1. **Explicit verb wins.** "Review" → `age`. "Fix" → `cook` or `cure`. "Design" → `mold`. "Commit", "publish", or "stack PRs" → `plate`. "Respond to comments" or "fix the build" on a pull request → `affinage`.
2. **Strongest signal wins.** A spec path beats free text. A stack trace beats a feature description. A PR URL beats a path glob.
3. **Smallest committed scope wins.** Prefer `cook` over `mold` when the fast-path checks pass. Only prefer `culture` over `mold` when the user has explicitly opted out of writes.
4. **If still tied, clarify.** Ask one question; do not guess.

## Confidence cues

| Cue | Effect on confidence |
| --- | --- |
| Path / slug / PR URL resolves cleanly | +1 step (toward `high`) |
| User uses an explicit cheese verb (`mold`, `cook`, `age`, `cure`, `culture`, `briesearch`, `plate`) | +1 step |
| Two competing signals of similar strength | -1 step |
| Referenced artifact does not exist on disk | downgrade to `clarify` |
| Recent context contradicts the new signal | -1 step, lean on the question pattern in `coherence-check.md` |

## Examples

| `$ARGUMENTS` | Intent | Reason |
| --- | --- | --- |
| `.cheese/specs/dark-mode.md` | cook | spec path resolves; fast-path obvious |
| `add dark mode to the web client` | mold | feature scope, no spec, multi-module likely |
| `PR#142` | age | PR reference, no fix verb |
| `respond to the review comments on PR#142` | affinage | review-feedback verb on a pull request |
| `fix the failing build on PR#142` | affinage | failing checks on an open pull request |
| `review and fix the high-severity items in PR#142` | age-then-cure | review verb + fix verb + PR ref |
| stack trace pasted | debug | trace present, cause not stated |
| `what's the best rate limiter library for fastify` | research | external library question |
| `help me think about splitting orders into a sub-slice — don't write anything yet` | rubber-duck | explicit no-writes opt-out |
| `help me think about splitting orders into a sub-slice` | mold | fuzzy multi-module idea; agent thinks via `/culture` internally, then routes to `/mold` |
| `commit this but do not push` | plate | commit-only transaction |
| `open a PR` | plate | publication request; plate resolves topology from explicit choice and review shape |
| `/cheese` | clarify | empty input; ask what they want |
| `make the cli help flag respect NO_COLOR` | cook | scoped, single-flag, verifiable |
