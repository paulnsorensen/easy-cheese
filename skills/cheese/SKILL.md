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
- `--continue [<legacy-note-path>]` — resume from the deterministic WorkRecord candidate set; an explicit old note path is migrated before selection.
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

For `cook` and `mold` intents, `/cheese` runs cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md`) and escalates through three tiers:

**Tier 1 — clear (all three checks pass).** First run the `## Spec-discovery check` — if an existing spec in `.cheese/specs/` substantially matches the request, dispatch `/cook --auto` against it and skip the mini-spec write. Otherwise the agent invokes `/mold`'s agent-invoked mini-spec mode (see `skills/mold/SKILL.md` § Agent-invoked mini-spec mode) to write `.cheese/specs/<slug>.md`, then dispatches `/cook --auto <spec-path>` in the same turn as the announce, where `<spec-path>` is the explicit mini-spec path returned by `/mold`. Do not collapse that path to a bare `<slug>`. No user interaction. When the input already names a spec path under `.cheese/specs/`, skip both the discovery scan and the mini-spec write and dispatch `/cook --auto` against the existing path directly.

**Tier 2 — borderline (any check fails or is uncertain).** Agent autonomously invokes `/culture` (internal thinking) and/or `/briesearch` (internal research), in any order, to fill the missing context. After the internal pass, re-run the cook fast-path check on the refined understanding. If all three checks now pass, drop into tier 1 (the mini-spec records the culture / briesearch synthesis under `## Provenance`). Otherwise tier 3.

**Tier 3 — still borderline after tier 2.** Block on the human via a single targeted host-routed question whose answer closes the failing check. On the answer, re-enter classification with the augmented input. This is the only sanctioned user-facing prompt in the autonomous-by-default path; the `clarify` intent and the below-`medium`-confidence path both map here.

`--safe` does not skip the escalation logic — the tiers still run silently — but it inserts a handoff gate before the final dispatch in every tier. The recommended option stays auto-flavoured (`/cook --auto <spec-path>` etc., using the explicit mini-spec path); the non-auto variant is offered as the alternative.

Non-implementation intents bypass the escalation entirely. Their target skills own their own internal escalation: `/pasteurize` has its Phase 1 feedback-loop check, `/briesearch` clarifies missing version/scope inline, `/age` and `/cure` work directly against the supplied diff or report.

## Rejected-directions check

Before dispatching any `mold` intent, scan `.cheese/.out-of-scope/` for rejection records whose `## Direction` section's one-line description substantially matches the incoming request. If a match is found:

1. Surface the previously-rejected direction and its rationale in one line.
2. Ask the user whether to proceed with the new request or take a different angle.
3. Do not suppress or re-propose the rejected direction silently.

This check is lightweight — a glob + keyword scan over `.cheese/.out-of-scope/*.md`. Skip silently when the directory does not exist. Non-`mold` intents skip this check.

## Spec-discovery check

Before minting a new mini-spec for a tier-1 `cook` or `mold` dispatch, look for an existing spec that already covers the request. Specs land in the durable XDG corpus (`default_root_for_phase("specs")`), not repo-local, so probe there:

