# Documentation reconciliation result

## Summary

- Reconciled the release documents and documentation site as one area.
- Removed two dead workflow path filters.
- Audited all prose from the three documentation slices for ASD-STE100 compliance.
- Rebuilt all skill bundles after the merged source changes.
- `just check` passed.
- The sidebar test passed all five cases.
- The local site served the homepage at `/easy-cheese/`.

## Commits

- `7a6d5d3` — `docs(site): reconcile release documentation`

## Source PRs

- PR #565 adds the release 0.14 decision plan and issue #477 suggestions.
- PR #585 adds the issue #553 gate conversion record.
- PR #592 adds the documentation site, contribution guide updates, and deployment workflow.

## Disagreements

- `.github/workflows/docs.yml`: PR #592 watched the old `shared/**` path.
  The integrated repository keeps shared runtime code under `src/easy_cheese/shared/**`.
  I removed the dead filters because runtime code does not generate documentation.

## Outward dependencies

- `this -> build`: `.github/workflows/docs.yml` calls the `docs:build` package script.
- `build -> this`: `scripts/gen_docs.py` writes generated Starlight pages from root documents and skill prose.
- `skills -> this`: `skills/*/SKILL.md` and skill references provide the generated site content.
- `this -> external`: `website/components/SiteTitle.astro` uses `@cheeselord/design/components/Brand.astro`.
- `this -> external`: `website/components/Sidebar.astro` uses the Starlight sidebar component and route data.

## STE100 status

compliant

## Follow-ups

none
