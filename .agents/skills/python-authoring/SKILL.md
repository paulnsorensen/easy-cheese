---
name: python-authoring
description: Write, edit, refactor, or review Python in easy-cheese with concise stdlib-first code, Python 3.12, Shiv .pyz packaging, and repository test and validation conventions. Use for Python changes under src/, scripts/, .github/scripts/, or tests/, especially when the user asks for Pythonic, succinct, de-slopped, dataclass-based, CLI, validator, or bundled-helper code.
---

# Authoring Python

Produce the smallest readable Python change that satisfies the request and matches easy-cheese.

This is a repository-local skill. Keep it under `.agents/skills/python-authoring/`; do not mirror it into the published `skills/` tree or add `agents/openai.yaml`. Renaming this directory requires updating the matching `!.agents/skills/<dir>/` line in `.gitignore` — that path list is an allowlist, so a renamed dir without its own line is silently untracked.

## Work in this order

1. Read the root configuration, owning skill, target exports, immediate callers, and nearby conventions.
2. Keep every changed line traceable to the request. Do not invent orchestration, compatibility layers, abstractions, dependencies, or future flexibility.
3. Put code in the owning package and preserve the bundle boundary.
4. Validate untrusted input once at the boundary, then work with typed trusted data.
5. Choose the clearest succinct Python construct; do not compress code until it becomes harder to read.
6. Remove only slop introduced by the change and code that the change orphaned.
7. Type-check changed files with basedpyright, run targeted tests, rebuild affected bundles, then run `just check`.

## Keep runtime code stdlib-first

- Target Python 3.12. Use its language and typing features directly; do not add compatibility code for older versions.
- Treat the standard library as the default dependency budget for bundled helpers under `src/`. Any third-party runtime dependency must be pure Python and admitted to `requirements/runtime.txt`; bundle builds resolve internal and external hashes into an ephemeral requirements file.
- Reuse the existing JSON-first, optional-YAML manifest boundary instead of importing PyYAML into new bundled modules.
- Treat configured third-party imports as surface-specific exceptions: PyYAML for existing validators, docs tooling, and manifest/test paths; pytest for tests. A new dependency requires an explicit package and CI decision.
- Prefer `argparse`, `json`, `pathlib`, `tempfile`, `shutil`, `zipfile`, `collections`, `itertools`, and `contextlib` over hand-written equivalents.

## Model and validate data explicitly

- Parse untrusted text with the appropriate stdlib parser, require the expected container shape, check required keys and value types, and raise a specific error at the boundary.
- Convert validated mappings into frozen dataclasses or domain value types when named fields and invariants make the contract clearer.
- Use `TypedDict` only when a mapping must remain a mapping. It documents a static shape; it does not validate runtime input.
- Use `Enum` or `Literal` for closed value sets and `Protocol` for structural interfaces that have multiple real consumers.
- Fully annotate function and public-method boundaries. Omit obvious local annotations when inference is clear.
- Do not pass raw structured dictionaries beyond the parsing boundary when a named record makes the contract clearer.

## Preserve skill package boundaries

- Keep skill runtime under `src/easy_cheese/skills/<skill_name>/` and declare its CLI surface in `commands.py`.
- Move code to `src/easy_cheese/shared/` only when multiple existing skills need the same behavior; consume it through the `easy-cheese-shared` internal distribution.
- Do not import another skill's internals. Wheel metadata, pip resolution, and the ephemeral hash-locked requirements file own each bundle's complete runtime dependency closure.
- Keep cross-skill orchestration in the owning workflow seam, not a leaf helper. Communicate through public or persisted contracts to avoid reverse dependencies and cycles.
- Never edit `skills/<skill>/scripts/*.pyz` by hand. Install `requirements-build.txt`, then run `just bundle` after changing bundle inputs and commit the regenerated archives.
- Keep CLI modules thin: accept `argv`, return an integer status, print diagnostics to stderr, and propagate failure through a nonzero exit.
- Keep `.github/scripts/` validators read-only. They inspect and report; they do not mutate the workspace.

## Prefer succinct, readable Python

