# Problem: the rate limiter loses its counter store

An API platform limits each client with counters in a shared store. Many gateways read and update those counters.

When the store is unreachable, a gateway cannot tell if a client is over its limit. The design must say what the gateway does: reject requests or allow them.

Traffic spikes are common. Backend teams rely on the limit to protect their services. Clients expect the API to stay up.

Actors: API client, platform on-call engineer, backend team.

Tier: light.

Source: our own prompt. Related topic: <https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter> (link only; no text copied).
