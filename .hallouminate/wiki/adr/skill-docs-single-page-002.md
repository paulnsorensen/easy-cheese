# ADR-002: Left-nav heading TOC is h2-only, via a custom Starlight Sidebar override  [status: accepted]

- **Context:** The user wants a skill page's section headings to appear as a table of contents under its link in the LEFT sidebar, only when that skill is the active page. Research settled the Starlight (`@astrojs/starlight` ^0.41.3) mechanics: anchor-link sidebar groups never auto-expand (`isCurrent` does an exact pathname compare including the fragment, and the server-side pathname has no hash), and a sidebar entry is strictly a link XOR a group. There is no built-in option to render the page TOC in the left nav.
- **Decision:** (1) Render the TOC at **h2 only**. (2) Implement it with a custom `src/components/Sidebar.astro` override wired via `astro.config.mjs` `components.Sidebar`, reading `Astro.locals.starlightRoute.{sidebar, toc}`, matching the active page's link and replacing it with an expanded group of `toc` h2 anchors. Primary path mutates the sidebar tree then renders `<Default />`; fallback renders the tree directly if mutation doesn't propagate.
- **Alternatives considered:**
  - *h2 + h3 TOC* — richer but long (mold ≈ 60+ entries) and exposes duplicate-h3-slug collisions across folded refs.
  - *Declarative anchor-item groups* — ruled out by research (no auto-expand, link XOR group).
  - *Rely on the right-hand "On this page" TOC* — doesn't meet "under the link on the left."
- **Consequences:** TOC entries come from `route.toc` (Starlight's real post-dedupe slugs), so duplicate folded headings never yield a wrong anchor. A first `docs:build` settles whether the `<Default />` mutation path or the direct-render fallback is needed.
