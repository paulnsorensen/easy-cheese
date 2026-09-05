# Build cure round 2

This node applies the build findings from the skill review, the four build
edge reviews, and the build hub review.

## Finding table

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-build.md | blocker | The isolated-execution test writes a marker into the real user site directory. | applied | 7b4fb2c3 | tests/python/test_bundle_closure.py:187 |
| review-build.md | high | `check_bundles.py` reads only literal `Command(...)` calls, so 11 of 13 archives discover no commands. | applied | 9f30c65c | scripts/check_bundles.py:471 |
| hub-build.md | high | The archive checker never imports Wheypoint handlers, because Wheypoint uses `@bundle_command`. | applied | 9f30c65c | tests/python/test_check_bundles.py:316 |
| review-build.md | high | `_baseline_blobs` returns an empty mapping after a Git failure, so the gate reports every archive current. | applied | 96a418a6 | scripts/check_bundles.py:757 |
| review-build.md | high | The `just` test environment omits `requirements-build.txt`, so the bundle seam skips. | applied | 60eec2cb | justfile:4 |
| edge-build-schemas.md | high | The same missing build requirement hides the bundle seam. | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:62 |
| edge-build-schemas.md | high | The generated writer reference omits the kind mapping, optional fields, and defaults. | applied | f86ac63d | scripts/render_generated_regions.py:151 |
| review-build.md | medium | The closure check accepts every `sys.stdlib_module_names` entry, including `winreg`. | rejected | none | src/easy_cheese/skills/wheypoint/storage.py:108 |
| edge-build-schemas.md | medium | `_ContractVersion` declares `major` and `minor` as `int`, but the registry emits `str`. | applied | 5bde1de7 | scripts/render_generated_regions.py:45 |
| edge-schemas-build.md | medium | The same version type mismatch. | applied | 5bde1de7 | tests/python/test_phase_projection_types.py:24 |
| edge-schemas-build.md | medium | The generated writer reference does not show optional fields or defaults. | applied | f86ac63d | tests/python/test_writer_views_reference.py:56 |
| edge-build-schemas.md | medium | The build rejects a stale runtime source but offers no generation command. | applied | 36106fc1 | justfile:42 |
| edge-build-docs.md | medium | No test protects the documentation deployment handoff. | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:86 |
| edge-docs-build.md | medium | The same missing workflow contract test. | applied | 60eec2cb | tests/python/test_justfile_ci_contract.py:86 |
| review-build.md | low | The closure tests accept any diagnostic that contains the module name. | applied | b4ded1ae | tests/python/test_bundle_closure.py:53 |
| review-build.md | low | The staged-index rebuild ignores every worktree removal failure. | applied | 679cf5f6 | scripts/check_bundles.py:855 |
| edge-build-shared.md | low | `_DocumentedCommand` repeats the shared `Command` shape. | applied | 5bde1de7 | scripts/render_generated_regions.py:290 |
| edge-build-schemas.md | low | `skills/cook/SKILL.md:123` names the Markdown reference as the schema generator. | deferred: owned by cook | none | skills/cook/SKILL.md:123 |
| edge-build-docs.md | low | Two Mold references use unsupported `pseudocode` fences. | deferred: owned by mold | none | skills/mold/references/adr.md:36 |
| edge-docs-build.md | low | The same two `pseudocode` fences. | deferred: owned by mold | none | skills/mold/references/grounding.md:11 |
| edge-build-schemas.md | low | `skills/mold/references/curdle.md:158` needs a complete active sentence. | deferred: owned by mold | none | skills/mold/references/curdle.md:158 |
| review-build.md | simplification | Replace the literal `Command(...)` parser with the decorator contract. | deferred: owned by press and easy-cheese-setup | none | src/easy_cheese/skills/press/commands.py:10 |
| review-build.md | simplification | `SKILL_SUBCOMMANDS` duplicates every manifest and omits `cook accept`. | applied | 2645cb06 | tests/python/test_pyz_bundle.py:34 |
| review-build.md | simplification | `_baseline_blobs` uses an empty mapping for two meanings. | applied | 96a418a6 | scripts/check_bundles.py:757 |
| review-build.md | simplification | `native_members` repeats the member scan in `_ArchiveAnalysis.from_archive`. | applied | 6ff8921b | scripts/check_bundles.py:562 |
| review-build.md | simplification | `_DocumentedCommand` repeats the public `Command.summary` field. | applied | 5bde1de7 | scripts/render_generated_regions.py:290 |
| review-build.md, edge-build-schemas.md | high | Add bundle test paths to the specialized build workflow filters. | deferred: no listed area owns `.github/workflows/build-pyz.yml` | none | .github/workflows/build-pyz.yml:7 |
| review-build.md | high | Install build requirements in the `validate.yml` test job. | deferred: no listed area owns `.github/workflows/validate.yml` | none | .github/workflows/validate.yml:79 |

## Rejected finding

The reviewer asks the closure check to reject a standard-library module that
this interpreter cannot import. A probe of that change failed the committed
archives. `src/easy_cheese/skills/wheypoint/storage.py:108-114` imports
`msvcrt` inside a deliberate Windows fallback branch. The checker cannot tell
that fallback from an unreachable import, so the proposed rule reports a false
problem for correct cross-platform code. The build keeps
`sys.stdlib_module_names` as the resolver.

## New tests

- `tests/python/test_check_bundles.py` covers decorator discovery, entry-point
  scoping, the real archive command inventory, a broken command target, the
  failed baseline read, and the failed worktree removal.
- `tests/python/test_bundle_closure.py` asserts the exact diagnostic list for
  each single-import fixture.
- `tests/python/test_phase_projection_types.py` checks every projected phase
  field against its declared type.
- `tests/python/test_writer_views_reference.py` compares the rendered optional
  markers with the JSON Schema `required` lists, and checks the kind mapping.
- `tests/python/test_generated_runtime_write.py` checks the new
  `--write-generated` command.
- `tests/python/test_justfile_ci_contract.py` pins the build requirements and
  the documentation workflow contract.

## Generated output

The renderer change rewrites two generated files:
`skills/cook/references/writer-views.md` and
`skills/mold/references/curdle.md`. Both files carry a generated region that
`scripts/render_generated_regions.py` owns. This node did not hand-edit either
file.

## Gate status

- `uvx ruff check .` passes.
- `just lint-py-dead-code` passes.
- `just typecheck` reports zero errors and zero warnings.
- The area test set passes: 334 passed, 198 skipped.

## STE100 status

compliant

## Cross-area gate repair

Two sibling cure commits left five `reportUnusedCallResult` warnings in
`tests/python/test_publication_gateway.py` and
`tests/wheypoint/python/test_storage.py`. The repo-wide typecheck gate fails on
warnings, so this node assigned each discarded result to `_`. No assertion
changed. The `shared` and `wheypoint` areas own those files.

## Follow-ups

- `tests/python/test_publication_gateway.py::test_syntax_normalize_normalize_quotes_recovers`
  fails at HEAD. The `shared` area owns `src/easy_cheese/shared/publication.py`.
- Four `ground_check` tests in `tests/python/test_pyz_bundle.py` fail because
  the error text changed. The `briesearch` area owns
  `src/easy_cheese/skills/briesearch/ground_check.py`.
- Thirteen `test_committed_bundle_matches_source` tests fail because the
  committed archives are stale. The integration barrier rebuilds the bundles.
- Add `tests/python/test_pyz_bundle.py` to the `build-pyz.yml` path filters, and
  install the build requirements in the `validate.yml` test job.
