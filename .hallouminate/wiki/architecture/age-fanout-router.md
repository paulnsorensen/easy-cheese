# Age fan-out router

Review fan-out sizing is a deterministic, unit-tested routing decision, not
agent judgment. `src/fanout/age_route.py::route()` maps diff stats + risk
flags to `{n, lenses, effort, overrides_hit, rationale}` with `n ∈ {1, 4, 10}`:
size tiers pick `n`, and any hard risk-override (`OVERRIDE_FLAGS`: auth/
secrets/crypto, tenant isolation, payments/ledgers/irreversible effects,
concurrency/idempotency/ordering/retries, schema/migration/protocol/public-API
change, production-destructive ops, weak integration coverage) forces `n=10` +
`effort=high` regardless of size. `entry="affinage"` additionally bumps on
unresolved comment count and CI failure class, so a heavily-commented or
red-CI PR gets the bigger fan-out even on a tiny diff.

Consumers are `/age`'s mode check and `/affinage`'s fresh-window review.

## Purity contract and the sibling-CLI gotcha

`age_route.py` is a pure module: its own test bans `os/sys/socket/subprocess/
requests/urllib/pathlib/shutil` imports **anywhere in the file — the check
AST-walks the whole module, so even a function-local `import sys` fails**
(`tests/fanout/python/test_age_route.py::TestPurity`). That is *why* the CLI
lives in a sibling wrapper, `src/fanout/age_route_cli.py` (JSON on stdin — no
path arg, not `-` — route JSON on stdout). Do not add a `main()` back into
`age_route.py`.


## Open design decision

`effort: "low"` is declared in the locked output schema but unreachable —
`route()` is a two-position dial (`high` at n=10, else `medium`). The spec
names no `low` trigger; either a trigger gets defined (e.g. trivial n=1
diffs) or the schema shrinks to `medium | high`. Deliberately left open at
PR1 review (age finding 10) rather than guessed.

## Canonicity

The routing-*policy* prose is canonical in the dotfiles wiki
(`repo:dotfiles:wiki`, `architecture/subagent-routing-policy.md`), mirrored
in-repo at `skills/cheese/references/routing-policy.md` with a provenance
header. This page records the easy-cheese-side **implementation** facts only.

_Source: subagent-routing-overhaul PR1 (#314) cure/plate write-back · Updated: 2026-07-24_
