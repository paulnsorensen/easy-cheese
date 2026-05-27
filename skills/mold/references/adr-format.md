# ADR format

An Architecture Decision Record captures one durable decision and *why* it was made. ADRs live in `docs/adr/` (or a context-specific `docs/adr/` in multi-context repos) with sequential numbering: `0001-slug.md`, `0002-slug.md`. Create the directory lazily — only when the first ADR is needed.

Adapted from Matt Pocock's grill-with-docs skill (MIT) — see [`domain-docs.md`](domain-docs.md) § Attribution.

## When to offer an ADR

Offer one **only when all three are true**:

1. **Hard to reverse** — changing your mind later carries meaningful cost.
2. **Surprising without context** — a future reader will look at the code and wonder "why on earth did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons.

Miss any one and skip it: an easy-to-reverse decision you'll just reverse; an unsurprising one nobody questions; a no-alternative one records only "we did the obvious thing."

### What qualifies

- **Architectural shape** — "monorepo"; "event-sourced write model, Postgres read model".
- **Integration patterns between contexts** — "Ordering and Billing talk via domain events, not synchronous HTTP".
- **Technology choices with lock-in** — database, message bus, auth provider, deployment target. Not every library — the ones that would take a quarter to swap.
- **Boundary and scope decisions** — "Customer data is owned by the Customer context; others reference it by ID only." The explicit no's matter as much as the yes's.
- **Deliberate deviations from the obvious path** — "manual SQL instead of an ORM because X." Stops the next engineer from "fixing" something deliberate.
- **Constraints invisible in the code** — "no AWS, for compliance"; "responses under 200ms because of the partner API contract".
- **Rejected alternatives when the rejection is non-obvious** — picked REST over GraphQL for subtle reasons? Record it, or it gets re-proposed in six months.

## Template

```md
# {Short title of the decision}

{1–3 sentences: the context, what was decided, and why.}
```

That's the whole thing. An ADR can be one paragraph. The value is recording *that* a decision was made and *why* — not filling out sections.

### Optional sections

Include only when they earn their place; most ADRs need none.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — when decisions get revisited.
- **Considered Options** — when the rejected alternatives are worth remembering.
- **Consequences** — when non-obvious downstream effects need calling out.

## Numbering

Scan `docs/adr/` for the highest existing number and increment by one. In multi-context repos, number within the relevant context's `docs/adr/`.
