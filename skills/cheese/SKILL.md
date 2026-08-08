---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", or any opening message that does not already name a downstream skill.
license: MIT
---

# /cheese

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

- `--safe` — gate dispatch behind a confirmation prompt.
- `--open-pr` — propagate through the implementation chain to terminal `/plate`; a new PR follows `/plate`'s explicit-choice and review-shape policy.
- `--continue <slug-or-note-path>` — resume an in-flight pipeline from a handoff slug or note.
- `--hard` — propagate to `/plate`, which runs the final artifact-writing gate before `/hard-cheese` and publication.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question through the host routing guide in [`references/handoff-gate.md`](references/handoff-gate.md) before classifying.

## Flow

0. **Read the full user message, not just `$ARGUMENTS`.** Any prose accompanying the invocation is a directive list; execute or answer it before — and where it conflicts, instead of — the flow's defaults and any handoff protocol. The handoff file restores state; the user's live message overrides it.
1. **Think first (silent).** Model the problem internally per `skills/culture/SKILL.md` — restate the ask, list candidate targets, name the deciding signal. Output is the classification that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (handled by the tier-3 escalation in step 4).
3. **Clarity check (implementation intents only).** Run cook's fast-path check for `cook` and `mold`. Direct `plate` intents bypass it.
4. **Escalate (if needed).** Tier 1 dispatches the chosen target (writing a mini-spec via `/mold`'s agent-invoked mode when the dispatch is `/cook --auto` and no spec path was supplied). Tier 2 autonomously invokes `/culture` and/or `/briesearch` in internal mode, then re-runs the clarity check. Tier 3 blocks on a single targeted host-routed question and re-enters classification on the answer. See `## Escalation`.
5. **Wiki grounding (when hallouminate is present).** Derive a search query from the dropped-in input, ground it against the wiki corpus — at most one `mcp__hallouminate__ground` call, corpus resolved via `list_corpora` (probe shape: `skills/mold/references/grounding.md`) — and fold the top hits into the dispatch packet as `handoff_context.wiki_hits` (`[{page, line, why}]`; see [`references/handoff-gate.md`](references/handoff-gate.md) § Context payloads). When hallouminate is absent or no wiki corpus exists, skip and degrade per [`references/optional-plugins.md`](references/optional-plugins.md).
6. **Announce** — print a short block (Intent / Reason / Target, plus wiki hits when present) per the format in `## Output`. Cite the signal that drove the routing decision.
7. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` (tier 3) or `research`.
8. **Dispatch** — without `--safe`, run the chosen skill immediately with its exact dispatch command and context packet, in the same turn as the announce. With `--safe`, issue a handoff gate per [`references/handoff-gate.md`](references/handoff-gate.md) (recommended target pre-selected, at least one alternative, `Stop`) and wait for the user's selection before dispatching.

`/cheese` is a router, not a worker: it never edits files, runs tests, or opens PRs. Use only the host's read, search, and dispatch capabilities. The sole exception is invoking `/mold`'s agent-invoked mini-spec mode in tier 1 when `/cook --auto` needs a spec first; that write happens inside `/mold`'s own capability scope, not the router's.

Portability reference: [`references/harness-portability.md`](references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Intent shapes

The full classification table — including all intent shapes, signals, disambiguation rules, and edge cases — lives in `references/classification.md`.

## Escalation

For `cook` and `mold` intents, `/cheese` runs cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md`) and escalates through three tiers: **tier 1** (clear) dispatches immediately — reusing a matching spec via the spec-discovery check, or having `/mold` write a mini-spec, with no user interaction; **tier 2** (borderline) autonomously invokes `/culture` and/or `/briesearch` to fill missing context, then re-runs the fast-path check; **tier 3** (still borderline) blocks on one targeted host-routed question and re-enters classification on the answer. `--safe` does not skip the tiers, it only gates the final dispatch. Full tier mechanics and the spec-discovery check: [`references/escalation.md`](references/escalation.md).

Non-implementation intents bypass the escalation entirely. Their target skills own their own internal escalation: `/pasteurize` has its Phase 1 feedback-loop check, `/briesearch` clarifies missing version/scope inline, `/age` and `/cure` work directly against the supplied diff or report.

## Rejected-directions check

Before dispatching any `mold` intent, scan `.cheese/.out-of-scope/` for rejection records whose `## Direction` section's one-line description substantially matches the incoming request. If a match is found:

1. Surface the previously-rejected direction and its rationale in one line.
2. Ask the user whether to proceed with the new request or take a different angle.
3. Do not suppress or re-propose the rejected direction silently.

This check is lightweight — a glob + keyword scan over `.cheese/.out-of-scope/*.md`. Skip silently when the directory does not exist. Non-`mold` intents skip this check.

## --continue

