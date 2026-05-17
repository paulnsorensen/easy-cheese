---
name: culture
description: This skill should be used when the user wants to think out loud, rubber-duck a design, walk through trade-offs, or explore an ambiguous problem WITHOUT producing production code or specs — phrases like "let's talk through X", "rubber duck this with me", "I'm trying to decide between A and B", "help me think about Y", "what would happen if we…", "/culture". Output is conversation; the only sanctioned artifact is an opt-in `.cheese/notes/<slug>.md` handoff slug at session end if the user asks for notes. Culture never writes to production code, never commits, never opens PRs. Use when the user wants shared mental model first; if the dialogue reveals real work to do, recommend `/mold` (fuzzy → spec) or `/cook` (clear ask → code) and stop. Before `/mold` or `/cook`.
license: MIT
---

# /culture

Use this skill for free-form technical thinking when the desired output is shared understanding, not production code, specs, or PRs.

Do not use it when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`).

## Invariant

`/culture` does not write production code, commit changes, open PRs, or mutate project state. The only sanctioned artifact is the **opt-in** notes handoff at `.cheese/notes/<slug>.md` (see `## Handoff slug` below), written only at session end and only when the user asks for notes — never during dialogue. If the conversation reveals that something should be built, route to `/mold` or `/cook` and stop.

## Flow

1. Restate the question or tension in one sentence. If the question rests on a false premise or a loaded assumption, name it before engaging.
2. Identify assumptions, constraints, and decision criteria.
3. Explore trade-offs and likely blast radius. When the trade-off hinges on "what does this touch", run a read-only shape check on the candidate seam — a `cheez-search` callers query (`tilth_search kind: "callers"`) plus `tilth_deps` — and label each option `[low | medium | high blast radius]`. Procedure mirrors `../mold/references/shape-check.md`; culture stops at the verdict and never drafts signatures. Steelman the rejected option before settling on a recommendation.
4. Use evidence only when it helps the conversation; avoid deep research unless the user asks.
5. End with a compact summary, open questions tagged with confidence (`certain | speculating | don't know`), and a `## Handoff` prompt (see below).

Default the model's own contribution to maximum useful depth — full pseudocode signatures over hand-waving, named edge cases over "consider edge cases", concrete file:line evidence over vague pointers. Smallest-useful-question discipline applies only to what you ask the user, never to what you offer them.

## Preferred tools and fallbacks

Code search and reading go through the cheez-* skills (`/cheez-search`, `/cheez-read`) — see those skills for tool selection rules. Blast-radius reads specifically use `cheez-search` callers (`kind: "callers"`) plus `tilth_deps` (read-only shape check); culture stops at the verdict and never drafts signatures.

Beyond cheez-* there are culture-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Visualizing diffs or examples | `delta` | plain `git diff` |
| External sanity check | `/briesearch` | clearly mark as an assumption |

Missing optional tools should not interrupt the conversation. Keep tool use light; this is a thinking session.

## Output

Return a short conversational summary:

- Current understanding
- Trade-offs or options
- Open questions

## Handoff slug

When (and only when) the user asks for notes at session end, write an optional handoff slug to `.cheese/notes/<slug>.md`. The slug uses the same minimum schema as the other phase handoffs so `/cheese --continue <slug>` can read it:

```markdown
status: ok | halt: <one-line reason>
next: mold | cook | ultracook | stop
artifact: <path-if-any>
<one-line orientation: what the culture session converged on>
```

`next:` is culture-specific — values are `mold` (fuzzy idea, route to spec), `cook` (clear ask, route to implementation), `ultracook` (clear ask with high blast radius, route to autonomous fresh-context chain), or `stop` (no further action). The orientation line captures the punchline of the dialogue in one factual sentence; deeper notes go in the body of the same file.

The notes slug is the **only** thing culture is allowed to write. No commits, no PRs, no production-code edits — those route to `/mold` or `/cook`.

## Handoff

**Pipeline:** **[culture]** → mold → cook → press → age → cure → ship

When the conversation reveals real work, ask via `AskUserQuestion` which downstream to run. Lead each option with the verb (what the user wants to *do* next); the skill command is the backing detail. Default options (pick at most three of these plus a stop):

- **Shape this into a written spec** *(recommended when the idea is still fuzzy)* — `/mold`.
- **Implement it directly** *(recommended when the ask is clear and unambiguous)* — `/cook`.
- **Implement and auto-review through ship** — `/cook --auto`, chains through `/press → /age → /cure` autonomously, fixing every medium-or-above finding across up to two cure passes. Offer this when the conversation reached an unambiguous contract *and* the user signalled they want the whole pipeline to run forward without per-step approval ("just do it", "ship it", "auto", "fix it all the way through"). Never pre-select; auto mode opts the user out of the gates that exist for their protection.
- **Pause** — keep the dialogue in head; no further action.

`/briesearch` is offered only when the conversation hit a factual gap that external docs could close. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- No production-code writes, no commits, no PRs. The only sanctioned write is the opt-in `.cheese/notes/<slug>.md` handoff at session end, and only when the user asks for it.
- Ask one useful question at a time when the user is exploring.
- Prefer clarity over completeness.
- Agree when agreement is warranted; do not manufacture counterpoints to seem balanced.
- When external evidence raises an alternative ("X uses Y or Z"), name it as a trade-off in the dialogue and a candidate option — never silently recommend "add both" or "expose a knob". Design choices need explicit user adjudication, not agent inference from a citation.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead with the answer, flag confidence as `certain | speculating | don't know`, steelman, track contradictions across turns.
