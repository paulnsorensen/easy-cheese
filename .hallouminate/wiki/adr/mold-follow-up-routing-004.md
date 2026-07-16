# ADR: external follow-up publication uses deterministic identity

### ADR-004: write-ahead prepared state and exact-ID discovery make retries idempotent [status: accepted]

- **Context:** A process can stop after an external Issue or roadmap goal is created but before its URL is reconciled into the originating spec. Retrying without durable identity can create a duplicate.[^1]
- **Decision:** Assign each accepted follow-up a deterministic spec-slug and ordinal ID, persist prepared state before the external call, include the ID in the published item, and search the exact ID before every retry.
- **Alternatives:** Rely on semantic-match search, accept best-effort recovery, or publish externally before local Curdle. Semantic similarity does not prove identity; best effort permits duplicates; external-first ordering risks dangling items.
- **Consequences:** A retry can link the already-created item instead of duplicating it. Publishers must preserve the ID in destination content and support exact-ID discovery or fall back to prepared state.

[^1]: ~/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-follow-up-routing.md:116-129,143-160
