# ADR: route follow-ups per deliverable unit instead of choosing one backlog

### ADR-002: Issues, roadmap goals, and local drafts keep distinct jobs [status: accepted]

- **Context:** Mold has a GitHub-flavoured local issue format, while /wiki-roadmap owns dependency-linked execution plans. Treating either destination as universal would blur discrete tasks and coordinated goals.[^1]
- **Decision:** Group candidates into independently deliverable units, search for related existing items, recommend GitHub Issues for discrete work and roadmap goals for coordinated or dependency-linked work, and retain local drafts as the preparation and recovery path. The user approves grouping, semantic-match reuse, destination, and action.
- **Alternatives:** Send the whole batch to one destination, always create new items, reuse matches silently, or make the user structure every artifact. These choices either lose destination semantics, create duplicates, risk false equivalence, or discard useful agent assistance.
- **Consequences:** Follow-ups land where their execution shape fits, and existing work can be reused without silent conflation. Discovery capabilities remain optional, and /wiki-roadmap retains roadmap authorship.

[^1]: skills/mold/references/handshake.md:95-105; skills/mold/references/curdle.md:127-145; ~/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-follow-up-routing.md:96-111
