# Synthesis and confidence

Build the claim-level evidence table after the fetchers report. Verify each citation. Then apply the confidence cap.

## Claim-level evidence table

One row per material claim, not per source. A single source can support multiple claims; a single claim can rest on multiple sources.

```markdown
| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| <one-line claim> | <quote or file:line>[^source-1] | vendor docs / paper / changelog / repository knowledge / repo code / Git host / blog | <date checked or "live"> | `certain` / `speculating` / `don't know` | <if any> |
```

The Evidence column uses footnote markers, such as `[^source-1]`. Put absolute URLs and fetch dates in the final `## References` block. Follow [`../../cheese/references/formatting.md`](../../cheese/references/formatting.md) § Citations. Keep inline `file:line` references without footnote markers. These references are locations, not citations.

Rules:

- **Each "latest" or "current" claim must include an absolute date** ("latest as of 2026-05-04"), not just "latest".
- **Versioned claims must include the version** ("Next.js 15.3", not "Next.js latest").
- **Conflicting evidence is its own row pair**, not silently averaged. Surface disagreement explicitly.
- **Cap a single-source claim at `speculating`.** An authoritative source for that claim type can remove this cap. Examples include vendor documentation for an API and repository knowledge for recorded rationale. Current code is authoritative for current local behavior. Documentation is authoritative only when its version matches the question. A provider name does not make an ambiguous excerpt authoritative.

The tokens `certain`, `speculating`, and `don't know` are exact label values. Write each one verbatim. Do not write a synonym or a case variant.

## Treat alternatives as open questions

A research call **returns evidence**. It does not pick design knobs.

A source can identify more than one alternative. Add each alternative to the open questions for the user. Do not turn an alternative into a synthesis recommendation. `/mold` and the user make design choices.

Rules:

- **Cap alternative claims at `speculating`** until the user selects a variant. One arXiv citation does not make either variant `certain`.
- **Put new distinguishing terms in Open questions.** This rule applies when the user did not use the terms. Examples include `convex`, `α`, `BM42`, and `hybrid`. Do not recommend these alternatives. Ask the user to select one.
- **Report evidence in the Finding paragraph.** Do not give design instructions there. `Paper X recommends tuning k in RRF` is a finding. `We should add convex fusion as a second algorithm` is a design choice. `/briesearch` does not make this choice.

Example failure: a Tavily snippet lists RRF and convex score combination for hybrid retrieval. A correct synthesis reports both known methods. It asks the user to select `RRF` or `convex fusion`. An incorrect synthesis recommends a `[search].fusion` setting. The research request does not authorize that design choice.

## Link / citation verification

**Short form requires minimum verification.** Inspect each cited source with a retrieval or host operation. Confirm that each URL in `## References` resolves. Accept HTTP 200 or a redirect to the same host. The exemptions below apply. Mark an unreachable footnote definition with `[unverified]`. Do not remove it. Always do this work for the short form. Do not defer it to a deep report.

For a deep report in `research/<slug>/<slug>.md`, also complete these checks:

1. Trace each quote or paraphrase to its source. Make the trace easy for the user to verify.
2. Give each dated claim a verified fetch date in the same row.

Skip link verification only for inline `file:line` references and URLs that the user supplies. You must still inspect source content that supports a claim.

## Mechanical confidence cap

| Situation | Overall confidence |
| --- | --- |
| Critical capability uncovered after fallbacks, or covered only by unusable evidence | `don't know` |
| Critical coverage or evidence quality drops materially | cap at `speculating` |
| Named provider unavailable but an evidence-equivalent provider completes the capability | no automatic impact |
| 3+ independent sources agree per claim | `certain` |
| 2 independent sources agree per claim | `speculating` |
| Sources disagree | `don't know` — and surface the disagreement |
| Single source per claim | cap at `speculating` unless authoritative for that claim |

