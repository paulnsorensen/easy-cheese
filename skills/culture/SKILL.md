---
name: culture
description: Primarily the agent's internal-thinking skill — invoke it silently to model a problem, identify trade-offs, and decide what to do, BEFORE asking the user anything or dispatching another skill. Workflow skills call `/culture` as their step-1 reasoning pass; the agent does not surface the dialogue. Only treat this as a user-facing skill when the user has explicitly opted out of writes — phrases like "no writes", "just rubber-duck this", "let's only talk", "/culture". In the user-facing path the output is conversation; the only sanctioned artifact is an opt-in `.cheese/notes/<slug>.md` handoff slug at session end if the user asks for notes. Culture never writes to production code, never commits, never opens PRs. If the dialogue reveals real work, recommend `/mold` (fuzzy → spec) or `/cook` (clear ask → code) and stop. Before `/mold` or `/cook`.
license: MIT
---

# /culture

Two modes:

1. **Internal mode (default).** Other workflow skills — and `/cheese` itself — invoke `/culture` silently as a thinking pass: restate the question, list assumptions, name candidate options, run a quick shape check, pick the next action. The dialogue does not surface to the user; only the resulting decision (and any code edits the calling skill makes) does. The most common callers are:
   - `/cheese` step 1 — silent classification reasoning before announce.
   - `/cheese` **tier-2 escalation** (see `skills/cheese/SKILL.md` § Escalation) — fills missing context when the cook-fast-path clarity check fails on the raw input; the synthesis lands in the mini-spec's `## Provenance` section.
   - Other workflow skills' own pre-dispatch reasoning passes (mold, cook taste-test, etc.).
2. **User-facing mode.** The user has explicitly opted out of writes for this session. Conversation is the deliverable; no code, no spec, no PR. Reach this mode only when the user said "no writes" / "rubber-duck this" / "just talk" or equivalent.

Do not use the user-facing mode when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`) — those targets get the internal-mode call instead, and the calling skill does the work.

## Invariant

`/culture` does not write production code, commit changes, open PRs, or mutate project state. The only sanctioned artifact is the **opt-in** notes handoff at `.cheese/notes/<slug>.md` (see `## Handoff slug` below), written only at session end of a user-facing session and only when the user asks for notes — never during dialogue, never in internal mode. If a user-facing conversation reveals that something should be built, route to `/mold` or `/cook` and stop. In internal mode, just return the decision and let the calling skill act.

## Flow

Both modes share the same reasoning loop. The difference is what the agent does with the output: internal mode returns a single decision back to the calling skill; user-facing mode renders the dialogue and waits for the user.

1. Restate the question or tension in one sentence. If the question rests on a false premise or a loaded assumption, name it.
2. Identify assumptions, constraints, and decision criteria.
3. Explore trade-offs and likely blast radius. When the trade-off hinges on "what does this touch", run a read-only shape check on the candidate seam — a `cheez-search` callers query (`tilth_search kind: "callers"`) plus `tilth_deps` — and label each option `[low | medium | high blast radius]`. Procedure mirrors `../mold/references/shape-check.md`; culture stops at the verdict and never drafts signatures. Steelman the rejected option before settling on a recommendation.
4. Use evidence only when it helps the reasoning; avoid deep research unless explicitly asked.
5. Converge on a single recommended next action. In internal mode, return that recommendation and stop. In user-facing mode, render a compact summary, open questions tagged with confidence (`certain | speculating | don't know`), and a `## Handoff` prompt (see below).

Default the model's own contribution to maximum useful depth — full pseudocode signatures over hand-waving, named edge cases over "consider edge cases", concrete file:line evidence over vague pointers. Smallest-useful-question discipline applies only to what you ask the user, never to what you offer them.

## Preferred tools and fallbacks

Code search and reading go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`) — see those skills for tool selection rules. Blast-radius reads specifically use `cheez-search` callers (`kind: "callers"`) plus `tilth_deps` (read-only shape check); culture stops at the verdict and never drafts signatures.

Beyond `cheez-*` there are culture-specific tools:

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

When the conversation reveals real work, ask via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command is the backing detail. Before asking, render a compact context packet so the downstream skill can dispatch without losing the discussion:

```yaml
handoff_context:
  source_skill: /culture
  summary: <one factual sentence>
  open_questions: [<only blockers, if any>]
  artifact: <.cheese/notes/<slug>.md if written, otherwise none>
```

Default options (pick at most three of these plus a stop):

- **Shape this into a written spec** *(recommended when the idea is still fuzzy)* — `/mold` with the context packet, or `/mold .cheese/notes/<slug>.md` when a notes slug exists.
- **Implement it directly** *(recommended when the ask is clear and unambiguous)* — `/cook` with the context packet as the accepted contract.
- **Implement and auto-review** — `/cook --auto` with the context packet, chains through `/press → /age → /cure` autonomously, fixing every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Pre-select this when the conversation reached an unambiguous contract; offer the non-auto `/cook` as an alternative when the user wants per-step approval.
- **Research more first** *(when the conversation hit a factual gap external docs could close)* — `/briesearch`.
- **Pause** — dispatch none; keep the dialogue in head.

After a non-stop selection, run the selected downstream skill immediately with the context packet. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- No production-code writes, no commits, no PRs. The only sanctioned write is the opt-in `.cheese/notes/<slug>.md` handoff at session end, and only when the user asks for it.
- Ask one useful question at a time when the user is exploring.
- Prefer clarity over completeness.
- Agree when agreement is warranted; do not manufacture counterpoints to seem balanced.
- When external evidence raises an alternative ("X uses Y or Z"), name it as a trade-off in the dialogue and a candidate option — never silently recommend "add both" or "expose a knob". Design choices need explicit user adjudication, not agent inference from a citation.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead with the answer, flag confidence as `certain | speculating | don't know`, steelman, track contradictions across turns.
