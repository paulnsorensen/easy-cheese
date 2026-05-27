---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", "figure out what skill I need", or any opening message that does not already name a downstream skill. Classifies the input into an intent shape, announces the target and reason, and gates dispatch behind explicit user selection so nothing runs silently. After a non-stop selection, immediately dispatches the selected downstream skill with the exact command and context packet. Before any other workflow skill.
license: MIT
---

# /cheese

Use this skill as the single front door to the easy-cheese workflow. Inspect whatever the user dropped in, classify it into an intent shape, announce the routing decision, and gate dispatch on explicit confirmation.

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

- `--continue <slug>` — resume an in-flight pipeline from the latest handoff slug. See `## --continue` below.
- `--hard` — inject the `/hard-cheese` metacognitive gate before code is shared for review. The flag propagates to whichever target the router dispatches and fires at `/cure`'s share-for-review handoff (or end of final auto pass under `--auto --hard`). See `skills/hard-cheese/SKILL.md`.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question via `AskUserQuestion` before classifying.

## Flow

1. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (see step 4).
2. **Announce** — print one short paragraph with: detected intent, chosen target skill (or pre-step), and the one-line reason for the decision. Cite the signal that drove it (e.g. "spec path under `.cheese/specs/`", "stack trace present", "PR URL").
3. **Self-check** — run the coherence questions in `references/coherence-check.md` before dispatching. If any fails, downgrade to `clarify` or `research`.
4. **Confirm** — issue a handoff gate per [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md): recommended target pre-selected, at least one alternative, and a `Stop` option. The user's selection is the only trigger for dispatch; never invoke a skill silently before the selection.
5. **Hand off** — once the user picks a non-stop option, immediately run the selected skill with the exact dispatch command and context packet. The downstream skill owns its own flow; `/cheese` does not narrate beyond the routing decision.

`/cheese` is a router, not a worker. It never edits files, runs tests, opens PRs, or paraphrases the downstream skill's output.

## Intent shapes

| Intent | Trigger signals | Pre-step | Target skill |
| --- | --- | --- | --- |
| clarify | Empty input, single keyword, or critical ambiguity | `AskUserQuestion` for the missing fact | re-enter `/cheese` once answered |
| research | Library / API / vendor question, "what's the best…", comparison | — | `/briesearch` |
| rubber-duck | "Help me think through…", architecture discussion, no artifact intent | — | `/culture` |
| mold | Feature description with fuzzy scope, multi-module idea, or stated need for a spec | optional `/briesearch` first if external evidence is missing | `/mold` → `/cook` |
| cook | Spec path, focused fix with clear inputs/outputs/verification, single-file tweak | — | `/cook` |
| cheese-factory | Approved spec at `.cheese/specs/<slug>.md` with 5+ acceptance criteria / behavioural curds, or user phrases like "send through the factory", "parallelize", "many curds", "fan out" | — | `/cheese-factory` |
| debug | Stack trace, failing test, reproduction steps, "why is X broken" | — | `/pasteurize` → `/cook --auto` |
| age | PR reference, file path/glob review request, "is this safe to merge", "find bugs" | — | `/age` |
| age-then-cure | Existing `.cheese/age/<slug>.md` plus a "fix the findings" instruction | — | `/age` (re-scope if needed) → `/cure` |

The full classification table — including disambiguation rules, edge cases, and confidence cues — lives in `references/classification.md`.

## --continue

`/cheese --continue <slug>` is the manual fresh-context resumption path. Use it after compacting the conversation, after `/ultracook` has stopped on a halt, or whenever the user wants to drive the pipeline by hand from a cleared context.

Flow:

