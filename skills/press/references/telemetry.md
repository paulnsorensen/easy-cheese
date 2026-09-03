# Press execution telemetry

Press provides a clean workflow gate for measurement. This record shows what happened. It never changes the Press decision.

The record gives evidence for a route that `press-route` already selected.

## Request

Run the command once for each attempt. Run it from the project root after `press-route`:

```sh
python3 "skills/press/scripts/press.pyz" press-telemetry \
  .cheese/press/outer-tdd-gates.attempt-1.telemetry-request.json
```

Include every field. Use an empty list to record no items.

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

- Use the route request values for `slug` and `outcome`.
- Set `attempt` to `repair_cycles + 1`. Do not use a value greater than 3.
- Set `phase` to `read`, `attack`, `classify`, `route`, `report`, or `handoff`. These values match the Flow steps.
- Set `operation` to the failed tool or command. Use the same name for repeated operations.
- Set `role` to the delegated agent.
- Include a `purpose` for each delegation. Do not record a delegation without a reason.
- Use repository-relative paths from `git status --porcelain` for `changed_files`. Include only paths from the Press interval.

## Record

Save the JSON at `.cheese/press/<slug>.attempt-N.telemetry.json`. Use an append-only file, as you do for candidate and route artifacts.

Cite the telemetry file from the Press report.

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

- `recurring` is true after the same phase and operation fail twice during one attempt. This result marks an operation failure, not a temporary tool failure.
- Each changed path has the class `tests`, `metadata`, or `production_source`. An unknown path has the `production_source` class. This rule exposes unfamiliar paths.
- `boundary_consistent` is false when an outcome other than `production_changed` reports production source paths. This audit flag does not control the route. `press-route` still selects the action.

## Read the records

Treat one attempt as one sample. Wait for 20 top-level invocations or four weeks of records before reassessment.

Change Press behavior only after a repeated cluster occurs. One `recurring` operation or one coder delegation is an audit point, not a defect.
