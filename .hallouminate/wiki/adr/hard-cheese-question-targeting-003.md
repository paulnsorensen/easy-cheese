# ADR: the hard-cheese prompt opens with a purpose-first sentence and keeps the paper's questions verbatim

**Status:** accepted (2026-09-16). Spec: `specs/hard-cheese-question-targeting.md` in the durable corpus. Fork F-3.

- **Context:** `SKILL.md` locks the prompt to Sankaranarayanan 2026. EiPE research shows purpose-level prompts separate Relational from line-by-line answers, and the paper's own data shows 62% of rejections are tautological loops, which a mechanics-first prompt invites.
- **Decision:** The prompt opens with a purpose-first lead ("explain in your own words what this change is for and why it produces the desired behavior"), keeps the paper's three questions verbatim, and ends with a pointer to the highlighted regions. This is recorded as divergence 3 in `## Divergence from the paper`.
- **Alternatives:** Replace the paper prompt with an EiPE prompt (loses stimulus fidelity). Keep the paper prompt unchanged and only append the regions (keeps the mechanics framing).
- **Consequences:** Attribution fidelity stays intact for the three questions. The purpose-first effect is measured on student EiPE items, not on diffs: confidence `speculating`.
