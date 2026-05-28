---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill and dispatch it immediately. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", "figure out what skill I need", or any opening message that does not already name a downstream skill. Classifies the input into an intent shape, announces the target and reason in one line, then runs the chosen skill with the exact command and context packet. Add `--safe` to gate dispatch behind a confirmation prompt; otherwise cheese decides and acts. Before any other workflow skill.
license: MIT
---

# /cheese

Use this skill as the single front door to the easy-cheese workflow. Inspect whatever the user dropped in, classify it into an intent shape, announce the routing decision in one line, and dispatch immediately to the chosen skill. Cheese is autonomous by default — it picks the best target and runs it, only stopping to ask when `--safe` is passed or when the input is genuinely ambiguous.

Do not use it once a downstream skill is already running, or when the user has already named the skill they want (`/mold ...`, `/cook ...`, `/age`, etc.) — pass straight through to that skill instead.

## Inputs

Accept anything the user supplies as `$ARGUMENTS`:

- A natural-language feature description, idea, or question.
- A spec path (`.cheese/specs/<slug>.md`) or pasted spec content.
- A bug report, stack trace, failing test output, or reproduction steps.
- A file path, glob, or directory.
- A PR or issue reference (`PR#142`, `#87`, GitHub URL).
- A research question about an external library, API, or pattern.
- An empty or near-empty prompt — treat as "what's next?" and clarify.

Optional flags:

- `--safe` — gate dispatch behind a confirmation prompt. Use when the user wants the chance to redirect routing before the chosen skill runs. Without this flag, cheese announces and dispatches in the same turn.
- `--continue <slug>` — resume an in-flight pipeline from the latest handoff slug. See `## --continue` below.
- `--hard` — inject the `/hard-cheese` metacognitive gate before code is shared for review. The flag propagates to whichever target the router dispatches and fires at `/cure`'s share-for-review handoff (or end of the autonomous chain under `--hard`). See `skills/hard-cheese/SKILL.md`.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question via `AskUserQuestion` before classifying.

## Flow

