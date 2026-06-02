# Synthesis and confidence

After fetchers report, build a claim-level evidence table, verify citations, and apply the confidence cap.

## Claim-level evidence table

One row per material claim, not per source. A single source can support multiple claims; a single claim can rest on multiple sources.

```markdown
| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| <one-line claim> | <quote or file:line>[^source-1] | vendor docs / paper / changelog / repo / GitHub / blog | <date checked or "live"> | `certain` / `speculating` / `don't know` | <if any> |
```

The Evidence column uses footnote markers (`[^source-1]`, `[^source-2]`, …); the absolute URLs and fetch dates live in a `## References` block at the bottom of the report per [`../shared/formatting.md`](../shared/formatting.md) § Citations. Inline `file:line` references stay raw — they are locations, not citations.

Rules:

- **Each "latest" or "current" claim must include an absolute date** ("latest as of 2026-05-04"), not just "latest".
- **Versioned claims must include the version** ("Next.js 15.3", not "Next.js latest").
- **Conflicting evidence is its own row pair**, not silently averaged. Surface disagreement explicitly.
- **Single-source claims cap at `speculating`** unless the source is authoritative for that claim type (vendor docs for an API; the codebase for a local convention) — only authoritative single sources earn `certain`. A lone Context7 chunk is authoritative *only when its version matches the version in the question*; on a version mismatch (or when the question pins a version the chunk does not state), cap at `speculating` — Context7 IDs can be version-stale (see `routing.md` § Cache library IDs).

The tokens `certain`, `speculating`, and `don't know` are exact label values — write them verbatim, never as synonyms.

## Alternatives are open questions, not recommendations

A research call **returns evidence**. It does not pick design knobs.

When a cited source mentions an alternative ("library X supports A or B", "papers recommend tuning C", "implementations vary between Y and Z"), the alternative becomes an **open question for the user**, not a synthesis recommendation. Never produce output of the form "use both" / "expose a knob to switch" / "add Y as an option alongside the existing X" — those are design choices reserved for `/mold` and the user.

Rules:

- **Cap confidence on alternative claims at `speculating`** until the user adjudicates which variant the project should use. A single arxiv citation saying "X or Y works" does not earn `certain` on either branch.
- **Distinguishing nouns the user did not type (introduced by the agent or by a cited source) must appear in the Open questions block**, not in the Finding paragraph. If the user did not type "convex", "α", "BM42", "hybrid", etc., research output cannot recommend them — only flag them for adjudication.
- **The Finding paragraph reports what the evidence says, not what to do.** "Paper X recommends tuning k in RRF" is a finding. "We should add convex fusion as a second algorithm" is a design choice — out of scope for `/briesearch`.

Canonical failure to avoid: a Tavily snippet says "hybrid retrieval combines sparse and dense signals via RRF or convex score combination." A correct synthesis reports both as known approaches and lists "RRF vs convex fusion" as an open question. An incorrect synthesis (the one this rule exists to prevent) writes "recommend exposing both via a `[search].fusion` knob" — that's a design choice the research call had no mandate to make.

## Link / citation verification

**Short form (always returned) — minimum verification:** before returning any claim, confirm **every URL cited in `## References` resolves** (HTTP 200 or matched-host redirect), except the inline-file and user-supplied URLs exempted below. Mark unreachable footnote definitions `[unverified]` rather than dropping them — the user can re-check. This runs on the always-returned path; it is not deferred to deep reports.

Deep reports (anything with a `research/<slug>/<slug>.md` artifact in the durable corpus) add, on top of the above:

1. Quote tracing: every quoted or paraphrased line traces back to its source (one-click verifiable for the user).
2. Every "as of <date>" claim has a verified fetch date in the same row.

Skip verification only for: (a) inline file references (`file:line`), (b) the user's own supplied URLs.

## Mechanical confidence cap

