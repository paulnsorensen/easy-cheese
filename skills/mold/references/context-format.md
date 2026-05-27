# CONTEXT.md format

`CONTEXT.md` is a glossary and nothing else — the project's ubiquitous language. It is devoid of implementation detail: define what a term **is**, not what it does. Not a spec, not a scratch pad.

Adapted from Matt Pocock's grill-with-docs skill (MIT) — see [`domain-docs.md`](domain-docs.md) § Attribution.

## Structure

```md
# {Context Name}

{One or two sentences: what this context is and why it exists.}

## Language

**Order**:
A customer's request to purchase, before fulfillment.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account

## Flagged ambiguities

- **Cancellation** — used for both order-level and line-level voids. Resolved: order-level only; a line-level void is a **Return**.

## Example dialogue

> **Dev:** If a Customer voids one line of a three-line Order, is the Order cancelled?
> **Domain expert:** No — that's a Return against the Order. Cancellation voids the whole Order before fulfillment.
```

## Rules

- **Be opinionated.** When several words mean one concept, pick the best and list the rest under `_Avoid_`.
- **Flag conflicts explicitly.** Ambiguous usage goes under "Flagged ambiguities" with a resolution — the durable form of the `[CONFLICT <id>]` mold tracks inline during the dialogue.
- **Keep definitions tight.** One or two sentences. Define what it IS.
- **Show relationships.** Bold term names; express cardinality where obvious.
- **Project-specific terms only.** General programming concepts (timeouts, retries, error types, utility patterns) do not belong, even if used heavily. Ask: unique to this domain, or general? Only the former.
- **Group under subheadings** when natural clusters emerge; a flat list is fine otherwise.
- **Write an example dialogue** — a dev / domain-expert exchange that shows the terms interacting and clarifies the boundaries between related concepts.

## CONTEXT-MAP.md (multi-context repos)

A root `CONTEXT-MAP.md` lists the bounded contexts, where each lives, and how they relate:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md) — receives and tracks customer orders
- [Billing](./src/billing/CONTEXT.md) — generates invoices and processes payments
- [Fulfillment](./src/fulfillment/CONTEXT.md) — warehouse picking and shipping

## Relationships

- **Ordering → Fulfillment**: Ordering emits `OrderPlaced`; Fulfillment consumes it to start picking.
- **Fulfillment → Billing**: Fulfillment emits `ShipmentDispatched`; Billing consumes it to invoice.
- **Ordering ↔ Billing**: share `CustomerId` and `Money` types.
```

Detection rules live in [`domain-docs.md`](domain-docs.md) § Multi-context detection.
