# Review dimensions

Each dimension has its own rubric.

Dimensions answer **what kind of problem**. Severity answers **how bad this one is**. The two stay orthogonal.

## Severity vocabulary

Four tiers, in order:

```
blocker > high > medium > low
```

| Tier | Meaning |
| --- | --- |
| `blocker` | Do not merge — contract broken, exposure open, or data at risk |
| `high` | Fix before merge — risk of incident or rework |
| `medium` | Real defect — fix before next release |
| `low` | Annoyance — safe to merge, fix at leisure |

## Severity computation

Each finding's severity is computed, not declared. Three independent contributors, max-merged, capped at `blocker`:

1. **Base** — from the dimension's per-tier rubric (see § Per-dimension rubrics below).
2. **Location bump** — `+1` tier if `location = contract` *and* the dimension is location-sensitive (see § Location sensitivity).
3. **Compounding bump** — `+1` tier if `fix-cost-later = structural`.

Do not compute the formula in-head — invoke `shared/scripts/severity.py compute`:

```bash
python3 shared/scripts/severity.py compute \
    --dimension <dim> --base <low|medium|high|blocker> \
    --location <class|module|cross-module|contract> \
    --fix-cost-later <contained|spreading|structural>
# -> blocker | high | medium | low
```

Mental shortcut: a class-private encapsulation leak lands `low`; the same leak at a slice's `index` re-export lands `blocker` (base `high` → contract bump → structural fix-cost bump, capped).

## Per-finding fields

Every finding carries these fields:

| Field | Values | Source |
| --- | --- | --- |
| `dimension` | correctness, security, encapsulation, spec, complexity, deslop, assertions, nih, efficiency, telemetry | reviewer-tagged |
| `severity` | `blocker / high / medium / low` | computed (formula above) |
| `location` | `class / module / cross-module / contract` | reviewer-classified |
| `fix-cost-now` | `contained / moderate / sprawling` | bucketed from blast-radius count |
| `fix-cost-later` | `contained / spreading / structural` | reviewer-classified |
| `recommendation` | one-line action | reviewer |

## Location classification

| Tier | Definition |
| --- | --- |
| `class` | Within a single class / type / file's private scope. Caller graph stays inside the file. |
| `module` | Within a single module / slice. Crosses files but stays inside the slice's internal namespace. |
| `cross-module` | Reaches into another module's internals (bypasses the public index/crust). |
| `contract` | Crosses an ingress/egress boundary: slice's public `index` re-exports, HTTP/RPC handler signature, DB schema, language-FFI boundary, plugin extension point, published library API. |

