# Change: send receipts from a queue

The order service already publishes an OrderPaid event to a queue, and a receipt worker already reads it and calls the email provider.
Today the worker acknowledges the message before it calls the provider, so an email provider outage loses receipts.
The change makes the worker acknowledge the message only after the email provider accepts it. A failed send goes back to the same queue with a delay, up to five tries.
No application, data store, or queue is added. The risk is the timing between the publish, the acknowledgment, and the retry.

Actors: buyer, on-call engineer.

Tier: light.

Source: our own prompt.