- Use `match` for genuine shape-based dispatch; keep a simple `if` for a binary decision.
- Use a handler mapping for stable command-to-function dispatch; do not create a registry for one or two branches.
- Use an assignment expression only when it removes a repeated computation or clarifies a loop condition.
- Use `any`, `all`, comprehensions, and generator expressions for pure collection queries or transformations. Keep a loop when it carries state, side effects, or clearer early exits.
- Prefer generators when the result is consumed once.
- Use `enumerate`, direct iteration, f-strings, context managers, and `pathlib` instead of manual indexing, string assembly, cleanup, or path manipulation.
- Ignore only named, intentional failures. Never use a bare `except`, swallow `Exception`, return an empty default on failure, or use `contextlib.suppress(Exception)`.
- Keep new top-level functions at 40 lines or fewer unless one contiguous algorithm is clearer than an artificial split.
- Prefer one clear expression to verbose scaffolding, but split dense expressions when intermediate names explain intent.

## De-slop before finishing

- Delete narration comments and docstrings that restate the code. Keep non-obvious rationale and public API documentation.
- Remove abstractions with one concrete consumer unless the current task requires the seam.
- Name values after domain concepts, not containers or implementation types.
- Consolidate repetitive tests by behavior; do not add shallow input-variation tests.
- Fix the underlying lint issue instead of adding a suppression.

## Type-check with basedpyright

- Run `basedpyright <changed .py files>` (fall back to `uvx basedpyright` if the binary is absent) before finishing. Changed files must report zero errors and warnings.
- Repo config lives in `[tool.basedpyright]` in `pyproject.toml`: include paths, `pythonVersion = "3.12"`, and an execution environment pinning `src/easy_cheese_schemas` to 3.11 to honor the published wheel's `requires-python >=3.11`. `typeCheckingMode` is deliberately unset — basedpyright defaults to `recommended`, which enables every rule with an error/warning split and `failOnWarnings`, so a full run fails on warnings too.
- Every checked tree (`src`, `scripts`, `.github/scripts`, `tests` — the `[tool.basedpyright]` include list) is basedpyright-clean and `just typecheck` (wired into `just check`, `just ci`, and the validate workflow) enforces zero errors and warnings. Any diagnostic your change surfaces is yours to fix before finishing — there is no baseline and no pre-existing backlog to defer to. Imports resolve against `.venv-typing`; `just typecheck-install` (re)creates it from `requirements/typing.txt`.
- basedpyright is stricter than stock pyright; its extra rules are binding here: assign deliberately ignored call results to `_` (`reportUnusedCallResult`), collapse implicit string concatenations, and `cast` untrusted boundary reads to their validated type.
- Load build-only modules that are excluded from wheels with `importlib.import_module` plus `cast`-typed `getattr`, not static imports the checker cannot resolve.
- Fix the type at its source. When a suppression is genuinely unavoidable, use rule-scoped `# pyright: ignore[ruleName]`, never a bare `# type: ignore` or a file-wide switch — `reportIgnoreCommentWithoutRule` flags unscoped ignores.
- Use `--outputjson` when a tool needs machine-readable diagnostics. In GitHub Actions the CLI detects CI and emits inline PR annotations with no extra flags.
- Read exit codes precisely: 0 clean, 1 diagnostics reported, 2 fatal internal error, 3 unreadable config, 4 bad CLI arguments. Treat 2–4 as tooling breakage to fix or report, never as type findings.
- The binary is mise-managed and pinned to an exact version (upstream recommends exact pinning for reproducibility); the `pyright` and `pyright-langserver` shims resolve to basedpyright.

## Test and finish

- Test observable behavior and the reason it matters; do not add assertions that can pass when the implementation is broken.
- Keep filesystem tests inside `tmp_path` or an equivalent temporary directory. Do not depend on user paths, repository-external state, network access, or auto-loaded pytest plugins.
- For bundle changes, exercise the generated `.pyz` with repository imports unavailable and verify no other skill package is present.
- Run the most focused affected tests first.
- Run `just bundle` when bundle inputs changed.
- Run `just check` as the final project gate.

## Completion check

Confirm:

- Runtime imports obey the stdlib-first, surface-specific dependency policy.
- Boundary input is validated once and converted into an appropriate trusted representation.
- Code lives in the owning skill source or a justified shared module.
- Bundle registration and generated `.pyz` files match their sources when applicable.
- CLI and validator failures remain loud, read-only validators remain read-only, and tests are hermetic.
- No silent failures, speculative abstractions, narration comments, unnecessary local annotations, or unrelated cleanup remain.
- Changed Python files pass basedpyright with zero errors and warnings.
- A fresh `just check` run passed.
