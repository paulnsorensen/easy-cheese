# Shared Area Reconciliation

## Summary

The shared area provides one command manifest, publication gateway, migration path, research layout, and Mold gate contract.

The publication gateway rejects unsafe operation IDs. It binds replay identity to the route and payload schema.

The reconciliation removes duplicate command helpers and keeps one publication path for new and migrated artifacts.

`just bundle` rebuilds all 13 affected skill bundles.

`just check` passes after the rebuild.

## Commits

- `47b2b88` ingests the PR #592 shared slice.
- `8be0c67` ingests the PR #568 shared slice.
- `f88c677` ingests the PR #581 shared slice.
- `21361fa` ingests the PR #582 shared slice.
- `7d7e8d4` ingests the PR #584 shared slice.
- `3e10a08` ingests the PR #585 shared slice.
- `ffd2025` ingests the PR #589 shared slice.
- `edeec07` reconciles the shared contracts.
- `b8d3b06` rebuilds the affected bundles.

## Source PRs

- #568
- #581
- #582
- #584
- #585
- #589
- #592

## Disagreements

- `bundle_commands.py` and skill `commands.py`: PR #592 derives placeholder summaries. PR #581 requires explicit summaries.
  The reconciliation requires each summary in `derive_command`. It removes local wrappers to prevent drift.
- `migrate.py`: the first migration path repeats publication persistence.
  The reconciliation keeps `publish_canonical` because one path enforces route checks and replay checks.
- `publication.py`: the first request digest omits route and schema identity.
  The reconciliation keeps those fields because one operation cannot replay across different contracts.

## Outward dependencies

- schemas -> shared: `contracts.py` generates `document_rules.py` with the Grounding rules.
- shared -> schemas: `migrate.py` and `publication.py` use contract models and transition registries.
- build -> shared: `scripts/render_generated_regions.py` reads `Command.summary`.
- affinage -> shared: `commands.py` uses the shared command contract.
- age -> shared: `commands.py` uses the shared command contract.
- briesearch -> shared: `commands.py` uses shared commands, and `research_layout.py` uses shared paths.
- cook -> shared: `commands.py` uses shared commands, and `contract_handlers.py` uses `accept`.
- cure -> shared: `commands.py` uses the shared command contract.
- easy-cheese-setup -> shared: `commands.py` uses `Command` and `dispatch`.
- hard-cheese -> shared: `commands.py` uses the shared command contract.
- melt -> shared: `commands.py` uses the shared command contract.
- mold -> shared: commands and validators use publication, migration, document, and taste-test contracts.
- pasteurize -> shared: `commands.py` uses the shared command contract.
- plate -> shared: `commands.py` uses the shared command contract.
- press -> shared: `commands.py` uses command, route, and telemetry contracts.
- wheypoint -> shared: commands use shared declarations, and runtime modules use shared paths.

## STE100 status

compliant

## Follow-ups

none