1. **Think first (silent).** Before announcing, model the problem internally per `skills/culture/SKILL.md` — restate the ask in one sentence, list the candidate targets, name the deciding signal. This is the agent's own reasoning, not a user-facing dialogue; the only output of this step is the classification decision that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (see step 5).
3. **Announce** — print one short paragraph with: detected intent, chosen target skill (or pre-step), and the one-line reason for the decision. Cite the signal that drove it (e.g. "spec path under `.cheese/specs/`", "stack trace present", "PR URL").
4. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` or `research`.
5. **Dispatch** — without `--safe`, run the chosen skill immediately with its exact dispatch command and context packet, in the same turn as the announce. With `--safe`, issue a handoff gate per [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) (recommended target pre-selected, at least one alternative, `Stop`) and wait for the user's selection before dispatching. Either way the downstream skill owns its flow; `/cheese` does not narrate beyond the routing decision.

`/cheese` is a router, not a worker. It never edits files, runs tests, opens PRs, or paraphrases the downstream skill's output.

## Intent shapes

| Intent | Trigger signals | Pre-step | Target skill |
| --- | --- | --- | --- |
| clarify | Empty input, single keyword, or critical ambiguity | `AskUserQuestion` for the missing fact | re-enter `/cheese` once answered |
| research | Library / API / vendor question, "what's the best…", comparison | — | `/briesearch` |
| rubber-duck | User explicitly asks for discussion only — "no writes", "let's just talk", "rubber-duck this" — with no artifact intent | — | `/culture` |
| mold | Feature description with fuzzy scope, multi-module idea, or stated need for a spec | optional `/briesearch` first if external evidence is missing | `/mold` → `/cook` |
| cook | Spec path, focused fix with clear inputs/outputs/verification, single-file tweak | — | `/cook --auto` (default) — chains through `/press → /age → /cure` |
| cheese-factory | Approved spec at `.cheese/specs/<slug>.md` with 5+ acceptance criteria / behavioural curds, or user phrases like "send through the factory", "parallelize", "many curds", "fan out" | — | `/cheese-factory` |
| debug | Stack trace, failing test, reproduction steps, "why is X broken", visual bug + repro path | — | `/pasteurize --auto` (default) → `/cook --auto` |
| age | PR reference, file path/glob review request, "is this safe to merge", "find bugs" | — | `/age` |
| age-then-cure | Existing `.cheese/age/<slug>.md` plus a "fix the findings" instruction | — | `/age` (re-scope if needed) → `/cure` |

`/culture` is otherwise an internal-use skill the agent invokes during step 1 of the flow to think through routing — it is not a default user-facing target. Only surface it when the user has explicitly opted out of writes for this session.

The full classification table — including disambiguation rules, edge cases, and confidence cues — lives in `references/classification.md`.

## --continue

`/cheese --continue <slug>` is the manual fresh-context resumption path. Use it after compacting the conversation, after `/ultracook` has stopped on a halt, or whenever the user wants to drive the pipeline by hand from a cleared context.

Flow:

1. Scan for the most recently modified handoff slug across `.cheese/{cook,press,age,cure,affinage,notes}/<slug>.md`.
2. If none exist, offer to start the pipeline from scratch — `/mold` for fuzzy specs, `/cook` for clear asks, `/ultracook` for high-blast-radius specs — and stop.
3. If at least one exists, read the latest one and surface the orientation line so the user knows where they are. Decide the next action from the slug's `next:` field:
   - **When `next:` names a phase** (`mold | cook | press | age | cure | ultracook`) — dispatch `/\<next\> \<slug\>` directly. Under `--safe`, offer it as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `next:` is terminal** (`done` from a phase slug, or `stop` from a culture-notes slug — the pipeline already finished) — report the terminal state and stop. The terminal values surface state to the user, not a runnable command; never construct `/done <slug>` or `/stop <slug>`.

Under `--safe`, gate the resumption through the handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md); otherwise run the named phase immediately with the slug. The slug files are the resumability contract: they tell the router where the pipeline is and how to move it forward.

## Confidence and the clarify gate

Treat classification confidence qualitatively (`low | medium | high`). Threshold for direct routing is `medium` or better. Below that:

- Pick the **clarify** path and ask exactly one question via `AskUserQuestion`.
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer.

At `medium` or above, dispatch — don't second-guess a clear signal with extra questions. Silent misrouting is worse than asking once, but reflexive gating is worse than acting on a confident read.

## Preferred tools and fallbacks

When the input is a path or slug, code reading and searching go through the `cheez-*` skills (`/cheez-read`, `/cheez-search`) — see those skills for tool selection rules.

Beyond `cheez-*` there are router-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming routing target with the user (only under `--safe` or `clarify`) | `AskUserQuestion` / host structured question (`request_user_input` in Codex when available) | a numbered list with explicit dispatch commands |

`/cheese` keeps tool use light. Treat anything heavier than a single-file read or one search call as a sign the work belongs in the downstream skill, not in the router.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the chosen skill, e.g. `Target: /cook .cheese/specs/foo.md`.

Then dispatch the target in the same turn. Under `--safe`, append a handoff gate (recommended target pre-selected, one alternative, `Stop`, exact dispatch records for every non-stop option) and wait for the user before dispatching. If `clarify` is chosen, replace the dispatch with the single clarifying question.

## Handoff

Dispatch happens through [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) when `--safe` is set; otherwise cheese runs the target directly. Without `--safe`, cheese propagates `--auto` to any target that supports it, so the chain runs all the way through without per-step gates. Under `--safe`, the auto variant becomes an alternative the user can pick, not the default.

Default targets per intent:

- **clarify** — single targeted question; no skills run until the answer arrives.
- **research** — `/briesearch` (recommended). No auto variant.
- **rubber-duck** — `/culture` (recommended). Only reached when the user explicitly opted out of writes. No auto variant.
- **mold** — `/mold` (recommended). Safe-mode alternative: `/briesearch first` when external evidence is missing.
- **cook** — default: `/cook --auto <slug-or-path>`. Safe-mode alternatives: `/cook <slug-or-path>` (no auto), `/mold first` if scope is borderline.
- **cheese-factory** — `/cheese-factory <slug-or-path>` (recommended when the spec decomposes into 5+ curds). Safe-mode alternative: `/ultracook <slug-or-path>` (sequential pipeline).
- **debug** — default: `/pasteurize --auto <input>`. Safe-mode alternatives: `/pasteurize <input>` (no auto), `/culture` only when the user explicitly wants no-write diagnosis.
- **age** — `/age <ref>` (recommended). Safe-mode alternative: `/age --scope <path>` when the user named a path glob.
- **age-then-cure** — `/age <slug>` (recommended). Safe-mode alternative: `/cure <slug>` when a fresh report already exists.

Pre-select only the highest-confidence target. Without `--safe`, surface the target as a decision, not a question — dispatch the recommended option directly. With `--safe`, dispatch waits for the user's selection; the captured dispatch packet runs immediately on a non-stop choice.

## Rules

- Default mode is autonomous: announce the routing decision and dispatch in the same turn. `--safe` is the only switch that re-introduces a confirmation prompt.
- Below `medium` confidence — or when a coherence check trips — route to `clarify` instead of guessing. One clarifying question, max, before re-entering classification.
- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.
- Never edit files, write specs, or run quality gates from `/cheese`.

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) — Codex-safe post-selection dispatch contract (shared across workflow skills).
