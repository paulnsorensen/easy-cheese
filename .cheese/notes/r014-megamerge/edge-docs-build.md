# Docs to Build Edge Review

## State

`untested`

Static names, inputs, outputs, defaults, and failure behavior agree.
The local build and focused tests pass.
No permanent test protects the workflow-to-package handoff.

## Evidence

| Contract item | Docs side | Build side | State |
| --- | --- | --- | --- |
| Command name | The workflow calls `pnpm run docs:build` (`.github/workflows/docs.yml:85-86`). | The package defines `docs:build` (`package.json:7-11`). | ok |
| Arguments and types | The workflow passes no arguments (`.github/workflows/docs.yml:85-86`). | The command accepts no arguments and reports process status (`package.json:10`). | ok |
| Working directory | Checkout populates the default job directory (`.github/workflows/docs.yml:55-58`). | The generator resolves the repository root from its file path (`scripts/gen_docs.py:17-20`). | ok |
| Dependencies | The workflow installs Python 3.12, PyYAML, pnpm, and Node 22 (`.github/workflows/docs.yml:60-79`). | The generator imports PyYAML, and the package pins pnpm (`scripts/gen_docs.py:5-20`; `package.json:6`). | ok |
| Generated inputs | The workflow runs the package command after dependency installation (`.github/workflows/docs.yml:65-86`). | The command generates content before Astro starts (`package.json:8-10`). | ok |
| Output path | The workflow uploads `dist` (`.github/workflows/docs.yml:88-92`). | Astro uses static output and its default `dist` directory (`astro.config.mjs:7-11`). | ok |
| Failure behavior | The deploy job needs the build job (`.github/workflows/docs.yml:94-111`). | `&&` stops Astro after a generator failure (`package.json:10`; `scripts/gen_docs.py:501-520`). | ok |
| Handoff fields | Docs sends a command and consumes its exit status plus `dist` (`.github/workflows/docs.yml:85-96`). | Build emits files and process status only (`package.json:10`; `astro.config.mjs:7-11`). | ok |
| Producer tests | No docs-side test invokes or parses the workflow. | Generator tests cover the sidebar, cleanup, and output tree (`tests/python/test_gen_docs.py:713-927`). | untested |
| Consumer tests | Sidebar tests cover route transformation (`tests/js/sidebar-toc.test.mjs:1-110`). | No test binds that behavior to `docs:build` or the `dist` upload. | untested |

The `just docs-build` command completes and writes the static site.
All 75 generator tests pass.
All five sidebar tests pass.
No unmatched contract change appears at HEAD.

## Findings

### Blocker

none

### High

none

### Medium

- **No test protects the workflow handoff.** Generator tests protect generated content (`tests/python/test_gen_docs.py:713-927`). Sidebar tests protect route transformation (`tests/js/sidebar-toc.test.mjs:1-110`). No test checks `.github/workflows/docs.yml:85-111` against `package.json:7-11`. A command or artifact-path change can fail only in GitHub Actions. **Fix:** Parse `docs.yml` in a contract test. Assert `docs:build`, `path: dist`, `needs: build`, and the main-only deployment condition.

### Low

- **The build emits two syntax highlighting warnings.** Two Mold references use unsupported `pseudocode` fences (`skills/mold/references/adr.md:36`; `skills/mold/references/grounding.md:11`). Astro renders each block as text and returns success. **Fix:** Use `text` fences or configure the language.

## STE100 status

compliant

Neither area has a `SKILL.md` file.
Therefore, this edge has no area-specific skill prose to compare.
This note complies with the stated rules.

## Follow-ups

- Add a contract test for the workflow command and deployment artifact.
- Replace the two `pseudocode` fences or configure their language.
