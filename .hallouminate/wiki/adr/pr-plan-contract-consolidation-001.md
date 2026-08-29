---
status: accepted
owner: easy-cheese
last_verified: 2026-08-29
confidence: high
---
# ADR: PrPlan v1 is the sole pull-request topology authority

PrPlan becomes a registered version-1 contract with one generated schema authority. The checked-in reference JSON is a compatibility mirror, not a second definition.

## Context

The existing attrs model, hand-authored JSON Schema, RunManifest embedding, and Cook validators disagree about the fields and guarantees of a pull-request plan.[^1] The reference JSON requires `plate_layout` and admits publication-result fields, while the runtime model lacks contract identity and validates only part of its dependency topology.[^2]

The current registered-contract mechanism also discovers roots by scanning one large module. Moving PrPlan into that module would remove one authority split by worsening another architectural concentration.

## Decision

- Register `PrPlan` at `https://schemas.easy-cheese.dev/pr-plan`, supported version 1.0.
- Make the serialized root own `contract_version`, `plate_layout`, `shape`, `groups`, and `target_branch`, defaulting the target to `main`.
- Replace single-module scanning with an explicit deterministic catalog of schema-bearing modules.
- Reject duplicate contract names and schema URIs when the catalog is built.
- Move `PlateLayout` to a neutral schema primitive and preserve its package-level export for RunManifest and PrPlan.
- Generate `skills/ultracook/references/pr-plan-schema.json` from the registered contract and fail the repository gate on drift.

## Alternatives

- **Do nothing:** rejected because incompatible authorities remain active at a trust boundary.
- **Register only the current attrs model:** rejected because it would standardize incomplete topology semantics.
- **Move PrPlan into the existing giant contracts module:** rejected because it increases concentration and import coupling.
- **Use import-time plugin discovery:** rejected because mutable discovery makes the published catalog order and membership harder to audit.

## Consequences

Schema lookup, validation, generation, and package exports share one catalog. Existing unversioned PrPlan documents stop validating and must be regenerated; no compatibility adapter is part of this change.

[^1]: architecture/schema-similarity-and-consolidation-audit.md
[^2]: src/easy_cheese_schemas/pr_plan.py:1-153; skills/ultracook/references/pr-plan-schema.json
