# ADR-001: Fold skill references into one docs page instead of separate sub-pages  [status: accepted]

- **Context:** Starlight docs (`scripts/gen_docs.py`) rendered each `skills/<name>/references/*.md` as a standalone sidebar sub-page under a per-skill collapsible group (`Overview` + one page per reference). Readers saw pages like "Context isolation" with no cue they belonged to `briesearch`, and each skill's material was fragmented. Skill *source* keeps references as separate files on purpose (agents load them on-demand), so the fix must live in docs generation only.
- **Decision:** Fold every `references/*.md` into its skill's single generated page as appended sections (`# H1 → ##`, internal headings bumped one level), rewrite reference links to intra-page anchors, and collapse the per-skill sidebar group to one flat link.
- **Alternatives considered:**
  - *Drop references from the site* — simplest, but loses genuinely useful docs (routing decision trees, evals, safety rules) and leaves a thin TOC.
  - *Keep sub-pages, only restyle the sidebar* — doesn't satisfy "one page each"; the disorientation persists.
- **Consequences:** Larger pages (mold 11 refs, age 9, cheese 7). Navigation shifts to a left-nav heading TOC (ADR-002). Skill source tree untouched — `test_reference_resolution.py` stays green; `test_gen_docs.py`'s sub-page-contract classes are rewritten.