- **hallouminate present** — `ground` the candidate spec text against the `cheese-durable` corpus for a near-duplicate (semantic match across every project's durable specs). Detect-and-degrade per [`references/optional-plugins.md`](references/optional-plugins.md).
- **hallouminate absent** — fall back to `resolve_slug(candidate_slug, phase_hint="specs")` (the XDG-correct `difflib` resolver in `shared/scripts/paths.py`), and note the degrade once: name-based rather than semantic matching. This keeps slug-level dedup on the headless/cron path where hallouminate is routinely unavailable.

Act on the result, do not guess:

1. **One clear match (high confidence)** — surface the resolved spec path in one line and dispatch against it (`/cook --auto <resolved-spec-path>`) instead of writing a duplicate.
2. **Multiple plausible matches, or a weak best match** — under `--safe`, present the candidates in the handoff gate for the user to pick; without `--safe`, fall back to minting a fresh mini-spec rather than risk dispatching against the wrong spec.

Skip silently when no specs exist yet, and when the user already named a spec path (the path is authoritative).

## --continue

`/cheese --continue [<legacy-note-path>]` resumes through WorkRecord. It never chooses the newest artifact or treats a slug file as a second authority. The executable protocol lives in [`references/work-contract.md`](references/work-contract.md).

Flow:

0. **Read the full user message, not just the `--continue` argument.** Any accompanying prose is a directive list; execute or answer it before, and where it conflicts, instead of, the restored handoff protocol. The handoff file restores state; the user's live message overrides it.
1. **Import an explicit legacy note.** When a readable legacy path is supplied, run `python3 skills/cheese/scripts/cheese.pyz work migrate "<path>"`. Preserve skipped input and stop if migration reports no imported record. Never scan by modification time.
2. **Resolve candidates.** Run `python3 skills/cheese/scripts/cheese.pyz work continue`. For `action: continue`, select the sole worktree record. For `action: picker`, render every returned record in its existing deterministic order and wait for the user to select one; do not pick by revision, file time, or update order.
3. **Restore the record.** Read its curated context, decisions, parked items, open questions, and current attempt. If the attempt has a linked artifact, read that exact path and call `handoff-resolve` with the phases actually callable in this harness. Do not search for a same-slug artifact.
   Treat an inherited `payload.baseline` as settled state per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md): do not re-ask, re-flag, or re-halt failures identical to that record.
4. **Act on the resolver result.** `done` reports terminal state. `hold` restores orientation and waits. `tasks` exposes the persisted task directives and dispatches those tasks with their inherited work ID and required isolation. `unavailable` retains and reports the phase without blocking the record. `dispatch` invokes the returned phase with the inherited work ID. `halt` reports the reason and never auto-dispatches during ordinary routing; because this `--continue` invocation is explicit resume permission, dispatch its retained `next` only when that value is a locally available phase, otherwise report `hold`, `done`, or local unavailability as appropriate.
   - **When `status:` starts with `gated:`** in an imported legacy note, migration converts it to `status: halt` plus `next: hold` and preserves the proposed destination in provenance. If the accompanying message contains directives or already answers the gate, execute them and surface the gate as one line of plain text; do not raise the structured question. Otherwise, ask the user which direction: research / decide / build. First classify each open gate item as mechanical or design per [`references/ask-user-question.md`](references/ask-user-question.md) § When to structure: a mechanical item may go straight to that structured question, but a design item whose weighing was not already shown this session must not. Re-establish the weighing in prose first (both ends, code-grounded evidence, pushback invited), converge conversationally, then ask at most one structured confirm, and never bundle multiple design forks into one prompt.
   - **When `next:` is a list** in imported legacy input, accept it only through bounded migration to `next: tasks`; malformed or ambiguous lists remain skipped. Versioned handoffs never carry list-form `next`.
5. **Apply interaction flags.** Under `--safe`, gate a dispatch through [`references/handoff-gate.md`](references/handoff-gate.md). Otherwise execute the resolved phase. `--continue` does not propagate `--auto`; the user must append it explicitly.

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
- **cook** — default: `/cook --auto <slug-or-path>`. Safe-mode alternatives: `/cook <slug-or-path>` (no auto), `/mold first` if scope is borderline.
- **ultracook** — `/ultracook <slug-or-path>` (recommended for a high-blast or decomposable spec). The decomposer picks the mode: parallel curd fan-out when the spec decomposes into 2+ file-disjoint curds, else the linear 7-phase chain.
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

## Continuation contract

For a meaningful direct request, create or join the WorkRecord before routing. A dispatched nested phase inherits the work ID. On bare `--continue`, consider durable WorkRecords and explicit repo-local snapshots without sorting by modification time, revision recency, or update order: zero candidates opens the project picker, one resumes automatically, and two or more opens the worktree picker. A local snapshot is portable evidence, not a second writable authority.

Read the handoff envelope through the global transition registry. `done` reports terminal state and never constructs or dispatches a phase command. `hold` pauses without dispatch. `tasks` exposes its structured pending directives and is never a phase command. When a globally valid next phase is not installed locally, retain it and report it unavailable rather than rewriting it. Validate the registry through `python3 skills/cheese/scripts/cheese.pyz contract-registry validate`. If that runtime is absent, halt with exactly: `Cheese contract runtime is required; install easy-cheese's Cheese companion runtime`.