`/cheese --continue <slug-or-note-path>` is the manual fresh-context resumption path — use it after compacting the conversation, after `/cook`'s fan pathway halts, or whenever the user wants to drive the pipeline by hand from cleared context. Resolve the argument through `wheypoint.pyz resolve --ref <absolute-path | work-id | slug>` and dispatch only the validated authoritative current revision it returns, with its deterministic legacy-note fallback; never pick a note by modification time, session, or slug recency, and never commit or publish to Git to make a resume work. Ambiguity, unresolved lineage, integrity failures, and `status: gated:` stop automatic dispatch. Before dispatching anything on a `--continue` invocation, read the full resume flow — resolution, `mode:`/`next:` parsing, parallel-task dispatch, gated-status handling, and baseline treatment — in [`references/continue-resume.md`](references/continue-resume.md).

`--continue` does *not* propagate `--auto` — dispatch `/<next> <slug>` in its default interactive mode even with no `--safe`. The user can append `--auto` explicitly (`/cheese --continue <slug> --auto`) to opt back in.
The durable pipeline is `culture -> mold -> cut -> cook -> press -> age -> cure -> plate`. An approved `red-required` Mold handoff routes to `/cut` (or `/cut --auto` only when auto is explicit); a successful Cut handoff uses `next: cook` and carries its authoritative GateReceipt pointer in `artifact:`.
Continuation forwards that `artifact:` unchanged and preserves validated optional `mode:` plus in-scope `--hard`, `--open-pr`, and `--safe` flags. `--auto` remains opt-in and is never inferred. Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.

## Confidence and the clarify gate

Treat classification confidence qualitatively (`low | medium | high`). Threshold for direct routing is `medium` or better. Below that, route to tier 3 (`clarify`):

- Ask exactly one question through the host routing guide in [`references/handoff-gate.md`](references/handoff-gate.md).
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer.

At `medium` or above, dispatch directly. For implementation intents, the cook-fast-path clarity check adds a second layer (see `## Escalation`).

## Preferred tools and fallbacks

When the input is a path or slug, call the selected source-code read or search backend directly according to [`references/code-intelligence-routing.md`](references/code-intelligence-routing.md).

Beyond source-code routing there are router-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming routing target with the user (only under `--safe` or `clarify`) | host-routed structured question per [`references/handoff-gate.md`](references/handoff-gate.md) | a numbered list with explicit dispatch commands |

`/cheese` keeps tool use light. Beyond the single wiki-grounding probe in `## Flow`, treat anything heavier than a single-file read or one search call as a sign the work belongs in the downstream skill, not in the router.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the chosen skill, e.g. `Target: /cook .cheese/specs/foo.md`.
4. **Wiki hits** — when `handoff_context.wiki_hits` is non-empty, one line per hit: `wiki: <page>:<line> — <why>` — always rendered before dispatch so the user sees what memory informed the routing and can challenge stale hits. Omit the section when hallouminate is absent.

Then dispatch in the same turn (or, under `--safe`, via the handoff gate). If `clarify` is chosen, replace the dispatch with the single clarifying question.

## Handoff

Without `--safe`, cheese propagates `--auto` to any target that supports it. Under `--safe`, dispatch waits for the user's selection via the handoff gate; the auto variant stays the pre-selected recommended target.

Default targets per intent:

- **clarify** — single targeted question; no skills run until the answer arrives.
- **research** — `/briesearch` (recommended). No auto variant.
- **rubber-duck** — `/culture` (recommended). Only reached when the user explicitly opted out of writes. No auto variant.
- **mold** — `/mold` (recommended). Safe-mode alternative: `/briesearch first` when external evidence is missing.
- **cook** — default: `/cook --auto <slug-or-path>`. Safe-mode alternatives: `/cook <slug-or-path>` (no auto), `/mold first` if scope is borderline. A high-blast-radius or decomposable spec triggers cook's own fan pathway automatically — no separate dispatch needed.
- **ultracook (retired)** — `/ultracook <slug-or-path>` resolves to `/cook <slug-or-path>`, carrying forward `--open-pr`/`--resume`/`--auto`.
- **plate** — `/plate` for commit-only work, ordinary PR publication, or stack publication/maintenance. New PRs infer an obviously cohesive single, recommend and ask for reviewable ordered stacks, and ask when shape is ambiguous; explicit choices win.
- **debug** — default: `/pasteurize --auto <input>`. Safe-mode alternatives: `/pasteurize <input>` (no auto), `/culture` only when the user explicitly wants no-write diagnosis.
- **age** — `/age <ref>` (recommended). Safe-mode alternative: `/age --scope <path>` when the user named a path glob.
- **age-then-cure** — `/age <slug>` (recommended). Safe-mode alternative: `/cure <slug>` when a fresh report already exists.

Pre-select only the highest-confidence target. Without `--safe`, surface the target as a decision, not a question — dispatch the recommended option directly. With `--safe`, dispatch waits for the user's selection; the captured dispatch packet runs immediately on a non-stop choice.

## Rules

- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.
- A declined question gate is an answer. Do not re-raise it; state the open item as one line and wait for freeform input.

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`references/handoff-gate.md`](references/handoff-gate.md) — cross-harness post-selection dispatch contract (shared across workflow skills).
- `references/escalation.md` — full escalation-tier mechanics and the spec-discovery check.
- `references/continue-resume.md` — the `--continue` resume flow.
