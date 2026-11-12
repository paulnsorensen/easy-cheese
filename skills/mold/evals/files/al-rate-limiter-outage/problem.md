# Problem: the rate limiter loses its counter store

An API platform limits each client with counters in a shared store. Many gateways read and update those counters.

When the store is unreachable, a gateway cannot tell if a client is over its limit. The design must say what the gateway does: reject requests or allow them.

Traffic spikes are common. Backend teams rely on the limit to protect their services. Clients expect the API to stay up.

## Recorded user decisions

The user made this choice in an earlier dialogue round. It is not an agent decision.

- D-1 (user): when the store is unreachable, each gateway allows requests under a fixed local cap. The user rejected failing closed, because it turns a store fault into a full API outage. The user rejected failing open with no cap, because it leaves backends open to a spike.
- Open (no user decision yet): whether a gateway tells clients that exact limits are off during the outage, for example with a response header.

Actors: API client, platform on-call engineer, backend team.

Tier: light.

Source: our own prompt. Related topic: <https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter> (link only; no text copied).
