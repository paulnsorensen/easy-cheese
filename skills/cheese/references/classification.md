# Classification reference

Intent shapes for `/cheese`, with the signals that drive each one and the disambiguation rules that resolve ambiguity. Confidence stays qualitative (`low | medium | high`); only `medium` or better dispatches. `/cheese` dispatches the chosen target immediately; `--safe` is the only switch that gates dispatch behind a confirmation prompt.

## Clarity check (implementation intents)

For `cook` and `mold` intents — and only these — classification feeds into cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md`: clear I/O, bounded scope, obvious verification). All three checks passing means tier 1: write a mini-spec via `/mold`'s agent-invoked mode and dispatch `/cook --auto`. Any check borderline means tier 2: invoke `/culture` and/or `/briesearch` internally, re-check. Still borderline means tier 3: a single targeted host-routed question. The full three-tier escalation lives in `skills/cheese/SKILL.md` § Escalation.

The `clarify` intent below is exclusively the tier-3 path; classify a request as `clarify` when the cook-fast-path check fails twice (input + post-tier-2-refined input) or when intent confidence stays below `medium` after the silent culture pass.

Other intents (`research`, `rubber-duck`, `debug`, `age`, `age-then-cure`, `cheese-factory`) bypass the clarity check and dispatch directly to their target skill — each target owns its own escalation.

## Shape index

| Intent | Pre-step | Target |
| --- | --- | --- |
| clarify | one host-routed question | re-enter `/cheese` |
| research | — | `/briesearch` |
| rubber-duck | — | `/culture` (only when the user explicitly opted out of writes) |
| mold | optional `/briesearch` | `/mold` → `/cook` |
| cook | — | `/cook --auto` (default — propagates through `/press → /age → /cure`) |
| debug | — | `/pasteurize --auto` (default) → `/cook --auto` |
| age | — | `/age` |
| age-then-cure | — | `/age` → `/cure` |
| cheese-factory | — | `/cheese-factory` |

## Signal table

### clarify

Use when classification confidence falls below `medium`, or critical facts are missing.

| Signal | Example |
| --- | --- |
| `$ARGUMENTS` is empty or a single word | `/cheese`, `/cheese help` |
| Pronoun-only reference with no recent context | "fix it", "review that" |
| Two strong but conflicting signals | spec path **and** PR url in one prompt |
| Mentioned file/spec/slug does not exist | path that fails `cheez-read` |

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

The user has explicitly asked for discussion only — no production writes, no code, no PRs. This is a narrow path; in all other cases, agent reasoning happens silently via `/culture` during step 1 of `/cheese` and never surfaces to the user.

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

Clear, scoped implementation request meeting the standalone fast-path checks.

| Signal | Example |
| --- | --- |
| Spec path under `.cheese/specs/` | `.cheese/specs/dark-mode.md` |
| Single-file fix with named function or test | "make `tail` count bytes correctly when no trailing newline" |
| All three of: clear inputs/outputs, bounded scope, obvious verification | the cook fast-path checklist |

When two of the three fast-path checks are clear but the third is borderline, downgrade to `mold`.

### debug (`/pasteurize --auto` → `/cook --auto`)

Symptom-driven work where the cause has not been confirmed yet and a code-level fix is expected.

| Signal | Example |
| --- | --- |
| Stack trace pasted in `$ARGUMENTS` | `TypeError: ...` block |
| Failing test name or output | "test_foo_handles_empty fails on main" |
| Reproduction steps without a stated cause | "open page, click X, see 500" |
| "Why is X broken" / "what's wrong with Y" framing | — |
| Visual / behavioural bug with a clear repro | "flash of white between two clips" with a file path |

Route to `/pasteurize` so the cause is named via a deterministic feedback loop, the regression test is written, and the minimal fix is applied. `/pasteurize` then hands off forward into the standard `/cook → /press → /age → /cure` chain. If the cause is already obvious **and** the fix is a single-file tweak with a known seam, jump straight to `/cook` instead. Only route a debug signal to `/culture` when the user explicitly opted out of writes (see the rubber-duck shape).

### age (`/age`)

Review-only requests against a diff, branch, PR, or scoped path.

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

## Disambiguation rules

When two intents are plausible, apply in order:

1. **Explicit verb wins.** "Review" → `age`. "Fix" → `cook` or `cure`. "Design" → `mold`. "Think through with no writes" → `culture`; "think through" alone is just the agent's internal reasoning before dispatching to `mold` or `cook`.
2. **Strongest signal wins.** A spec path beats free text. A stack trace beats a feature description. A PR URL beats a path glob.
3. **Smallest committed scope wins.** Prefer `cook` over `mold` when the fast-path checks pass. Only prefer `culture` over `mold` when the user has explicitly opted out of writes.
4. **If still tied, clarify.** Ask one question; do not guess.

## Confidence cues

| Cue | Effect on confidence |
| --- | --- |
| Path / slug / PR URL resolves cleanly | +1 step (toward `high`) |
| User uses an explicit cheese verb (`mold`, `cook`, `age`, `cure`, `culture`, `briesearch`) | +1 step |
| Two competing signals of similar strength | -1 step |
| Referenced artifact does not exist on disk | downgrade to `clarify` |
| Recent context contradicts the new signal | -1 step, lean on the question pattern in `coherence-check.md` |

## Examples

| `$ARGUMENTS` | Intent | Reason |
| --- | --- | --- |
| `.cheese/specs/dark-mode.md` | cook | spec path resolves; fast-path obvious |
| `add dark mode to the web client` | mold | feature scope, no spec, multi-module likely |
| `PR#142` | age | PR reference, no fix verb |
| `review and fix the high-severity items in PR#142` | age-then-cure | review verb + fix verb + PR ref |
| stack trace pasted | debug | trace present, cause not stated |
| `what's the best rate limiter library for fastify` | research | external library question |
| `help me think about splitting orders into a sub-slice — don't write anything yet` | rubber-duck | explicit no-writes opt-out |
| `help me think about splitting orders into a sub-slice` | mold | fuzzy multi-module idea; agent thinks via `/culture` internally, then routes to `/mold` |
| `/cheese` | clarify | empty input; ask what they want |
| `make the cli help flag respect NO_COLOR` | cook | scoped, single-flag, verifiable |
