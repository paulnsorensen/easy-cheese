# Schema package boundary

## Hard rule

`easy_cheese_schemas` is a shared contract library, not a workflow runtime.
Define shared semantic contracts for Easy Cheese skills and Milknado.
Keep execution machinery under `src/easy_cheese/`, never in this package.

## Allowed here

- Shared domain types and their invariants.
- Agent-facing writer views where agent and host responsibilities differ.
- Pure, deterministic input normalization and strict validation.
- Canonical serialization and digest calculation from supplied values or bytes.
- Pure JSON Schema generation and immutable conformance fixture data.

## Keep machinery outside

Do not put agent dispatch, workflow execution, scheduling, retries, or worktree management here.
Do not put artifact resolution, storage, publication, or workflow filesystem and network operations here.
Do not put subprocess execution, environment discovery, benchmark runners, or operational telemetry here.
Contract types may describe these operations; this package must not perform them.

Place skill-owned machinery under `src/easy_cheese/skills/<skill_name>/`.
Place machinery shared by multiple existing skills under `src/easy_cheese/shared/`.
Place repository build and generation commands under `scripts/`.
Keep tests under `tests/`.

Consumers import this package; this package must not import `easy_cheese` or Milknado.
Do not re-export runtime machinery through `__init__.py`.
Existing violations require relocation or removal; they are not precedents.

## Contract design

Define each shared concept once.
Reuse its types, validators, and fixtures across skills when their meanings match.
Do not create skill-specific copies or speculative generic frameworks.
Require a concrete producer, consumer, and purpose for every contract and field.
Agents supply semantic observations; hosts supply known or computed metadata.
Do not replace missing observations with host assumptions.

Accept unambiguous, bounded syntax repairs at agent ingress.
Reject ambiguous input, missing semantic information, and semantic coercion.
Write one strict canonical form and validate it before publication and downstream execution.
Keep Python validation, generated schemas, and canonical serialization consistent.
Test producer output against the actual consumer contract, including Milknado.

## Clean-break redesign

Breaking schema and Python API changes are permitted for this redesign.
No migrations are required.
Do not retain legacy formats, compatibility aliases, adapters, or dual-write paths solely for backward compatibility.
Update active consumers to the chosen contracts instead.
This permission does not authorize deletion of stored user work.
