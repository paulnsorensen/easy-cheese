# Review dimensions side by side: default angles versus /age rubrics

Prompt-level comparison of what each review sub-agent is told to measure.
Default quotes are verbatim from the Claude Code v2.1.261 binary (`/simplify`
and `/code-review` share one angle table). `/age` quotes are from
`skills/age/references/dimensions.md` at `6dd17839`, with the taste-test lenses
from `skills/cook/references/tdd-loop.md`. Fan-out mechanics are on the sibling
page [review-fanout-policy-comparison](./review-fanout-policy-comparison.md).

## The map

```text
DEFAULT (claude binary)                  OVERLAP AREA          MINE (easy-cheese)
/code-review · /simplify                                       /age · taste-test · /press · /cure
────────────────────────────────         ──────────────        ─────────────────────────────────────
Angle A line-by-line            ─┐
Angle D language pitfalls (xh+)  ├─────▶  1 correctness  ◀──── age:correctness
Angle E wrapper/proxy (xh+)     ─┘
Angle B removed-behavior        ───────▶  2 dropped invariants ◀ age:spec (inherited req) · /press
Angle C cross-file tracer       ───────▶  3 caller impact ◀──── packet Seam 5 · Wired-callers lens · age:encapsulation
Reuse ─────────── Reuse         ───────▶  4 reuse         ◀──── age:nih · age:deslop · Simplify/Reuse lens
Simplification ── Simplification ──────▶  5 simplification ◀─── age:complexity · age:deslop · Simplify/Quality lens
Efficiency ────── Efficiency    ───────▶  6 efficiency    ◀──── age:efficiency · Simplify/Efficiency lens
Altitude ──────── Altitude      ───────▶  7 altitude      ◀──── age:complexity (one sentence) · age:encapsulation
Conventions (CLAUDE.md)         ───────▶  8 conventions   ◀──── (none)
Sweep for gaps (xh+)            ───────▶  9 gap pass      ◀──── (none)
1-vote verifier per candidate   ───────▶ 10 verification  ◀──── Seam 6 verifier (n>1 only) · "default to refuted"
--fix · simplify Phase 2        ───────▶ 11 apply         ◀──── /cure: locked rec · proving test · gates · taste-test
(none)                          ◀──────  security · spec · assertions · telemetry · encapsulation/crust
                                          Production-path · Locked-decision · Scope lenses · /press
```

## 1. Correctness

**Default, Angle A (medium and above):**

> Read every hunk in the diff, line by line. Then Read the enclosing function for each hunk — bugs in unchanged lines of a touched function are in scope (the PR re-exposes or fails to fix them). For every line ask: what input, state, timing, or platform makes this line wrong? Look for inverted/wrong conditions, off-by-one, null/undefined deref, missing `await`, falsy-zero checks, wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

**Default, Angle D (xhigh and max):**

> Scan for the classic pitfalls of the diff's language/framework — for example: JS falsy-zero, `==` coercion, closure-captured loop var; Python mutable default args, late-binding closures; Go nil-map write, range-var capture; SQL injection; timezone/DST drift; float equality. Flag any instance the diff introduces.

**Default, Angle E (xhigh and max):**

> When the PR adds or modifies a type that wraps another (cache, proxy, decorator, adapter): check that every method routes to the wrapped instance and not back through a registry/session/global — e.g. a caching provider holding a `delegate` field that resolves IDs via `session.get(...)` instead of `delegate.get(...)` will re-enter the cache or recurse. Also check that the wrapper forwards all the methods the callers actually use.

**/age `correctness` (`dimensions.md:142-156`):**

> Look for off-by-one errors, ordering errors, null/empty edge cases, silent failures, races, contradictory branches, and lost writes.

Base tiers: blocker for data loss, corruption, shared-state races, lost writes, or irreversible side effects on wrong input; high for wrong data, misordered results, or silent failure without recovery; medium for a recoverable flow mishandling a rare null or empty input; low for cosmetic edge cases in leaf code. Plus: "The diff's new path can exercise an existing race, lost write, or contradictory branch in the caller graph. Expand callers one level before grading clean." Recommendation shapes: "Add a guard for X", "Return early when Y", "Replace `catch (_)` with explicit handling".

**Difference.** The default has the sharper procedure: read the enclosing function, ask the four-way "what makes this line wrong" question per line, and at xhigh apply a per-language pitfall catalog and a wrapper-recursion check. `/age` has severity, location, and the one-level caller expansion, but a thinner checklist and no language catalog on the correctness side (its per-language catalogs are slop catalogs under `deslop`).

## 2. Removed behavior and dropped invariants

