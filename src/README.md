# src/

Pure Python. No Astro, no site sources — those live under `website/`.

- `affinage/` — /affinage subcommand sources (pr-status, post-reply)
- `age/` — /age subcommand sources (html-report)
- `briesearch/` — /briesearch subcommand sources (ground-check)
- `cut/` — /cut subcommand sources (red-gate) and Press's gate-receipt types
- `easy_cheese_schemas/` — shared schema/record package, bundled whole via PACKAGE_TREES
- `fanout/` — fan-out routing and validation modules shared across age, affinage, pasteurize, press, mold, and ultracook
- `hard-cheese/` — /hard-cheese subcommand sources (append-attempt, freshness-check)
- `melt/` — /melt subcommand sources (conflict/lockfile resolution)
- `mold/` — /mold subcommand sources (curd-count, gate-graph, taste-test)
- `pasteurize/` — /pasteurize subcommand sources (debug-tag-sweep, repro-rerun)
- `wheypoint/` — /wheypoint subcommand sources (commit, resolve, show, lint)

See `src/PYTHON_SCRIPTS.md` for the generated subcommand -> source -> bundle map.
Bundles are built by `scripts/build_pyz.py` and gated for currency against these
sources; see `.hallouminate/wiki/specs/pyz-pipeline-contracts.md`.
