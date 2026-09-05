# Docs cure round 2

This node applies the docs findings from the skill review and the two docs
edge reviews. The hub notes list no `docs` row.
`.cheese/notes/r014-megamerge/skill-review-cure.md` does not exist.

## Finding table

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-docs.md | high | The re-review note gives two current states. | applied | `427dfac5` | `.cheese/notes/r014-megamerge/re-review.md:5,44,63,67` |
| review-docs.md | high | The release records keep superseded limitations active. | applied | `56dba2c2` | `.cheese/issues/477-suggestions.md:3-14`; `.cheese/plans/release-0-14-decisions.md:199-207` |
| review-docs.md | high | The contributor guide describes a rejected command pattern. | applied | `db185240` | `CONTRIBUTING.md:50-61`; `tests/python/test_contributing_contract.py:13-21` |
| review-docs.md | high | The contributor verification procedure omits required tools and suites. | applied | `db185240` | `CONTRIBUTING.md:14-32,66-75`; `tests/python/test_contributing_contract.py:24-36` |
| review-docs.md | medium | The dependency notes omit active external contracts. | applied | `5b33d360` | `.cheese/notes/r014-megamerge/dependency-map.md:186-189`; `.cheese/notes/r014-megamerge/docs.md:34-37` |
| review-docs.md | medium | Twenty-two Markdown files violate the required prose tense or voice. | applied | `f526e345` | `.cheese/notes/r014-megamerge/cheese.md:5-14`; `.cheese/plans/release-0-14-decisions.md:14-36` |
| review-docs.md | low | A completed Mold follow-up remains open. | applied | `76ff9958` | `.cheese/notes/r014-megamerge/hard-cheese.md:44-47` |
| review-docs.md | low | One test title uses the wrong verb form. | applied | `057b8e00` | `tests/js/sidebar-toc.test.mjs:63` |
| review-docs.md | simplification | Remove the `isActive` parameter from `injectToc`. | applied | `057b8e00` | `website/components/sidebar-toc.mjs:22,34`; `website/components/Sidebar.astro:11` |
| review-docs.md | simplification | Replace the manual test list in `CONTRIBUTING.md` with `just test`. | applied | `db185240` | `CONTRIBUTING.md:66-75` |
| review-docs.md | simplification | Keep one current release state under one historical heading. | applied | `56dba2c2` | `.cheese/issues/477-suggestions.md:37,178` |
| review-docs.md | simplification | Keep one current re-review verdict under one historical heading. | applied | `427dfac5` | `.cheese/notes/r014-megamerge/re-review.md:67,92,101` |
| review-docs.md | simplification | The website code contains no duplicate helper. | no change needed | none | `website/components/sidebar-toc.mjs:1-55` |
| edge-build-docs.md | medium | No pre-merge test protects the deployment handoff. | rejected: duplicate | none | `.cheese/notes/r014-megamerge/cure2-build.md:23`; `tests/python/test_justfile_ci_contract.py:86` |
| edge-docs-build.md | medium | No test protects the workflow handoff. | rejected: duplicate | none | `.cheese/notes/r014-megamerge/cure2-build.md:24`; `tests/python/test_justfile_ci_contract.py:86` |
| edge-build-docs.md | low | Two Mold references use unsupported `pseudocode` fences. | deferred: owned by mold | none | `skills/mold/references/adr.md:36` |
| edge-docs-build.md | low | The same two `pseudocode` fences. | deferred: owned by mold | none | `skills/mold/references/grounding.md:11` |

## Rejected findings

The `build` cure node applies both edge medium findings.
`tests/python/test_justfile_ci_contract.py:86` parses `.github/workflows/docs.yml`.
It asserts `docs:build`, `path: dist`, `needs: build`, and the main-only condition.
The `build` area owns that test file, so this node adds no second test.

## Deferred findings

The `mold` area owns `skills/mold/references/adr.md` and
`skills/mold/references/grounding.md`. The Mold cure node reads the same two
edge notes.

## Disagreements

none

## New tests

- `tests/python/test_contributing_contract.py` asserts that `CONTRIBUTING.md`
  documents `@bundle_command`, `derive_command`, and
  `validate_command_surface`. It rejects the superseded direct `Command`
  instruction. It requires each toolchain that `just check` needs. It requires
  `just test` and `just check` as the verification commands.

## Edge state

| Edge | State | Evidence |
| --- | --- | --- |
| docs -> build | ok | `.github/workflows/docs.yml:85-86` calls `docs:build`, which `package.json:7-11` defines. `tests/python/test_justfile_ci_contract.py:86` pins the contract. |
| build -> docs | ok | `scripts/gen_docs.py:606-646` emits the content tree and the sidebar module. `astro.config.mjs:5,11,18` consumes both. |

## Gate status

- `bash .milknado/reconcile-gate.sh` passes with exit status 0.
- `node --test 'tests/js/**/*.test.mjs'` passes all five cases.
- `pytest tests/python/test_contributing_contract.py tests/python/test_gen_docs.py`
  passes 79 tests.
- `uvx ruff check tests/python/test_contributing_contract.py` passes.

## STE100 status

compliant

## Follow-ups

- The `mold` area must replace the two `pseudocode` fences or configure that
  language.
