# ADR: cook joins COMMON_CONSUMERS so its documented common.pyz fallback ships

Status: superseded (2026-08-26)

Spec: pyz-pipeline-contracts (durable specs corpus).

This decision records the retired bundle topology. The Shiv migration replaced
`COMMON_CONSUMERS` and `common.pyz` with one same-named archive per
Python-backed skill.[^1]

## Context

Before the Shiv migration, `skills/cook/references/fan-pathway.md` documented
a `common.pyz` fallback for `read_handoff_slug`, but cook was absent from
`COMMON_CONSUMERS`.

## Historical decision

Cook joined `COMMON_CONSUMERS`, shipped
`skills/cook/scripts/common.pyz`, and gained a contract test connecting
`common.pyz` prose references to consumer membership.

## Supersession

Each Python-backed skill now owns exactly one
`skills/<skill>/scripts/<skill>.pyz` Shiv archive. Package metadata resolves
the skill application's dependency on the cohesive shared distribution and the
schemas package, so cook receives `read_handoff_slug` without a separate
shared archive.[^2] Do not restore `COMMON_CONSUMERS` or `common.pyz`; follow
the [skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md).

[^1]: scripts/build_pyz.py; .hallouminate/wiki/architecture/skill-python-bundle-doctrine.md
[^2]: pyproject.toml; src/easy_cheese/shared; src/easy_cheese/skills/cook
