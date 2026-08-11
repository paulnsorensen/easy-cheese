
# Artifact timing contract

Human-readable workflow artifacts carry local wall-clock provenance.
Ordinary Markdown reports also carry a rendered phase ledger; typed JSON
artifacts keep their owning schemas.[^1]

## Decision

Use one shared, dependency-free renderer rather than per-skill timing code.
The input ledger contains offset-aware `started_at` and `ended_at`
timestamps plus a non-empty phase list. Each phase records a monotonic
`duration_ms`, attempts, status, optional item counts, and short notes.[^1]

Ordinary Markdown reports append `## Timing`. Two parser-owned formats keep
their native timestamp fields instead of changing shape:

- Wheypoint projections use `created:`.
- Hard Cheese audit rows use the `timestamp` column.

Typed JSON receipts, plans, and manifests do not gain undeclared timing
fields. Their schemas remain authoritative.[^1]

## Implementation

`shared/scripts/timing.py` provides two commands:

- `timing now` emits an ISO-8601 UTC timestamp at whole-second precision.
- `timing render` validates a JSON ledger and emits Markdown.

The renderer rejects naive or reversed timestamps and negative durations or
counts. It escapes Markdown table cells and redacts common authorization,
token, API-key, password, and secret assignments.[^2]

Artifact-owning skill bundles expose the helper as a `timing` subcommand.
Cure receives it through the fanned `common.pyz` bundle.[^3]

## Rationale

The design generalizes the Affinage-only prototype from PR #126 instead of
keeping a skill-specific renderer.[^4] A local ledger is required because the
artifact must remain complete offline and without an observability backend.

OpenTelemetry is a possible optional exporter, not the artifact source of
truth. Workflow phases cross agent instructions and subprocess boundaries, so
they still need explicit instrumentation. An OTel integration may translate
the same ledger into spans later without making artifact creation depend on
an SDK, Collector, sampling decision, or remote backend.[^5]

[^1]: skills/cheese/references/artifact-timing.md
[^2]: shared/scripts/timing.py
[^3]: scripts/build_pyz.py
[^4]: https://github.com/paulnsorensen/easy-cheese/pull/126
[^5]: https://opentelemetry.io/docs/languages/python/instrumentation/