**Default, Angle B:**

> For every line the diff DELETES or replaces, name the invariant or behavior it enforced, then search the new code for where that invariant is re-established. If you can't find it, that's a candidate: a removed guard, a dropped error path, a narrowed validation, a deleted test that was covering a real case.

**/age:** `spec` (`dimensions.md:209-227`) carries one sentence: "The diff can inherit a requirement that an earlier commit dropped without restoring or violating it. Compare the diff against the spec." `/press` hunts deleted test coverage on the test side only.

**Difference.** The default is a mechanical per-deletion procedure that needs no spec. `/age` only catches a dropped invariant when a located spec names it, and grades `spec` as `don't know` when no source resolves.

## 3. Caller impact

**Default, Angle C:**

> For each function the diff changes, find its callers (Grep for the symbol) and check whether the change breaks any call site: a new precondition, a changed return shape, a new exception, a timing/ordering dependency. Also check callees: does a parallel change in the same PR make a call unsafe?

**/age:** the orchestrator computes callers once through `tilth_deps` plus the semantic caller search and ships them in the packet (Seam 5, `skills/age/references/fan-out.md`). `encapsulation` checks import direction and crust integrity against `sliced-bread.md`. The taste-test Wired-callers lens requires "a non-test caller exists, or the diff carries an explicit 'wired in phase X' note".

**Difference.** Roughly even. The default's per-call-site question is sharper. `/age` is cheaper (evidence computed once, not per worker) and broader (crust and import direction), but never asks "does this call site break".

## 4. Reuse

**Default (shared by `/simplify` and `/code-review`):**

> Flag new code that re-implements something the codebase already has — Grep shared/utility modules and files adjacent to the change, and name the existing helper to call instead.

**/age `nih` (`§ nih`):**

> Look for hand-rolled retry/validation/UUID/debounce/date-parse/argparse/deep-equality/sanitizer when an import exists. Look for in-project utility duplication.

Base tiers: high for reinvented logging, telemetry, concurrency primitives, or crypto; medium for retry, debounce, validation, or UUID; low for a small stdlib utility. Plus: "Check imports and the helper set before grading clean." `deslop` adds "Look for a reimplementation of an existing repository utility." Packet component 3 pre-indexes helper names (`sanitize`, `validate`, `escape`, `retry`, `logger`) across the source roots.

**Difference.** `/age`, clearly. The default is one instruction with on-demand grep. `/age` tiers by what was reinvented and pre-computes the helper index so five workers do not grep the same tree.

## 5. Simplification

**Default:**

> Flag unnecessary complexity the diff adds: redundant or derivable state, copy-paste with slight variation, deep nesting, dead code left behind. Name the simpler form that does the same job.

**/age `complexity` (`§ complexity`):**

> Look for functions over budget: 40 lines, 4 parameters, or 3 nesting levels. Look for files over 300 lines that grew. Look for speculative abstractions, redundant state, parameter sprawl, and stringly-typed code. Look for explanatory-renaming comments. Look for special cases layered on shared infrastructure when generalising the underlying mechanism costs less. Treat this as a bandaid-depth fix. Also look for abstractions whose interfaces cost more than they hide.

Base tiers: high for a god function at 3x budget, parameter sprawl through 3+ layers, a new god module, or a shallow layer; medium for 2x budget, a one-user generic helper, redundant cached state, a pass-through method, or a pass-through variable threaded through 3+ layers; low for a few lines over budget. Guard: "The budget is a smell trigger, not a target. Do not split a coherent function into shallow pieces just to stay under 40 lines." Nine recommendation shapes, including "Keep `<function>` whole — the split to meet budget fragments one abstraction".

**/age `deslop` (`§ deslop`):** dead code; AI signatures (generic catch, empty docstring, placeholder comments); duplicated logic where a helper exists; vague or container-typed names; abbreviated identifiers whose scope exceeds about ten lines; false module boundaries; lint suppressions that hide the real fix; edge-case branches for an input nobody can name; test bloat; partial shell strict mode. Per-language catalogs in `deslop-{rust,typescript,python,shell,go}.md`.

**Difference.** `/age`, by a wide margin. The default's four nouns are a subset of `complexity` alone. `/age` adds numeric budgets, layer-depth rules, the anti-over-splitting guard, naming rules with a citation, lint-suppression residue, and five language catalogs.

## 6. Efficiency

**Default:**

> Flag wasted work the diff introduces: redundant computation or repeated I/O, independent operations run sequentially, blocking work added to startup or hot paths. Also flag long-lived objects built from closures or captured environments — they keep the entire enclosing scope alive for the object's lifetime (a memory leak when that scope holds large values); prefer a class/struct that copies only the fields it needs. Name the cheaper alternative.

