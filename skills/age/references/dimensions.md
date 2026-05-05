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
- Comments that try to explain code that should rename instead.

Recommendation shape: "Extract `<sub-function>`" / "Inline `<one-call helper>`" / "Replace `<vague-name>` with `<concrete-name>`".

### deslop

Look for:
- Dead code: unreachable branches, unused exports, commented-out blocks left as "for reference".
- AI tells: catch-all `try/except` that re-raises a generic error, useless docstrings that restate the function name, "// TODO: implement" left in committed code.
- Duplicated logic: copy-paste of an existing helper, two functions that should be one.
- Vague names: `data`, `result`, `temp`, `info`, `manager`, `helper` without a noun that says what they hold.

Recommendation shape: "Delete dead branch at <line>" / "Reuse `<existing-helper>`" / "Rename `data` to `<noun>`".

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

Recommendation shape: "Replace with `<existing-dep>.<fn>`" / "Use the stdlib `<fn>` instead of the local helper".

## Stake assignment

Stake is fixed per dimension. Do not vary it at runtime based on diff size or perceived severity — the rubric already encodes severity. A high-stake dimension produces fewer findings when the rubric does not match the diff; do not promote a medium-stake finding to fill space.
