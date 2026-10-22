# Session state: Shape round 1 done

Tier: light.

Goal: The ledger stores invoices with lines, and each refund moves through a fixed set of states.

Actors: billing staff, support agent.

## Evidence

- ev-1 (certain, schema dump): The ledger has a customers table and a products table. It has no invoice table.
- ev-2 (certain, code): A refund holds one boolean, done.

## Acceptance so far

- AC-1: An invoice lists each product line with its amount and currency.
- AC-2: A refund is never paid before it is approved.

## Forks for round 2

- F-1: How are invoices stored? A: an invoices table with an invoice_lines table. B: one invoices table with a JSON lines column. C: an event log only. The branches differ in tables and relations.
- F-2: How does a refund move through its life? A: five states with guarded moves. B: three states: open, paid, failed. C: keep the boolean. The branches differ in the allowed moves between states.
- F-3: How long does the team keep invoice rows? A: seven years. B: ten years. C: forever.

Source: our own prompt.
