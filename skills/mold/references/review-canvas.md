# Mold review canvas

Use the bundled review canvas when visual artifacts or browser interaction help resolve Mold forks.

## Procedure

1. Publish the review document with `python3 skills/mold/scripts/mold.pyz review publish --state-dir DIR --input FILE [--base-revision N]`.
2. Start `python3 skills/mold/scripts/mold.pyz review serve --state-dir DIR --port 0` and give the returned private URL to the user.
3. Read submitted snapshots with `python3 skills/mold/scripts/mold.pyz review poll --state-dir DIR --after CURSOR --timeout SECONDS`.
4. Reconcile each exact question and option identifier into the decision ledger.
5. Publish a new revision when the review document changes. Never replace dirty feedback silently.
6. Stop the server with `python3 skills/mold/scripts/mold.pyz review close --state-dir DIR` when the review ends.

Autosave only preserves a working copy. `Send to agent` creates feedback, not approval.

Browser feedback never satisfies the taste gate, typed-plan gate, or two-key handshake.

The canvas is optional. It is a local-only review aid, not an approval mechanism. It must not request approval, bypass the taste gate, bypass the typed-plan gate, or bypass the two-key handshake.