1. Scan for the most recently modified handoff slug across `.cheese/{cook,press,age,cure,affinage,notes}/<slug>.md`.
2. If none exist, offer to start the pipeline from scratch — `/mold` for fuzzy specs, `/cook` for clear asks, `/ultracook` for high-blast-radius specs — and stop.
3. If at least one exists, read the latest one and use its `next:` field to decide the recommended action. Surface the orientation line so the user knows where they are.
4. Confirm the resumption via the handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). The recommended option depends on the slug's `next:` value:
   - **When `next:` names a phase** (`mold | cook | press | age | cure | ultracook`):
     - **Run /\<next\> \<slug\>** *(recommended)* — continue the chain at the named phase.
     - **Run /ultracook \<slug\>** — re-enter the autonomous fresh-context chain.
     - **Stop** — leave the pipeline paused.
   - **When `next:` is terminal** (`done` from a phase slug, or `stop` from a culture-notes slug — the pipeline already finished):
     - **Stop** *(recommended)* — review the diff and `/gh` when ready; there is no further phase to run.
     - **Run /age \<slug\>** — re-review the diff in fresh context if you want another pass.
     - **Run /ultracook \<slug\>** — only if you want to redo the whole chain over the same slug. Refuses when phase handoffs already exist (per `/ultracook`'s existing-handoffs guard); requires removing the existing slugs first.

`/cheese --continue` never dispatches before the user selects, and it never builds `/done <slug>` or `/stop <slug>` from a terminal `next:` field — those values surface the terminal state to the user, not a runnable command. After a non-stop selection, run the selected phase immediately with the slug. The slug files are the resumability contract: they tell the router where the pipeline is, and the user picks how to move it forward.

## Confidence and the clarify gate

Treat classification confidence qualitatively (`low | medium | high`). Threshold for direct routing is `medium` or better. Below that:

- Pick the **clarify** path and ask exactly one question via `AskUserQuestion`.
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer; do not chain a partial classification.

Never resolve uncertainty by guessing — silent misrouting is worse than asking once.

## Preferred tools and fallbacks

When the input is a path or slug, code reading and searching go through the cheez-* skills (`/cheez-read`, `/cheez-search`) — see those skills for tool selection rules.

Beyond cheez-* there are router-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming routing target with the user | `AskUserQuestion` / host structured question (`request_user_input` in Codex when available) | a numbered list with explicit dispatch commands and "no auto-invoke before selection" wording |

`/cheese` keeps tool use light. Treat anything heavier than a single-file read or one search call as a sign the work belongs in the downstream skill, not in the router.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the recommended skill, e.g. `Target: /cook .cheese/specs/foo.md`.
4. **Confirmation prompt** — handoff gate with the recommended target pre-selected, one alternative, `Stop`, and exact dispatch records for every non-stop option.

If `clarify` is chosen, replace step 4 with the single clarifying question.

## Handoff

Dispatch happens through [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Default option set per intent:

- **clarify** — single targeted question; no skills offered until the answer arrives.
- **research** — `Run /briesearch` (recommended), `Run /culture`, `Stop`.
- **rubber-duck** — `Run /culture` (recommended), `Run /briesearch`, `Stop`.
- **mold** — `Run /mold` (recommended), `Run /briesearch first`, `Stop`.
- **cook** — `Run /cook <slug-or-path>` (recommended), `Run /cook --auto <slug-or-path>` (offer only when the input is unambiguous *and* the user signalled autonomous pipeline intent — "auto", "ship it", "all the way through"; never pre-select), `Run /mold first`, `Stop`.
- **cheese-factory** — `Run /cheese-factory <slug-or-path>` (recommended when the spec decomposes into 5+ curds), `Run /ultracook <slug-or-path>` (when the user wants the sequential pipeline instead), `Run /cook --auto`, `Stop`.
- **debug** — `Run /pasteurize <input>` (recommended), `Run /pasteurize --auto <input>` (offer only when the user signalled autonomous intent — "auto", "ship it", "fix it all the way"; never pre-select), `Run /culture` (when the user explicitly wants no-write diagnosis only), `Stop`.
- **age** — `Run /age <ref>` (recommended), `Run /age --scope <path>`, `Stop`.
- **age-then-cure** — `Run /age <slug>` (recommended), `Run /cure <slug>` (when a fresh report already exists), `Stop`.

Pre-select only the highest-confidence target. If two targets are viable, surface both and let the user decide.

`/cheese` never auto-invokes before the user selects. After a non-stop selection, the selected skill runs immediately with the captured dispatch packet.

## Rules

- Classification is the only output until the user confirms; after a non-stop confirmation, dispatch instead of stopping at a recommendation.
- One clarifying question, max, before re-entering classification.
- Below `medium` confidence, route to `clarify`, not to a guess.
- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.
- Never edit files, write specs, or run quality gates from `/cheese`.

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) — Codex-safe post-selection dispatch contract (shared across workflow skills).
