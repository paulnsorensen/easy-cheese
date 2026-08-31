# Press execution telemetry

Press is the cleanest measured workflow gate, so this records what happened;
it never changes what Press decides. The record is evidence about a routing
decision already made by `press-route`.

## Request

Run it from the project root, once per attempt, after `press-route`:

```sh
python3 "skills/press/scripts/press.pyz" press-telemetry \
  .cheese/press/outer-tdd-gates.attempt-1.telemetry-request.json
```

Every field is required; an empty list is how an attempt records "none".

```json
{
  "slug": "outer-tdd-gates",
  "attempt": 1,
  "outcome": "in_contract_red",
  "repair_cycles": 0,
  "tool_errors": [
    {"phase": "attack", "operation": "pytest"},
    {"phase": "attack", "operation": "pytest"}
  ],
  "delegations": [
    {"role": "reviewer", "purpose": "assertion sensitivity sweep"}
  ],
  "changed_files": ["tests/fanout/python/test_press_route.py"]
}
```

- `slug` and `outcome` are the same values the route request used; `attempt`
  must equal `repair_cycles + 1` and never exceeds 3.
- `phase` is one of `read`, `attack`, `classify`, `route`, `report`,
  `handoff` — the Flow steps. `operation` is the failing tool or command,
  named consistently so repeats aggregate.
- `role` is the delegated agent; `purpose` is required, so no delegation is
  recorded without a reason.
- `changed_files` are repository-relative paths from `git status --porcelain`
  for the Press-owned interval.

## Record

Save the emitted JSON at
`.cheese/press/<slug>.attempt-N.telemetry.json` — append-only, like the
candidate and route artifacts — and cite it from the Press report.

```json
{
  "slug": "outer-tdd-gates",
  "attempt": 1,
  "outcome": "in_contract_red",
  "repair_cycles": 0,
  "changed_file_count": 1,
  "changed_file_classes": ["tests"],
  "production_source_files": [],
  "boundary_consistent": true,
  "tool_error_count": 2,
  "operations": [
    {"phase": "attack", "operation": "pytest", "errors": 2, "recurring": true}
  ],
  "delegations": [
    {"role": "reviewer", "purpose": "assertion sensitivity sweep"}
  ]
}
```

- `recurring` is true once the same phase/operation pair fails twice in one
  attempt: that is an operation-level failure, not a transient tool blip.
- Each changed path classifies as `tests`, `metadata`, or `production_source`;
  anything unrecognized counts as production source, so an unfamiliar path is
  surfaced rather than hidden.
- `boundary_consistent` is false when an attempt reports production-source
  paths under any outcome other than `production_changed`. It is an audit
  flag, not a route: `press-route` still decides the action.

## Reading the records

Treat one attempt as one sample. Reassess only with at least 20 top-level
invocations or four weeks of records, and change Press behavior only for a
reproduced recurring cluster — a single `recurring` operation or one coder
delegation is an audit point, not a defect.
