# ADR: Progressive agent resolution is a shared contract

Status: accepted (2026-07-17)

## Decision

Every skill that dispatches sub-agents declares `metadata.dispatches-agents:
true`, links the shared resolver, and carries a local `## Agent resolution`
table. Resolution filters candidates by capabilities, permissions, and
isolation first; then by minimum model power; then by specificity. Exact
easy-cheese specialists win over compatible specialists and general workers.[^1]

Power (`cheap | default | powerful`) and effort
(`low | medium | high`) are independent. A known-underpowered candidate is
rejected. Unknown power is allowed only as the final fallback and is recorded
as degraded. A general worker may fill a read-only role through an explicit
prompt-only no-write constraint, also recorded as degraded; prompting cannot
supply missing tools, write access, or isolation.[^2]

Canonical artifacts record the request, ordered attempts, accepted
resolution, fallback reason, degradation, and permission-enforcement mode.
This provenance is part of reproducibility rather than optional debug output.[^3]

## Why

Agent type, model power, effort, permissions, and context topology affect the
work independently. The previous phase-blind policy hid fallbacks and made
internal and standalone review runs incomparable. One shared algorithm keeps
the semantics portable while skill-local tables keep each workflow readable.

## Enforcement

A dedicated documentation-contract test discovers the eight dispatching
skills and requires their metadata, table, and shared-reference link. The
frontmatter validator remains concerned only with skill shape.[^4]

[^1]: skills/cheese/references/agent-resolution.md:3-13
[^2]: skills/cheese/references/agent-resolution.md:9-13,48-54
[^3]: skills/cheese/references/agent-resolution.md:15-46
[^4]: tests/python/test_agent_resolution_contract.py
