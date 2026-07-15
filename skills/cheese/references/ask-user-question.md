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

The record is the source of truth. A host rendering may change presentation, but it must preserve the prompt, recommended choice, every option's effect or tradeoff, selection mode, and a free-form `Other` path.

## Capability-first rendering

Use the richest callable structured question primitive that can faithfully
encode the complete decision. Discover callability and the active primitive's
advertised question and option capacities at runtime instead of assuming a
harness-wide limit. Never name a host tool in the transcript unless it is
callable in that session.

Wrapper and orchestrator hosts such as Conductor and Emdash / Em Dash route to
the selected underlying agent or provider rather than inventing a common
question schema. Runtime capability detection always wins over the wrapper or provider name. If the expected provider primitive is absent, denied, headless,
or too small for the complete decision, use the lossless fallback.

| Harness | Prefer | Notes |
| --- | --- | --- |
| Claude Code | `AskUserQuestion` | Supports `questions[]` with `question`, short `header`, `options[]`, and optional `multiSelect`; hooks can fill `answers` via `updatedInput`. Source: [Claude Code hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks#askuserquestion). |
| Codex / OpenAI app-server | `request_user_input` / `tool/requestUserInput` when exposed and lossless | In Codex CLI, use `request_user_input` only when the active tool list and current collaboration mode both allow it **and the full question fits the capacities advertised by that callable primitive**. If an active schema advertises only 2-3 explicit choices, a four-option decision does not fit: render every option with the numbered fallback, or use a lossless hybrid where every omitted button remains an explicit numbered choice. Never merge or drop options to make the tool call fit. Source: [Codex app-server reference](https://developers.openai.com/codex/app-server). |
| Conductor | Underlying agent primitive | Conductor runs Claude Code or Codex sessions; route to the selected underlying agent's currently callable question primitive. Conductor Plan Mode exists for both, but Conductor is not a separate question API. Source: [Conductor agent modes](https://conductor.build/docs/concepts/agent-modes). |
| OpenCode | `question` tool | The built-in `question` tool asks during execution with header, question text, options, and custom answers; ensure `permission.question` is not denied. Source: [OpenCode tools](https://opencode.ai/docs/tools#question). |
| Pi | Visibly loaded extension question tool | Pi has no built-in model-callable question tool. Use a visibly loaded and callable extension tool only when its UI is available (`ctx.hasUI`); a Markdown skill cannot call `ctx.ui` directly. JSON/print or another headless mode must use numbered text. Sources: [Pi extensions](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md), [question extension example](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/examples/extensions/question.ts). |
| OMP / Oh My Pi | `ask` interactive-only built-in | Each `questions[]` item carries `id`, `question`, and `options[]`, with optional `header`, `multi`, and zero-based `recommended`; `Other` is automatic. Use it only when callable in an interactive session and the complete question fits. Do not use a timeout that can auto-select a blocking approval or state-changing choice. Sources: [OMP ask reference](https://github.com/can1357/oh-my-pi/blob/main/docs/tools/ask.md), [OMP ask schema](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/src/tools/ask.ts). |
| Emdash / Em Dash | Selected provider primitive | Emdash runs provider CLIs through PTY and can host ACP providers; it does not define one universal question API. Route through the selected provider's advertised primitive when callable and lossless, otherwise use numbered text. Sources: [Emdash docs](https://emdash.ai/docs), [provider integrations](https://github.com/generalaction/emdash/blob/main/agents/integrations/providers.md). |
| GitHub Copilot CLI | `ask_user` tool | Copilot CLI lists `ask_user` as "Ask the user a question" and `--no-ask-user` disables it. Use it when available; otherwise numbered text. Source: [Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference). |
| Gemini CLI | `ask_user` tool | Google codelab output lists `Ask User (ask_user)` in `/tools`; use it when present. Source: [Gemini CLI codelab](https://codelabs.developers.google.com/gemini-cli-hands-on). |
| Cursor CLI / ACP | `cursor/ask_question` when exposed | Cursor ACP documents `cursor/ask_question` as a blocking extension method; use it only inside hosts that expose that ACP method. Source: [Cursor ACP docs](https://cursor.com/docs/cli/acp#cursor-extension-methods). |
| Windsurf Cascade | Plan-mode interactive questions when in Plan Mode | Cascade Plan Mode can ask clarifying questions and present multiple options with an interactive interface. Outside that mode, use numbered text unless a host tool is exposed. Source: [Cascade modes](https://docs.windsurf.com/windsurf/cascade/modes). |
| MCP server flows | `elicitation/create` | Use only when an MCP server is requesting user input through a client that supports elicitation. It is not a general assistant-to-user question primitive. Source: [MCP elicitation](https://modelcontextprotocol.io/specification/latest/client/elicitation). |
| Aider and unknown harnesses | Numbered text | If no structured primitive is visible, ask a plain numbered question and wait for the next user reply. |

This is native-first, not lowest-common-denominator behavior. Never merge, hide, or drop options to fit a host primitive.

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
