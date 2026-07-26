# Code-intelligence routing

Workflow skills call the selected source-code backend directly. Route by question or edit shape, not by a wrapper command or preferred vendor.

## Backend selection

| Shape | Backend capability |
| --- | --- |
| Type-grounded definition, reference, caller, rename, or code action | LSP; use Serena when its symbol tools expose the needed operation. |
| Broad symbol, caller, content, file, or dependency search and bounded source reads | tilth when available, otherwise an equivalent semantic source-code backend. |
| Syntax-shaped pattern or repeated structural rewrite | AST search or rewrite such as `sg`; preview every rewrite before applying it. |
| Ordinary block, line, import, config, or documentation edit | A stale-safe anchored editor such as tilth tag-anchored writes, an LSP workspace edit, or a native snapshot edit. |

Use the smallest capability that answers the question. A later edit may change the choice: if a symbol read cannot provide an edit anchor, perform the fresh bounded read with the backend family that will validate the write.

## Required edit sequence

For source changes, keep this order:

1. **Search** — locate the definition, callers, affected files, and immediate dependencies before multi-file changes.
2. **Fresh bounded read** — read the exact symbol or ranges that will change, plus immediate callers or shared utilities required by the task.
3. **Stale-safe write** — pass the read's tag, snapshot, or workspace version to a compatible write operation. Never invent an anchor or apply an unbounded blind rewrite.

Read and write anchors are backend-family contracts. A tilth tag belongs to tilth write; a native snapshot belongs to that native editor; an LSP workspace edit depends on the language server's current document state. Re-read with the intended write backend when the families are incompatible or the file has changed.

## Fallbacks

When no semantic or stale-checking backend covers the shape, use the narrowest native search, bounded read, or anchored edit available. State the missing capability and the resulting precision loss in evidence or handoff output. Blind shell search/view/edit is weaker evidence, never an equivalent backend; keep it bounded and do not use it to claim caller, type, or stale-write safety.
