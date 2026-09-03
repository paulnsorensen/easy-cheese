# Ask user question

Use this reference whenever a skill needs user input. It owns question transport;
workflow-specific records and consequences stay with the calling skill.

## Semantic question record

Build the decision before choosing a host tool:

```yaml
question:
  id: stable-id
  prompt: One short decision
  recommended: option-id
  multi: false
  options:
    - id: option-id
      label: Short label
      description: Effect or tradeoff
```

The record is the source of truth.
A host can change its presentation.
It must preserve the recommended choice and every option's effect or tradeoff.
It must also preserve selection mode and the free-form `Other` path.

**Self-containment (hard).** The rendered question must stand alone.
A user must understand the decision and each option from the visible widget.
Widgets can truncate `prompt` and hide text from other turns or thinking blocks.
Do not depend on separate or earlier framing.
Add the required context to `prompt` and each option description.
Alternatively, show that context immediately before the question call.
A picker without visible framing is a transport defect.

## When to structure

Answers *when* a decision may be a structured question; capability-first
rendering (above) governs *how* once that gate passes.

**Freshness rule.** A structured question may only confirm a trade-off
already discussed with the user this session. A structured question must
never introduce an undiscussed design option — anything undiscussed gets
prose weighing first, before any structured question.

**Mechanical fast-path.** A mechanical item is intelligible without
prior-session context — for example, a branch name or a yes/no dispatch. A
mechanical item may be asked as a direct structured question.

**Design definition.** A design item is one whose options need session
context to be intelligible — the tradeoffs cannot be judged without the
discussion behind them. An undiscussed design fork is by definition
non-fresh.

**One confirm, never bundled.** After prose convergence, ask at most one
structured confirm. Never bundle multiple design forks into one prompt.

## Capability-first rendering

Use the richest callable structured question primitive visible in your active tool list.
The primitive must encode the complete decision.
Otherwise, use the portable fallback.
Read the advertised question and option capacities from the active schema.
You must never consult a harness lookup table for a tool name.
Never name a host tool unless it is callable in that session.
Wrapper hosts route to the selected underlying agent or provider.
They do not create a common question schema.
Runtime capability detection always wins over the wrapper or provider name.
Use the lossless fallback when the provider tool is absent, denied, headless, or too small.

Caveats that capability detection alone cannot infer:

- **Capacity-limited schemas.** If an active schema has only 2-3 explicit choices, a four-option decision does not fit.
  Render every option with the numbered fallback.
  Alternatively, use a lossless hybrid that keeps each omitted button as an explicit numbered choice.
  Never merge or drop options to fit the tool.
- **Mode-gated tools.** Use a question tool only when the active tool list and
  current collaboration mode both allow it (Codex `request_user_input` is the
  known case).
- **Headless modes.** JSON/print or another non-interactive mode must use
  numbered text even when a question tool is nominally loaded.
- **Auto-select timeouts.** Do not use a timeout that can auto-select a
  blocking approval or state-changing choice (OMP `ask` exposes one).
- **MCP elicitation.** `elicitation/create` is only for an MCP server
  requesting user input through a client that supports elicitation; it is not
  a general assistant-to-user question primitive.

This is native-first, not lowest-common-denominator behavior. Never merge, hide, or drop options to fit a host primitive.

Per-harness tool names and doc citations are maintainer evidence, not runtime
instructions — they live in
[`ask-user-question-sources.md`](ask-user-question-sources.md). Do not read
that appendix to answer a question; the active tool list already shows what is
callable.

## Portable fallback

```markdown
Question: <one short question>
Recommended: <label> — <recommended option's description>

1. <label> — <effect/tradeoff>
2. <label> — <effect/tradeoff>
3. <label> — <effect/tradeoff>
4. <label> — <effect/tradeoff, when present>
... <continue until every question option is explicit>
Other: reply with `other: <short answer>`
```

A fallback must enumerate every option; its list is not capped at three. When
`question.recommended` names an option, render its label and description on the
`Recommended:` line; do not assume it is option 1. When
`question.recommended` is `none`, omit the `Recommended:` line.
A hybrid is lossless only when every action omitted from the structured control
remains an explicit, equally actionable numbered choice.

## Batching and defaults

- Ask one decision by default.
- Batch at most three related questions, and only when the callable primitive
  explicitly supports batching.
- Mark the recommended option; never select it merely because it is recommended.
- Never auto-resolve a blocking approval or state-changing choice.
- Use single-select unless the semantic record explicitly sets `multi: true`.

## Normalize the answer

1. Map a displayed 1-based ordinal to the corresponding option `id`. Otherwise,
   normalize an option `id`, an unambiguous option label, or a free-form
   `other:` value.
2. Preserve multiple selections only when `multi: true`.
3. If the answer is ambiguous, ask one clarifying question through this same
   transport; do not guess.
4. Return the normalized value to the calling skill. The caller owns what
   happens after selection.
