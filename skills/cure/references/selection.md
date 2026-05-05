# Selection gate

`/cure` never applies findings without an explicit selection. The default selection is empty.

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
