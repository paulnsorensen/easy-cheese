# Review dimensions

Each dimension has its own rubric.

Each dimension answers **what kind of problem**. Severity answers **how bad this one is**. The two remain orthogonal.

## Severity vocabulary

Four tiers, in order:

```
blocker > high > medium > low
```

| Tier | Meaning |
| --- | --- |
| `blocker` | Do not merge when the contract breaks, exposure stays open, or data remains at risk |
| `high` | Fix before merge when the code risks an incident or rework |
| `medium` | Fix the real defect before the next release |
| `low` | Merge safely and fix the annoyance later |

## Severity computation

Compute each finding's severity; do not declare it. Merge three independent contributors by their maximum, and cap the result at `blocker`:

1. **Base** — Use the dimension's per-tier rubric (see § Per-dimension rubrics below).
2. **Location bump** — Add one tier when `location = contract` and the dimension is location-sensitive (see § Location sensitivity).
3. **Compounding bump** — Add one tier when `fix-cost-later = structural`.

Do not compute the formula mentally. Invoke `src/easy_cheese/shared/severity.py compute`:

```bash
python3 skills/age/scripts/age.pyz severity compute \
    --dimension <dim> --base <low|medium|high|blocker> \
    --location <class|module|cross-module|contract> \
    --fix-cost-later <contained|spreading|structural>
# -> blocker | high | medium | low
```

A class-private encapsulation leak lands at `low`. The same leak at a slice's `index` re-export lands at `blocker` (base `high` → contract bump → structural fix-cost bump, capped).

## Per-finding fields

Every finding carries these fields:

| Field | Values | Source |
| --- | --- | --- |
| `dimension` | correctness, security, encapsulation, spec, complexity, deslop, assertions, nih, efficiency, telemetry | reviewer-tagged |
| `severity` | `blocker / high / medium / low` | computed (formula above) |
| `location` | `class / module / cross-module / contract` | reviewer-classified |
| `fix-cost-now` | `contained / moderate / sprawling` | bucketed from blast-radius count |
| `fix-cost-later` | `contained / spreading / structural` | reviewer-classified |
| `confidence` | `certain / speculating` | reviewer-assigned per the voice-kernel scale (`voice.md`); `don't know` findings are never emitted |
| `recommendation` | one-line action | reviewer |

## Location classification

| Tier | Definition |
| --- | --- |
| `class` | The scope stays inside one class / type / file's private scope. The caller graph stays inside the file. |
| `module` | The scope stays within one module / slice. Calls cross files but stay inside the slice's internal namespace. |
| `cross-module` | The caller reaches another module's internals and bypasses the public index/crust. |
| `contract` | The caller crosses an ingress/egress boundary, such as a public slice `index`, HTTP/RPC handler signature, DB schema, language-FFI boundary, plugin extension point, or published library API. |

In projects without an explicit public-index layer, classify a direct import of another file's internal function across a package boundary as `cross-module`. This includes flat scripts and packages without an `__init__` re-export surface. Classify CLI `argv` / stdin ingress as `contract`.

## Location sensitivity

Apply the `contract` bump only to dimensions where boundary position changes finding impact:

| Dimension | Contract bump? | Why |
| --- | --- | --- |
| correctness | yes | A contract bug reaches every consumer; an internal bug stays contained |
| security | yes | A tainted input crosses a trust boundary |
| encapsulation | yes | This dimension measures boundary integrity |
| spec | yes | Spec drift at the API surface contradicts the published contract |
| complexity | no | Complexity grades function/file shape, not boundary position |
| deslop | no | Dead code stays dead wherever it lives |
| assertions | no | Test quality does not change with SUT location |
| nih | yes | Reinvented primitives that cross the boundary cause more harm than internal helpers |
| efficiency | yes | A public handler on a hot path shows the typical blocker shape |
| telemetry | yes | A boundary outbound call with silent failure forms the canonical blocker |

## Fix-cost-now

> "How hard would it be to fix this *right now*?"

Count files in the proposed fix's blast radius. Do not bucket the count mentally. Pipe raw file/module counts through `src/easy_cheese/shared/severity.py bucket`:

```bash
python3 skills/age/scripts/age.pyz severity bucket --files <N> [--modules <M>]
# -> contained | moderate | sprawling
```

