---
name: cheese
description: >-
  Route an idea, path, pull request, issue, failure, question, or bare `/cheese` to the correct workflow skill.
  Use this skill for `/cheese`, routing requests, help requests, or opening messages without a named workflow skill.
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
- `--open-pr` — propagate through the implementation chain to `/cure`.
  `/cure` consumes this flag and sends the publication intent to terminal `/plate`.
  `/plate` accepts no `--open-pr` flag of its own.
  A new PR follows `/plate`'s explicit choice and review shape policy.
- `--continue <slug-or-note-path>` — resume an in-flight pipeline from a handoff slug or note.
- `--hard` — propagate to `/plate`, which runs the final artifact-writing gate before `/hard-cheese` and publication.
- `--reground` — use with `--continue` only. Adversarially re-check the handoff claims before phase dispatch.

If `$ARGUMENTS` is missing, ask one clarifying question through the host routing guide.
Use [`references/handoff-gate.md`](references/handoff-gate.md).

## Flow

0. **Read the full user message, not just `$ARGUMENTS`.** Treat all other user prose as a directive list.
   Follow live directives instead of conflicting defaults or the handoff protocol.
   The handoff file restores state.
   The user's live message overrides it.
   **Exception: a live directive never waives a resume integrity gate.**
   Ambiguity, unresolved lineage, an integrity finding, and `status: gated:` still stop dispatch.
   A live directive answers only the informed trust gate for a clean legacy result.
   [`references/continue-resume.md`](references/continue-resume.md) owns these gates.
1. **Think first (silent).** Model the problem internally per `skills/culture/SKILL.md` — restate the ask, list candidate targets, name the deciding signal. Output is the classification that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (handled by the tier-3 escalation in step 4).
3. **Clarity check (`cook` intents only).** Run Cook's fast-path check for a `cook` intent.
   Dispatch a `mold` intent to `/mold`'s user mode instead.
   Direct `plate` intents bypass this check.
4. **Escalate when needed.** Tier 1 dispatches the chosen target.
   It uses `/mold`'s agent mode when `/cook --auto` needs a specification.
   Tier 2 invokes `/culture` or `/briesearch` internally, then repeats the clarity check.
   Tier 3 blocks on a single targeted host-routed question.
   Classify the answer again.
   See `## Escalation`.
5. **Ground the wiki when hallouminate is present and the route is escalated.** Derive a query from the input.
   Skip this step on the fast path.
   A fast route grounds nothing and spends no probe.
   Make at most one grounding call against the wiki corpus.
   Resolve the corpus through the corpus listing tool first.
   Resolve both tool names through [`references/optional-plugins.md`](references/optional-plugins.md).
   That reference matches the capability, because each host prefixes the names differently.
   Use the probe shape in `skills/mold/references/grounding.md`.
   Add the best hits to `handoff_context.wiki_hits` as `[{page, line, why}]`.
   See [`references/handoff-gate.md`](references/handoff-gate.md) section Context payloads.
   When no wiki corpus exists, use [`references/optional-plugins.md`](references/optional-plugins.md).
