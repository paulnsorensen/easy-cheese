# Domain documentation

mold's spec captures *this change*. Domain docs capture *the project's shared language and durable decisions* — knowledge that outlives any one spec. mold accumulates both during the dialogue and writes them at the same two-key handshake that gates the spec.

Three artifacts, all optional, all lazy (created only when there is something to write):

| Artifact | What it is | Path |
| --- | --- | --- |
| **CONTEXT.md** | Domain glossary — the ubiquitous language. Terms, canonical names, aliases to avoid, flagged ambiguities. No implementation detail. | repo root, or per-context (see multi-context) |
| **CONTEXT-MAP.md** | Bounded-context map for multi-context repos — where each context lives and how they relate. | repo root |
| **ADR** | Architecture Decision Record — one durable, hard-to-reverse decision and its rationale. | `docs/adr/NNNN-slug.md` (or a per-context `docs/adr/`) |

Formats: glossary + map in [`context-format.md`](context-format.md); ADRs in [`adr-format.md`](adr-format.md).

## Live tracking, gated writes

The glossary and ADR candidates are **in-session state first, files second** — same discipline as validate cycles (`validate-cycle.md`). mold does not write domain docs mid-dialogue; it accumulates them in the state ledger and flushes them at curdle, after the handshake. This keeps mold's cardinal rule intact — no production files before the approval gate — while preserving the "capture terms as they resolve, don't reconstruct them from memory" benefit.

Track in the mold state file alongside `validate_cycles`:

```yaml
glossary_terms:
  - term: Order
    definition: A customer's request to purchase, before fulfillment.
    avoid: [Purchase, transaction]
    context: ordering          # omit for single-context repos
    status: resolved           # resolved | flagged
adr_candidates:
  - title: Event-sourced write model
    criteria: [hard-to-reverse, surprising, real-tradeoff]   # all three required
    decision: "Write model is event-sourced; read model projected to Postgres."
```

Surface the running ledger when a term resolves or an ADR-worthy decision lands — e.g. `📓 glossary: Order ≠ Purchase (logged)` — so the user watches it accrue. Write nothing yet.

## Behaviours during the dialogue

These extend existing modes; they do not replace mold's grounding discipline.

- **Sharpen fuzzy language (Glossary / Ground).** When the user uses a vague or overloaded term, propose a precise canonical name plus the aliases to avoid. "You said *account* — do you mean **Customer** or **User**? Those are different things." Log the resolution.
- **Challenge against the glossary (Glossary / Ground).** If a `CONTEXT.md` exists and a term conflicts with it, flag it immediately as `[CONFLICT <id>]`: "Your glossary defines *cancellation* as X; you seem to mean Y — which is it?" This is the same contradiction-tracking mold already runs against code, pointed at the lexicon.
- **Stress-test boundaries with concrete scenarios (Grill).** Invent specific scenarios that probe the edges between concepts and force precision: "A customer voids one line of a three-line order — partial Cancellation, Return, or neither?" See Grill mode in `modes.md`.
- **Offer ADRs sparingly (handshake).** Only when all three criteria hold — hard to reverse, surprising without context, the result of a real trade-off. Miss any one, skip it. Full test in `adr-format.md`.

## Multi-context detection

Most repos are single-context: one `CONTEXT.md` at the root. Before writing glossary terms, detect the shape:

1. `CONTEXT-MAP.md` at the repo root → multi-context. Read it to find each context's `CONTEXT.md`; route each term to the context it belongs to (ask if unclear).
2. Only a root `CONTEXT.md` → single context.
3. Neither → single context; create the root `CONTEXT.md` lazily when the first term is approved.

Do not scaffold a `CONTEXT-MAP.md` unless the user is genuinely working across multiple bounded contexts.

## Attribution

The domain-documentation model — `CONTEXT.md` as a ubiquitous-language glossary, lazy `CONTEXT-MAP.md` for bounded contexts, and the sparingly-offered ADR with its three-part test — is adapted from Matt Pocock's **grill-with-docs** skill (MIT): <https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs>. mold integrates it behind the two-key handshake rather than writing inline.
