# CodeQL cure (r014-megamerge)

## Rule table

| rule | fixed | left | reason |
|---|---|---|---|
| py/non-iterable-in-for-loop | 2/2 | 0 | done in a prior session |
| py/file-not-closed | 2/2 | 0 | done in a prior session |
| py/empty-except | 11/11 | 0 | done in a prior session |
| py/ineffectual-statement | 0/166 | 166 | every flagged line ends in `...`. Each is a Protocol or abstract stub body. |
| py/unused-import | 0/18 | 18 | ruff confirms every import is used, inside a `cast("Type", ...)` string literal. CodeQL does not resolve quoted forward references. |
| py/import-and-import-from | 2/9 | 7 | 2 fixed: `schema_runtime.py` dropped a redundant module alias; `test_schemas_compat.py` moved a local `import` to a module-level name. The other 7 need the bare module object for private (`_review`, `_MARKED_CONTRACTS`, `_NoRedirectHandler`) or dunder (`__all__`) attribute access that a from-import cannot carry. |
| py/unnecessary-lambda | 5/5 | 0 | replaced `lambda: f()` with `f` and `lambda x: dict(x)` with `dict`. |
| py/unused-local-variable | 1/1 | 0 | renamed the discarded tuple element to `_`, the repo's existing discard idiom. |

## Commits (integration/r014-megamerge)

1. `fix(codeql): iterate str-enum members through list()`
2. `fix(schemas): close artifact temp files on every path`
3. `refactor: replace best-effort empty excepts with contextlib.suppress`
4. `refactor(codeql): use one import form per module`
5. `refactor(codeql): replace unnecessary lambdas`
6. `refactor(codeql): drop unused local`
7. `build(test): parallelize the larger pytest suites`
8. `build(skills): rebuild bundles after codeql cure`
9. `docs(notes): record codeql cure` (this file)

## Gates

`uvx ruff check .`: pass.
`just typecheck`: 0 errors, 0 warnings, 0 notes.
`just check`: pass (lint, typecheck, test, docs-build, check-bundles all green).
