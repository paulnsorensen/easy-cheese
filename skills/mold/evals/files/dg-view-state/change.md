# Change: give refunds a lifecycle

A refund today has a boolean: done or not done.
The change gives it states: requested, approved, rejected, paid, and failed.
Only an approved refund can be paid. A failed refund can be retried and goes back to approved.
The risk is the allowed moves between states. No table or service changes.

Actors: customer, support agent, finance staff.

Tier: light.

Source: our own prompt.