Source priority for the raw count:

1. **`tilth_deps`** — primary. It returns the file set that needs changes.
2. **LSP `find-references` / `find-callers`** — fallback when tilth is unavailable.

**Worked recipe.** Start with a finding at `path:line`. Run `tilth_deps` on the containing file. Count distinct files in the imported-by set. Use the `<N> dependents` header count for `--files`. The `Used by` list reports one entry per call site. Several entries can identify one file, so raw entries overcount. Use each logical package root to count distinct slice/module roots for `--modules`. For example, `src/easy_cheese/skills/melt` and `src/easy_cheese/skills/affinage` count as two modules. Do not count the shared `src/easy_cheese/skills` parent. Then run `python3 skills/age/scripts/age.pyz severity bucket --files <N> --modules <M>`. If `tilth_deps` is unavailable, use LSP callers. Count distinct touched files and distinct module directories in the same way. This method keeps the buckets comparable.

Report Fix-cost-now; do not bump severity with it. Severity selects fixes. Fix-cost-now explains effort and supports triage scheduling.

## Fix-cost-later (compounding)

> "How much harder does this get if we leave it?"

| Tier | Meaning |
| --- | --- |
| `contained` | Cost stays roughly fixed. A typo in a docstring takes the same effort in six months. |
| `spreading` | Cost grows linearly. New code extends the bad pattern; each new caller adds one unit of fix work. |
| `structural` | Cost grows non-linearly. Consumers harden against the current shape. They re-export types, calcify mocks, and build downstream APIs on the leak. Public-API leaks, DB-schema mistakes, and ingress-contract violations belong here. |

**Decision.** Mark `structural` when a consumer re-exports the changed symbol. Also mark `structural` when the fix touches a file outside the diff. Mark `spreading` when the fix stays local but the diff adds callers of the bad shape. Also mark `spreading` when multiple sites copy the pattern. Otherwise, mark `contained`. When two tiers apply, choose the higher tier.

Per-dimension `structural` anchors:

| Dimension | `structural` looks like |
| --- | --- |
| correctness | A race or lost write reaches a public API boundary. Consumers harden retry/mock logic around broken atomicity. |
| security | A taint path crosses a published signature. Every consumer must validate again after the contract leaks the unsafe shape. |
| encapsulation | A slice `index` re-exports a leaked internal type. Downstream slices build on it. |
| spec | A dropped requirement becomes baked into downstream behavior. Later code depends on it. |
| complexity | New code keeps landing in a god module. Each addition compounds untangling cost. |
| deslop | A duplicated block spreads across modules. Each copy diverges and multiplies the eventual merge. |
| assertions | A test mocks the SUT or uses a weak harness. Other tests copy that pattern. |
| nih | Other modules import a reinvented primitive. Replacing it later requires migrating every caller. |
| efficiency | An unbounded structure runs on a long-running path. Retained references accumulate as callers grow. |
| telemetry | New code standardizes on a hand-rolled logging shape. Migrating to the real logger later touches every call site. |

The `structural` tag triggers the compounding `+1` bump in the formula. Use the tag to show users "fix now or pay exponentially later" without presenting that message as severity.

## Per-dimension rubrics

Each dimension uses a base-severity table for each violation shape before modifiers. Apply location and compounding modifiers after the base tier.

### correctness

Look for off-by-one errors, ordering errors, null/empty edge cases, silent failures, races, contradictory branches, and lost writes.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` to data loss, data corruption, races in shared concurrent state, lost writes, or irreversible side effects on wrong input |
| `high` | Assign `high` when code returns wrong data, misorders results, or fails silently without recovery |
| `medium` | Assign `medium` when a recoverable flow mishandles a rare null/empty input |
| `low` | Assign `low` to cosmetic edge cases in well-bounded leaf code |

The diff's new path can exercise an existing race, lost write, or contradictory branch in the caller graph. Expand callers one level before grading clean.

Use telemetry for no-log failures. Use security for access-control findings. Use deslop for silent-failure claims. Use efficiency for TOCTOU wrong-data claims. Use spec for contract commitments and correctness for runtime risks; emit both. Read the full rules in § Dimension boundaries.

Recommendation shape: "Add a guard for X" / "Return early when Y" / "Replace `catch (_)` with explicit handling".

### security

Look for authN/authZ holes, injection, secrets in source/logs/URLs, tainted inputs reaching dangerous sinks, and crypto missteps.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` to injection (SQL/shell/template/deser), authn bypass, secrets in source, RCE, or plaintext secrets on the wire |
| `high` | Assign `high` when unvalidated input reaches a dangerous sink, internal-route authz breaks, or weak crypto protects durable data |
| `medium` | Assign `medium` when tainted input reaches a limited surface with secondary validation, or an auth-adjacent route lacks a rate limit |
| `low` | Assign `low` when already-validated input lacks defense in depth |