**Independent means a separate origin, not a separate URL or provider.** Combine pages that have the same root domain or upstream source. Determine criticality from the claim and capability. Documentation is critical for a version-specific API claim. Current web evidence is critical for a freshness claim. Local code is critical for current repository behavior. Repository knowledge is critical for prior decisions and rationale. Git hosting evidence usually supports other evidence. It becomes critical when the question asks about hosted state or precedent. A missing named provider does not reduce confidence when an equivalent source supplies the required evidence.

## Absence and negative claims

An absence claim is easy to infer from silence. It is also difficult to disprove. An unsupported absence claim can survive many review turns. Apply a higher standard to an absence claim than to a positive claim.

- **Do not mark an unsupported absence as `certain`.** Cite a source that states the absence. Otherwise, list each candidate mechanism and cite evidence that excludes it.
- **Downgrade an incomplete search.** Report `not found in <sources checked>` at `speculating`. Name the searched sources. Do not report `does not exist`.
- **A recorded fact has priority over an inferred absence.** If evidence records the item, correct the absence claim.

## Synthesis-fidelity self-check

Before you finish a deep report, run the grounding gate. Then compare the conclusion with the captured evidence.

1. **Run `ground-check`.** Run `python3 skills/briesearch/scripts/briesearch.pyz ground-check "$ROOT/research/<slug>/<slug>.md"`. The command fails on an unsupported claim, invalid confidence label, or remote citation without a recorded retrieval. It prints `ADVISORY` for each `certain` absence claim. Correct each error before you return the report. For each advisory, add exclusion evidence or reduce confidence.
2. **Compare the conclusion with the raw capture.** A conclusion must not conflict with a recorded fact. Read the cited `raw/NN-host.md` lines for each material claim. Correct a conflicting Finding or stop. Do not return the conflict.

## Output shape

Cross-cutting house style and citation form: [`../../cheese/references/formatting.md`](../../cheese/references/formatting.md).

Short form (always returned to the caller):

```markdown
## Research: <Question>

### Finding
<1-3 short paragraphs. Lead with the answer the evidence supports, not a design recommendation. Report what cited sources say; do not promote alternatives mentioned in citations into design knobs.>

### Evidence
<the claim-level table above, trimmed to the critical rows>

### Open questions
<one bullet per alternative or unresolved choice raised by the evidence — phrased as a question for the user. Tag each `speculating`. If the user did not type the distinguishing noun (e.g. "convex", "α", "BM42") in their prompt, the alternative belongs here, not in Finding.>

### Confidence
<`certain` | `speculating` | `don't know`> — <one-line justification, including any caveat>

### Next step
<recommended skill or action — limited to which skill should run next (`/mold`, `/cook`, etc.), never which design knob to expose.>

### Searched, empty
<one line per routed capability/provider that ran and returned nothing usable, naming the query and relevant filters (for example "Current web via native search, last 30 days, \"<query>\" → 0 relevant results"). This is the provenance for any `don't know` or lowered cap. Omit the section only when no routed capability came back empty.>

## References
[^source-1]: <absolute URL or `.cheese/...` path> (fetched <YYYY-MM-DD>).
[^source-2]: <absolute URL or `.cheese/...` path> (fetched <YYYY-MM-DD>).
```

Long form (when the question warranted a deep look):

- Resolve each path with `python3 skills/briesearch/scripts/briesearch.pyz research-layout <slug>`. Use a slug with four to six kebab-case words. The command prints `corpus_root`, `dir`, `report`, `raw_dir`, `manifest`, and `artifact`. Write the complete report to `report`. Write raw bodies under `raw_dir`. Report `artifact` to a caller that records a corpus-relative path. Do not construct these paths manually.
- Include the complete claim table and the verification log. Cite each raw body with a path relative to `raw_dir`, such as `raw/01-example.md#Lstart-end`. Never put URL user information, query values, or a fragment in a persisted citation.
- Return one summary paragraph, the report path, and the confidence line in chat. Do not paste the complete report in chat.
