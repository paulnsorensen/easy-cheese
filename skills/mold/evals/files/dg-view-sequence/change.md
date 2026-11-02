# Change: add a fraud check to payment capture

The web app calls the payment service to capture a payment.
The payment service already calls a fraud service, but only after the card provider charges the card. The change moves the fraud call before the card provider call.
Every call waits for the reply. If the fraud service rejects, the payment service returns an error to the web app.
The order of the calls is the risk.

Actors: buyer, risk analyst.

Tier: light.

Source: our own prompt.
