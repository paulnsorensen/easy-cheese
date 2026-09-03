# Selection gate

The default selection is the **recommended composite**: `all-medium, cheap`.
It includes medium and higher findings plus inexpensive contained low findings.
Apply it without a gate by default.

Render the gate when `--safe` is present.
Also render it for a structural fix, a wide fix, or conflicting findings.
A rendered gate preselects the recommended composite.
This rule replaces the old empty default.

`/age` and `/affinage` normally calculate the selection.
They pass a locked selection to `/cure`.
This handoff lets the user see the fix work without another prompt.
If no locked selection exists, Cure calculates the recommended composite.

`--auto --stake <floor>` replaces the composite with a severity floor.
`/cook --auto` passes this pair.
Read `## Auto-mode selection` for its rules.

## Handoff from /age

When `/age` or `/affinage` selects findings, it dispatches `/cure <slug>`.
It passes this block with the invocation:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5 | all-blocker | all-high | all-medium | cheap | all | skip N"
  resolved_ids: [1, 3, 5]
```

Both `selection` and `resolved_ids` are required.
`selection` stores the verb.
`resolved_ids` stores the expanded identifiers.
The source skill expands the verb before dispatch.
Cure checks the identifiers against the report and applies them.

Do not use a `--select` CLI flag.
The selection moves through the handoff context.

## Render the selection list

With a slug, read `.cheese/age/<slug>.md`.
Render a numbered table by severity.
Use blocker, high, medium, then low order.

```text
| # | severity | confidence  | dim           | location                  | summary |
|---|----------|-------------|---------------|---------------------------|---------|
| 1 | blocker  | certain     | encapsulation | src/users/index.ts:42     | `index` re-exports `SqlPgUser` across slice boundary. |
| 2 | high     | certain     | security      | src/handler.ts:108        | Unvalidated path joined into fs.read. |
| 3 | medium   | speculating | complexity    | src/util.ts:200-240       | Function is 41 lines and 4 levels nested. |
| 4 | low      | certain     | deslop        | src/old.ts:55-60          | Unused export `_helper`. |
```

Without a slug, accept a findings list, Age path, CI summary, or scoped fix request.
Render the same table.

## Recognized selection verbs

```text
1,3,5         # specific item ids
all-blocker   # every blocker item
all-high      # every blocker or high item
all-medium    # every blocker, high, or medium item
cheap         # every contained-cost item
all           # every item; requires explicit input
none          # explicit opt-out
skip N        # remove item N from the application order
```

Interactive selectors use floor semantics.
`all-blocker` contains only blockers because blocker is the highest level.
`all-high` includes blockers and high findings.
`all-medium` includes blockers, high findings, and medium findings.
Combine `all-medium, cheap` to match the `medium+` automatic floor.

### Verb composition

Combine verbs with commas:

- `all-blocker, cheap` selects blockers and contained-cost findings.
- `all-high, 7` selects blocker and high findings plus item 7.
- `all-blocker, cheap, skip 4` selects the first two groups without item 4.

Remove duplicates when you apply the selection.
Apply `skip N` last.
Do not combine `all` or `none` with another verb.

Older reports can lack `fix-cost-now`.
For these reports, resolve `cheap` to the empty set.
Add one note to the Cure report.
Do not infer cost from missing data.

## Hard rules

- Use `all-medium, cheap` by default.
  Apply it without a gate unless a gate condition exists.
  At a rendered gate, bare return, `ok`, or `go` selects it.
- Require explicit input for `all`.
  The default excludes costly low findings.
- Lock the selection after the user or source skill selects it.
  Report new findings and let the user start another `/cure` run.

## After selection

For each selected finding:

1. Read the cited location again and confirm that the finding still applies.
2. Apply a stale-safe edit that matches the read anchor.
3. Follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md).
4. Run the narrowest test that proves the fix.
5. Continue to the next finding.

When a finding no longer applies, put it under `Skipped` with the reason.
Do not remove it silently.

## Auto-mode selection

When `/cure` receives `--auto --stake <floor>`, skip the list and user prompt.
Calculate the selection from the floor.

Use these floors:

- `blocker` selects blocker findings.
- `high` selects blocker and high findings.
- `medium+` selects blocker, high, and medium findings.
  It also selects low findings with `fix-cost-now: contained`.
- `all` selects every finding.

`/cook --auto` always passes `medium+`.
This floor matches the interactive `all-medium, cheap` selection.
Do not support a separate `--stake cheap` value.
Use an interactive composite to combine cheap findings with another floor.

Apply blocker, high, medium, then inexpensive low findings.
Within one severity, group findings by file to reduce repeated reads.
For each finding, follow `## After selection`.

When a fix breaks a passing test or project gate, revert that finding's edit.
Put it under `### Deferred` with the test name and failure summary.
Continue with the remaining findings.

When a finding no longer applies, put it under `### Skipped`.
After all findings, invoke `/age --scope <touched-paths> --auto` directly (no handoff gate).
`/age --auto` enforces the pass cap.
Cure continues to apply findings when Age calls it.

`--auto` is not an interactive verb.
If `/cure --auto` lacks `--stake`, return one error line.
Direct the user to `/cure <slug>`.
Do not prompt for a floor or fall back to interactive selection.

## Older report shape

Older Age reports can lack `severity`, `location`, `fix-cost-now`, and `fix-cost-later`.
When `severity` is absent, infer it from the section heading.
For example, `## High-stake findings` maps to `high`.
When `fix-cost-now` is absent, resolve `cheap` to the empty set.
Record each inference under `### Notes` in the Cure report.
Treat missing `confidence:` as unspecified.
Do not infer confidence or reject the report.