6. **Announce** — print a short block (Intent / Reason / Target, plus wiki hits when present) per the format in `## Output`. Cite the signal that drove the routing decision.
7. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` (tier 3) or `research`.
8. **Dispatch.** Without `--safe`, run the chosen skill and its context packet after the announcement.
   With `--safe`, issue a handoff gate from [`references/handoff-gate.md`](references/handoff-gate.md).
   Pre-select the recommended target, include an alternative, and put `Stop` last.
   Wait for the user's selection before dispatch.

`/cheese` is a router, not a worker.
It never edits files, runs tests, or opens pull requests.
Use only the host's read, search, and dispatch capabilities.
Tier 1 can invoke `/mold`'s agent mode, and that write stays inside `/mold`'s scope.

See [`references/harness-portability.md`](references/harness-portability.md) for helper resolution, agent dispatch, GitHub operations, and handoff transitions.
Prefer bundled or repository helpers.
Do not use `${CLAUDE_SKILL_DIR}` in invocation paths.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Intent shapes

The full classification table — including all intent shapes, signals, disambiguation rules, and edge cases — lives in `references/classification.md`.

## Escalation

Only a `cook` intent runs Cook's fast-path check and the three escalation tiers.
Dispatch a `mold` intent to `/mold`'s user mode.
`--safe` gates only the final dispatch.
[`references/escalation.md`](references/escalation.md) owns the tier rules and the specification discovery check.

Every other intent bypasses this escalation.
Its target skill owns its own escalation.

## Rejected-directions check

Before each `mold` dispatch, scan `.cheese/.out-of-scope/*.md` for a matching rejection record.
Compare the incoming request with the record's `## Direction` line.
On a match, surface the rejected direction and its rationale in one line.
Then ask the user whether to proceed or take a different angle.
Never suppress or re-propose a rejected direction silently.
Skip this check silently when the directory is absent or the intent is not `mold`.

## --continue

Use `/cheese --continue <slug-or-note-path>` to resume manually from a fresh context.
Use it after conversation compaction, a stopped `/cook` fan pathway, or a manual resume request.
Resolve the argument through `/wheypoint resolve --ref <absolute-path | work-id | slug>`.
Dispatch only the validated authoritative current revision.
The runtime provides the deterministic legacy-note fallback.
Never select a note by modification time, session, or slug recency.
Never commit or publish to Git to make a resume work.
Ambiguity, unresolved lineage, integrity failures, and `status: gated:` stop automatic dispatch.
Read [`references/continue-resume.md`](references/continue-resume.md) before dispatch.
For a `next:` list, parse the required `order:` through the same reference.

`--continue` does not propagate `--auto`.
Dispatch `/<next> <slug>` in its default interactive mode, even without `--safe`.
The user can append `--auto` explicitly, as in `/cheese --continue <slug> --auto`.
The durable pipeline is `culture -> mold -> cook -> press -> age -> cure -> plate`.
An approved Mold handoff routes to `/cook`.
It routes to `/cook --auto` only when the user makes auto explicit.
It carries its durable specification pointer in the typed `spec_ref` field.
Continuation forwards `spec_ref` unchanged.
It also forwards `artifact:` unchanged, which always names the prior consumed report.
Continuation preserves the validated optional `mode:` value.
It preserves the in-scope `--hard`, `--open-pr`, and `--safe` flags.
`--auto` remains opt-in and is never inferred.
Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.

## Confidence and the clarify gate

Confidence is `low | medium | high`. Route directly at `medium` or better.
Below that, route to tier 3 (`clarify`):

- Ask exactly one question through the host routing guide in [`references/handoff-gate.md`](references/handoff-gate.md).
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer.

At `medium` or above, dispatch directly.
For a `cook` intent, the Cook fast-path clarity check adds a second layer.
See `## Escalation`.

## Preferred tools and fallbacks

When the input is a path or a slug, call the selected source-code backend directly.
[`references/code-intelligence-routing.md`](references/code-intelligence-routing.md) selects that read or search backend.

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming the routing target with the user, under `--safe` or `clarify` only | a host-routed structured question per [`references/handoff-gate.md`](references/handoff-gate.md) | a numbered list with explicit dispatch commands |

One evidence probe is one file read, one search call, one `gh` call, or the wiki-grounding probe in `## Flow`.
The router spends at most three probes.
The fast path spends zero probes.
If the router needs more probes, escalate to `/culture` or `/briesearch` in internal mode.
See [`references/routing-receipt.md`](references/routing-receipt.md) for the budget, fast path, and receipt fields.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the chosen skill, e.g. `Target: /cook .cheese/specs/foo.md`.
4. **Wiki hits** — Emit one line for each `handoff_context.wiki_hits` entry.
   Use `wiki: <page>:<line> — <why>`.
   Put these lines before the receipt.
   This order lets the user identify stale wiki information.
   Omit these lines when hallouminate is absent.
5. **Routing receipt** — The last line before dispatch, always emitted, is:

   ```text
   route: intent=<intent> target=<skill> path=<fast|escalated> probes=<n>
   ```

   This line is the terminal routing boundary. Never put a duration or a timestamp in it. The host timestamps the line. See [`references/routing-receipt.md`](references/routing-receipt.md) for all fields and rules.

Then dispatch in the same turn.
Under `--safe`, use the handoff gate.
For `clarify`, replace the dispatch with the single clarifying question.
The receipt still prints, with `target=clarify` and the actual probe count.

## Handoff

Without `--safe`, propagate `--auto` only along documented autonomous chains.
For `--continue`, forward it only when the handoff contains it or the user appends it.
Forward `--open-pr` only when the user supplied it.
Never add `--open-pr` to a dispatch that the user did not authorize.
Forward `--hard` on every route that accepts it, including the retired `/ultracook` redirect.
Under `--safe`, dispatch waits for the user's gate selection.
The auto variant stays the pre-selected recommended target.

Default targets per intent:

- **clarify** — single targeted question; no skills run until the answer arrives.
- **research** — `/briesearch` (recommended). No auto variant.
- **rubber-duck** — `/culture` (recommended). Only reached when the user explicitly opted out of writes. No auto variant.
- **mold** — `/mold` (recommended). Safe-mode alternative: `/briesearch first` when external evidence is missing.
- **cook** — default: `/cook --auto <slug-or-path>`.
  Safe-mode alternatives are `/cook <slug-or-path>` and `/mold first`.
  Use `/mold first` when scope is borderline.
  A large or decomposable specification starts cook's fan pathway automatically.
- **ultracook (retired)** — `/ultracook <slug-or-path>` resolves to `/cook <slug-or-path>`, carrying forward `--open-pr`/`--resume`/`--auto`/`--hard`.
- **plate** — `/plate` handles commits, ordinary pull requests, and pull request stacks.
  New pull requests infer an obviously cohesive single change.
  They recommend reviewable ordered stacks.
  `/plate` asks before mutation when it recommends a stack.
  `/plate` also asks before mutation when the shape is ambiguous.
  Explicit choices win.
- **debug** — default: `/pasteurize --auto <input>`. Safe-mode alternatives: `/pasteurize <input>` (no auto), `/culture` only when the user explicitly wants no-write diagnosis.
- **affinage** — `/affinage <pr>` (recommended).
  Use bare `/affinage` when the input names no pull request.
  Send `--auto` only with an explicit `--stake <floor>` value.
  Safe-mode alternative: `/age <pr>` when the user wants a fresh review instead.
- **age** — `/age <ref>` (recommended). Safe-mode alternative: `/age --scope <path>` when the user named a path glob.
- **age-then-cure** — `/age <slug>` (recommended). Safe-mode alternative: `/cure <slug>` when a fresh report already exists.

Pre-select only the highest-confidence target.
Without `--safe`, show the target as a decision and dispatch it directly.
With `--safe`, wait for the user's selection.
Run the captured dispatch packet immediately after a non-stop choice.

## Rules

- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.
- A declined question gate is an answer. Do not re-raise it; state the open item as one line and wait for freeform input.

## Baseline-aware routing

Treat each recorded `baseline:` block as settled state. Do not re-ask about identical failures.

See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`references/handoff-gate.md`](references/handoff-gate.md) — cross-harness post-selection dispatch contract (shared across workflow skills).
- [`references/handback-contract.md`](references/handback-contract.md) — the one preamble, status vocabulary, and dispatch/handback boundary inventory every phase speaks.
- `references/escalation.md` — full escalation-tier mechanics and the spec-discovery check.
- `references/continue-resume.md` — the `--continue` resume flow and the `--reground` re-check.
- `references/routing-receipt.md` — the terminal routing receipt, the probe budget, and the fast path.
