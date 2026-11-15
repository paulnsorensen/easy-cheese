# ADR: Runtime source locations follow the package layout

Status: superseded (2026-08-28)

Spec: pyz-pipeline-contracts (durable specs corpus).

This ADR records an unimplemented generated-source-map proposal. The implemented Shiv migration uses the package layout and the bundle architecture pages as the source-location contract; it does not generate `src/PYTHON_SCRIPTS.md`, `src/README.md`, or per-source banners.[^1]

## Historical context

The earlier runtime layout mixed documentation-site source and Python source under `src/`. The repository had no generated map from bundle subcommands to source files.

## Historical decision

The proposal required `build_pyz.py` to generate and gate `src/PYTHON_SCRIPTS.md`, add a short `src/README.md`, and add a one-line deployment banner to every registered source file.

## Supersession

Runtime Python now lives under two explicit packages: application and shared code under `src/easy_cheese/`, and published schemas under `src/easy_cheese_schemas/`.[^2] `scripts/build_pyz.py` discovers Python-backed skills from `src/easy_cheese/skills/*/commands.py`; package metadata defines the runtime closure.[^3] The public README and contributor guide describe how source becomes a same-named skill archive, while the wiki's bundle doctrine and pipeline pages document the full distribution graph.[^4]

Do not add the proposed generated map or source banners without new demonstrated navigation pressure. Keep the package layout and existing architecture pages accurate instead.

[^1]: specs/pyz-pipeline-contracts.md:68-72,149-151
[^2]: AGENTS.md; .hallouminate/wiki/architecture/skill-python-bundle-doctrine.md
[^3]: scripts/build_pyz.py:23-41,181-196
[^4]: README.md; CONTRIBUTING.md; .hallouminate/wiki/architecture/pyz-bundling-pipeline.md

_Source: implemented repository architecture · Updated: 2026-08-28 · Supersedes: the unimplemented generated source-map and source-banner proposal accepted 2026-08-18_
