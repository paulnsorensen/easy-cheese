# Selection gate

The default selection is the **recommended composite** (`all-medium, cheap`) — mediums-and-above plus cheap contained-fix lows. `/cure` applies it without a gate unless `--safe` is passed, a recommended fix is sprawling/structural, or findings conflict — in which cases the gate below is rendered. (This inverts the old "default is empty" contract: gating is now the exception, not the rule, mirroring `/cheese`'s autonomous-by-default routing.)

`/age` and `/affinage` are the preferred places to compute this selection — they pass it to `/cure` as a pre-locked handoff so the user sees the work happen, not a "whether to run /cure" prompt. When `/age` / `/affinage` hands off with a pre-locked selection, `/cure` adopts it and skips re-rendering the table; otherwise `/cure` computes the recommended composite itself, gating only on the reasons above.

The `--auto --stake <floor>` flag pair (propagated from `/cook --auto`) substitutes a severity floor for the recommended composite and runs the headless chain. (`--stake` is a severity floor — the flag literal is preserved across callers, the underlying semantics is per-finding severity, not a dimension bucket.) See `## Auto-mode selection` at the bottom of this file.

## Handoff from /age

When `/age` or `/affinage` resolves a non-empty selection — auto-selected by default (the recommended composite) or chosen at the gate — it dispatches `/cure <slug>` with the selection locked in by passing a structured context block alongside the invocation:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5 | all-blocker | all-high | all-medium | cheap | all | skip N"
  resolved_ids: [1, 3, 5]
```

Both `selection` (the verb) and `resolved_ids` (the expanded list) are required. `/age` expands the verb before dispatch so `/cure` never has to interpret it; `/cure` re-confirms the resolved ids against the report and goes straight to apply.

There is no CLI flag (`--select` is not a supported syntax). The selection travels in the handoff context, not as a parsed argument.

## Rendering the selection list

When invoked with a slug, load `.cheese/age/<slug>.md` and render a numbered table grouped by severity (`blocker` first, then `high → medium → low`):

```text
| # | severity | dim           | location                  | summary |
|---|----------|---------------|---------------------------|---------|
| 1 | blocker  | encapsulation | src/users/index.ts:42     | `index` re-exports `SqlPgUser` across slice boundary. |
| 2 | high     | security      | src/handler.ts:108        | Unvalidated path joined into fs.read. |
| 3 | medium   | complexity    | src/util.ts:200-240       | Function is 41 lines and 4 levels nested. |
| 4 | low      | deslop        | src/old.ts:55-60          | Unused export `_helper`. |
```

If no slug is supplied, accept any of: a pasted findings list, a `.cheese/age/` path, a CI failure summary, or "fix the high-severity age findings" — and re-render as the same table.

## Recognized selection verbs

```
1,3,5         # specific item ids
all-blocker   # every blocker-severity item (strict; no high included)
all-high      # every blocker- or high-severity item (floor at high; matches --stake high auto-floor)
all-medium    # every blocker-, high-, or medium-severity item (floor at medium; compose `all-medium, cheap` to match the --stake medium+ auto-floor, which also sweeps cheap lows)
cheap         # every finding where fix-cost-now == contained, regardless of severity
all           # every item (requires explicit type-out, not assumed)
none          # explicit opt-out; exit cleanly (the default is the recommended composite — see Hard rules)
skip N        # drop item N from the change-order
```

Interactive verbs use **floor** semantics, aligned with auto-mode: `all-blocker` is the only strict selector (because blocker is the top of the ladder, there is nothing above it to include); `all-high` includes blockers + high; `all-medium` includes blockers + high + medium; compose `all-medium, cheap` to match the `medium+` auto-floor, which also sweeps cheap lows. Use composition (`all-blocker, ...`) when you specifically want strict blocker-only behaviour combined with another verb.

### Verb composition

Verbs may be combined with commas. Set algebra:

- `all-blocker, cheap` = blockers ∪ contained-fix-cost findings; dedup at apply time.
- `all-high, 7` = every blocker- or high-severity item ∪ item #7.
- `all-blocker, cheap, skip 4` = (blockers ∪ contained-fix-cost) − item #4.

`skip N` always applies last. `all` and `none` are mutually exclusive with every other verb.

When an age report lacks the `fix-cost-now` sub-field on its findings (older report shape), treat `cheap` as resolving to the empty set and emit a one-line note in the cure report explaining the older shape; never silently expand `cheap` against missing data.

## Hard rules

- **Default is the recommended composite (`all-medium, cheap`).** Applied without a gate unless `--safe`, a sprawling/structural fix, or conflicting findings forces the gate. When the gate *is* rendered, a bare return / "ok" / "go" selects the pre-selected recommended composite.
- **`all` is opt-in only.** The default sweeps mediums-and-above plus cheap lows, never the expensive lows — `all` still requires an explicit type-out.
- **Selection is locked once chosen.** If new findings appear during cure (e.g. a fix exposes a new bug), surface them in the report and let the user re-invoke `/cure`.

## After selection

For each selected finding:

1. Re-read the cited file/lines via `cheez-read` to confirm the finding is still accurate (the diff may have moved).
2. Apply the fix via `cheez-write` using hash anchors.
3. Run the narrowest test that proves the fix.
4. Move to the next selected item.

If a finding is no longer applicable (file moved, code already fixed), record it in the cure report under "Skipped" with the reason. Do not silently drop it.

## Auto-mode selection

When `/cure` is invoked with `--auto --stake <floor>`:

- **Skip the selection list and the user prompt entirely.** The selection is computed from the severity floor, not asked for. (The flag literal stays `--stake` for caller stability; the underlying semantics is per-finding severity.)
- **Severity floors:**
  - `blocker` — only `blocker` severity findings.
  - `high` — `blocker` and `high` severity findings.
  - `medium+` — `blocker`, `high`, and `medium` severity findings, **plus every `Low` whose `fix-cost-now: contained`** (cheap lows — small valid nits cheaper to fix than to defer; `moderate`/`sprawling`/`structural` lows are excluded). This is what `/cook --auto` always passes, so the autonomous chain fixes mediums-and-above and the cheap lows. It is the auto analogue of the recommended interactive selection `all-medium, cheap`.
  - `all` — every finding regardless of severity.
- **Cheap lows ride the `medium+` floor only.** There is no standalone `--stake cheap`. The `medium+` floor sweeps contained-fix lows automatically (above); the `blocker` and `high` floors do not (they are strict severity thresholds), and `all` already includes every low. To combine `cheap` with a different floor, invoke `/cure <slug>` interactively and type a composite verb like `all-blocker, cheap`.
- **Order of application:** blocker first, then high, then medium, then — under the `medium+` floor — the cheap lows, in the order they appear in the age report. Within a severity band, group by file to minimise re-reads.
- **Per-finding flow is the same as interactive:** `cheez-read` to re-confirm, `cheez-write` to apply, narrowest test to verify.
- **On test breakage:** revert that single finding's edit, log it under the cure report's `### Deferred` section with the test name and one-line failure summary, and continue with the next finding. Do not stop the whole pass for one bad fix.
- **On a finding that is no longer applicable** (file moved, code already fixed): record under `### Skipped` exactly as in interactive mode.
- **After all selected findings are processed:** invoke `/age --scope <touched-paths> --auto` directly (no handoff gate). The pass-cap is enforced inside `/age --auto`, not here — cure keeps applying when called.

`--auto` is not a verb the user should type interactively. It exists to make the `/cook --auto` chain coherent. If a user types `/cure --auto` directly without `--stake`, error out with a one-line message pointing them at standard interactive `/cure <slug>` — `--stake` is the contract for auto mode, and without it `/cure --auto` has no inclusion threshold. Do not prompt for a floor; do not silently fall back to interactive selection.
