# Problem: holding seats during checkout

A ticket site sells seats for live events. A buyer picks seats, then has a few minutes to pay.

Two buyers must never own the same seat. A buyer who walks away must free the seats for others.

At an on-sale, one hundred thousand buyers may arrive for one event within a minute. Most of them want the same few seats.

The booking service, the payment step, and the expiry job already run as separate services. This change only changes the hold protocol between them.

## Recorded user decisions

The user made this choice in an earlier dialogue round. It is not an agent decision.

- D-1 (user): the booking service holds each seat for one buyer for a fixed time. The hold ends on payment or on expiry. The user rejected a database row lock for the whole session, because it blocks other buyers and ties up connections. The user rejected a hold kept only in the client, because the client cannot be trusted.
- Open (no user decision yet): what happens to a payment that lands after its hold expired: refund it, or honor it when the seat is still free.

Actors: buyer, event organizer, on-call engineer.

Tier: light.

Source: our own prompt. Related topic: <https://www.hellointerview.com/learn/system-design/problem-breakdowns/ticketmaster> (link only; no text copied).