**/age `efficiency` (`§ efficiency`):**

> Look for unnecessary work, missed concurrency, hot-path bloat, and no-op updates. Look for TOCTOU pre-checks and memory leaks. Look for long-lived objects built from closures that capture the enclosing scope. Such captures keep the whole scope alive. Prefer a type that copies only the fields it needs. Look for overly broad reads.

Base tiers: blocker for an unbounded cache or queue, a listener or timer leak, or retained references after teardown; high for blocking work on a per-request, startup, or per-render path or N+1 on a high-traffic endpoint; medium for N+1 on a moderate endpoint; low for redundant compute outside hot paths. Plus: "Check whether the changed path runs hot or long-running before grading clean."

**Difference.** Slight edge to `/age`. The enumerations are nearly identical, closure-capture paragraph included; `/age` adds the blocker tier for unbounded growth and the hot-path check.

## 7. Altitude

**Default:**

> Check that each change fixes the root cause at the right depth rather than patching a symptom with a fragile bandaid. Special cases layered on shared infrastructure are a sign the fix isn't deep enough — prefer the simpler, more general change to the underlying mechanism over adding special cases, and name that change.

**/age:** one sentence inside `complexity` ("Look for special cases layered on shared infrastructure when generalising the underlying mechanism costs less. Treat this as a bandaid-depth fix.") and, in `encapsulation`, "Check whether the producer could absorb error, default, or configuration decisions instead of exporting them." No taste-test lens asks it.

**Difference.** Default. The default makes altitude a first-class question every review asks. `/age` has it as a sub-clause of two dimensions and no recommendation shape names "the more general change".

## 8. Conventions

**Default:**