Language-agnostic note: in projects without an explicit public-index layer (flat scripts, no crust / `__init__` re-export surface, as in this repo's `src/melt`, `src/affinage`, `src/mold`, `src/fanout`), treat a direct import of another file's internal function across a directory boundary as `cross-module`, and CLI `argv` / stdin ingress as `contract`.

## Location sensitivity

The `contract` bump only applies to dimensions where boundary position genuinely changes how bad a finding is:

| Dimension | Contract bump? | Why |
| --- | --- | --- |
| correctness | yes | A bug at the contract leaks into every consumer; internal bugs stay contained |
| security | yes | Tainted input crossing a trust boundary is the canonical case |
| encapsulation | yes | The whole dimension is about boundary integrity |
| spec | yes | Spec drift at the API surface contradicts the published contract |
| complexity | no | Complexity grades by function/file shape, not boundary position |
| deslop | no | Dead code is dead code wherever it lives |
| assertions | no | Test quality doesn't change by where the SUT lives |
| nih | yes | Reinventing primitives that cross the boundary is worse than internal helpers |
| efficiency | yes | Hot path on a public handler is the typical blocker shape |
| telemetry | yes | Silent failure on an outbound call (boundary) is the canonical blocker |

## Fix-cost-now

> "How hard would it be to fix this *right now*?"

Bucket the blast-radius file count for the proposed fix. Do not bucket in-head — pipe the raw file/module counts through `shared/scripts/severity.py bucket`:

```bash
python3 shared/scripts/severity.py bucket --files <N> [--modules <M>]
# -> contained | moderate | sprawling
```

Source priority for the raw count:

1. **`tilth_deps`** — primary. Returns the file set that would need to change.
2. **LSP `find-references` / `find-callers`** — fallback when tilth is unavailable.

**Worked recipe.** Given a finding at `path:line`, run `tilth_deps` on the *containing file*. Count the **distinct files** in the imported-by set as `--files` — use the `<N> dependents` header count, since the `Used by` list emits one entry per call site and several entries can map to one file (counting raw entries overcounts). Count the **distinct slice/module roots** among them as `--modules` — the directory immediately under `src/` (so `src/melt` and `src/affinage` are two modules, not the shared `src` parent). Then run `python3 shared/scripts/severity.py bucket --files <N> --modules <M>`. Falling back to LSP callers, count the same way (distinct touched files, distinct module dirs) so buckets stay comparable across tools.

Fix-cost-now is **reported, not bumped**. Severity decides what to fix; fix-cost-now explains effort and lets triage schedule.

## Fix-cost-later (compounding)

> "How much harder does this get if we leave it?"

| Tier | Meaning |
| --- | --- |
| `contained` | Cost stays roughly fixed. A typo in a docstring is the same fix in six months. |
| `spreading` | Cost grows linearly. New code piles onto the bad pattern; each new caller adds one unit of fix work. |
| `structural` | Cost grows non-linearly. Consumers *harden* against the current shape — types get re-exported, mocks calcify, downstream APIs build on the leak. Public-API leaks, DB-schema mistakes, and ingress-contract violations live here. |

**Decision.** `structural` if the changed symbol is re-exported by any consumer or fixing it requires touching a file outside the diff. `spreading` if the fix is local but the diff adds new callers of the bad shape, or the pattern is being copy-pasted. `contained` otherwise. When two tiers apply, take the higher.

Per-dimension `structural` anchors:

| Dimension | `structural` looks like |
| --- | --- |
| correctness | A race or lost write at a public API boundary; consumers harden retry/mock logic around the broken atomicity. |
| security | A taint path through a published signature; every consumer must re-validate once the contract leaks the unsafe shape. |
| encapsulation | A leaked internal type re-exported from a slice `index`; downstream slices build on it. |
| spec | A dropped requirement now baked into downstream behaviour that later code depends on. |
| complexity | A god module new code keeps landing in; each addition compounds the untangling cost. |
| deslop | A duplicated block forked across modules; each copy diverges and multiplies the eventual merge. |
| assertions | A mocked SUT or weak harness other tests copy as the pattern to follow. |
| nih | A reinvented primitive other modules import; replacing it later means migrating every caller. |
| efficiency | An unbounded structure on a long-running path; retained references accumulate as callers grow. |
| telemetry | A hand-rolled logging shape new code standardises on; migrating to the real logger later touches every call site. |

`structural` triggers the compounding `+1` bump in the formula. The point of carrying this tag is to surface "fix now or pay exponentially later" to the user without dressing it up as severity.

## Per-dimension rubrics

Each dimension's base-severity table — *severity-by-violation-shape*, before modifiers. Modifiers (location, compounding) layer on top per the formula.

### correctness

Look for: off-by-one, ordering, null/empty edge cases, silent failures, races, contradictory branches, lost writes.

| Base | Trigger |
| --- | --- |
| `blocker` | Data loss, data corruption, race in shared concurrent state, lost write, irreversible side effect on wrong input |
| `high` | Wrong data returned, ordering bug, silent failure with no recovery path |
| `medium` | Edge case in a flow with a recovery path; null/empty handling that misbehaves on rare input |
| `low` | Cosmetic edge case in well-bounded leaf code |

Inherited shape: a race, lost write, or contradictory branch already present in the caller graph that the diff's new path now exercises. Expand callers one level before grading clean.

Boundaries: telemetry (no-log failure to here), security (access-control to security), deslop (silent-failure claim to here), efficiency (TOCTOU wrong-data to here), spec (contract commitment to spec, runtime risk to here; emit both). Full rules in § Dimension boundaries.

Recommendation shape: "Add a guard for X" / "Return early when Y" / "Replace `catch (_)` with explicit handling".

### security

Look for: authN/authZ holes, injection, secrets in source/logs/URLs, tainted inputs reaching dangerous sinks, crypto missteps.

| Base | Trigger |
| --- | --- |
| `blocker` | Injection (SQL/shell/template/deser), authn bypass, secret in source, RCE, plaintext secret on the wire |
| `high` | Unvalidated input reaches dangerous sink; broken authz on internal route; weak crypto on durable data |
| `medium` | Tainted input reaches limited surface with secondary validation; missing rate-limit on auth-adjacent route |
| `low` | Missing defense-in-depth on already-validated input |

Inherited shape: a tainted-input path or missing authz that predates the diff, where the change only adds a new caller of the unsafe sink. Trace the input to its boundary before grading clean.

Definitions: a *dangerous sink* is any call that executes, queries, renders, deserialises, or persists its argument (SQL/shell exec, template render, `eval` / `pickle` / `yaml.load`, file-path open, request to an internal service). *Secondary validation* is an independent check downstream of the sink's entry that constrains the value (a schema parse, an allowlist, a parameterised query) so the tainted value cannot reach the sink unconstrained.

Boundaries: telemetry (secrets-in-logs to security), correctness (access-control to security), nih (reinvented crypto/sanitizer to security). Full rules in § Dimension boundaries.

Recommendation shape: "Validate at the boundary" / "Use the project's existing `<helper>`" / "Move secret to env or vault".

### encapsulation

Look for: cross-module reach into internals, public APIs leaking implementation types, parameters that take more context than needed, new exports without a use case, and the inverse — a domain invariant lifted *out* of the producer and enforced above it by every caller.

| Base | Trigger |
| --- | --- |
| `blocker` | **Ingress/egress contract violation** — public API leaks ORM model, infra adapter, framework type, or storage internal across the slice boundary; slice's `index` re-exports an internal type |
| `high` | Cross-module reach into another slice's internals, bypassing crust/index |
| `high` | **Caller-shadowed domain invariant** — a guard/validation that all callers must invoke (or redundantly do) lives *outside* the producer; the domain doesn't enforce its own invariant, so a caller can skip it. Especially when a symbol is made public *solely* to be called from above the domain layer. |
| `medium` | Module-internal leak (cross-file inside one slice exposes private detail) |
| `low` | Class-level — one class touches another's private member within the same file |

Detection signals for the caller-shadowed invariant: a guard defined inside a slice but never called by that slice (only by external entrypoints); N callers each repeating the same check before/after one producer; a public/exported guard whose only consumers sit above the domain layer; asymmetry where some callers apply the check and others skip it. Beware the false-clean trap — this often reads as good Sliced-Bread hygiene (a private helper promoted to public + crust-exported), so a diff-scoped pass grades it clean. The violation is usually *inherited*, not introduced by the diff under review.

Boundaries: deslop (misplaced-invariant dup to encapsulation), complexity (boundary-leaking param to encapsulation). Full rules in § Dimension boundaries.

Note: base tier *is* the location tier here, so the contract bump tends to redundantly raise an already-blocker finding (capped).

Recommendation shape: "Import from `<slice>/index` instead of `<slice>/internal/foo`" / "Narrow the public surface to `<minimal-type>`" / "Move the `<invariant>` into `<producer>` so every caller inherits it; drop the external guard and narrow the public surface".

### spec

Look for: behaviour in the spec but not in the diff, behaviour in the diff but not in the spec, renamed concepts or relocated boundaries, missing acceptance criteria.

| Base | Trigger |
| --- | --- |
| `blocker` | Silent drift on a security/data/correctness requirement the spec explicitly nailed down |
| `high` | Behavior contradicts spec |
| `medium` | Acceptance criterion partially implemented |
| `low` | Naming/style drift the user can re-align in 30s |

Inherited shape: a requirement dropped in an earlier commit that the current diff neither restores nor violates outright. Compare against the spec, not only the diff.

Spec resolution: locate the spec before grading. Search order: the durable spec corpus via `python3 shared/scripts/paths.py artifact_path specs <slug>` (or `mold.pyz artifact-path specs <slug>`), falling back to the legacy literal `.cheese/specs/<slug>.md` only when the resolver is unavailable (see `../../cheese/references/formatting.md` § Corpus location; never hardcode `.cheese/specs/`); then unresolved items in `.cheese/press/<slug>.md`, then the PR body or linked issue (`gh pr view`), then a commit-message ticket ref. If none resolves, record "no spec located; searched [list]" and grade spec findings `don't know` rather than clean.

Boundaries: correctness (contract commitment to spec, runtime risk to correctness; emit both). Full rules in § Dimension boundaries.

Recommendation shape: "Restore the X requirement" / "Confirm with the user that Y is intentional" / "Update the spec to reflect Z".

### complexity

Look for: functions over budget (40 lines / 4 params / 3 nesting), files over 300 lines that grew, speculative abstractions, redundant state, parameter sprawl, stringly-typed code, explanatory-renaming comments.

| Base | Trigger |
| --- | --- |
| `high` | God function (3× budget), param sprawl threading through 3+ layers, new god module created in this diff |
| `medium` | 2× budget, generic helper with one user, redundant cached state |
| `low` | Few lines over budget, mildly speculative abstraction |

Inherited shape: a god function or param-sprawl the diff extends by a few lines rather than introduces. Grade the function as it now stands, not only the added lines.

Boundaries: encapsulation (boundary-leaking param to encapsulation), efficiency (cache decision to complexity, runtime cost to efficiency). Full rules in § Dimension boundaries.

No default `blocker` row, but complexity still *reaches* `blocker`: a base `high` finding with `fix-cost-later: structural` takes the `+1` compounding bump to `blocker`. "No blocker row" means no *base* blocker, not that complexity caps at high. (Once criticality returns, the floor may push complexity findings up on `critical`-tier paths.)

Recommendation shape: "Extract `<sub-function>`" / "Inline `<one-call helper>`" / "Derive `<value>` instead of caching" / "Replace `<string>` with `<enum>`" / "Replace `<vague-name>` with `<concrete-name>`".

### deslop

Look for: dead code, AI tells (generic catches, useless docstrings, "// TODO: implement"), duplicated logic, copy-paste-with-variation, vague names.

| Base | Trigger |
| --- | --- |
| `high` | Large duplicated logic with diverging behavior; AI residue actively misshapes flow |
| `medium` | Dead branch left "for reference", duplicated small block, "// TODO: implement" committed |
| `low` | Vague name; single weak copy-paste |

Inherited shape: duplicated logic or a dead branch the diff copies or leaves untouched beside its change. Read the surrounding block, not only the hunk.

Boundaries: correctness (AI-residue claim to deslop, silent-failure to correctness), nih (existing helper to nih), assertions (generic catch in tests to assertions), encapsulation (misplaced-invariant dup to encapsulation). Full rules in § Dimension boundaries.

No default `blocker` row.

Recommendation shape: "Delete dead branch at <line>" / "Reuse `<existing-helper>`" / "Extract shared `<helper>` from the two near-duplicate blocks" / "Rename `data` to `<noun>`".

### assertions

Look for: existence assertions instead of equality, catch-any-error, no-crash-as-success, mocked SUT, time/random/external coupling.

| Base | Trigger |
| --- | --- |
| `blocker` | SUT itself is mocked; test asserts the bug as correct behavior |
| `high` | Test passes when the implementation is wrong (no-crash-as-success) |
| `medium` | Catches generic `Exception`; depends on time/random without bounding |
| `low` | `toBeDefined` where equality is one line away (`assert x is not None` where `assert x == <expected>` is one line away) |

Inherited shape: a weak assertion in a touched-but-unmodified test that the diff's behaviour change now leaves under-covering. Read the touched test bodies, not only the diff hunks.

Boundaries: deslop (generic catch in production to deslop, correctness, or telemetry per the claim), telemetry (asserting on log strings to telemetry). Full rules in § Dimension boundaries.

Recommendation shape: "Replace `toBeTruthy` with `toEqual(<expected>)`" / "Catch `<specific-error>` not `Exception`" / "Replace `assert result` with `assert result == <expected>`" / "Catch `<SpecificError>`, not bare `except:` / `except Exception`".

### nih

Look for: hand-rolled retry/validation/UUID/debounce/date-parse/argparse/deep-equality/sanitizer when an import exists; in-project utility duplication.

| Base | Trigger |
| --- | --- |
| `high` | Reinvented logging/telemetry/concurrency primitives the project already wires; reinvented crypto |
| `medium` | Reinvented retry, debounce, validation, UUID |
| `low` | Reinvented small util the stdlib already has |

Inherited shape: an in-project helper or dependency already does this; the diff re-implements it because the existing one was not visible from the changed file. Check imports and the helper set before grading clean.

Boundaries: deslop (diff-internal dup to deslop), security (crypto/sanitizer to security), telemetry (custom logger to telemetry), efficiency (algorithm choice to efficiency). Full rules in § Dimension boundaries.

No default `blocker` row.

Recommendation shape: "Replace with `<existing-dep>.<fn>`" / "Use the stdlib `<fn>` instead of the local helper" / "Call the existing `<project-helper>` instead of re-implementing".

### efficiency

Look for: unnecessary work, missed concurrency, hot-path bloat, no-op updates, TOCTOU pre-checks, memory leaks, overly broad reads.

| Base | Trigger |
| --- | --- |
| `blocker` | Unbounded cache/queue, listener/timer leak, retained references after teardown — anything that grows without bound in a long-running process |
| `high` | Blocking work on per-request / startup / per-render path; N+1 on a high-traffic endpoint |
| `medium` | N+1 on a moderate endpoint; redundant compute in a non-hot loop |
| `low` | Redundant compute outside hot paths |

Inherited shape: an N+1, unbounded structure, or hot-path cost already present that the diff's new call site now triggers. Check whether the changed path runs hot or long-running before grading clean.

Boundaries: nih (import exists to nih), correctness (TOCTOU wrong-data to correctness), complexity (cache decision to complexity). Full rules in § Dimension boundaries.

Recommendation shape: "Hoist `<call>` out of the loop" / "Run `<a>` and `<b>` in parallel with `Promise.all` (or equivalent)" / "Guard the store write on a value change" / "Drop the existence pre-check; handle the error from `<op>` instead" / "Bound `<structure>` or add cleanup on `<teardown>`" / "Read only the needed range/columns".

### telemetry

Covers logging, metrics, and tracing hygiene — both **presence** (is the path instrumented at all?) and **shape** (structure / levels / context / cardinality). Non-interactive paths need real telemetry (servers, daemons, workers, outbound calls); interactive paths where the operator watches stdout do not need backend-shipped telemetry on the happy path. Secrets-in-logs stays under `security`; hot-path log-volume cost stays under `efficiency`; exceptions swallowed with no handling at all stay under `correctness`.

| Base | Trigger |
| --- | --- |
| `blocker` | Silent failure on critical infra (payments, auth, irreversible side effects) where the operator has nothing to grep |
| `high` | Silent error branches on outbound calls to external services; un-instrumented new handler on a non-interactive path |
| `medium` | Silent catch on a non-critical worker; un-instrumented new background loop |
| `low` | Missing one structured field; wrong level on dev path |

Inherited shape: a silent catch or un-instrumented loop in a touched module that the diff extends rather than introduces. Check the surrounding handler, not only the changed branch.

Boundaries: correctness (no-handling silent failure to correctness), security (secrets-in-logs to security), nih (custom logger to telemetry primary), assertions (log-string asserts to telemetry). Full rules in § Dimension boundaries.

Look for: silent error branches on non-interactive paths; outbound calls without observability; silent daemons/workers/schedulers; missing request/response instrumentation; hand-rolled logging infrastructure; missing operational hygiene (rotation/retention) on new file logging; unstructured/string-concat log messages; wrong log levels; double-logging; errors logged without context; missing correlation/trace ids; high-cardinality metric labels or span names; logs-as-metrics; `print()`/`console.log` left in production; tests asserting on log strings; unbounded list/object dumps into logs.

Recommendation shape: "Emit a structured error log (and a failure counter) in this catch block before re-raising" / "Wrap the outbound `<call>` in a span and add a failure-counter metric" / "Add startup + per-iteration logs to the `<worker>` loop with the failing item id on error" / "Add entry/exit log + latency metric to the new `<handler>`" / "Use the project's existing logger / standard `<stdlib-or-ecosystem-library>` instead of the hand-rolled `<class>`" / "Configure rotation (size + age cap, retention policy) on the new file handler" / "Read log path / level from project config instead of hardcoding" / "Replace string-concat log with structured fields" / "Demote to DEBUG (or drop)" / "Log once at the boundary, not at every catch" / "Add `exc_info=True` (or equivalent) to capture the stack" / "Thread `trace_id` through the log context at the request boundary" / "Move `<high-cardinality-attr>` from metric label to span attribute" / "Emit a counter instead of grepping logs" / "Replace `print()` with the project logger" / "Assert on behavior, not on log text".

## Dimension boundaries

When two dimensions could tag the same `path:line`, this table decides the primary. The per-dimension `Boundaries:` lines point here. The grader dedups by `file:line` when writing the report, keeping the higher-base finding and noting the secondary dimension.

| Pair | Tiebreaker |
| --- | --- |
| correctness / telemetry | Silent failure with no logging is correctness; telemetry owns it once the failure is caught and the gap is observability. |
| security / telemetry | Secrets in logs or URLs are security regardless of surrounding code. |
| security / correctness | A behavioural bug with an access-control consequence tags security; correctness only when there is no security consequence. |
| security / nih | Reinvented crypto or a security sanitizer tags security (higher base wins); leave nih off to avoid downgrading a blocker through nih's missing blocker row. |
| deslop / correctness | Tag by the claim: deslop when the primary claim is AI residue, correctness when it is silent failure. |
| deslop / nih | nih when a pre-existing helper or import already does it; deslop when the duplication is internal to the diff with no existing helper. |
| deslop / assertions | Generic catches in test files are assertions; in production code they are deslop, correctness, or telemetry per the claim. |
| nih / telemetry | Custom loggers tag telemetry primary (richer rubric); note the nih angle in the recommendation; do not double-tag. |
| efficiency / nih | nih when an import or library exists for the primitive; efficiency when it is an algorithm or concurrency choice with no available import. |
| efficiency / correctness | TOCTOU as wasted work tags efficiency; TOCTOU that can produce wrong data under a race tags correctness. Split by failure mode. |
| encapsulation / deslop | Duplication caused by a misplaced invariant tags encapsulation (root cause is ownership), not deslop. |
| encapsulation / complexity | A parameter that leaks context or type across a boundary tags encapsulation; raw param count or threading with no boundary concern tags complexity. |
| spec / correctness | Emit both with a cross-reference: spec records the broken contract commitment, correctness records the runtime risk. They are orthogonal. |
| assertions / telemetry | Tests asserting on log strings are telemetry-owned. |
| complexity / efficiency | Complexity owns the structural decision to cache; efficiency owns the runtime cost of redundant work. |

## Deferred: criticality inference (v2)

A fourth severity contributor — a **criticality floor** keyed off the file's path/import/structural fingerprint — is bookshelved for v1. When wired, the formula extends with:

```
sev = max(sev, criticality_floor(file))   # inserted before the cap
```

Bookshelved material lives in:

- `.cheese/research/severity-rubric/rubric-draft.md` § Deferred: criticality inference — full inference ladder (critical / high / standard / low), four-tier vocabulary, two consumers (severity floor + weighted fix-cost-now), `.cheese/criticality.toml` override schema.
- `.cheese/research/critical-pathways/critical-pathways.md` — 35+ detection rules across six signal classes (taint sources/sinks, compliance libraries, framework convention markers, production-pathway layout, graph-structural signals, empirical Pareto from Walkinshaw 2018 ESEM).

v1 does **not** mine the catalogs, build the override file, or compute the floor. v1 ships without any criticality awareness; the deferred material is read-only context for the v2 ticket.