The diff can add a caller to an existing tainted-input path or missing authz. Trace the input to its boundary before grading clean.

Define a *dangerous sink* as any call that executes, queries, renders, deserializes, or persists its argument. Examples include SQL/shell exec, template render, `eval` / `pickle` / `yaml.load`, file-path open, and requests to an internal service. Define *secondary validation* as an independent check downstream of the sink's entry that constrains the value. Examples include a schema parse, an allowlist, and a parameterized query. These checks prevent unconstrained tainted values from reaching the sink.

Use telemetry for secrets-in-logs. Use security for access-control findings. Use nih for reinvented crypto or sanitizers. Read the full rules in § Dimension boundaries.

Recommendation shape: "Validate at the boundary" / "Use the project's existing `<helper>`" / "Move secret to env or vault".

### encapsulation

Look for cross-module access to internals, public APIs that leak implementation types, and parameters that carry excess context. Look for new exports without a use case. Also look for a domain invariant lifted from its producer and enforced above it by every caller. Check whether the producer could absorb error, default, or configuration decisions instead of exporting them.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` when a public API leaks an ORM model, infra adapter, framework type, or storage internal across the slice boundary. Also assign it when a slice's `index` re-exports an internal type. |
| `high` | Assign `high` when code reaches another slice's internals and bypasses crust/index |
| `high` | Assign `high` when callers must invoke or repeat a guard/validation outside the producer. The domain then fails to enforce its invariant, so callers can skip it. Also assign `high` when a symbol is public solely for calls from above the domain layer. |
| `high` | Assign `high` when every caller must handle an error, empty/boundary case, or configuration decision identically. Use this tier when the producer has the information to absorb that decision, such as returning an empty result instead of raising or applying a safe default instead of demanding one. |
| `medium` | Assign `medium` to a module-internal leak that exposes private detail across files inside one slice |
| `low` | Assign `low` when one class touches another class's private member within the same file |

Look for a guard inside a slice that only external entry points call. Look for N callers that repeat one check before or after one producer. Look for a public/exported guard whose only consumers sit above the domain layer. Look for callers that apply a check inconsistently. A false-clean result often hides this violation: a private helper becomes public and crust-exported. A diff-scoped pass can grade this clean. Treat the violation as inherited when the diff does not introduce it.

Look for N callers that wrap the same call in the same `try`/`except`. Look for the same literal at the same parameter at every call site. Look for callers that re-derive the same default. Test whether the producer has the information to decide. Treat a parameter as valid when callers legitimately differ. Treat a configuration knob as a finding when callers cannot set it correctly, such as a "voodoo constant" the module should compute itself. Do not flag a knob that expresses genuine caller-specific policy.

Use deslop for duplication caused by a misplaced invariant. Use complexity for a boundary-leaking parameter. Read the full rules in § Dimension boundaries.

Here, the base tier is also the location tier. The contract bump can raise an already-blocker finding, but the cap stops it.

Use one of these recommendation shapes:

- "Import from `<slice>/index` instead of `<slice>/internal/foo`"
- "Narrow the public surface to `<minimal-type>`"
- "Move the `<invariant>` into `<producer>` so every caller inherits it; drop the external guard and narrow the public surface"
- "Return an empty `<result>` instead of raising on the boundary case"
- "Absorb `<default>` into `<producer>` and drop the parameter"
- "Compute `<constant>` inside the module instead of asking every caller for it"

### spec

Look for behavior in the spec but not in the diff.
Look for behavior in the diff but not in the spec.
Look for renamed concepts, relocated boundaries, and missing acceptance criteria.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` to silent drift on a security, data, or correctness requirement that the spec explicitly fixes |
| `high` | Assign `high` when behavior contradicts the spec |
| `medium` | Assign `medium` when the implementation partially meets an acceptance criterion |
| `low` | Assign `low` to naming or style drift that the user can realign in 30s |

