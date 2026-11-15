# ADR: Strict contract-version equality and a single cook CLI module

Decision status: accepted
Supersedes: the minor-forward-migration clause of adr/workflow-contract-milknado-seam-002.md

## Context

Session analytics over 551 easy-cheese sessions (~43k tool calls) found zero runtime validation failures of agent-authored payloads; the only observed seam failures were interface drift between the repo's own tools. The minor-migration registry had been empty since introduction. Producer and consumer ship in the same commit — there is no independently versioned client.

## Decision

`validate_contract` and curd-plan validation require exact version equality with the catalog; the minor-forward migration machinery (`_migrate_payload`, `_MIGRATION_REGISTRY`, `_decimal_greater`) is removed. Writer-view slimming and boundary validation stay.

`cook normalize` and `cook validate` are verbs of one module sharing a single schema-resolution and ingress path (wheypoint-style dual pyz registration), eliminating the drift class that produced the PR #467 validate/normalize coherence bug.

## Alternatives

- Keep migration machinery for future consumers: rejected — YAGNI; reintroduce under demonstrated pressure.
- Fold validate into normalize as --check-only: rejected — changes the external surface without extra coherence benefit.

## Consequences

Older supported minors now reject instead of normalizing forward. Any future cross-version consumer must reintroduce negotiation deliberately. compat.load's legacy path is unaffected.
