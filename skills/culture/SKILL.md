---
name: culture
description: Primarily the agent's internal-thinking skill — invoke it silently to model a problem, identify trade-offs, and decide what to do, BEFORE asking the user anything or dispatching another skill. Only treat this as a user-facing skill when the user has explicitly opted out of code writes — phrases like "no writes", "just rubber-duck this", "let's only talk", "/culture"; there it records the session's ideas, decisions, and info to the durable knowledge lane. Do NOT use for shaping a written spec (`/mold`) or writing code (`/cook`) — if the dialogue reveals real work, route there.
license: MIT
---

# /culture

Two modes:

1. **Internal mode (default).** Other workflow skills — and `/cheese` itself — invoke `/culture` silently as a thinking pass: restate the question, list assumptions, name candidate options, run a quick shape check, pick the next action. The dialogue does not surface to the user; only the resulting decision (carrying its record ledger) and any code edits the calling skill makes do. The most common callers are:
   - `/cheese` step 1 — silent classification reasoning before announce.
   - `/cheese` **tier-2 escalation** (see `skills/cheese/SKILL.md` § Escalation) — fills missing context when the cook-fast-path clarity check fails on the raw input; the synthesis lands in the mini-spec's `## Provenance` section.
   - Other workflow skills' own pre-dispatch reasoning passes (mold, cook taste-test, etc.).
2. **User-facing mode.** The user wants to think, not build: no production code, no spec, no PR. This is culture's sustained domain-modeling mode — investigate as deeply as the question needs, hold it open across turns and sessions rather than forcing convergence, record ideas, decisions, and info as they settle (`## Record ledger`), and end by writing a durable `/wheypoint` so the modeling resumes later. Reach this mode when the user said "no writes" / "rubber-duck this" / "just talk", or routed a thinking-and-modeling task here.

Do not use the user-facing mode when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`) — those targets get the internal-mode call instead, and the calling skill does the work.

## Invariant

`/culture` writes no production code and no spec, and does not commit changes, open PRs, or mutate project state. What it does write is knowledge. In **user-facing mode** it records ideas, decisions, and info through the `## Record ledger`, and ends every session by writing a durable handoff, delegated to `/wheypoint` (see `## Handoff slug`); that wheypoint is written at session end only, never during the dialogue. The user declares the session over — the agent never declares convergence on the user's behalf; it may ask whether the thread feels settled, and otherwise carries it forward. In **internal mode** it writes nothing at all and hands its ledger back to the caller. If a user-facing conversation reveals that something should be built, route to `/mold` or `/cook` after the wheypoint is written. In internal mode, just return the decision and let the calling skill act.

## Flow

Both modes share this reasoning loop; the per-step difference is internal-returns-a-decision vs user-facing-renders-the-dialogue.

1. Restate the question or tension in one sentence. If the question rests on a false premise or a loaded assumption, name it.
2. Identify assumptions, constraints, and decision criteria.
3. Explore trade-offs and likely blast radius. When the trade-off hinges on "what does this touch", run a read-only shape check on the candidate seam — semantic caller search plus dependency/blast-radius context from the selected backend — and label each option `[low | medium | high blast radius]`. Procedure mirrors `../mold/references/shape-check.md`; culture stops at the verdict and never drafts signatures. Steelman the rejected option before settling on a recommendation.
4. Gather evidence to the depth the question needs. Start with a light wiki probe — is this already decided or already known? — per the detect-and-degrade contract in [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md): at most one `ground` call in internal mode, scaled up as useful in user-facing mode; when hallouminate is absent, skip, note the absence once, and cap confidence at `speculating` when design rationale is central. In internal mode keep the rest light — a quick shape check, no deep research — so the calling skill stays fast. In user-facing mode investigate as deeply as useful: dispatch the read-only `explorer` agent for code grounding and take back its digest, rather than dumping raw reads into the dialogue; when that agent is unavailable, call the selected source-code backends directly.
5. Decide the next move. In internal mode, return a single recommendation and stop. In user-facing mode you need not force convergence: render a compact summary, the `Ideas / Decisions / Info` ledger, and confidence-tagged open questions (`certain | speculating | don't know`), then either recommend a downstream skill or defer and carry the thread forward. Once the user calls the thread over, flush the ledger, then end the session by writing the wheypoint (`## Handoff slug`), whose `next:` records where the modeling landed.

Asking the user is the point: every consequential fork is theirs to decide, surfaced as a choice rather than settled for them. The depth you offer — full signatures, named edge cases, file:line evidence — informs each question; it never substitutes for asking it. In user-facing mode, raise forks conversationally in the dialogue; reserve structured question tools for the end-of-session handoff gate. Never bundle multiple consequential forks into one prompt.

## Record ledger

Thinking is worth keeping. Each user-facing round prints an `Ideas / Decisions / Info` ledger beside the open questions, and every entry lands in the durable knowledge lane, never in code:

| Kind | What qualifies | Target with hallouminate | Fallback without it |
| --- | --- | --- | --- |
| Decision | a fork the user settled that had a real rejected alternative | an ADR under `adr/` in `repo:<repo>:wiki`, in the format and resolution of [`../mold/references/adr.md`](../mold/references/adr.md) | `docs/adr/<slug>-NNN.md` |
| Idea | a direction worth revisiting that nobody committed to | `ideas/<slug>.md` in the wiki | `docs/culture/<slug>.md` § Ideas |
| Info | a fact, constraint, or gotcha learned mid-dialogue | fold into the wiki page it extends (`ground` → `read_markdown` → `add_markdown { overwrite: true }`); a new page only when nothing fits | `docs/culture/<slug>.md` § Info |

Resolve the target the way `adr_target()` does: shape-match the current repo's `repo:<repo>:wiki` corpus, never a literal name; when hallouminate is absent, write the tracked fallback and say so in one loud line. Write an entry the moment the user says `record that`, `note that`, or `remember that`; flush the rest once the user calls the thread over, before the wheypoint, which then links each record under its artifacts. Never record a passing thought the user did not settle or ask to keep — those stay in the wheypoint. Internal mode writes nothing: it returns the ledger inside its decision so the calling skill persists it (Mold's Curdle turns decisions into ADRs; a mini-spec cites them under `## Provenance`).

## Preferred tools and fallbacks

Call source-code search and read backends directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Blast-radius reads use semantic caller search plus a read-only dependency/shape check when the backend offers one.

Beyond source-code routing there are culture-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Visualizing diffs or examples | `delta` | plain `git diff` |
| External sanity check | `/briesearch` | clearly mark as an assumption |
| Wiki grounding (evidence step, ≤1 `ground` in internal mode) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` — see [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md) | skip; note the absence once; cap at `speculating` when design rationale is central |

Missing optional tools should not interrupt the conversation. In internal mode keep tool use light; it is a fast thinking pass. In user-facing mode tool use scales to the question — investigation through the `explorer` agent, or direct source-code backend calls when it is unavailable, is expected when the modeling needs grounding.

## Output

See Flow step 5.

## Handoff slug

**Every** user-facing session ends by writing a durable wheypoint, so the modeling is resumable. Invoke `/wheypoint <focus>` and let it own compaction, secret redaction, the state-mapped suggested-skills section, and the resumable slug. Culture does not maintain its own schema; the slug contract (`status` / `next` / `mode` / `artifact` and the `## Document` body) is defined in `skills/wheypoint/SKILL.md`, which is the single source of truth.

Culture-relevant `next:` values: `culture` or `hold` to resume the modeling in a later session (defer convergence), `mold` (fuzzy idea, route to spec), `cook` (clear ask, route to implementation), or `done` when the user judges the thread genuinely closed. When the next step is blocked on a human decision, set `status: gated:` rather than a `next:` value.

## Handoff

**Pipeline:** **[culture]** → mold → cook → press → age → cure → plate

At session end, write the durable wheypoint first (invoke `/wheypoint`), then — when the conversation reveals real work — ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md). Any structured confirm reaching this gate must satisfy the freshness rule in [`../cheese/references/ask-user-question.md`](../cheese/references/ask-user-question.md) — only a fork already discussed conversationally this session may reach a structured question here. Lead each option with the verb (what the user wants to *do* next); the skill command is the backing detail. Before asking, render a compact context packet so the downstream skill can dispatch without losing the discussion:

```yaml
handoff_context:
  source_skill: /culture
  summary: <one factual sentence>
  open_questions: [<only blockers, if any>]
  artifact: .cheese/notes/<slug>.md  # the session wheypoint, always written
  records: [<wiki page or fallback path per written ledger entry>]
```

Default options (pick at most three of these plus a stop):

- **Shape this into a written spec** *(recommended when the idea is still fuzzy)* — `/mold` with the context packet, or `/mold .cheese/notes/<slug>.md` when a notes slug exists.
- **Implement it directly** *(recommended when the ask is clear and unambiguous)* — `/cook` with the context packet as the accepted contract.
- **Implement and auto-review** — `/cook --auto` with the context packet, chains through `/press → /age → /cure` autonomously, fixing every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Pre-select this when the conversation reached an unambiguous contract; offer the non-auto `/cook` as an alternative when the user wants per-step approval.
- **Research more first** *(when the conversation hit a factual gap external docs could close)* — `/briesearch`.
- **Pause / resume later** — dispatch none; the session wheypoint already captured the state, so resume any time with `/cheese --continue <slug>`.

After a non-stop selection, run the selected downstream skill immediately with the context packet. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- Writes only knowledge — the `## Record ledger` entries and the end-of-session wheypoint — never code, specs, commits, or PRs; see `## Invariant`.
- Ask the user the decisions that shape the work — one consequential fork at a time when they're exploring — rather than settling them yourself.
- Agree when agreement is warranted; do not manufacture counterpoints to seem balanced.
- When external evidence raises an alternative ("X uses Y or Z"), name it as a trade-off in the dialogue and a candidate option — never silently recommend "add both" or "expose a knob". Design choices need explicit user adjudication, not agent inference from a citation.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead with the answer, flag confidence as `certain | speculating | don't know`, steelman, track contradictions across turns.