The diff can inherit a requirement that an earlier commit dropped without restoring or violating it. Compare the diff against the spec.

Locate the spec before grading. Search the durable spec corpus with `python3 skills/age/scripts/age.pyz artifact-path specs <slug>`. If the resolver is unavailable, use the legacy literal `.cheese/specs/<slug>.md`. See `../../cheese/references/formatting.md` § Corpus location. Never hardcode `.cheese/specs/`. Then search unresolved items in `.cheese/press/<slug>.md`. Next, search the PR body or linked issue with `gh pr view`. Finally, search a commit-message ticket ref. If no source resolves, record "no spec located; searched [list]". Grade spec findings `don't know` rather than clean when no source resolves.

Use correctness for contract commitments to spec and runtime risk to correctness. Emit both. Read the full rules in § Dimension boundaries.

Recommendation shape: "Restore the X requirement" / "Confirm with the user that Y is intentional" / "Update the spec to reflect Z".

### complexity

Look for functions over budget: 40 lines, 4 parameters, or 3 nesting levels. Look for files over 300 lines that grew. Look for speculative abstractions, redundant state, parameter sprawl, and stringly-typed code. Look for explanatory-renaming comments. Look for special cases layered on shared infrastructure when generalising the underlying mechanism costs less. Treat this as a bandaid-depth fix. Also look for abstractions whose interfaces cost more than they hide. Examples include pass-through methods, pass-through variables, adjacent layers that restate one abstraction, and wrapper types that forward every call.

| Base | Trigger |
| --- | --- |
| `high` | Assign `high` to a god function at 3× budget, parameter sprawl through 3+ layers when intermediate layers read or transform it, or a new god module in this diff |
| `high` | Assign `high` to a **shallow layer** when a new module, class, or layer exposes an interface nearly as large as the functionality it hides. Callers must still know the internals to use it correctly. |
| `medium` | Assign `medium` to 2× budget, a generic helper with one user, or redundant cached state |
| `medium` | Assign `medium` to a **pass-through method** that forwards an unchanged signature without functionality. Also assign it to a **pass-through variable** threaded through 3+ layers to reach one consumer when intermediate layers do not read it. Assign it to adjacent layers whose abstractions are the same. |
| `low` | Assign `low` to a few lines over budget or a mildly speculative abstraction |

Look for a method body that makes one delegating call with an unchanged or nearly unchanged signature. Look for a parameter that exists only to reach the next call. Look for adjacent layers whose method names map 1:1. Look for a class whose public method count approaches its count of non-delegating statements. Treat dispatchers as the deliberate exception. A dispatcher routes to different implementations by type or key, so it does real work.

The diff can extend an inherited god function or parameter sprawl by a few lines. Grade the function as it now stands, not only the added lines.

Route boundary-leaking parameters to encapsulation. Route exported-decision parameters to encapsulation. Route pass-through and same-abstraction layers to complexity. Route fake-modularity file sprawl to deslop. Route cache decisions to complexity. Route runtime cost to efficiency. Read the full rules in § Dimension boundaries.

Complexity has no default `blocker` row. A base `high` finding with `fix-cost-later: structural` still reaches `blocker` after the `+1` compounding bump. The phrase "No blocker row" means no base blocker. It does not mean complexity caps at high. When criticality returns, its floor may raise complexity findings on `critical`-tier paths.

**The budget is a smell trigger, not a target.** Do not split a coherent function into shallow pieces just to stay under 40 lines. That split creates a `complexity` finding. Grade the resulting call depth and interface cost, not only the line count. When a function exceeds the budget but has no clean decomposition, grade it clean and record why. Fire budget rows only when an available decomposition leaves each piece independently understandable.

Use one of these recommendation shapes:

- "Extract `<sub-function>`"
- "Inline `<one-call helper>`"
- "Derive `<value>` instead of caching"
- "Replace `<string>` with `<enum>`"
- "Replace `<vague-name>` with `<concrete-name>`"
- "Inline `<pass-through>` into its caller"
- "Collapse `<layer-a>` and `<layer-b>` — same abstraction twice"
- "Pass `<context-object>` instead of threading `<param>` through 3 layers"
- "Keep `<function>` whole — the split to meet budget fragments one abstraction"

