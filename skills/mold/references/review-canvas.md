# Mold review canvas

Use the bundled review canvas when visual artifacts or browser interaction help resolve Mold forks.

## Procedure

1. Publish the review document with `python3 skills/mold/scripts/mold.pyz review publish --state-dir DIR --input FILE [--base-revision N]`.
2. Start `python3 skills/mold/scripts/mold.pyz review serve --state-dir DIR --port 0` and give the returned private URL to the user.
3. Read submitted snapshots with `python3 skills/mold/scripts/mold.pyz review poll --state-dir DIR --after CURSOR --timeout SECONDS`.
4. Reconcile each exact question and option identifier into the decision ledger. Fold `notes` and each pin's `anchor` and `text` into that ledger.
5. Publish a new revision when the review document changes. Never replace dirty feedback silently.
6. When feedback carries `end_session: true`, run `python3 skills/mold/scripts/mold.pyz review close --state-dir DIR` and stop polling. This flag marks the user's choice to end the session, not approval.
7. Stop the server with `python3 skills/mold/scripts/mold.pyz review close --state-dir DIR` when the review ends for another reason.

## Remote access over Tailscale

Use this mode only when the user asks to open the canvas from another tailnet device.
If `tailscale` is missing, `Self.DNSName` is empty, or the tailnet has no HTTPS certificates, tell the user that remote access is unavailable.
Then serve without `--trusted-host` and give the loopback `url`, or continue the review in conversation.

1. Read the node name from `tailscale status --json` at `Self.DNSName`, without the trailing dot.
2. Add `--trusted-host NODE.TAILNET.ts.net` to `review serve`.
3. Give the user the `tailscale_serve` command from the launch output.
   Give the user the `remote_url` from the launch output.
4. Tell the user that the `tailscale_serve` command replaces an existing HTTPS mapping on port 443.
   To keep that mapping, add `--https=PORT` to the command.
   Then add `:PORT` to the host in `remote_url`.
5. After the review closes, tell the user to remove the mapping with `tailscale serve --https=PORT off`.

The server still binds `127.0.0.1` and never starts or stops `tailscale serve` itself.
It accepts the trusted host only with `X-Forwarded-Proto: https` and an `https://` origin.
It refuses every request that carries `Tailscale-Funnel-Request`, so Funnel never exposes the canvas.
The launch token still protects every request.
The tailnet needs MagicDNS and HTTPS certificates.

## Review document

The canvas requires only `questions`. Every other field is optional, and the canvas hides a view when its field is absent.

| Field | Shape | Canvas use |
|---|---|---|
| `questions` | `[{id, prompt, meta?, selection_mode, recommended_option_id?, depends_on?, options: [{id, label, tradeoff?}]}]` | Open fork cards in the conversation rail |
| `requirements` | `[{id, text, status, fork_ids?}]`; status is `settled` or `draft` | Full EARS text and linked forks in a persistent, scrollable pane outside the shape tabs; drafts list before settled entries |
| `settled_fork_ids` | list of question IDs | Every decision the agent has reconciled so far; cumulative, and republished in full each round, not only the ones settled in this revision |
| `goal`, `goal_emphasis` | strings | Page title; the emphasis substring shows in the accent color |
| `tier`, `stage` | strings (`stage`: `bounds`, `shape`, `sketch`, or `decision map`) | Eyebrow; `decision map` opens that view first |
| `summary`, `agent_status` | strings | Agent message and status line above the forks |
| `ledger` | `[{label, tone?, text?, items?: [{id, text}]}]` | Ledger view; the label `asking` and tone `accent` use the accent color; the label `agent-decided` and tone `dim` mute the row's items |
| `placement` | `{title?, badge?, rows: [{key, value, highlight?}]}` | Placement view; `title` defaults to "Placement"; multi-line values align under the key |
| `artifacts` | existing artifact list | Diagram view; without artifacts the view shows scratch Mermaid and Excalidraw panels |
| `gates` | `{items: [{label, state}]}` (`met`, `current`, `open`, or `na`) | Gates view |
| `decision_map` | `{settled: [{id, text}], open: [{id, text, marker?}], verdict?: {title, lines}}` | Decision map view |
| `trail` | `[{label, state, note?, position}]` (`answered` or `waiting`; `before` or `after`) | Settled and blocked forks around the current fork |
| `revisions` | `[{label, note?}]` | Revisions popover |
| `shape_note` | string | Note under the shape views |

Text in `ledger`, `decision_map`, and `summary` renders `` `code` `` spans as chips. Document text always renders as inert text, never as HTML.

Publish the entire current EARS requirement list each round, including settled and draft entries. Keep stable requirement and fork IDs. Link each requirement to its relevant fork cards through `fork_ids`. A linked fork shows its prompt and, when not answerable, its waiting or dependency-error state; a settled fork shows its ID. An unresolved link remains visible.

A question's optional `depends_on` lists prerequisite question IDs. The question is answerable only when every prerequisite is in `settled_fork_ids` and absent from `questions`. Local selection, autosave, submission, and restored feedback never settle a fork. The browser shows waiting and dependency-error questions but disables their controls, shows no restored answer on them, and excludes their answers from feedback. Missing references and malformed dependencies show a dependency error. Cycles remain waiting. The agent reconciles feedback and publishes a new revision before dependent forks become answerable.

Independent, already-explained forks can share one batch submission. Do not batch a dependent fork before its prerequisites settle. Legacy documents without these fields retain their existing rendering and answer behavior. Desktop requirements sit above shapes beside the conversation. Narrow screens stack requirements, shapes, and conversation in separate, non-overlapping scroll panes. Each pane keeps a usable minimum height. The page scrolls on short screens. Legacy documents keep the phone sheet.

`frontend/mold-review/examples/` holds three documents: `01-bounds.json`, `02-sketch.json`, and `03-decision-map.json`.

## Feedback

A submission carries `answers`, `notes` (the composer text), `pins`, `annotations`, `view`, `scene`, `artifacts`, and `mermaid_source`. Each pin is `{id, anchor, text}`, where `anchor` names the part of the canvas, for example `placement › public`. `annotations` repeats the pins as numbered plain text. `end_session: true` means the user chose `send & end` and wants the Mold session to stop after this feedback.

Autosave only preserves a working copy. `Send to agent` creates feedback, not approval. Waiting and dependency-error questions never appear in submitted `answers`, even if an earlier working copy holds an answer.

Browser feedback never satisfies the taste gate, typed-plan gate, or coherence self-check.

The canvas is optional. It is a loopback-bound review aid, not an approval mechanism. It must not request approval, bypass the taste gate, bypass the typed-plan gate, or bypass the coherence self-check.
