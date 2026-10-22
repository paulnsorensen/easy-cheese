# Change: add a fraud check to payment capture

The web app calls the payment service to capture a payment.
The change adds a call from the payment service to a fraud service before it calls the card provider.
Every call waits for the reply. If the fraud service rejects, the payment service returns an error to the web app.
The order of the calls is the risk.

Actors: buyer, risk analyst.

Tier: light.

Source: our own prompt.
