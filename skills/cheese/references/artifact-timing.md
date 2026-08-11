# Artifact timing

Every human-readable workflow artifact records wall-clock provenance. Ordinary reports record when their run started and ended, plus phase durations, so later optimization uses evidence rather than guesses.

## Scope

This contract covers Markdown specs, reports, research, handoffs, and audit trails written by easy-cheese skills. Typed JSON receipts, plans, and manifests keep their owning schemas; do not inject Markdown or undeclared timestamp fields into them.

Most Markdown artifacts include the rendered `## Timing` section below, before `## References` when citations must stay last. Two native formats already carry equivalent wall-clock provenance and keep their existing shape:

- Wheypoint projections use the runtime-authored `created:` field.
- Hard Cheese audit rows use the `timestamp` column written by `append-attempt`.

## Capture

Capture `started_at` before the first phase and `ended_at` at the durable stopping point. Use the helper rather than hand-writing wall-clock values:

```text
python3 shared/scripts/timing.py now
python3 ${CLAUDE_SKILL_DIR}/scripts/<skill>.pyz timing now
```

The first command is the source-checkout path. The second is the installed-skill path; replace `<skill>` with the owning skill. Skills that ship only `common.pyz`, currently Cure, use `common.pyz timing now`.

Measure durations with a monotonic clock. Wall-clock subtraction is invalid because clock adjustments can make elapsed time jump or run backward. Record at least `total` and `report_write`, plus each network call, delegated wait, test/build gate, or other phase useful for locating delay. Attempts count actual executions.

A halt preserves every completed phase and the halted phase. Post-report work rerenders the same section before the final handoff so the artifact reflects its durable stopping point.

## Render

Pass a JSON object on stdin or as the optional path argument:

```json
{
  "started_at": "2026-08-11T17:00:00Z",
  "ended_at": "2026-08-11T17:10:30Z",
  "phases": [
    {
      "phase": "total",
      "duration_ms": 630000,
      "attempts": 1,
      "status": "ok",
      "notes": "end-to-end handling"
    },
    {
      "phase": "report_write",
      "duration_ms": 3000,
      "attempts": 1,
      "status": "ok",
      "items_seen": 8,
      "items_actionable": 1,
      "notes": ".cheese/age/example.md"
    }
  ]
}
```

```text
python3 shared/scripts/timing.py render < timing.json
python3 ${CLAUDE_SKILL_DIR}/scripts/<skill>.pyz timing render timing.json
```

The renderer normalizes offset-aware timestamps to UTC, validates non-negative counts and durations, escapes Markdown cells, and redacts common authorization, token, API-key, password, and secret assignments. Timing metadata must remain small and non-sensitive: no headers, cookies, raw command output, full logs, or credentials.

The shared renderer generalizes the Affinage timing prototype from PR #126 rather than keeping one skill-specific copy.[^pr-126]

[^pr-126]: easy-cheese PR #126, "feat(affinage): add timing report renderer." <https://github.com/paulnsorensen/easy-cheese/pull/126>
