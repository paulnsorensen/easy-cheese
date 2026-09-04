# Build to Docs Edge Review

## State

`untested`

The current producer and consumer agree on every static contract.
The local site build and two route checks pass.
No repository test protects the deployment handoff before a main-branch run.

## Evidence

| Contract item | Build side | Docs side | State |
| --- | --- | --- | --- |
| Commands | Package scripts run generation before Astro (`package.json:7-11`). | The workflow calls `docs:build` (`.github/workflows/docs.yml:85-86`). Just calls the same command (`justfile:111-123`). | ok |
| Dependencies | The generator imports PyYAML (`scripts/gen_docs.py:5-20`). | The workflow installs Python 3.12, PyYAML, pnpm, and Node 22 (`.github/workflows/docs.yml:60-79`). | ok |
| Content path | The generator writes `website/content/docs` (`scripts/gen_docs.py:17-20,135-160`). | Astro uses `website` as `srcDir` (`astro.config.mjs:7-12`). Starlight loads the `docs` collection (`website/content.config.ts:1-7`). | ok |
| Page fields | Generated pages contain `title`, optional `description`, and `editUrl` (`scripts/gen_docs.py:109-160`). | `docsSchema` validates the generated frontmatter (`website/content.config.ts:1-7`). | ok |
| Generated pages | The generator emits skill pages, indexes, install content, and four root documents (`scripts/gen_docs.py:402-468,501-558,606-626`). | The build consumes all pages through the Starlight loader (`website/content.config.ts:1-7`). | ok |
| Sidebar module | `emit_sidebar` exports `sidebar` as groups with `items` (`scripts/gen_docs.py:568-603`). | Astro imports that exact export and passes it to Starlight (`astro.config.mjs:5,13-23`). | ok |
| Generated cleanup | The generator preserves unchanged files and removes stale files (`scripts/gen_docs.py:163-211`). | Git ignores generated pages, the sidebar module, and `dist` (`.gitignore:48-53`). | ok |
| Reverse audit | The bundle checker reads generated skill pages and derives their owners (`scripts/check_bundles.py:659-716`). | Its test uses the exact generated path (`tests/python/test_check_bundles.py:232-245`). | ok |
| Build artifact | Astro uses static output and the default `dist` directory (`astro.config.mjs:7-11`). | The workflow uploads `dist` and deploys after `build` (`.github/workflows/docs.yml:88-111`). | ok |
| Defaults and errors | `docs:build` uses `&&`, so generator errors stop Astro (`package.json:7-11`). Missing README sections raise an error (`scripts/gen_docs.py:501-520`). | `deploy` needs `build`, and upload runs only after a successful main build (`.github/workflows/docs.yml:85-111`). | ok |
| Handoff fields | The build emits files and process status only. It emits no handoff record. | Docs consumes paths, module exports, exit status, and the Pages artifact. | ok |
| Producer tests | Generator tests assert sidebar data, complete output, stale cleanup, and links (`tests/python/test_gen_docs.py:713-927,989-1069`). | The focused generator suite passes all 75 tests. | ok |
| Consumer tests | The sidebar tests cover Starlight route data and transformed links (`tests/js/sidebar-toc.test.mjs:1-110`). | The five sidebar tests pass. The real Astro build creates 24 pages. | ok |
| Deployment tests | No test names the build command, upload action, deploy action, or `dist` path. | Main runs the deployment path only after merge (`.github/workflows/docs.yml:88-111`). | untested |

The generator emits 16 skill pages, one skills index, five project pages, and `website/sidebar.mjs`.
Astro emits 24 static pages because it also emits the homepage and the 404 page.
The preview serves `/easy-cheese/` and `/easy-cheese/skills/age/` successfully.
No unmatched contract change appears at HEAD.

## Findings

### Blocker

none

### High

none

### Medium

- **No pre-merge test protects the deployment handoff.** Generator tests protect produced content (`tests/python/test_gen_docs.py:713-927`). Sidebar tests protect only route transformation (`tests/js/sidebar-toc.test.mjs:1-110`). No test asserts the workflow contract at `.github/workflows/docs.yml:85-111`. A workflow drift can fail only after merge. **Fix:** Parse `docs.yml` in a contract test. Assert `docs:build`, `path: dist`, `needs: build`, and the main-only deployment condition.

### Low

- **The site build emits two syntax-highlighting warnings.** Mold uses unsupported `pseudocode` fences (`skills/mold/references/adr.md:36`; `skills/mold/references/grounding.md:11`). Astro uses `txt` instead, so the site remains usable. **Fix:** Use `text` fences or configure a supported custom language.

## STE100 status

compliant

Neither area has a `SKILL.md` file. Therefore, this edge has no area-specific skill prose to compare.
This note complies with the stated rules.

## Follow-ups

- Add a contract test for the build and deployment workflow.
- Replace the two rendered `pseudocode` fences or configure their language.
