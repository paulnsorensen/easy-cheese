# Documentation reconciliation result

## Summary

- This node reconciles the release documents and documentation site as one area.
- This node removes two dead workflow path filters.
- This node audits all prose from the three documentation slices for ASD-STE100 compliance.
- This node rebuilds all skill bundles after the merged source changes.
- `just check` passes.
- The sidebar test passes all five cases.
- The local site serves the homepage at `/easy-cheese/`.

## Commits

- `7a6d5d3` — `docs(site): reconcile release documentation`

## Source PRs

- PR #565 adds the release 0.14 decision plan and issue #477 suggestions.
- PR #585 adds the issue #553 gate conversion record.
- PR #592 adds the documentation site, contribution guide updates, and deployment workflow.

## Disagreements

- `.github/workflows/docs.yml`: PR #592 watches the old `shared/**` path.
  The integrated repository keeps shared runtime code under `src/easy_cheese/shared/**`.
  This node removes the dead filters because runtime code does not generate documentation.

## Outward dependencies

- `this -> build`: `.github/workflows/docs.yml` calls the `docs:build` package script.
- `build -> this`: `scripts/gen_docs.py` writes generated Starlight pages from root documents and skill prose.
- `skills -> this`: `skills/*/SKILL.md` and skill references provide the generated site content.
- `this -> @cheeselord/design`: `website/components/SiteTitle.astro` uses `components/Brand.astro`. `website/pages/index.astro` uses `components/Header.astro`, `styles/cheeselord.css`, and `styles/flavors/easy-cheese.css`.
- `this -> @astrojs/starlight`: `website/components/Sidebar.astro` overrides `components/Sidebar.astro` and reads `Astro.locals.starlightRoute`. `website/content.config.ts` uses `loaders/docsLoader` and `schema/docsSchema`.
- `this -> astro`: `website/content.config.ts` uses `defineCollection` from `astro:content`. `website/pages/index.astro` uses `import.meta.env.BASE_URL` and `Astro.site`.
- `this -> GitHub Actions`: `.github/workflows/docs.yml` pins `actions/checkout`, `actions/setup-python`, `pnpm/action-setup`, `actions/setup-node`, `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages` by commit.

## STE100 status

compliant

## Follow-ups

none
