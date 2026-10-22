# Change: share customer records across three systems

The company owns three software systems: the CRM, the billing system, and the support desk.
Today each system keeps its own copy of the customer record.
The change makes the CRM the source of truth. Billing and support read from it.
The spec must show how the three systems relate, not what is inside any one of them.

Actors: sales staff, billing staff, support agent.

Tier: light.

Source: our own prompt.
