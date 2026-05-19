# Review dimensions

Each dimension has its own rubric. Apply each dimension to the scoped diff. A dimension with nothing to say simply omits itself from the report — do not pad with no-op observations.

## High-stake

### correctness

Look for:
- Off-by-one, ordering, null/empty, undefined-behaviour edge cases.
- Silent failures: caught exceptions that swallow the error, default values that hide a missing input.
- Race conditions when concurrency is in scope (locks, atomics, transaction boundaries).
- Logic that contradicts itself across branches of an `if` / `match`.

Recommendation shape: "Add a guard for X" / "Return early when Y" / "Replace `catch (_)` with explicit handling".

### security

Look for:
- AuthN/AuthZ holes: missing checks, role confusion, privilege escalation paths.
- Injection: SQL, shell, template, deserialization, path traversal, ReDoS.
- Secrets: hardcoded tokens, secrets in logs, secrets passed via URL/query string.
- Tainted inputs reaching `eval`, `exec`, `system`, file paths, or HTTP redirects without validation.
- Crypto missteps: hand-rolled hashing, missing salts, weak randomness, known-broken algorithms.

Recommendation shape: "Validate at the boundary" / "Use the project's existing `<helper>`" / "Move secret to env or vault".

### encapsulation

Look for:
- Cross-module imports that reach into another slice's internals instead of its public interface.
- Public APIs that leak implementation types (ORM models, framework objects, infra adapters).
- Functions that take `Context | DI container | App` when they only need one field.
- New exports added without a use case.

Recommendation shape: "Import from `<slice>/index` instead of `<slice>/internal/foo`" / "Narrow the public surface to `<minimal-type>`".

### spec

Look for:
- Behaviour described in the spec that is not present in the diff.
- Behaviour in the diff that is not described in the spec.
- Renamed concepts, changed defaults, or relocated boundaries that the spec did not approve.
- Missing acceptance criteria the user's request implied (e.g. "should return 401" with no 401 path).

Recommendation shape: "Restore the X requirement" / "Confirm with the user that Y is intentional" / "Update the spec to reflect Z".

## Medium-stake

### complexity

Look for:
- Functions over the project's complexity budget (40 lines / 4 params / 3 nesting levels are common).
- Files over 300 lines that grew in this diff.
- Speculative abstractions: a generic helper used in one place; a strategy pattern with one strategy.
- Redundant state: duplicated state, or a cached value that could be derived on read.
- Parameter sprawl: a new parameter added to thread data through, where restructuring or a smaller struct would carry it instead.
- Stringly-typed code: raw strings where a constant, enum, or string-union type already exists.
- Comments that try to explain code that should rename instead.

Recommendation shape: "Extract `<sub-function>`" / "Inline `<one-call helper>`" / "Derive `<value>` instead of caching" / "Replace `<string>` with `<enum>`" / "Replace `<vague-name>` with `<concrete-name>`".

### deslop

Look for:
- Dead code: unreachable branches, unused exports, commented-out blocks left as "for reference".
- AI tells: catch-all `try/except` that re-raises a generic error, useless docstrings that restate the function name, "// TODO: implement" left in committed code.
- Duplicated logic: copy-paste of an existing helper, two functions that should be one.
- Copy-paste-with-variation: near-duplicate blocks that differ only in a value or branch, where a shared helper or parameter is the natural shape.
- Vague names: `data`, `result`, `temp`, `info`, `manager`, `helper` without a noun that says what they hold.

Recommendation shape: "Delete dead branch at <line>" / "Reuse `<existing-helper>`" / "Extract shared `<helper>` from the two near-duplicate blocks" / "Rename `data` to `<noun>`".

### assertions

Look for:
- Tests that assert existence (`toBeDefined`, `is not None`) instead of value equality.
- Tests that catch any error instead of the specific expected error.
- Tests that pass when the implementation is wrong (no-crash-as-success).
- Mocks that mock the system under test.
- Tests that depend on time, random, or external state without bounding it.

Recommendation shape: "Replace `toBeTruthy` with `toEqual(<expected>)`" / "Catch `<specific-error>` not `Exception`".

### nih

Look for:
- Hand-rolled retry, validation, UUID, debounce, date parse, argparse, deep-equality, sanitizer that the project already imports a library for.
- Custom JSON walking when `jq` (in scripts) or a dependency would do.
- New string-format / template helpers when the language stdlib has them.
- "Utility" file that recreates a small library.
- Newly written code that duplicates an existing in-project utility, helper, or component — including inline logic (string manipulation, path handling, parsing/formatting) that already has a project helper.

Recommendation shape: "Replace with `<existing-dep>.<fn>`" / "Use the stdlib `<fn>` instead of the local helper" / "Call the existing `<project-helper>` instead of re-implementing".

### efficiency

Look for:
- Unnecessary work: redundant computation, repeated reads of the same value, N+1 query/IO patterns inside a loop.
- Missed concurrency: independent async operations awaited sequentially when they could run in parallel.
- Hot-path bloat: blocking work added to startup, per-request, or per-render paths.
- Recurring no-op updates: unconditional state/store writes inside loops, intervals, or handlers without a change-detection guard.
- Time-of-check/time-of-use (TOCTOU) pre-checks: pre-checking file/resource existence before use; prefer performing the operation and handling the resulting error.
- Memory issues: unbounded caches/queues, missing cleanup, listener/timer leaks, retained references after teardown.
- Overly broad operations: reading a full file or dataset when only a slice is needed.

