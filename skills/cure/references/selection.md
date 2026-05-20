# Selection gate

`/cure` never applies findings without an explicit selection. The default selection is empty.

`/age` is the preferred place to render this gate — it inverts the path so the user is asked *which findings to cure* immediately after the report lands, rather than first being asked *whether to run /cure*. When `/age` hands off with a pre-locked selection, `/cure` adopts it and skips re-rendering the table; otherwise `/cure` renders the table itself using the same shape below.

The only sanctioned bypass of the selection rule is the `--auto --stake <floor>` flag pair, propagated from `/cook --auto`. (`--stake` is a severity floor — the flag literal is preserved across callers, the underlying semantics is per-finding severity, not a dimension bucket.) See `## Auto-mode selection` at the bottom of this file. Outside of auto mode, every rule below applies as written.

## Handoff from /age

When `/age` completes the selection gate and the user picks a non-empty set, it dispatches `/cure <slug>` with the selection locked in by passing a structured context block alongside the invocation:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5 | all-blocker | all-high | cheap | all | skip N"
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
cheap         # every finding where fix-cost-now == contained, regardless of severity
all           # every item (requires explicit type-out, not assumed)
none          # default; exit cleanly
skip N        # drop item N from the change-order
```

Interactive verbs use **floor** semantics, aligned with auto-mode: `all-blocker` is the only strict selector (because blocker is the top of the ladder, there is nothing above it to include); `all-high` includes blockers + high; future `all-medium` would include blockers + high + medium. Use composition (`all-blocker, ...`) when you specifically want strict blocker-only behaviour combined with another verb.

### Verb composition

Verbs may be combined with commas. Set algebra:

- `all-blocker, cheap` = blockers ∪ contained-fix-cost findings; dedup at apply time.
- `all-high, 7` = every blocker- or high-severity item ∪ item #7.
- `all-blocker, cheap, skip 4` = (blockers ∪ contained-fix-cost) − item #4.

`skip N` always applies last. `all` and `none` are mutually exclusive with every other verb.

When an age report lacks the `fix-cost-now` sub-field on its findings (older report shape), treat `cheap` as resolving to the empty set and emit a one-line note in the cure report explaining the older shape; never silently expand `cheap` against missing data.

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

- **Skip the selection list and the user prompt entirely.** The selection is computed from the severity floor, not asked for. (The flag literal stays `--stake` for caller stability; the underlying semantics is per-finding severity.)
- **Severity floors:**
  - `blocker` — only `blocker` severity findings.
  - `high` — `blocker` and `high` severity findings.
  - `medium+` — `blocker`, `high`, and `medium` severity findings. This is what `/cook --auto` always passes.
  - `all` — every finding regardless of severity.
- **`cheap` has no auto-mode equivalent.** The `cheap` selection verb is interactive-only — there is no `--auto --stake cheap`. To combine `cheap` with severity selection, invoke `/cure <slug>` interactively and type a composite verb like `all-blocker, cheap`. Auto mode operates strictly on the four severity floors above.
- **Order of application:** blocker first, then high, then medium, in the order they appear in the age report. Within a severity band, group by file to minimise re-reads.
- **Per-finding flow is the same as interactive:** `cheez-read` to re-confirm, `cheez-write` to apply, narrowest test to verify.
- **On test breakage:** revert that single finding's edit, log it under the cure report's `### Deferred` section with the test name and one-line failure summary, and continue with the next finding. Do not stop the whole pass for one bad fix.
- **On a finding that is no longer applicable** (file moved, code already fixed): record under `### Skipped` exactly as in interactive mode.
- **After all selected findings are processed:** invoke `/age --scope <touched-paths> --auto` directly (no handoff gate). The pass-cap is enforced inside `/age --auto`, not here — cure keeps applying when called.

`--auto` is not a verb the user should type interactively. It exists to make the `/cook --auto` chain coherent. If a user types `/cure --auto` directly without `--stake`, error out with a one-line message pointing them at standard interactive `/cure <slug>` — `--stake` is the contract for auto mode, and without it `/cure --auto` has no inclusion threshold. Do not prompt for a floor; do not silently fall back to interactive selection.
