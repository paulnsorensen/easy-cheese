# Fork questions

A consequential fork question must let the user decide without a reread of the session.
The user must see what the fork decides, how each branch behaves, and what each branch costs.
This reference owns the shape of a Mold fork question.
The transport at [`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md) owns the delivery.

## Fork card

Show a fork card in visible prose immediately before every consequential question.
The card is the context that the transport's self-containment rule requires.

| Field | Content |
| --- | --- |
| `F-n` title | The decision as one question, in the user's terms. |
| `Decides:` | One sentence: the behavior or contract that changes with the choice. |
| `Moves:` | The acceptance criterion, public seam, or non-goal that the fork moves (the altitude tag). |
| `Today:` | One line or one graph of the current behavior, or `new` for new behavior. |
| Branches | One row or one graph per option, with its gains, costs, and risks. |
| `Legend:` | The symbols that the card uses. |

Use this symbol set. Use one meaning for each symbol.

| Symbol | Meaning |
| --- | --- |
| `✔` | gain |
| `✘` | cost |
| `⚠` | risk |
| `?` | unverified claim (the `[?]` marker) |
| `──▶` | data or control flow |
| `──✗` | failure or lost data |

Draw the branches as a plain-text graph in a `text` fence when the fork changes flow, ownership, or order.
Use a symbol table when the branches differ only in properties.
Use Mermaid only when the host renders it. A terminal does not.
Keep each graph to eight lines or fewer.

Example:

```text
F-3  Where does the retry count live?
Decides: whether a job keeps its retry count after a worker crash.
Moves:   AC-2 (retries survive restart), seam `JobStore`
Today:   job ──▶ worker ──✗ crash ──▶ count lost

A  job ──▶ worker ──▶ [jobs.attempts]   ✔ survives crash   ✘ one migration
B  job ──▶ worker ──▶ (memory map)      ✔ no schema change ✘ lost on crash
C  job ──▶ broker header: attempts      ✔ no DB write      ⚠ couples to broker ?
D  Do Nothing                          ✔ zero work        ✘ AC-2 fails

Legend: ✔ gain  ✘ cost  ⚠ risk  ? unverified  ──▶ flow  ──✗ loss
```

Each option description in the question widget repeats that option's `✔`/`✘` line in words.
The widget can truncate the card. The option text must still stand alone.

Before you ask, check the question against these terse-question tests:

- The user can answer without a reread of an earlier turn.
- Each option states an observable result, not only a label or a mechanism name.
- The question defines every project term that the user did not introduce.
- The card names the evidence and its confidence for each `⚠` and `?` claim.

If a test fails, expand the card before you ask.

## Explain more

Every consequential fork question offers `Explain more` as an explicit choice.
Its description is "Show more context, an example, and the downstream effect before I choose."
When the options plus `Explain more` exceed the question primitive's capacity, use the transport's numbered fallback or lossless hybrid.
Never drop a design option to make space for `Explain more`.

Treat these replies as an `Explain more` selection:

- the user selects `Explain more`;
- the user replies `explain` or `explain <option>`;
- the reply says the question is unclear, too terse, or confusing;
- the reply is a question about the fork instead of a choice.

Do not guess a choice from an unclear reply.

On an `Explain more` selection:

1. Keep the same fork id. Do not open a new fork.
2. Add the context that the card left out. Use one or more of these angles:
   - background: why the fork exists, with ledger and evidence citations;
   - example: one concrete input that runs through each branch to its observable result;
   - graph: a larger diagram of the affected path, at the C4 level that the fork changes (see [`diagrams.md`](../../cheese/references/diagrams.md));
   - downstream: what each branch makes easy or hard later, and which follow-up it forecloses.
3. Ask the same fork again with the same options and `Explain more`.
   Its description becomes "Explain from a different angle."

Each re-explanation uses an angle that the user has not seen. Never repeat earlier text.
When the user selects `Explain more` for a specific option, explain only that option.
An explain round does not count toward the fork-round cap.
It adds no ledger decision.