### deslop

Look for dead code and AI tells. AI tells include generic catches, useless docstrings, "// TODO: implement", and placeholder/apology comments like "// in a real implementation". Look for duplicated logic and copy-paste-over-reuse. Look for vague or container-typed names such as `user_data_dictionary`. Look for convention blindness, including reimplementing an existing repo utility from scratch. Look for fake modularity, such as a single-function utils file or a God class spread thin. Look for lint-suppression band-aids (`# noqa` / `@ts-ignore` / `#[allow(...)]` / `//nolint`) that mask the real fix. Look for phantom edge-case handling for inputs nobody can name. Look for cargo-cult boilerplate, over-abstraction for one consumer, and test bloat. Test bloat includes shallow near-duplicate tests. Look for partial shell strict mode (`set -e` without `-uo pipefail`).

The per-language pattern catalogs and lint-rule mappings live in `deslop-rust.md` / `deslop-typescript.md` / `deslop-python.md` / `deslop-shell.md` / `deslop-go.md` (same directory).

| Base | Trigger |
| --- | --- |
| `high` | Assign `high` to large duplicated logic with diverging behavior or AI residue that actively misshapes flow |
| `medium` | Assign `medium` to a dead branch left "for reference", a duplicated small block, or a committed "// TODO: implement" |
| `low` | Assign `low` to a vague name or a single weak copy-paste |

The diff can inherit duplicated logic or a dead branch that it copies or leaves beside its change. Read the surrounding block, not only the hunk.

Use correctness for an AI-residue claim or silent-failure claim as appropriate. Use nih when an existing helper handles the task. Use assertions for generic catches in tests. Use encapsulation for a misplaced-invariant duplicate. Use deslop for fake-modularity file sprawl. Use complexity for pass-through and same-abstraction layers. Read the full rules in § Dimension boundaries.

Deslop has no default `blocker` row.

Use one of these recommendation shapes:

- "Delete dead branch at <line>"
- "Reuse `<existing-helper>`"
- "Extract shared `<helper>` from the two near-duplicate blocks"
- "Rename `data` to `<noun>`"
- "Remove `<allow/noqa/ts-ignore>` and fix the underlying `<lint-rule>`"
- "Delete the placeholder comment at <line> and implement the real branch"

### assertions

Look for existence assertions instead of equality, catch-any-error, no-crash-as-success, mocked SUT, and time/random/external coupling.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` when the test mocks the SUT or asserts the bug as correct behaviour |
| `high` | Assign `high` when the test passes even though the implementation is wrong (no-crash-as-success) |
| `medium` | Assign `medium` when the test catches generic `Exception` or depends on time/random without bounding |
| `low` | Assign `low` to `toBeDefined` when equality is one line away (`assert x is not None` when `assert x == <expected>` is one line away) |

A touched-but-unmodified test can inherit a weak assertion that the diff's behaviour change leaves under-covering. Read the touched test bodies, not only the diff hunks.

Use deslop for generic catches in production when the claim concerns residue. Use correctness when the claim concerns a swallowed failure. Use telemetry when the claim concerns missing observability. Use telemetry for assertions on log strings. Read the full rules in § Dimension boundaries.

Recommendation shape: "Replace `toBeTruthy` with `toEqual(<expected>)`" / "Catch `<specific-error>` not `Exception`" / "Replace `assert result` with `assert result == <expected>`" / "Catch `<SpecificError>`, not bare `except:` / `except Exception`".

### nih

Look for hand-rolled retry/validation/UUID/debounce/date-parse/argparse/deep-equality/sanitizer when an import exists. Look for in-project utility duplication.

| Base | Trigger |
| --- | --- |
| `high` | Assign `high` to reinvented logging, telemetry, or concurrency primitives that the project already wires, or to reinvented crypto |
| `medium` | Assign `medium` to reinvented retry, debounce, validation, or UUID |
| `low` | Assign `low` to a reinvented small utility that the stdlib already provides |

The diff can inherit an in-project helper or dependency that already performs this task. Check imports and the helper set before grading clean.

Use deslop for duplication inside the diff. Use security for crypto or sanitizer concerns. Use telemetry for custom logger concerns. Use efficiency for algorithm choice. Read the full rules in § Dimension boundaries.

Nih has no default `blocker` row.

Recommendation shape: "Replace with `<existing-dep>.<fn>`" / "Use the stdlib `<fn>` instead of the local helper" / "Call the existing `<project-helper>` instead of re-implementing".

### efficiency

Look for unnecessary work, missed concurrency, hot-path bloat, and no-op updates. Look for TOCTOU pre-checks and memory leaks. Look for long-lived objects built from closures that capture the enclosing scope. Such captures keep the whole scope alive. Prefer a type that copies only the fields it needs. Look for overly broad reads.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` to an unbounded cache or queue, a listener or timer leak, or retained references after teardown. Use it for anything that grows without bound in a long-running process. |
| `high` | Assign `high` to blocking work on a per-request, startup, or per-render path, or N+1 work on a high-traffic endpoint |
| `medium` | Assign `medium` to N+1 work on a moderate endpoint or redundant compute in a non-hot loop |
| `low` | Assign `low` to redundant compute outside hot paths |

