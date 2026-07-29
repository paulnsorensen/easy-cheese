---
name: python-authoring
description: Write, edit, refactor, or review Python in easy-cheese with concise stdlib-first code, Python 3.12, self-contained .pyz packaging, and repository test and validation conventions. Use for Python changes under src/, shared/scripts/, scripts/, .github/scripts/, or tests/, especially when the user asks for Pythonic, succinct, de-slopped, dataclass-based, CLI, validator, or bundled-helper code.
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
7. Run targeted tests, rebuild affected bundles, then run `just check`.

## Keep runtime code stdlib-first

- Target Python 3.12. Use its language and typing features directly; do not add compatibility code for older versions.
- Treat the standard library as the dependency budget for bundled helpers under `src/` and `shared/scripts/`. Do not add Pydantic, Requests, pandas, or another runtime dependency.
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

- Keep a skill-owned executable helper in its registered `src/<skill>/` source directory.
- Move code to `shared/scripts/` only when multiple existing skills need the same behavior.
- Register executable subcommands in `scripts/build_pyz.py` under `SKILLS`. Use `Shared(...)` for shared entry points and `EXTRA_MODULES` only for an explicit cross-skill source dependency.
- Do not casually import another skill's internals. Each generated bundle must contain only its owning source plus explicitly registered local or shared dependencies.
- Never edit `skills/<skill>/scripts/*.pyz` by hand. Run `just bundle` after changing `src/`, `shared/scripts/`, or bundle registration, and commit the regenerated bundle with its source when publication is in scope.
- Keep CLI modules thin: accept `argv`, return an integer status, print diagnostics to stderr, and propagate failure through a nonzero exit.
- Keep `.github/scripts/` validators read-only. They inspect and report; they do not mutate the workspace.

## Prefer succinct, readable Python

- Use `match` for genuine shape-based dispatch; keep a simple `if` for a binary decision.
- Use `any`, `all`, comprehensions, and generator expressions for pure collection queries or transformations. Keep a loop when it carries state, side effects, or clearer early exits.
- Prefer generators when the result is consumed once.
- Use `enumerate`, direct iteration, f-strings, context managers, and `pathlib` instead of manual indexing, string assembly, cleanup, or path manipulation.
- Ignore only named, intentional failures. Never use a bare `except`, swallow `Exception`, return an empty default on failure, or use `contextlib.suppress(Exception)`.
- Keep new top-level functions at 40 lines or fewer unless one contiguous algorithm is clearer than an artificial split.
- Delete narration comments and docstrings that restate the code. Keep non-obvious rationale and public API documentation.
- Prefer one clear expression to verbose scaffolding, but split dense expressions when intermediate names explain intent.

## Test and finish

- Test observable behavior and the reason it matters; do not add assertions that can pass when the implementation is broken.
- Keep filesystem tests inside `tmp_path` or an equivalent temporary directory. Do not depend on user paths, repository-external state, network access, or auto-loaded pytest plugins.
- For bundle changes, exercise the generated `.pyz` with repository imports unavailable and verify cross-skill code is absent unless explicitly registered.
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
- A fresh `just check` run passed.
