# Synthesis and confidence

After fetchers report, build a single evidence row per routed source and apply the confidence cap.

## Evidence table

```markdown
| Source | Finding | Confidence | Notes |
| --- | --- | --- | --- |
| Context7 | <one-line> | high | <library version, freshness> |
| Tavily   | <one-line> | medium | <date, vendor> |
| Codebase | <one-line> | high | <file:line> |
| GitHub   | unavailable | — | <reason> |
```

## Mechanical confidence cap

| Situation | Overall confidence |
| --- | --- |
| Critical routed source unavailable and no equivalent fallback exists | low |
| Non-critical routed source unavailable, failed, or skipped | cap at medium |
| 3+ completed sources agree | high |
| 2 completed sources agree | medium |
| Sources disagree | low and explain why |
| 1 completed source | inherit that source's confidence, capped at medium unless it is authoritative |

Criticality depends on the question. Context7 is critical for version-specific API claims, Tavily is critical for freshness-sensitive facts, Codebase is critical for local precedent questions, and GitHub is usually supporting evidence unless the user asked for real-world examples.

## Output shape

```markdown
## Research: <Question>

### Finding
<1–3 short paragraphs>

### Evidence
<the table above>

### Implications
<2–4 sentences on how this affects the user's task>

### Confidence
<low | medium | high> — <one-line justification>

### Next step
<recommended skill or action, if any>
```

## Optional report

When the question warranted a deep look, also write the full report to `.cheese/research/<slug>.md` and pass back only the path in the synthesis. Slug is 4–6 kebab-case words derived from the topic.
