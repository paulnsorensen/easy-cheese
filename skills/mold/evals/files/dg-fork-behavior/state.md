# Session state: Shape round 1 done

Tier: full.

Goal: A payment is checked for fraud before capture, and the buyer gets a receipt after it.

Actors: buyer, risk analyst.

## Evidence

- ev-1 (certain, runbook): The web app calls the payment service, and the payment service calls the card provider.
- ev-2 (certain, ops notes): The shop already runs a queue for email jobs.

## Acceptance so far

- AC-1: A payment that the fraud check rejects is never charged.
- AC-2: A buyer gets one receipt for each captured payment, even after an email provider outage.

## Forks for round 2

- F-1: In what order does capture call the fraud check? A: before the card provider, and wait. B: after the card provider, and refund on a reject. C: in parallel. The branches differ in the order of calls that wait for a reply.
- F-2: How does the receipt get sent? A: the order service publishes an event, and a worker sends it later. B: the payment service sends it inline. C: a nightly batch. The branches differ in message timing and retry.
- F-3: Who handles a payment that the fraud check holds for review? A: a triage agent drafts a case note, then the risk analyst decides. B: the risk analyst alone. C: the triage agent decides, and the risk analyst audits a sample later. The branches differ in who hands the case to whom.
- F-4: Which fraud score rejects a payment? A: 0.9 or higher. B: 0.7 or higher. C: 0.5 or higher.

Source: our own prompt.
