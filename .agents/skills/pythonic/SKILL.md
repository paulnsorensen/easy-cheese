---
name: pythonic
description: Write, edit, refactor, or review Python in easy-cheese with concise declarative contracts, idiomatic control flow, skill-owned package boundaries, deterministic .pyz packaging, and Python de-slop rules. Use for Python changes under src/, shared/scripts/, scripts/, .github/scripts/, or tests/, especially when the user asks for Pythonic, succinct, LLM-optimized, de-slopped, Pydantic, dataclass, pattern-matching, CLI, validator, or bundled-helper code.
---

# Pythonic

Produce the smallest readable Python change that satisfies the request and matches easy-cheese.

This is a repository-local agent skill. Keep it under `.agents/skills/pythonic/`; do not mirror it into the published `skills/` tree.

## Work in this order

1. Read the root configuration, owning skill, target exports, immediate callers, and nearby conventions.
2. Keep every changed line traceable to the request. Do not invent orchestration, dependency-injection rules, compatibility layers, abstractions, dependencies, or future flexibility.
3. Put code in the owning skill package and preserve dependency direction and bundle boundaries.
4. Express boundary schemas and internal data with the appropriate declarative type.
5. Choose the clearest succinct Python construct; do not compress code until it becomes harder to read.
6. Remove slop introduced by the change and code the change directly orphaned.
7. Run targeted tests, rebuild affected bundles, then run `just check`.

## Use dependencies deliberately

- Target Python 3.12. Use its language and typing features directly; do not add compatibility code for older versions.
- Prefer the standard library for bundled helpers. Use `argparse`, `json`, `pathlib`, `tempfile`, `shutil`, `zipfile`, `collections`, `itertools`, and `contextlib` before adding a package.
- PyYAML 6.0.2 is the approved runtime exception for schema-bounded YAML contracts. `cheese.pyz` bundles only its pure-Python modules and license so users install no Python packages separately.
- PyYAML is also approved for existing validators, docs tooling, manifest paths, and tests; pytest is approved for tests. Any other dependency requires an explicit package, bundle, and CI decision.
- Do not add Pydantic, Requests, pandas, or another dependency because this skill mentions a pattern that library supports. Match this repository's approved dependency set.

## Model data declaratively

- Validate untrusted input once at the boundary: parse it with the appropriate library, require the expected container shape, check keys and value types, and raise a specific error there.
- Use frozen dataclasses for trusted internal records that need named fields and invariants. Use domain value types when invariants belong to the business concept rather than transport validation.
- Use `TypedDict` only when a mapping must remain a mapping. It documents a static shape; it does not validate runtime input.
- Use `Enum` or `Literal` for closed value sets and `Protocol` for structural interfaces with multiple real consumers.
- Fully annotate function and public-method boundaries. Omit obvious local annotations when inference is clear.
- Do not pass structured data as raw dictionaries beyond the parsing boundary when a named record makes the contract clearer.

## Preserve skill package boundaries

Organize by workflow capability rather than technical layer:

- Keep a skill-owned executable helper in its registered `src/<skill>/` source directory. The owning skill and its registered commands are the public crust.
- Move code to `shared/scripts/` only when multiple existing skills need the same behavior.
- Register executable subcommands in `scripts/build_pyz.py` under `SKILLS`. Use `Shared(...)` for shared entry points and `EXTRA_MODULES` only for an explicit cross-skill source dependency.
- Do not import another skill's internals. Depend on its public command or an explicitly shared contract instead.
- Keep orchestration that spans skills in the owning workflow seam, not inside a leaf helper. Use persisted contracts to avoid reverse dependencies and cycles.
- Grow factories, registries, abstract bases, protocols, directories, and shared utilities only under demonstrated pressure from multiple consumers.
- Never edit `skills/<skill>/scripts/*.pyz` by hand. Run `just bundle` after changing bundle inputs and commit regenerated archives with their sources when publication is in scope.
- Keep CLI modules thin: accept `argv`, return an integer status, print diagnostics to stderr, and propagate failure through a nonzero exit.
- Keep `.github/scripts/` validators read-only. They inspect and report; they do not mutate the workspace.

## Prefer succinct, readable Python

- Use `match` for genuine shape-based payload, event, command, or AST dispatch. Keep a simple `if` when it communicates a binary decision better.
- Use a handler mapping for stable command-to-function dispatch; do not create a registry for one or two branches.
- Use an assignment expression only when it removes a repeated computation or clarifies a loop condition.
- Use `any`, `all`, comprehensions, and generator expressions for pure collection queries or transformations. Keep a loop when it carries state, side effects, or clearer early exits.
- Prefer generators when the result is consumed once.
- Use `enumerate`, direct iteration, f-strings, context managers, `pathlib`, `itertools`, and `collections` instead of manual equivalents.
- Use `contextlib.suppress(SpecificError)` only when ignoring that exact failure is intended. Never use a bare `except`, swallow `Exception`, return an empty default on failure, or use `suppress(Exception)`.
- Keep new top-level functions at 40 lines or fewer unless one contiguous algorithm is clearer than an artificial split.
- Prefer one clear expression to verbose scaffolding, but split dense expressions when intermediate names explain intent.

## De-slop before finishing

- Delete comments and docstrings that restate the code; keep non-obvious rationale and public API documentation.
- Propagate failures instead of returning empty defaults or swallowing exceptions.
- Remove abstractions with one concrete consumer unless the current task requires the seam.
- Name values after domain concepts, not containers or implementation types.
- Remove imports, branches, alternatives, and boilerplate orphaned by the change.
- Consolidate repetitive tests by behavior; do not add shallow input-variation tests.
- Fix the underlying lint issue instead of adding a suppression.

## Test and finish

- Test observable behavior and the reason it matters; do not add assertions that can pass when the implementation is broken.
- Keep filesystem tests inside `tmp_path` or an equivalent temporary directory. Do not depend on user paths, repository-external state, network access, or auto-loaded pytest plugins.
- For bundle changes, exercise the generated `.pyz` with repository and ambient package imports unavailable. Verify bundled dependencies, licenses, and cross-skill module boundaries explicitly.
- Run the most focused affected tests first.
- Run `just bundle` when bundle inputs changed.
- Run `just check` as the final project gate.

## Completion check

Confirm:

- Runtime imports obey the approved dependency and self-contained bundle policy.
- Boundary input is validated once and converted into an appropriate trusted representation.
- Code lives in the owning skill source or a justified shared module.
- Bundle registration and generated `.pyz` files match their sources when applicable.
- Control flow is succinct without being clever.
- CLI and validator failures remain loud, validators remain read-only, and tests are hermetic.
- No silent failures, speculative abstractions, raw structured dictionaries, narration comments, unnecessary local annotations, or unrelated cleanup remain.
- A fresh `just check` run passed.