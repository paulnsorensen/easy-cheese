# Synthesis and confidence

After fetchers report, build a claim-level evidence table, verify citations, and apply the confidence cap.

## Claim-level evidence table

One row per material claim, not per source. A single source can support multiple claims; a single claim can rest on multiple sources.

```markdown
| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| <one-line claim> | <quote, file:line, or URL> | vendor docs / paper / changelog / repo / GitHub / blog | <date checked or "live"> | high / medium / low | <if any> |
```

Rules:

- **Each "latest" or "current" claim must include an absolute date** ("latest as of 2026-05-04"), not just "latest".
- **Versioned claims must include the version** ("Next.js 15.3", not "Next.js latest").
- **Conflicting evidence is its own row pair**, not silently averaged. Surface disagreement explicitly.
- **Single-source claims are capped at medium confidence** unless the source is authoritative for that claim type (vendor docs for an API; the codebase for a local convention).

## Link / citation verification

For deep reports (anything with a `.cheese/research/<slug>/<slug>.md` artifact):

1. Every URL in the evidence column resolves (HTTP 200 or matched-host redirect). Mark unreachable links `[unverified]` rather than dropping them — the user can re-check.
2. Every quoted or paraphrased line traces back to its source (one-click verifiable for the user).
3. Every "as of <date>" claim has a verified fetch date in the same row.

Skip verification only for: (a) inline file references (`file:line`), (b) the user's own supplied URLs.

## Mechanical confidence cap

| Situation | Overall confidence |
| --- | --- |
| Critical routed source unavailable and no equivalent fallback exists | low |
| Non-critical routed source unavailable, failed, or skipped | cap at medium |
| 3+ independent sources agree per claim | high |
| 2 independent sources agree per claim | medium |
| Sources disagree | low — and surface the disagreement |
| Single source per claim | inherit that source's authority, capped at medium unless authoritative |

Criticality depends on the question. Context7 is critical for version-specific API claims, Tavily is critical for freshness-sensitive facts, Codebase is critical for local precedent questions, and GitHub is usually supporting evidence unless the user asked for real-world examples.

## Output shape

Short form (always returned to the caller):

```markdown
## Research: <Question>

### Finding
<1-3 short paragraphs. Lead with the answer, not the methodology.>

### Evidence
<the claim-level table above, trimmed to the load-bearing rows>

### Confidence
<low | medium | high> — <one-line justification, including any caveat>

### Next step
<recommended skill or action, if any>
```

Long form (when the question warranted a deep look):

- Write the full report to `.cheese/research/<slug>/<slug>.md` (slug is 4-6 kebab-case words).
- Include the full claim table, raw bodies referenced from `.cheese/research/<slug>/raw/` (see `context-isolation.md`), and the verification log.
- In the chat reply: a one-paragraph summary, the report path, and the confidence line. Do not paste the full report inline — the user will see only the last collapsed message by default.
