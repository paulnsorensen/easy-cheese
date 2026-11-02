# Change: route support tickets by priority

A new ticket arrives. A rule reads its priority.
A high priority ticket goes to the on-call queue and pages a person. A normal ticket goes to the day queue.
A ticket with no priority goes to a triage queue, and a person sets the priority.
The spec must show the decision steps. These queues are existing support work lists, not message brokers. Only the rule branches change, inside one module. No application, data store, broker queue, or external system changes.

Actors: customer, support agent, on-call engineer.

Tier: light.

Source: our own prompt.
