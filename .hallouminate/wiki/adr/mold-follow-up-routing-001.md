# ADR: every non-goal enters a disposition batch before Curdle

### ADR-001: candidate status separates scope boundaries from future commitments [status: accepted]

- **Context:** Mold already audits non-goals, but only explicit deferrals have an issue-draft path. Valuable exclusions can be forgotten, while automatically backlogging every non-goal would create work the user did not approve.[^1]
- **Decision:** Record every non-goal and explicit dialogue deferral as a follow-up candidate. Resolve all candidates in one user-approved batch before the two-key handshake completes.
- **Alternatives:** Ask immediately for each deferral, triage candidates silently, or leave ordinary non-goals passive. Immediate prompts fragment the design dialogue; silent triage gives the agent policy authority; passive exclusions preserve the current loss mode.
- **Consequences:** Every scope boundary receives an explicit disposition without becoming an automatic commitment. Large candidate sets can add review time, so Mold proposes grouping before asking.

[^1]: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-follow-up-routing.md:48-68,90-111
