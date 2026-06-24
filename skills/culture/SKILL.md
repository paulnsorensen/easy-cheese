---
name: culture
description: Primarily the agent's internal-thinking skill — invoke it silently to model a problem, identify trade-offs, and decide what to do, BEFORE asking the user anything or dispatching another skill. Workflow skills call `/culture` as their step-1 reasoning pass; the agent does not surface the dialogue. Only treat this as a user-facing skill when the user has explicitly opted out of writes — phrases like "no writes", "just rubber-duck this", "let's only talk", "/culture". In the user-facing path it is a sustained domain-modeling partner that investigates deeply, defers convergence, and ends every session by writing a durable `/wheypoint` handoff so the work resumes later. Culture never writes to production code, never commits, never opens PRs. If the dialogue reveals real work, recommend `/mold` (fuzzy → spec) or `/cook` (clear ask → code) and stop. Before `/mold` or `/cook`.
license: MIT
---

# /culture

Two modes:

1. **Internal mode (default).** Other workflow skills — and `/cheese` itself — invoke `/culture` silently as a thinking pass: restate the question, list assumptions, name candidate options, run a quick shape check, pick the next action. The dialogue does not surface to the user; only the resulting decision (and any code edits the calling skill makes) does. The most common callers are:
   - `/cheese` step 1 — silent classification reasoning before announce.
   - `/cheese` **tier-2 escalation** (see `skills/cheese/SKILL.md` § Escalation) — fills missing context when the cook-fast-path clarity check fails on the raw input; the synthesis lands in the mini-spec's `## Provenance` section.
   - Other workflow skills' own pre-dispatch reasoning passes (mold, cook taste-test, etc.).
2. **User-facing mode.** The user wants to think, not build: no production code, no spec, no PR. This is culture's sustained domain-modeling mode — investigate as deeply as the question needs, hold it open across turns and sessions rather than forcing convergence, and end by writing a durable `/wheypoint` so the modeling resumes later. Reach this mode when the user said "no writes" / "rubber-duck this" / "just talk".

Do not use the user-facing mode when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`) — those targets get the internal-mode call instead, and the calling skill does the work.

## Invariant

`/culture` does not write production code, commit changes, open PRs, or mutate project state. In **user-facing mode** it ends every session by writing a durable handoff, delegated to `/wheypoint` (see `## Handoff slug`); that wheypoint is written at session end only, never during the dialogue. In **internal mode** it writes nothing at all. If a user-facing conversation reveals that something should be built, route to `/mold` or `/cook` after the wheypoint is written. In internal mode, just return the decision and let the calling skill act.

## Flow

Both modes share the same reasoning loop. The difference is what the agent does with the output: internal mode returns a single decision back to the calling skill; user-facing mode renders the dialogue and waits for the user.

