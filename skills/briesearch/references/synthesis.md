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
| Any routed source unavailable, failed, or skipped | cap at 49 (low) |
| 3+ sources agree | 85–100 (high) |
| 2 sources agree | 60–84 (medium) |
| Sources disagree | cap at 49 (low) and explain why |
| 1 completed source | inherit that source's score |

Easy Cheese uses qualitative buckets (`low | medium | high`) in user-facing output; the numeric scale only drives the cap.

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
