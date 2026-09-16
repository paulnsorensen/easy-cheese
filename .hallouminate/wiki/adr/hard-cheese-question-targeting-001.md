# ADR: hard-cheese targets diff hunks with a script and lets the judge phrase the questions

**Status:** accepted (2026-09-16). Spec: `specs/hard-cheese-question-targeting.md` in the durable corpus. Fork F-1.

- **Context:** The gate asked one generic prompt and sent the judge up to 80 unranked diff lines. Neither the source paper nor vibecheck selects which part of a change to ask about. Research (`research/hard-cheese-question-selection-leverage/`) shows JIT defect features (churn, diffusion, prior-change history, author inexperience) are validated risk proxies, and AI-written changes fail most at error paths, cross-module invariants, and authorization logic.
- **Decision:** A deterministic `rank-hunks` bundle command scores hunks from git history plus pattern flags and emits the top three with reasons. The judge sub-agent, which already runs, phrases the targeted Socratic questions from those hunks.
- **Alternatives:** A fresh-context model picks the regions (semantic, but one extra `powerful` call, non-reproducible, and the targets become an attack surface). A script alone phrases the questions (reproducible but generic wording). Do nothing (whole-diff prompt).
- **Consequences:** Target selection is testable and reproducible. Surface features can miss a low-churn invariant edit; the judge still sees the full diff summary. One new export on the hard-cheese bundle (`contract` leverage trigger).
