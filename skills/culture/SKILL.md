---
name: culture
description: This skill should be used when the user wants to think out loud, rubber-duck a design, walk through trade-offs, or explore an ambiguous problem WITHOUT producing files, code, or specs — phrases like "let's talk through X", "rubber duck this with me", "I'm trying to decide between A and B", "help me think about Y", "what would happen if we…", "/culture". Hard invariant — culture never writes to production files, never commits, never opens PRs. Output is conversation, not artifacts. Use when the user wants shared mental model first; if the dialogue reveals real work to do, recommend `/mold` (fuzzy → spec) or `/cook` (clear ask → code) and stop. Before `/mold` or `/cook`.
license: MIT
---

# /culture

Use this skill for free-form technical thinking when the desired output is shared understanding, not files, commits, specs, or PRs.

Do not use it when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`).

## Hard invariant

`/culture` does not write production files, commit changes, open PRs, or mutate project state. If the conversation reveals that something should be built or written, stop and recommend the next skill.

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

## Handoff

When the conversation reveals real work, ask via `AskUserQuestion` which downstream to run. Default options (pick at most two of these plus a stop):

- **Run /mold** *(recommended when the idea is still fuzzy)* — converge on a spec.
- **Run /cook** *(recommended when the ask is clear and unambiguous)* — implement directly.
- **Pause** — keep the dialogue in head; no further action.

`/briesearch` is offered only when the conversation hit a factual gap that external docs could close. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- No writes, no commits, no PRs.
- Ask one useful question at a time when the user is exploring.
- Prefer clarity over completeness.
- Agree when agreement is warranted; do not manufacture counterpoints to seem balanced.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead with the answer, flag confidence as `certain | speculating | don't know`, steelman, track contradictions across turns.