1. Restate the question or tension in one sentence. If the question rests on a false premise or a loaded assumption, name it.
2. Identify assumptions, constraints, and decision criteria.
3. Explore trade-offs and likely blast radius. When the trade-off hinges on "what does this touch", run a read-only shape check on the candidate seam — a `cheez-search` callers query (`tilth_search kind: "callers"`) plus `tilth_deps` — and label each option `[low | medium | high blast radius]`. Procedure mirrors `../mold/references/shape-check.md`; culture stops at the verdict and never drafts signatures. Steelman the rejected option before settling on a recommendation.
4. Gather evidence to the depth the question needs. In internal mode keep it light — a quick shape check, no deep research — so the calling skill stays fast. In user-facing mode investigate as deeply as useful: dispatch the read-only `explorer` agent for code grounding and take back its digest, rather than dumping raw reads into the dialogue (where the `explorer` agent isn't available, e.g. a harness that installs only easy-cheese, ground directly via `/cheez-search` / `/cheez-read`).
5. Decide the next move. In internal mode, return a single recommendation and stop. In user-facing mode you need not force convergence: render a compact summary and confidence-tagged open questions (`certain | speculating | don't know`), then either recommend a downstream skill or defer and carry the thread forward. End the session by writing the wheypoint (`## Handoff slug`), whose `next:` records where the modeling landed.

Default the model's own contribution to maximum useful depth — full pseudocode signatures over hand-waving, named edge cases over "consider edge cases", concrete file:line evidence over vague pointers. Smallest-useful-question discipline applies only to what you ask the user, never to what you offer them.

## Preferred tools and fallbacks

Code search and reading go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`) — see those skills for tool selection rules. Blast-radius reads specifically use `cheez-search` callers (`kind: "callers"`) plus `tilth_deps` (read-only shape check); culture stops at the verdict and never drafts signatures.

Beyond `cheez-*` there are culture-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Visualizing diffs or examples | `delta` | plain `git diff` |
| External sanity check | `/briesearch` | clearly mark as an assumption |

Missing optional tools should not interrupt the conversation. In internal mode keep tool use light; it is a fast thinking pass. In user-facing mode tool use scales to the question — deep investigation via the `explorer` agent (or, where it isn't available, `/cheez-search` / `/cheez-read` directly) is expected when the modeling needs grounding.

## Output

Return a short conversational summary:

- Current understanding
- Trade-offs or options
- Open questions

## Handoff slug

A user-facing session ends by writing a durable handoff, and this is not opt-in: **every** user-facing culture session produces a wheypoint at session end so the modeling is resumable. Invoke `/wheypoint <focus>` and let it own compaction, secret redaction, the state-mapped suggested-skills section, and the resumable slug. Culture does not maintain its own schema; the slug contract (`status` / `next` / `mode` / `artifact` and the `## Document` body) is defined in `skills/wheypoint/SKILL.md`, which is the single source of truth.

Culture-relevant `next:` values: `culture` or `hold` to resume the modeling in a later session (defer convergence), `mold` (fuzzy idea, route to spec), `cook` (clear ask, route to implementation), or `done` when the thread is genuinely closed. When the next step is blocked on a human decision, set `status: gated:` rather than a `next:` value. The wheypoint is the **only** thing a culture session writes: no commits, no PRs, no production-code edits.

## Handoff

**Pipeline:** **[culture]** → mold → cook → press → age → cure → ship

At session end, write the durable wheypoint first (invoke `/wheypoint`), then — when the conversation reveals real work — ask via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command is the backing detail. Before asking, render a compact context packet so the downstream skill can dispatch without losing the discussion:

```yaml
handoff_context:
  source_skill: /culture
  summary: <one factual sentence>
  open_questions: [<only blockers, if any>]
  artifact: .cheese/notes/<slug>.md  # the session wheypoint, always written
```

Default options (pick at most three of these plus a stop):

- **Shape this into a written spec** *(recommended when the idea is still fuzzy)* — `/mold` with the context packet, or `/mold .cheese/notes/<slug>.md` when a notes slug exists.
- **Implement it directly** *(recommended when the ask is clear and unambiguous)* — `/cook` with the context packet as the accepted contract.
- **Implement and auto-review** — `/cook --auto` with the context packet, chains through `/press → /age → /cure` autonomously, fixing every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Pre-select this when the conversation reached an unambiguous contract; offer the non-auto `/cook` as an alternative when the user wants per-step approval.
- **Research more first** *(when the conversation hit a factual gap external docs could close)* — `/briesearch`.
- **Pause / resume later** — dispatch none; the session wheypoint already captured the state, so resume any time with `/cheese --continue <slug>`.

After a non-stop selection, run the selected downstream skill immediately with the context packet. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- No production-code writes, no commits, no PRs. The only sanctioned write is the end-of-session wheypoint, delegated to `/wheypoint`; user-facing sessions always write one, internal mode writes nothing.
- Ask one useful question at a time when the user is exploring.
- Prefer clarity over completeness.
- Agree when agreement is warranted; do not manufacture counterpoints to seem balanced.
- When external evidence raises an alternative ("X uses Y or Z"), name it as a trade-off in the dialogue and a candidate option — never silently recommend "add both" or "expose a knob". Design choices need explicit user adjudication, not agent inference from a citation.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead with the answer, flag confidence as `certain | speculating | don't know`, steelman, track contradictions across turns.
