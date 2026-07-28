# ADR-001 — Risk overrides promote a dimension, they do not escalate `n`

**Status:** accepted · **Spec:** `deterministic-fanout-sizing`

## Context

`src/fanout/age_route.py:110-117` treats any `OVERRIDE_FLAGS` hit as a hard
escalation: `n` jumps to 10 and `effort` to `high` regardless of diff size. A
one-line change touching an auth path therefore buys ten reviewers.

The escalation conflates two different things — *how much* code needs reading,
and *which lens* needs to be sharp. Diff size answers the first; a risk flag
answers the second.

## Decision

An override **promotes its dimension out of its lens group into a solo lens
carrying a focus brief**. The group survives with its remaining members. `n`
grows by the number of distinct promotions, not to a fixed ceiling.

| flags | promotes |
|---|---|
| `auth` `secrets` `crypto` `tenant-isolation` | security |
| `payments` `ledgers` `irreversible-effects` `production-destructive` `concurrency` `idempotency` `ordering` `retries` | correctness |
| `schema-migration` `protocol-change` `public-api-change` | encapsulation |
| `weak-integration-coverage` | assertions |

**Uncapped**, natural maximum 9 (all four categories tripped simultaneously).

## Why uncapped

A cap of 8 was considered and rejected. Truncating at 8 means dropping a
*promoted* lens — precisely the thing promotion exists to guarantee — and nothing
in the design says which one falls off. A cap that can silently discard the
security lens on a payments + auth + migration diff is worse than no cap. Nine
lenses only occurs when a diff trips all four override categories, which is
genuinely severe.

An alternative was considered where the cap is absorbed by re-merging the
*unpromoted* groups, protecting promotions. It works, but it adds a truncation
branch and a priority ordering to get wrong, for a case that is already rare.
Rejected on simplicity.

## Consequence

The headline effect is at the small end, not the large one: a one-line auth
change goes from `n=10` to `n=2` — `[security, focused]` + `[everything else]`.
Risk gets a dedicated eye without buying nine other agents.

The locked output schema `{n, lenses, effort, overrides_hit, rationale}` is
unchanged; `lenses` is simply a different partition.

## Related

- [ADR-002](./deterministic-fanout-sizing-002.md) — the inverted weight table
- [ADR-003](./deterministic-fanout-sizing-003.md) — no LLM in the sizing path
- [age-fanout-router](../architecture/age-fanout-router.md) — the component this changes
