# Mold review canvas

Use the bundled review canvas when visual artifacts or browser interaction help resolve Mold forks.

## Procedure

1. Publish the review document with `python3 skills/mold/scripts/mold.pyz review publish --state-dir DIR --input FILE [--base-revision N]`.
2. Start `python3 skills/mold/scripts/mold.pyz review serve --state-dir DIR --port 0` and give the returned private URL to the user.
3. Read submitted snapshots with `python3 skills/mold/scripts/mold.pyz review poll --state-dir DIR --after CURSOR --timeout SECONDS`.
4. Reconcile each exact question and option identifier into the decision ledger.
5. Publish a new revision when the review document changes. Never replace dirty feedback silently.
6. Stop the server with `python3 skills/mold/scripts/mold.pyz review close --state-dir DIR` when the review ends.

## Review document

The canvas requires only `questions`. Every other field is optional, and the canvas hides a view when its field is absent.

| Field | Shape | Canvas use |
|---|---|---|
| `questions` | `[{id, prompt, meta?, selection_mode, recommended_option_id?, options: [{id, label, tradeoff?}]}]` | Fork cards in the conversation rail |
| `goal`, `goal_emphasis` | strings | Page title; the emphasis substring shows in the accent color |
| `tier`, `stage` | strings (`stage`: `bounds`, `shape`, `sketch`, or `decision map`) | Eyebrow; `decision map` opens that view first |
| `summary`, `agent_status` | strings | Agent message and status line above the forks |
| `ledger` | `[{label, tone?, text?, items?: [{id, text}]}]` | Ledger view; the label `asking` uses the accent color |
| `placement` | `{badge?, rows: [{key, value, highlight?}]}` | Placement view; multi-line values align under the key |
| `artifacts` | existing artifact list | Diagram view; without artifacts the view shows scratch Mermaid and Excalidraw panels |
| `gates` | `{items: [{label, state}]}` (`met`, `current`, `open`, or `na`) | Gates view |
| `decision_map` | `{settled, open: [{id, text, marker?}], verdict?: {title, lines}}` | Decision map view |
| `trail` | `[{label, state, note?, position}]` (`answered` or `waiting`; `before` or `after`) | Settled and blocked forks around the current fork |
| `revisions` | `[{label, note?}]` | Revisions popover |
| `shape_note` | string | Note under the shape views |

Text in `ledger`, `decision_map`, and `summary` renders `` `code` `` spans as chips. Document text always renders as inert text, never as HTML.

`frontend/mold-review/examples/` holds one document for each stage.

## Feedback

A submission carries `answers`, `notes` (the composer text), `pins`, `annotations`, `view`, `scene`, `artifacts`, and `mermaid_source`. Each pin is `{id, anchor, text}`, where `anchor` names the part of the canvas, for example `placement › public`. `annotations` repeats the pins as numbered plain text. `end_session: true` means the user chose `send & end` and wants the Mold session to stop after this feedback.

Autosave only preserves a working copy. `Send to agent` creates feedback, not approval.

Browser feedback never satisfies the taste gate, typed-plan gate, or two-key handshake.

The canvas is optional. It is a local-only review aid, not an approval mechanism. It must not request approval, bypass the taste gate, bypass the typed-plan gate, or bypass the two-key handshake.
