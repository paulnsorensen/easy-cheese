# The shape check

Run this before drafting in Sketch mode, and any time the discussion in any mode hinges on "what does this touch" or "what depends on this". The check is read-only — culture and mold both run it; only the artifact stage differs.

## What it answers

- **Signatures**: what does the touched function/type look like today? What sibling signatures already exist in the same module so a new one fits convention?
- **Callers** (upstream): who calls the touched symbol, and from which modules?
- **Callees** (downstream): what does the touched symbol call into? Surfaced by the same symbol query — `kind: "symbol"` returns a `── calls ──` footer with one-hop callees. No extra call.
- **Imports / blast radius**: which files import this module? Which does this module import?

These four answers together describe the shape of the change and bound its blast radius — both upstream (who breaks if I change this) and downstream (what could I drag into the change). The downstream half is what InlineCoder-style bidirectional inlining is empirically worth on repo-level edits; ignoring it leaves a known gap.

## Procedure

Run all three. Cheap when the answers are small; the cost of skipping is silent misrouting later.

| Question | Tool | Call |
| --- | --- | --- |
| Current signature? Sibling signatures? Downstream callees (`── calls ──` footer)? | `cheez-search` | `tilth_search(query: "<symbol>", kind: "symbol", expand: 2, scope: "<module>")` |
| Who calls this? (upstream) | `cheez-search` | `tilth_search(query: "<symbol>", kind: "callers", scope: ".")` |
| What's the import / blast radius? | `cheez-search` | `tilth_deps(path: "<file>")` |

The first call does double duty — its `── calls ──` footer is the cheap callee read; do not issue a separate query for it.

For multi-symbol changes, batch up to five symbols in a single `cheez-search` call (`query: "a, b, c"`). Re-run only when a new symbol enters scope.

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

A `high` verdict (multi-module callers or more than five importers) makes the Grill gate mandatory in mold (see `handshake.md`) and forces culture to label the option `[high blast radius]` before continuing trade-off talk.

## When tilth / cheez-search is unavailable

Shape-check should not block the dialogue when its preferred tools are missing. Substitute and degrade the verdict:

- **Callers / callees**: fall back to LSP `find_references` / `prepare_call_hierarchy` (or `ripgrep` against the symbol name when LSP is also down). Note the substitution out loud.
- **Imports / blast radius**: fall back to `ripgrep` for `import .*<module>` and reverse-import patterns; counts will be approximate.
- **Verdict**: cap at `[?]` instead of `low | medium | high` — a guessed verdict is worse than an honest unknown. Sketch and culture should treat `[?]` like `high` for gating purposes (Grill gate engages, option labelled `[high blast radius]`) until the user accepts the gap.

## When to skip

- The touched symbol has zero callers (greenfield) — say so out loud.
- The change is contained to one private function inside a single file with no exports — sibling signature lookup still applies; deps and callers can be skipped.
- The user explicitly said `skip the shape check`.

## Why

Trade-offs and seams discussed without a shape check rely on the agent's guess at impact. The check converts that guess into numbers — caller count, callee count, importer count — the user can argue with.

The directionality matters: upstream (callers) tells you who breaks if the seam changes; downstream (callees) tells you what the change might drag in. Bidirectional structural context is empirically worth a measurable accuracy lift on repo-level edits, and the downstream half rides for free on the existing symbol query.
