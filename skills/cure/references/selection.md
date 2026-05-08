# Selection gate

`/cure` never applies findings without an explicit selection. The default selection is empty.

`/age` is the preferred place to render this gate — it inverts the path so the user is asked *which findings to cure* immediately after the report lands, rather than first being asked *whether to run /cure*. When `/age` hands off with a pre-locked selection, `/cure` adopts it and skips re-rendering the table; otherwise `/cure` renders the table itself using the same shape below.

The only sanctioned bypass of the selection rule is the `--auto --stake <floor>` flag pair, propagated from `/cook --auto`. See `## Auto-mode selection` at the bottom of this file. Outside of auto mode, every rule below applies as written.

## Handoff from /age

When `/age` completes the selection gate and the user picks a non-empty set, it dispatches `/cure` with the selection locked in by passing the chosen ids as plain text in the invocation context — the same verbs accepted at the prompt (`1,3,5`, `all-high`, etc.). `/cure` reads this from the dispatch context, skips rendering the selection table, and goes straight to apply.

There is no CLI flag (`--select` is not a supported syntax). The selection travels as prose context in the `AskUserQuestion` resolution, not as a parsed argument.

## Rendering the selection list

When invoked with a slug, load `.cheese/age/<slug>.md` and render a numbered table grouped by stake:

```text
| # | stake  | dim          | location                  | summary |
|---|--------|--------------|---------------------------|---------|
| 1 | high   | correctness  | src/auth.ts:42-50         | Token check uses == on bytes; switch to constant-time. |
| 2 | high   | security     | src/handler.ts:108        | Unvalidated path joined into fs.read. |
| 3 | medium | complexity   | src/util.ts:200-240       | Function is 41 lines and 4 levels nested. |
| 4 | medium | deslop       | src/old.ts:55-60          | Unused export `_helper`. |
```

If no slug is supplied, accept any of: a pasted findings list, a `.cheese/age/` path, a CI failure summary, or "fix the high-stake age findings" — and re-render as the same table.

## Recognized selection verbs

```
1,3,5         # specific item ids
all-high      # every high-stake item
all           # every item (requires explicit type-out, not assumed)
none          # default; exit cleanly
skip N        # drop item N from the change-order
```

## Hard rules

- **Default is `none`.** A bare return / "ok" / "go" is not a selection.
- **`all` is opt-in only.** Never assume the user wants everything.
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

- **Skip the selection list and the user prompt entirely.** The selection is computed from the stake floor, not asked for.
- **Stake floors:**
  - `high` — only `high` stake findings.
  - `medium+` — `high` and `medium` stake findings. This is what `/cook --auto` always passes.
  - `all` — every finding regardless of stake.
- **Order of application:** high stake first, then medium, in the order they appear in the age report. Within a stake band, group by file to minimise re-reads.
- **Per-finding flow is the same as interactive:** `cheez-read` to re-confirm, `cheez-write` to apply, narrowest test to verify.
- **On test breakage:** revert that single finding's edit, log it under the cure report's `### Deferred` section with the test name and one-line failure summary, and continue with the next finding. Do not stop the whole pass for one bad fix.
- **On a finding that is no longer applicable** (file moved, code already fixed): record under `### Skipped` exactly as in interactive mode.
- **After all selected findings are processed:** invoke `/age --scope <touched-paths> --auto` directly (no `AskUserQuestion`). The pass-cap is enforced inside `/age --auto`, not here — cure keeps applying when called.

`--auto` is not a verb the user should type interactively. It exists to make the `/cook --auto` chain coherent. If a user types `/cure --auto` directly without `--stake`, error out with a one-line message pointing them at standard interactive `/cure <slug>` — `--stake` is the contract for auto mode, and without it `/cure --auto` has no inclusion threshold. Do not prompt for a floor; do not silently fall back to interactive selection.
