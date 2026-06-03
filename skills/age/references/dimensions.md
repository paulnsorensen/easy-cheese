# Review dimensions

Each dimension has its own rubric. Apply each dimension to the scoped diff. A dimension with nothing to say simply omits itself from the report — do not pad with no-op observations.

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
2. **CRG `get_impact_radius_tool`** — when code-review-graph is wired. Equivalent blast-radius output.
3. **LSP `find-references` / `find-callers`** — fallback when neither tilth nor CRG is available.

Fix-cost-now is **reported, not bumped**. Severity decides what to fix; fix-cost-now explains effort and lets triage schedule.

## Fix-cost-later (compounding)

> "How much harder does this get if we leave it?"

| Tier | Meaning |
| --- | --- |
| `contained` | Cost stays roughly fixed. A typo in a docstring is the same fix in six months. |
| `spreading` | Cost grows linearly. New code piles onto the bad pattern; each new caller adds one unit of fix work. |
| `structural` | Cost grows non-linearly. Consumers *harden* against the current shape — types get re-exported, mocks calcify, downstream APIs build on the leak. Public-API leaks, DB-schema mistakes, and ingress-contract violations live here. |

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

Recommendation shape: "Add a guard for X" / "Return early when Y" / "Replace `catch (_)` with explicit handling".

### security

Look for: authN/authZ holes, injection, secrets in source/logs/URLs, tainted inputs reaching dangerous sinks, crypto missteps.

| Base | Trigger |
| --- | --- |
| `blocker` | Injection (SQL/shell/template/deser), authn bypass, secret in source, RCE, plaintext secret on the wire |
| `high` | Unvalidated input reaches dangerous sink; broken authz on internal route; weak crypto on durable data |
| `medium` | Tainted input reaches limited surface with secondary validation; missing rate-limit on auth-adjacent route |
| `low` | Missing defense-in-depth on already-validated input |

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

Recommendation shape: "Restore the X requirement" / "Confirm with the user that Y is intentional" / "Update the spec to reflect Z".

### complexity

Look for: functions over budget (40 lines / 4 params / 3 nesting), files over 300 lines that grew, speculative abstractions, redundant state, parameter sprawl, stringly-typed code, explanatory-renaming comments.

| Base | Trigger |
| --- | --- |
| `high` | God function (3× budget), param sprawl threading through 3+ layers, new god module created in this diff |
| `medium` | 2× budget, generic helper with one user, redundant cached state |
| `low` | Few lines over budget, mildly speculative abstraction |

No default `blocker` row — complexity blockers are rare. (Once criticality returns, the floor may push complexity findings up on `critical`-tier paths.)

Recommendation shape: "Extract `<sub-function>`" / "Inline `<one-call helper>`" / "Derive `<value>` instead of caching" / "Replace `<string>` with `<enum>`" / "Replace `<vague-name>` with `<concrete-name>`".

### deslop

Look for: dead code, AI tells (generic catches, useless docstrings, "// TODO: implement"), duplicated logic, copy-paste-with-variation, vague names.

| Base | Trigger |
| --- | --- |
| `high` | Large duplicated logic with diverging behavior; AI residue actively misshapes flow |
| `medium` | Dead branch left "for reference", duplicated small block, "// TODO: implement" committed |
| `low` | Vague name; single weak copy-paste |

No default `blocker` row.

Recommendation shape: "Delete dead branch at <line>" / "Reuse `<existing-helper>`" / "Extract shared `<helper>` from the two near-duplicate blocks" / "Rename `data` to `<noun>`".

### assertions

Look for: existence assertions instead of equality, catch-any-error, no-crash-as-success, mocked SUT, time/random/external coupling.

| Base | Trigger |
| --- | --- |
| `blocker` | SUT itself is mocked; test asserts the bug as correct behavior |
| `high` | Test passes when the implementation is wrong (no-crash-as-success) |
| `medium` | Catches generic `Exception`; depends on time/random without bounding |
| `low` | `toBeDefined` where equality is one line away |

Recommendation shape: "Replace `toBeTruthy` with `toEqual(<expected>)`" / "Catch `<specific-error>` not `Exception`".

