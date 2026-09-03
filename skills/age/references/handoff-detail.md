# Handoff detail: selection gate, dispatch, auto mode

Read this before rendering the selection gate (a reason to ask, or `--safe`) or dispatching `/cure`.

## Selection gate (`--safe`, or a reason to ask)

Use the shared handoff gate in [`../../cheese/references/handoff-gate.md`](../../cheese/references/handoff-gate.md).
Age's finding selection is the core decision.
The tail (**Plate it**, **Checkpoint & stop**, **Stop**) follows.

1. Render the numbered selection table:

   ```
   python3 skills/age/scripts/age.pyz findings-cli render-table --report .cheese/age/<slug>.md
   ```

   Mark any sprawling/structural-fix row as *heavy*.
2. Ask which findings to cure.
Lead each option with the verb that describes what the user wants to *do* next.
Use the underlying selection verb as the backing detail.
Lead with the recommended composite.
Then present the same four severity-floor options below it.
Keep the options in the same most-inclusive-to-least order.
This order keeps the gate predictable across every run:
- **Fix mediums-and-above plus cheap lows** *(recommended)* — equivalent to `all-medium, cheap`.
  This composite floor appears under **Compute the recommended set** in `SKILL.md § Handoff`.
  Cheap lows are small, valid nits that cost less to fix now than to defer.
  Leave sprawling/structural lows out.
- **Fix everything** — use `all` for every finding, regardless of severity.
- **Fix medium-severity and above** — use `all-medium`.
  This option uses the medium severity floor from **Compute the recommended set**.
  It excludes the cheap-lows union.
  Add `cheap` to include contained-fix lows and use the recommended composite.
  - **Fix high-severity and blockers** — equivalent to `all-high` (floor at high, includes blockers).
- **Fix blockers only** *(strict)* — use `all-blocker`.
  Land only the must-fix blockers.
  Defer the rest to a follow-up.

Offer the non-floor and standard-tail options last.
- **Pick findings to fix** — accept a free-text reply using the verbs from `../../cure/references/selection.md`.
  Expand the verb to finding ids.

  ```
  python3 skills/age/scripts/age.pyz findings-cli parse-selection --report .cheese/age/<slug>.md --selection "<verb>"
  ```

- **Plate it** — apply the recommended composite via `/cure <slug> --auto --open-pr --stake medium+`.
  Terminal `/plate` resolves topology and publishes.
  Carry `--hard`.
- **Checkpoint & stop** — run `/wheypoint` to write a resumable handoff and pause instead of curing now.
- **Stop — leave the report for later** — use `none`.

Present all four severity options on every run.
Present them even when a severity band is empty, such as no blockers.
Treat a floor that resolves to an empty set as a valid, predictable no-op.
Do not drop or reorder options based on the populated bands.
If the selected floor or recommended composite resolves to an empty set, treat it as `none`.
Report that no findings match.
Do not dispatch `/cure` with empty `resolved_ids`.
The non-empty-selection contract in **Dispatch** still holds.

## Dispatch

Dispatch `/cure <slug> [--safe] [--open-pr] [--hard]` immediately when the selection is non-empty.
Apply this rule to automatic selections and gate selections.
Pass the selection through context, not a CLI flag.
Invoke `/cure` instead of repairing files in the review context.
End the report with `/age`.
Step 1 review lock rejects a report after inline edits.

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "<recognized verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` skips its own selection prompt when this context is present.
`/cure` re-confirms that the cited ids still exist.
`/cure` owns the apply / validate / push loop.
Always emit `resolved_ids` alongside `selection`.
Expand the verb yourself instead of leaving the field empty.
`/cure` re-confirms the ids against the report regardless.
Propagate `--safe`, `--open-pr`, and `--hard` to `/cure` when they are in scope.

On `none` or Stop (only reachable via the gate), exit cleanly with the report path.
`--auto` substitutes a severity-floor selection and its own chain. See `SKILL.md § Auto mode`.

## Within cook's own fan pathway

The `/cook` fan pathway uses its retired-`/ultracook` mechanics, now self-hosted.
See `../../cook/SKILL.md § Fan pathway`.
The pathway spawns age as a fresh-context sub-agent and owns the chain.
Follow the no-chain isolation directive:

- Write `.cheese/age/<slug>.md` with the handoff slug at the top.
  Stop after writing it.
  Do not invoke `/cure <slug> --auto --stake medium+` from inside the sub-agent.
- Set `next:` from what you observe on this run.
  Do not infer it from the chain position.
  Set `next: cure` when at least one finding meets the **medium+ floor**.
  Set `next: done` when no finding meets that floor.
- The fan pathway's fixed chain length enforces the two-cure-pass cap.
  Age does not count passes.
  Publish the terminal age only with `next: done`.
  Treat `next: cure` or a missing `next` as a halt without publishing.
  Dispatch parallel curds and post-merge review as a top-level fresh-context reviewer.
  Never dispatch them as nested inline self-review.