> Find the CLAUDE.md files that govern the changed code: the user-level ~/.claude/CLAUDE.md, the repo-root CLAUDE.md, plus any CLAUDE.md or CLAUDE.local.md in a directory that is an ancestor of a changed file (a directory's CLAUDE.md only applies to files at or below it). Read each one that exists, then check the diff for clear violations of the rules they state. Only flag a violation when you can quote the exact rule and the exact line that breaks it — no style preferences, no vague "spirit of the doc" inferences. In the finding, name the CLAUDE.md path and quote the rule so the report can cite it. If no CLAUDE.md applies, return nothing for this angle.

**/age:** nothing. No file under `skills/age/`, `skills/cure/`, `skills/cook/references/tdd-loop.md`, `~/.claude/agents/reviewer.md`, or `~/.claude/agents/taste-tester.md` mentions CLAUDE.md or AGENTS.md. The nearest check is glossary naming drift under `deslop` via `.cheese/glossary/<slug>.md`.

**Difference.** Default only. A real gap: the global CLAUDE.md carries eight numbered rules and `AGENTS.md` carries the bundle doctrine, and no reviewer quotes either.

## 9. Gap sweep

**Default (xhigh and max):**

> Run one more finder as a fresh reviewer who has the verified list. Re-read the diff and enclosing functions looking ONLY for defects not already listed. Do not re-derive or re-confirm anything already there — the job is gaps. Focus on what the first pass tends to miss: moved/extracted code that dropped a guard or anchor; second-tier footguns (dataclass default evaluated once, `hash()` non-determinism, lock-scope shrink, predicate methods with side effects); setup/teardown asymmetry in tests; config defaults flipped. Surface up to 8 additional candidates, each naming a defect not already on the list. If nothing new, return an empty sweep — do not pad.

**/age:** none. Coverage comes from the lens partition plus "Report every defect, however minor" (`skills/age/SKILL.md § Flow` step 3).

**Difference.** Default only, at the top two effort levels.

## 10. Verification

**Default verdicts:**

> **CONFIRMED** — can name the inputs/state that trigger it and the wrong output or crash. Quote the line.
> **PLAUSIBLE** — mechanism is real, trigger is uncertain (timing, env, config). State what would confirm it.
> **REFUTED** — factually wrong (code doesn't say that) or guarded elsewhere. Quote the line that proves it.

High and above add: "PLAUSIBLE by default — do not refute a candidate for being 'speculative' or 'depends on runtime state' when the state is realistic: concurrency races, nil/undefined on a rare-but-reachable path (error handler, cold cache, missing optional field), falsy-zero treated as missing, off-by-one on a boundary the code does not exclude, retry storms / partial failures, regex/allowlist that lost an anchor. These are PLAUSIBLE. REFUTED only when constructible from the code: factually wrong (quote the actual line); provably impossible (type/constant/invariant — show it); already handled in this diff (cite the guard); or pure style with no observable effect."

One verifier agent per deduped candidate, at every level from medium up.

**/age:** Seam 6 (`fan-out.md`) runs only at n>1: a cheap verifier at low effort, batches of up to ten claims, one result object per claim with confirm, downgrade-or-drop, or escalate. Escalated claims go under `## Confidence` and never appear as finding rows. At n=1 the only filter is the reviewer agent's own rule: "Default to refuted: drop a candidate you cannot make concrete, or label it a question outside the findings schema."

**Difference.** Mixed. `/age` has the richer outcome (a severity downgrade instead of binary keep/drop) and never ships an unsettled claim. The default verifies small diffs too and is deliberately recall-biased at high; `/age` at n=1 is precision-biased with no second opinion.

## 11. Apply

**Default, `/simplify` Phase 2:**

> Wait for all four agents to complete, dedup findings that point at the same line or mechanism, and fix each remaining one directly. Skip any finding whose fix would change intended behavior, require changes well outside the reviewed diff, or that you judge to be a false positive — note the skip rather than arguing with it.

`/code-review --fix` applies the reported findings the same way after the review.

**/age to /cure:** `/age` never edits (review lock). `/cure` selects by severity floor or locked ids, implements each `recommendation:` as the locked decision, runs the narrowest proving test per fix and then the project gates, runs the fresh-context taste test whose Locked-decision lens halts on a silent substitution, records rebuttals under `### Deferred`, and re-dispatches `/age` on the touched paths.

**Difference.** `/age` on discipline, default on speed. The default has no equivalent of the proving-test rule, the rebuttal record, or the re-review.

## Only in /age

| Dimension | "Look for" | Blocker row |
| --- | --- | --- |
| `security` (`dimensions.md:158-175`) | authN/authZ holes, injection, secrets in source/logs/URLs, tainted inputs reaching dangerous sinks, crypto missteps | injection, authn bypass, secrets in source, RCE, plaintext secrets on the wire |
| `spec` (`dimensions.md:209-227`) | behavior in the spec but not the diff, in the diff but not the spec, renamed concepts, relocated boundaries, missing acceptance criteria | silent drift on a security, data, or correctness requirement the spec fixes |
| `encapsulation` (`dimensions.md:177-205`) | cross-module access to internals, leaked implementation types, excess-context parameters, new exports without a use case, crust deltas the Placement block did not name, invariants lifted from their producer | a public API leaks an ORM model, infra adapter, framework type, or storage internal; a slice `index` re-exports an internal type |
| `assertions` (`§ assertions`) | existence assertions instead of equality, catch-any-error, no-crash-as-success, mocked SUT, time/random/external coupling | the test mocks the SUT or asserts the bug as correct |
| `telemetry` (`§ telemetry`) | silent error branches on non-interactive paths, outbound calls without observability, silent daemons, hand-rolled logging, missing correlation IDs, `print()` in production, high-cardinality labels | (no blocker row; high for silent non-interactive failure paths) |

Plus the taste-test lenses Spec/Drift, Readability, Scope, Production path, Wired callers, and Locked decision, and `/press` for adversarial test hardening. The default has no counterpart for any of these.

## Only in the default

Conventions (CLAUDE.md), the gap sweep, Angle D language pitfalls, Angle E wrapper/proxy, model-keyed effort cells, `--comment` inline GitHub posting, the `ReportFindings` host UI, and the cloud `ultra` review.

## Finding-shape contract

| Field | Default finders | `/age` |
| --- | --- | --- |
| Location | `file`, `line` | `path:line` or `path:start-end` in backticks |
| Claim | `summary`, one sentence | claim after the em dash on the bullet line |
| Failure evidence | `failure_scenario`: "concrete inputs/state → wrong output/crash"; for cleanup angles, the concrete cost instead | `confidence: certain \| speculating`; `don't know` is never a row |
| Kind | `category` slug: correctness, simplification, efficiency, reuse, altitude, conventions | `[<dimension>:<severity>]` tag |
| Severity | none, ordered "most-severe first" | computed tier |
| Cost | none | `location`, `fix-cost-now`, `fix-cost-later` |
| Fix | none (the parent decides) | `recommendation:` in a per-dimension shape, treated by `/cure` as the locked decision; optional `invariants:` |
| Verifier trace | `verdict` when a verify pass ran | verifier reasoning in the `## Confidence` trail |

_Source: binary string extraction and Skill load of Claude Code v2.1.261; `skills/age/references/dimensions.md` and `skills/cook/references/tdd-loop.md` at `6dd17839`; PR #667 · Updated: 2026-09-12_
