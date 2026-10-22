# Change: send receipts from a queue

The order service now publishes an OrderPaid event to a queue and returns at once.
A receipt worker reads the event later and calls the email provider.
The worker acknowledges the message only after the email provider accepts it. A failed send goes to a retry queue.
The risk is the timing between the publish, the acknowledgment, and the retry.

Actors: buyer, on-call engineer.

Tier: light.

Source: our own prompt.
