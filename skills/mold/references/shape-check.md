# The shape check

Run this before drafting in Sketch mode. Also run it whenever discussion in any mode depends on "what does this touch" or "what depends on this". The check is read-only. Culture and mold both run it; only the artifact stage differs.

## What it answers

- **Signatures**: what does the touched function/type look like today? What sibling signatures already exist in the same module so a new one fits convention?
- **Callers** (upstream): who calls the touched symbol, and from which modules?
- **Callees** (downstream): what does the touched symbol call into? Surfaced by the same symbol query — `kind: "symbol"` returns a `── calls ──` footer with one-hop callees. No extra call.
- **Imports / blast radius**: which files import this module? Which does this module import?

These four answers describe the change's shape and bound its blast radius. Upstream identifies who breaks if you change it. Downstream identifies what you could pull into the change. InlineCoder-style bidirectional inlining gives the downstream half empirical value for repo-level edits. Ignoring it leaves a known gap.

## Procedure

Run all three. Cheap when the answers are small; the cost of skipping is silent misrouting later.

| Question | Backend capability | Call |
| --- | --- | --- |
| Current signature? Sibling signatures? Downstream callees (`── calls ──` footer)? | semantic symbol search | `tilth_search(queries: [{query: "<symbol>", kind: "symbol"}], expand: 2, scope: "<module>")` |
| Who calls this? (upstream) | semantic caller search | `tilth_search(queries: [{query: "<symbol>", kind: "callers"}])` |
| What's the import / blast radius? | dependency search | `tilth_deps(path: "<file>")` |

The first call serves two purposes. Its `── calls ──` footer provides the cheap callee read. Do not issue a separate query.

For multi-symbol changes, batch up to five symbols in a single semantic search call (`query: "a, b, c"`). Re-run only when a new symbol enters scope. Follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md).

## Output expected before exit

A summary at the top of the Sketch turn (or culture's blast-radius step):

```
Shape check on <symbol(s)>:
  signature(s):  <one line per touched seam>
  callers:       <count> sites in <N> non-test files (paths)
  callees:       <count> one-hop calls (names) — omit line if empty
  blast radius:  imported by <count> files; imports <count> modules
  verdict:       low | medium | high
```

The `callees` line is optional — print it only when the symbol query's `── calls ──` footer is non-empty. A leaf function with no callees should drop the line, not print `0`.

A `high` verdict means multi-module callers or more than five importers. It makes the Grill gate mandatory in mold; see `handshake.md`. Before continuing trade-off talk, culture must label the option `[high blast radius]`.

## When semantic source tooling is unavailable

Shape-check must not block dialogue when its preferred tools are missing. Use a sanctioned alternative when available. **For shape-check specifically, do not substitute textual search**. `grep` / `rg` over a symbol name counts string occurrences, not callers or importers. A guessed blast-radius verdict is worse than an unknown.

- **Callers / callees**: fall back to LSP `textDocument/references` / `textDocument/prepareCallHierarchy` when a language server is reachable. Note the substitution out loud.
- **Imports / blast radius**: no LSP equivalent. Skip the count, mark the line `unknown`, and lean on the verdict downgrade below.
- **Verdict**: cap it at `[?]`, not `low | medium | high`. A guessed verdict is worse than an honest unknown. For gating, Sketch and culture must treat `[?]` like `high` until the user accepts the gap. The Grill gate engages, and culture labels the option `[high blast radius]`.

If both tilth and LSP are unavailable, say so once and proceed with `[?]`. Do not silently substitute a textual search for the shape-check itself.

## When to skip

- The touched symbol has zero callers (greenfield) — say so out loud.
- The change affects one private function in one file and has no exports. Sibling signature lookup still applies. You can skip dependencies and callers.
- The user explicitly said `skip the shape check`.

## Why

Trade-offs and seams discussed without a shape check rely on the agent's guess at impact. The check converts that guess into numbers — caller count, callee count, importer count — the user can argue with.

Direction matters. Upstream callers identify who breaks if the seam changes. Downstream callees identify what the change can pull in. Bidirectional structural context measurably improves accuracy on repo-level edits. The existing symbol query provides the downstream half at no additional cost.