The diff can trigger an inherited N+1, unbounded structure, or hot-path cost. Check whether the changed path runs hot or long-running before grading clean.

Use nih when an import exists for the task. Use correctness for TOCTOU wrong-data claims. Use complexity for cache decisions. Read the full rules in § Dimension boundaries.

Use one of these recommendation shapes:

- "Hoist `<call>` out of the loop"
- "Run `<a>` and `<b>` in parallel with `Promise.all` (or equivalent)"
- "Guard the store write on a value change"
- "Drop the existence pre-check; handle the error from `<op>` instead"
- "Bound `<structure>` or add cleanup on `<teardown>`"
- "Read only the needed range/columns"

### telemetry

This dimension covers logging, metrics, and tracing hygiene. It checks **presence**: does the path have instrumentation? It checks **shape**: does instrumentation use the right structure, levels, context, and cardinality? Non-interactive paths need real telemetry. Examples include servers, daemons, workers, and outbound calls. Interactive paths where the operator watches stdout do not need backend-shipped telemetry on the happy path. Keep secrets-in-logs under `security`. Keep hot-path log-volume cost under `efficiency`. Keep exceptions swallowed without handling under `correctness`.

| Base | Trigger |
| --- | --- |
| `blocker` | Assign `blocker` to silent failure on critical infrastructure (payments, auth, or irreversible side effects) when the operator has nothing to grep |
| `high` | Assign `high` to silent error branches on outbound calls to external services or an un-instrumented new handler on a non-interactive path |
| `medium` | Assign `medium` to a silent catch on a non-critical worker or an un-instrumented new background loop |
| `low` | Assign `low` to one missing structured field or a wrong level on a development path |

The diff can extend an inherited silent catch or un-instrumented loop in a touched module. Check the surrounding handler, not only the changed branch.

Look for silent error branches on non-interactive paths and outbound calls without observability. Look for silent daemons, workers, or schedulers. Look for missing request/response instrumentation. Look for hand-rolled logging infrastructure. Look for missing operational hygiene, including rotation/retention on new file logging. Look for unstructured or string-concatenated log messages, wrong log levels, double-logging, and errors logged without context. Look for missing correlation IDs or trace IDs.
Look for high-cardinality metric labels or span names.
Look for logs that act as metrics.
Look for `print()` or `console.log` in production.
Look for tests that assert log strings.
Look for unbounded list or object dumps in logs.

Use correctness for silent failures with no handling. Use security for secrets-in-logs. Use nih as the primary dimension for custom logger findings. Use assertions for log-string assertions. Read the full rules in § Dimension boundaries.

Use one of these recommendation shapes:

- "Emit a structured error log (and a failure counter) in this catch block before re-raising"
- "Wrap the outbound `<call>` in a span and add a failure-counter metric"
- "Add startup + per-iteration logs to the `<worker>` loop with the failing item id on error"
- "Add entry/exit log + latency metric to the new `<handler>`"
- "Use the project's existing logger / standard `<stdlib-or-ecosystem-library>` instead of the hand-rolled `<class>`"
- "Configure rotation (size + age cap, retention policy) on the new file handler"
- "Read log path / level from project config instead of hardcoding"
- "Replace string-concat log with structured fields"
- "Demote to DEBUG (or drop)"
- "Log once at the boundary, not at every catch"
- "Add `exc_info=True` (or equivalent) to capture the stack"
- "Thread `trace_id` through the log context at the request boundary"
- "Move `<high-cardinality-attr>` from metric label to span attribute"
- "Emit a counter instead of grepping logs"
- "Replace `print()` with the project logger"
- "Assert on behavior, not on log text"