| Situation | Overall confidence |
| --- | --- |
| Critical routed source unavailable and no equivalent fallback exists | `don't know` |
| Non-critical routed source unavailable, failed, skipped, or searched-but-empty | cap at `speculating` |
| 3+ independent sources agree per claim | `certain` |
| 2 independent sources agree per claim | `speculating` |
| Sources disagree | `don't know` — and surface the disagreement |
| Single source per claim | inherit that source's authority, cap at `speculating` unless authoritative (see lone-Context7 caveat above) |

**"Independent" means distinct origin, not distinct URL.** Before counting sources toward the cap, dedup by origin: collapse to one source any that share a root domain, or that quote/paraphrase the same upstream (three blogs reprinting one vendor post are one source, not three). Count only the surviving distinct origins. Criticality depends on the question. Context7 is critical for version-specific API claims, Tavily is critical for freshness-sensitive facts, Codebase is critical for local precedent questions, and GitHub is usually supporting evidence unless the user asked for real-world examples.

## Absence and negative claims

A claim that something *does not exist* ("X has no Y", "Z doesn't support W") is the most dangerous shape in a synthesis: it is easy to infer from silence, hard to falsify, and an un-grounded one can survive many turns of pushback (issue #113). Hold negatives to a higher bar than positives.

- **Never assert a bare "doesn't exist" as `certain`.** A `certain` absence claim must either cite a source that *states* the absence, or enumerate the candidate mechanisms that would satisfy it and cite a ruling-out for each.
- **Otherwise downgrade.** If you only failed to find it, the claim is "not found in `<sources checked>`" at `speculating` — name the sources searched, never "does not exist".
- **A recorded fact outranks an inferred absence.** If any raw capture or evidence row records the thing existing, the absence claim is the error, not the note.

## Synthesis-fidelity self-check

Before finalizing a deep report (`research/<slug>/<slug>.md`), run the mechanical grounding gate and reconcile the conclusion against what the run actually captured:

1. **Run `ground-check`:** `python3 ${CLAUDE_SKILL_DIR}/scripts/briesearch.pyz ground-check "$ROOT/research/<slug>/<slug>.md"`. It exits non-zero on any claim with no verifiable citation or a non-label confidence value, and prints `ADVISORY` lines for `certain` absence claims. Resolve every error before returning; treat each advisory as a prompt to enumerate-and-rule-out or downgrade per the section above.
2. **Diff the conclusion against the raw capture:** a conclusion may not contradict a fact the run already recorded. Re-read the cited `raw/NN-host.md` lines behind each material claim; if the Finding contradicts a recorded fact, the Finding is wrong — fix it or halt. Do not ship the contradiction.

## Output shape

Cross-cutting house style and citation form: [`../shared/formatting.md`](../shared/formatting.md). This section owns the research-report shape; formatting.md owns the voice rules and the footnote primitive.

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
<one line per routed source that ran and returned nothing usable, naming the query/filters that came up dry (e.g. "Tavily `basic`, time_range=month, \"<query>\" → 0 results above score 0.5"). This is the provenance for any `don't know` or lowered cap — proof the search ran. Omit the section only when no routed source came back empty.>

## References
[^source-1]: <absolute URL or `.cheese/...` path> (fetched <YYYY-MM-DD>).
[^source-2]: <absolute URL or `.cheese/...` path> (fetched <YYYY-MM-DD>).
```

Long form (when the question warranted a deep look):

- Resolve the durable corpus root with `ROOT=$(python3 ${CLAUDE_SKILL_DIR}/scripts/briesearch.pyz artifact-path research <slug>)` (slug is 4-6 kebab-case words), then write the full report to `"$ROOT/research/<slug>/<slug>.md"`. The root is the per-project durable corpus (see `../shared/formatting.md` § Corpus location); briesearch owns the nested `research/<slug>/` layout composed under it.
- Include the full claim table, raw bodies referenced from `"$ROOT/research/<slug>/raw/"` (see `context-isolation.md`), and the verification log.
- In the chat reply: a one-paragraph summary, the report path, and the confidence line. Do not paste the full report inline — the user will see only the last collapsed message by default.
