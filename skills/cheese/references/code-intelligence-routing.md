# Code-intelligence routing

Workflow skills call the selected source-code backend directly. Route by question or edit shape, not by a wrapper command or preferred vendor.

## Backend selection

| Shape | Backend capability |
| --- | --- |
| Type-grounded definition, reference, caller, rename, or code action | LSP; use Serena when its symbol tools expose the needed operation. |
| Broad symbol, caller, content, file, or dependency search and bounded source reads | tilth when available, otherwise an equivalent semantic source-code backend. |
| Syntax-shaped pattern or repeated structural rewrite | AST search or rewrite such as `sg`; preview every rewrite before applying it. |
| Ordinary block, line, import, config, or documentation edit | A stale-safe anchored editor. Examples are tilth tag-anchored writes, an LSP workspace edit, and a native snapshot edit. |

Use the smallest capability that answers the question.
A later edit can change this choice.
When a symbol read gives no edit anchor, use the backend that validates the write.

## Required edit sequence

For source changes, keep this order:

1. **Search** — locate the definition, callers, affected files, and immediate dependencies before multi-file changes.
2. **Fresh bounded read** — read the exact symbol or ranges that you change.
   Also read the immediate callers and the shared utilities that the task needs.
3. **Stale-safe write** — pass the read's tag, snapshot, or workspace version to a compatible write operation.
   Never invent an anchor.
   Never apply an unbounded blind rewrite.

Read and write anchors are backend-family contracts.
A tilth tag belongs to tilth write.
A native snapshot belongs to its native editor.
An LSP workspace edit uses the language server's current document state.
Re-read with the write backend when families differ or the file changes.

## Fallbacks

When no semantic or stale-checking backend fits, use the narrowest available native tool.
State the missing capability and precision loss in the evidence or handoff.
Blind shell operations give weaker evidence.
Keep them bounded.
Do not use them to claim caller, type, or stale-write safety.
