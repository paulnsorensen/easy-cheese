# ADR: publish follow-ups after the local Curdle write

### ADR-003: two-phase Curdle preserves approval and recovers from external failure [status: accepted]

- **Context:** External Issues and roadmap goals provide final references, but creating them before the spec exists risks dangling tracker items. Requiring all external services to succeed would also block an otherwise approved specification.[^1]
- **Decision:** Curdle first writes the spec, ADRs, and local recovery drafts. It then links or creates approved external items, patches Deferred follow-ups with prepared, linked, or created states, and finishes publication before the implementation handoff.
- **Alternatives:** Publish externally first, omit external references from the spec, reconcile in a later session, or begin implementation in parallel. These choices weaken recoverability, auditability, or workflow ordering.
- **Consequences:** The durable spec survives service failure and remains the audit source. Publication is not atomic across local and external systems, so failures retain a prepared draft and an explicit recovery action.

[^1]: skills/mold/references/curdle.md:129-145; /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-follow-up-routing.md:113-123
