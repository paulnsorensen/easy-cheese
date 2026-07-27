# Age fan-out router

Review fan-out sizing is a deterministic, unit-tested routing decision, not
agent judgment. `src/fanout/age_route.py::route()` maps a `review_surface`
**score** (not raw diff stats) + risk flags to
`{n, lenses, effort, overrides_hit, rationale}`.

`review_surface.score()` (`src/fanout/review_surface.py`) computes
`score = sum(weight * lines) + FILE_COST * sum(weight)`, `FILE_COST = 8` --
see [ADR-002](../adr/deterministic-fanout-sizing-002.md) for the weight
table and why it is inverted. The base ladder reads the score alone:
`< 60` -> `n=1`, `60-250` -> `n=2`, `> 250` -> `n=5`. `entry="affinage"`
escalates that base tier on unresolved comment count and CI failure class
**before** any override promotion is applied, so a heavily-commented or
red-CI PR gets the bigger fan-out even on a tiny diff, and an override on
top of that escalation composes rather than overwrites it.

At `n=5` the base lens tree is `[correctness, spec, assertions]`,
`[security, telemetry]`, `[encapsulation, complexity]`, `[deslop, nih]`,
`[efficiency]`; `n=2` merges it into two lenses, `n=1` into one. A hard
risk-override (`OVERRIDE_FLAGS`: auth/secrets/crypto, tenant isolation,
payments/ledgers/irreversible effects, concurrency/idempotency/ordering/
retries, schema/migration/protocol/public-API change, production-destructive
ops, weak integration coverage) **promotes** its mapped dimension out of its
base group into a solo lens; the group's remaining members survive as one
lens. It does not escalate `n` to a fixed ceiling -- see
[ADR-001](../adr/deterministic-fanout-sizing-001.md) for why promotion
replaced escalation. Maximum `n` is 9, reachable only from base tier 5
(5 at `score < 60`, 6 at `60-250`); minimum with any override is 2.

`effort` is `high` when any override hits or `score > 900`; `low` only at
`n=1`; `medium` otherwise. An override retains the `effort=high` forcing
regardless of score -- see [ADR-002](../adr/deterministic-fanout-sizing-002.md)
for where this is recorded, since ADR-001 governs `n` only and is silent on
`effort`. Sizing stays deterministic globs rather than an LLM classifier --
see [ADR-003](../adr/deterministic-fanout-sizing-003.md).

Consumers are `/age`'s mode check and `/affinage`'s fresh-window review.

## Purity contract and the sibling-CLI gotcha

`age_route.py` is a pure module: its own test bans `os/sys/socket/subprocess/
requests/urllib/pathlib/shutil` imports **anywhere in the file -- the check
AST-walks the whole module, so even a function-local `import sys` fails**
(`tests/fanout/python/test_age_route.py::TestPurity`). That is *why* the CLI
lives in a sibling wrapper, `src/fanout/age_route_cli.py` (JSON on stdin -- no
path arg, not `-` -- route JSON on stdout). Do not add a `main()` back into
`age_route.py`. `review_surface.py` follows the same purity pattern with its
own `review_surface_cli.py` sibling, and `pasteurize_route.py` likewise
gained a `pasteurize_route_cli.py` sibling this session.

## Deployment

The CLI ships as the `age-route` subcommand of the `age`, `affinage`, and
`ultracook` bundles. `scripts/build_pyz.py` supports cross-directory sources
(a `"dir/file.py"` source resolves under `src/`) and `EXTRA_MODULES` staging
so `age_route.py` rides alongside its CLI in each bundle; shared-module
dependencies (`manifest_io`, `schema`) auto-vendor. Skill docs carry the
standard repo-path-then-bundle fallback for the router call.

## Canonicity

The routing-*policy* prose is canonical in the dotfiles wiki
(`repo:dotfiles:wiki`, `architecture/subagent-routing-policy.md`), mirrored
in-repo at `skills/cheese/references/routing-policy.md` with a provenance
header. This page records the easy-cheese-side **implementation** facts only.

_Source: subagent-routing-overhaul PR1 (#314) cure/plate write-back; deterministic-fanout-sizing rewrite · Updated: 2026-07-27_