## Dimension boundaries

When two dimensions could tag the same `path:line`, this table decides the primary. The per-dimension `Boundaries:` lines point here. The grader dedups by `file:line` when writing the report, keeping the higher-base finding and noting the secondary dimension.

Look for one primary dimension per finding. Use this table to choose the primary when dimensions overlap.

| Pair | Tiebreaker |
| --- | --- |
| correctness / telemetry | Silent failure with no logging belongs to correctness. Telemetry owns the finding once the failure is caught and only observability remains missing. |
| security / telemetry | Secrets in logs or URLs belong to security regardless of surrounding code. |
| security / correctness | A behavioral bug with an access-control consequence belongs to security. Use correctness only without a security consequence. |
| security / nih | Reinvented crypto or a security sanitizer belongs to security (higher base wins). Leave nih off to avoid downgrading a blocker through nih's missing blocker row. |
| deslop / correctness | Tag by the claim. Use deslop for AI residue and correctness for silent failure. |
| deslop / nih | Use nih when a pre-existing helper or import already does the task. Use deslop when duplication stays internal to the diff and no existing helper exists. |
| deslop / assertions | Generic catches in test files belong to assertions. In production code, classify them as deslop, correctness, or telemetry according to the claim. |
| nih / telemetry | Tag custom loggers as telemetry primary because it has the richer rubric. Note the nih angle in the recommendation. Do not double-tag. |
| efficiency / nih | Use nih when an import or library exists for the primitive. Use efficiency for an algorithm or concurrency choice without an available import. |
| efficiency / correctness | Tag TOCTOU as efficiency when it wastes work. Tag it as correctness when a race can produce wrong data. Split by failure mode. |
| encapsulation / deslop | Tag duplication from a misplaced invariant as encapsulation. Ownership forms the root cause, not deslop. |
| encapsulation / complexity | Tag a parameter that leaks context or type across a boundary as encapsulation. Tag raw parameter count or threading without a boundary concern as complexity. |
| complexity / encapsulation (exported special case) | Extend the `encapsulation / complexity` row above. When a threaded parameter carries a decision the producer can make (a voodoo constant), choose encapsulation because misplaced ownership causes the problem. Keep structural cost alone in complexity when no decision is misplaced. |
| complexity / deslop | Tag pass-through methods and same-abstraction layers as complexity. Tag a single-function utils file or one-consumer over-abstraction as deslop. Both show fake modularity; split them by call depth or file sprawl. |
| spec / correctness | Emit both with a cross-reference. Spec records the broken contract commitment. Correctness records the runtime risk. The dimensions remain orthogonal. |
| assertions / telemetry | Tests that assert on log strings belong to telemetry. |
| complexity / efficiency | Complexity owns the structural cache decision. Efficiency owns the runtime cost of redundant work. |

## Deferred: criticality inference (v2)

v1 defers a fourth severity contributor: a **criticality floor** keyed to the file's path/import/structural fingerprint. When wired, extend the formula with:

```
sev = max(sev, criticality_floor(file))   # inserted before the cap
```

The deferred material lives in:

- `.cheese/research/severity-rubric/rubric-draft.md` contains `§ Deferred: criticality inference`. It defines the full inference ladder (critical / high / standard / low) and the four-tier vocabulary. It names two consumers: the severity floor and weighted fix-cost-now. It defines the `.cheese/criticality.toml` override schema.
- `.cheese/research/critical-pathways/critical-pathways.md` contains 35+ detection rules across six signal classes.
  The classes cover taint sources and sinks, compliance libraries, framework markers, and production-pathway layouts.
  They also cover graph signals and empirical Pareto evidence from Walkinshaw 2018 ESEM.

v1 does **not** mine the catalogs, build the override file, or compute the floor. v1 ships without criticality awareness. The deferred material provides read-only context for the v2 ticket.