Recommendation shape: "Hoist `<call>` out of the loop" / "Run `<a>` and `<b>` in parallel with `Promise.all` (or equivalent)" / "Guard the store write on a value change" / "Drop the existence pre-check; handle the error from `<op>` instead" / "Bound `<structure>` or add cleanup on `<teardown>`" / "Read only the needed range/columns".

### telemetry

Covers logging, metrics, and tracing hygiene — both **presence** (is the path instrumented at all?) and **shape** (structure / levels / context / cardinality). Non-interactive paths need real telemetry (HTTP/RPC handlers, outbound API/DB/queue/cache calls, daemons, queue consumers, schedulers, background workers, retry loops); interactive paths where the operator watches stdout (CLI tools, dev scripts, one-shot commands) do not need backend-shipped telemetry on the happy path, though structured error output still helps. Secrets-in-logs stays under `security`; hot-path log-volume cost stays under `efficiency`; exceptions swallowed with no handling at all stay under `correctness`.

Look for:
- **Silent error branches on non-interactive paths.** `catch` / `except` / `if err != nil` blocks in servers, daemons, workers, and outbound calls that handle the error but emit no log and no metric. The failure becomes invisible to anyone not attached to a debugger.
- **Outbound calls without observability.** HTTP / RPC / DB / queue / cache calls with no surrounding span, no error log, and no failure counter. Operators learn the integration broke only from downstream symptoms.
- **Silent daemons / workers / schedulers.** Long-running processes with no startup log, no heartbeat or per-iteration progress signal, and no per-item error emission. When the worker stalls or crashes, there is nothing to grep.
- **Missing request/response instrumentation on server handlers.** New routes or RPC methods added with no entry/exit log, no latency metric, and no error counter.
- **Hand-rolled logging infrastructure.** New logger class, formatter, level filter, JSON serializer, ring buffer, or log-shipping code when the project already wires a logger or the ecosystem has a standard one (Python `logging` / `structlog`; Node `pino` / `winston`; Go `slog` / `zerolog`; Rust `tracing` / `log`; Java `slf4j` / `logback`). Overlaps with `nih`; both dimensions may flag the same line.
- **Missing operational hygiene on new file-based logging.** Logs written to disk without rotation (size cap, age cap, archive policy), no retention bound, hardcoded log paths that bypass project config, synchronous writes on the request path, or custom log-shipping where the project's standard handler / sidecar / OTel collector already does the job.
- Unstructured or string-concatenated log messages where structured (key-value or JSON) fields would be queryable — `f"user {id} failed"` instead of `log.error("operation failed", user_id=id)`.
- Wrong log levels: DEBUG-spam in production hot paths, ERROR used for expected outcomes, everything-at-INFO walls that bury real signal.
- Double-logging: code that logs an error and then rethrows / returns it, so the same failure appears at every frame up the stack.
- Errors logged without context: `log.error("failed")` with no exception object, stack trace, or causal fields. Use `exc_info=True` (Python) / `{ err }` (JS) / equivalent.
- Missing correlation: cross-service or async work without a trace/request/correlation id threaded through the log line and span.
- High-cardinality metric labels or span names: `user_id`, `request_id`, full URLs with query strings, timestamps, or other unbounded values used as metric labels or in span names. Belongs in span attributes (sampled) or log fields, not in metric label sets.
- Logs-as-metrics: counting log occurrences in a downstream pipeline instead of emitting a counter, gauge, or histogram directly.
- `print()` / `console.log` / raw stderr scribbles left in production code paths instead of the project's logger.
- Tests asserting on log strings — couples implementation details to test assertions and breaks on cosmetic log changes.
- Unbounded list / object / request-body dumps into logs (can balloon log volume and leak sensitive structure).

Recommendation shape: "Emit a structured error log (and a failure counter) in this catch block before re-raising" / "Wrap the outbound `<call>` in a span and add a failure-counter metric" / "Add startup + per-iteration logs to the `<worker>` loop with the failing item id on error" / "Add entry/exit log + latency metric to the new `<handler>`" / "Use the project's existing logger / standard `<stdlib-or-ecosystem-library>` instead of the hand-rolled `<class>`" / "Configure rotation (size + age cap, retention policy) on the new file handler" / "Read log path / level from project config instead of hardcoding" / "Replace string-concat log with structured fields" / "Demote to DEBUG (or drop)" / "Log once at the boundary, not at every catch" / "Add `exc_info=True` (or equivalent) to capture the stack" / "Thread `trace_id` through the log context at the request boundary" / "Move `<high-cardinality-attr>` from metric label to span attribute" / "Emit a counter instead of grepping logs" / "Replace `print()` with the project logger" / "Assert on behavior, not on log text".

## Stake assignment

Stake is fixed per dimension. Do not vary it at runtime based on diff size or perceived severity — the rubric already encodes severity. A high-stake dimension produces fewer findings when the rubric does not match the diff; do not promote a medium-stake finding to fill space.
