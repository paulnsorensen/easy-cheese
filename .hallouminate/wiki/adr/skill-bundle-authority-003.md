# ADR: Package layout and decorators define each skill bundle

Status: accepted (2026-08-24)

## Decision

<certain> Runtime ownership derives from `src/easy_cheese/skills/<skill>`, with shared runtime under `src/easy_cheese/shared`. No runtime ownership manifest is added. Each Python-owning skill produces one `skills/<skill>/scripts/<skill>.pyz`.[^doctrine]

Decorator-declared `@bundle_command` functions compile at build time into the owning archive dispatcher and generated command guidance. Payload models remain schema authority; `phase-contract.yaml` remains route authority.

## Consequences

The builder must reject duplicate or unreferenced commands, projection drift, unresolved deferred imports, native members, ambient dependencies, repository-path dependence, and cross-skill archive calls. It must prove shipped interfaces in isolated subprocesses.

This decision replaces useful enforcement from open PRs #429, #455, #459, and #460 without preserving their superseded `common.pyz` or whole-package topology.[^spec]

[^doctrine]: [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md); https://github.com/paulnsorensen/easy-cheese/pull/472
[^spec]: `.cheese/specs/enforceable-skill-boundaries.md` sections Goals, Decisions, and Acceptance.
