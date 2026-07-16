# ADR: hallouminate wiring ships as a stacked 4-PR build, one PR per issue

**Status:** accepted (2026-07-16)

- **Context:** Issues #201/#202/#203/#205 could ship as one PR, two PRs (prose vs CI), or a 4-PR stack. #202 and #203 both edit `skills/age/SKILL.md`, so full parallelism was never available; #205 is fully file-disjoint.
- **Decision:** Stacked build, bottom → top: #205 (CI validator, disjoint base) → #201 (mold/culture grounding) → #203 (query-time retrieval) → #202 (durable-change gates). Each PR closes exactly one issue.
- **Alternatives:** One PR — fastest but mixes a Python validator with prose skill wiring in one review and squashes four issues into one commit. Two PRs — still bundles three issues into one wiring review.
- **Consequences:** Four reviewable units with clean issue closure; the shared-file overlap is sequenced instead of conflicted. Costs stack maintenance (restacks on review changes to lower PRs).
