# Handoff detail: selection gate, dispatch, auto mode

Read this before rendering the selection gate (a reason to ask, or `--safe`) or dispatching `/cure`.

## Selection gate (`--safe`, or a reason to ask)

Use the shared handoff gate in [`../../cheese/references/handoff-gate.md`](../../cheese/references/handoff-gate.md). Age's finding selection is the core decision; the tail (**Plate it**, **Checkpoint & stop**, **Stop**) follows.

1. Render the numbered selection table:

   ```
   python3 shared/scripts/findings_cli.py render-table --report .cheese/age/<slug>.md
   ```

   If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz findings_cli render-table --report .cheese/age/<slug>.md` is the fallback.
   Mark any sprawling/structural-fix row as *heavy*.
2. Ask which findings to cure. Lead each option with the verb (what the user wants to *do* next); the underlying selection verb is the backing detail. Lead with the recommended composite, then present the same four severity-floor options below it, in the same most-inclusive-to-least order, so the gate is predictable across every run:
   - **Fix mediums-and-above plus cheap lows** *(recommended)* — equivalent to `all-medium, cheap` (the composite floor defined at **Compute the recommended set** under `SKILL.md § Handoff`). The cheap lows are the small valid nits that are cheaper to fix than to defer; sprawling/structural lows are left out.
   - **Fix everything** — equivalent to `all` (every finding regardless of severity).
   - **Fix medium-severity and above** — equivalent to `all-medium` (the medium severity-floor from **Compute the recommended set**, without the cheap-lows union; add `cheap` to also union the contained-fix lows, i.e. the recommended composite above).
   - **Fix high-severity and blockers** — equivalent to `all-high` (floor at high, includes blockers).
   - **Fix blockers only** *(strict; land only the must-fix blockers and defer the rest to a follow-up)* — equivalent to `all-blocker`.

   Then offer the non-floor and standard-tail options last:
   - **Pick findings to fix** — accept a free-text reply using the verbs from `../../cure/references/selection.md`; expand the verb to finding ids:

     ```
     python3 shared/scripts/findings_cli.py parse-selection --report .cheese/age/<slug>.md --selection "<verb>"
     ```

     If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz findings_cli parse-selection ...` is the fallback.
   - **Plate it** — apply the recommended composite via `/cure <slug> --auto --open-pr --stake medium+`; terminal `/plate` resolves topology and publishes. Carry `--hard`.
   - **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause instead of curing now.
   - **Stop — leave the report for later** — equivalent to `none`.

   Present all four severity options on every run even when a severity band is empty (e.g. no blockers): a floor that resolves to an empty set is a valid, predictable no-op — do not drop or reorder options based on which bands happen to be populated. If the user selects a floor (or the recommended composite) that resolves to an empty set, treat the selection as `none`: report that no findings match and do not dispatch `/cure` with empty `resolved_ids` (the non-empty-selection contract in **Dispatch** still holds).

## Dispatch

On a non-empty selection — whether auto-selected by default or chosen at the gate — immediately dispatch `/cure <slug> [--safe] [--open-pr] [--hard]` with the selection locked in via context, not a CLI flag:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "<recognized verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` skips its own selection prompt when this context is present, re-confirms the cited ids still exist, then owns the apply / validate / push loop. Always emit `resolved_ids` alongside `selection` — expand the verb yourself rather than leaving the field empty; `/cure` re-confirms against the report regardless. Propagate `--safe`, `--open-pr`, and `--hard` to `/cure` when they are in scope.

On `none` / `Stop` (only reachable via the gate), exit cleanly with the report path.

`--auto` substitutes a severity-floor selection and its own chain — see `SKILL.md § Auto mode`.

## Within cook's own fan pathway

`/cook`'s fan pathway (its retired-`/ultracook` mechanics, now self-hosted — see `../../cook/SKILL.md § Fan pathway`) spawns age as a fresh-context sub-agent and owns the chain itself. Honour the no-chain isolation directive:

- Write `.cheese/age/<slug>.md` (with the handoff slug at the top) and stop. Do not invoke `/cure <slug> --auto --stake medium+` from inside the sub-agent.
- Set `next:` from what you observe on this run, not from any guess about chain position. `next: cure` when at least one finding meets the **medium+ floor**; `next: done` when none do.
- The two-cure-pass cap is enforced by the fan pathway's fixed chain length, not by age counting passes. The terminal age is publishable only with `next: done`; `next: cure` or a missing `next` halts without publishing. Parallel curds and post-merge review dispatch age as a top-level fresh-context reviewer, never as nested inline self-review.