### nih

Look for: hand-rolled retry/validation/UUID/debounce/date-parse/argparse/deep-equality/sanitizer when an import exists; in-project utility duplication.

| Base | Trigger |
| --- | --- |
| `high` | Reinvented logging/telemetry/concurrency primitives the project already wires; reinvented crypto |
| `medium` | Reinvented retry, debounce, validation, UUID |
| `low` | Reinvented small util the stdlib already has |

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

Recommendation shape: "Hoist `<call>` out of the loop" / "Run `<a>` and `<b>` in parallel with `Promise.all` (or equivalent)" / "Guard the store write on a value change" / "Drop the existence pre-check; handle the error from `<op>` instead" / "Bound `<structure>` or add cleanup on `<teardown>`" / "Read only the needed range/columns".

### telemetry

Covers logging, metrics, and tracing hygiene — both **presence** (is the path instrumented at all?) and **shape** (structure / levels / context / cardinality). Non-interactive paths need real telemetry (servers, daemons, workers, outbound calls); interactive paths where the operator watches stdout do not need backend-shipped telemetry on the happy path. Secrets-in-logs stays under `security`; hot-path log-volume cost stays under `efficiency`; exceptions swallowed with no handling at all stay under `correctness`.

| Base | Trigger |
| --- | --- |
| `blocker` | Silent failure on critical infra (payments, auth, irreversible side effects) where the operator has nothing to grep |
| `high` | Silent error branches on outbound calls to external services; un-instrumented new handler on a non-interactive path |
| `medium` | Silent catch on a non-critical worker; un-instrumented new background loop |
| `low` | Missing one structured field; wrong level on dev path |

Look for: silent error branches on non-interactive paths; outbound calls without observability; silent daemons/workers/schedulers; missing request/response instrumentation; hand-rolled logging infrastructure; missing operational hygiene (rotation/retention) on new file logging; unstructured/string-concat log messages; wrong log levels; double-logging; errors logged without context; missing correlation/trace ids; high-cardinality metric labels or span names; logs-as-metrics; `print()`/`console.log` left in production; tests asserting on log strings; unbounded list/object dumps into logs.

Recommendation shape: "Emit a structured error log (and a failure counter) in this catch block before re-raising" / "Wrap the outbound `<call>` in a span and add a failure-counter metric" / "Add startup + per-iteration logs to the `<worker>` loop with the failing item id on error" / "Add entry/exit log + latency metric to the new `<handler>`" / "Use the project's existing logger / standard `<stdlib-or-ecosystem-library>` instead of the hand-rolled `<class>`" / "Configure rotation (size + age cap, retention policy) on the new file handler" / "Read log path / level from project config instead of hardcoding" / "Replace string-concat log with structured fields" / "Demote to DEBUG (or drop)" / "Log once at the boundary, not at every catch" / "Add `exc_info=True` (or equivalent) to capture the stack" / "Thread `trace_id` through the log context at the request boundary" / "Move `<high-cardinality-attr>` from metric label to span attribute" / "Emit a counter instead of grepping logs" / "Replace `print()` with the project logger" / "Assert on behavior, not on log text".

## Deferred: criticality inference (v2)

A fourth severity contributor — a **criticality floor** keyed off the file's path/import/structural fingerprint — is bookshelved for v1. When wired, the formula extends with:

```
sev = max(sev, criticality_floor(file))   # inserted before the cap
```

Bookshelved material lives in:

- `.cheese/research/severity-rubric/rubric-draft.md` § Deferred: criticality inference — full inference ladder (critical / high / standard / low), four-tier vocabulary, two consumers (severity floor + weighted fix-cost-now), `.cheese/criticality.toml` override schema.
- `.cheese/research/critical-pathways/critical-pathways.md` — 35+ detection rules across six signal classes (taint sources/sinks, compliance libraries, framework convention markers, production-pathway layout, graph-structural signals, empirical Pareto from Walkinshaw 2018 ESEM).

v1 does **not** mine the catalogs, build the override file, or compute the floor. v1 ships without any criticality awareness; the deferred material is read-only context for the v2 ticket.
