# Handoff gate

Use this reference whenever a workflow skill asks the user to choose the next step after a gate.

## Contract

A handoff gate prevents silent dispatch. It does not mean the agent stops after the user selects an option. Once the user chooses a non-stop option, the current assistant turn immediately starts the selected action — either dispatching a downstream skill (skill transition) or continuing internal work in the current skill (in-skill continuation).

"Never auto-invoke" means no downstream skill starts before an explicit user selection. It is not permission to answer only with "next: /some-skill" after the user has already selected that option.

## Vocabulary

- **Dispatch** — start a *new* skill with a concrete command. Reserved for skill transitions.
- **Continue / proceed** — keep working inside the *current* skill (e.g. write a manifest, ask one targeted follow-up, re-run an internal phase). Never write `dispatch:` for in-skill continuation; use `continue:` instead.
- **Stop / pause** — return a final status with no further action.

## Gate shape

Before asking, render each option as a structured record. The host UI may show this as buttons, a structured question, or a numbered list, but the semantics must be stable. The top-level key is `handoff_gate:` to distinguish it from per-option context payloads (`handoff_context:` — see below):

```yaml
handoff_gate:
  source_skill: /<current-skill>
  recommended: <label-or-none>
  options:
    - label: Run /press <slug>
      dispatch: /press <slug>
      context:
        slug: <slug>
        source_report: .cheese/cook/<slug>.md
        flags: []
    - label: Modify decomposition
      continue: ask-for-decomposition-change
      context:
        scope: current-skill
    - label: Stop
      dispatch: none
      context:
        reason: leave pipeline paused
```

Every option must include:

- **Label** — the user-facing choice.
- Exactly one of:
  - **Dispatch** — the exact command for a skill transition (`/press <slug>`, `/age <slug> --hard`, …), including slug/path/scope and propagated flags such as `--hard`.
  - **Continue** — a short identifier for an in-skill action the current skill knows how to execute (e.g. `ask-for-decomposition-change`, `re-run-decomposer`, `write-manifest-then-seed`).
  - `dispatch: none` — terminal options (Stop, Pause, Compact) that return a final status and do not start another skill.
- **Context** — any prose or structured payload the action needs but that is not part of the command line.
- **On select** — execute the dispatch or continue action immediately after the user selects it.

`dispatch: none` is for *terminal* options only. Options that keep the current skill running must use `continue:`, not `dispatch: none`, so the gate reader can tell "stop" apart from "do something else in this skill".

## Host routing guide

The `handoff_gate:` block is the semantic source of truth. After building it,
choose the richest question mechanism the current harness actually exposes;
never name a host tool in the transcript unless it is callable in that session.

| Harness | Prefer | Notes |
| --- | --- | --- |
| Claude Code | `AskUserQuestion` | Supports `questions[]` with `question`, short `header`, `options[]`, and optional `multiSelect`; hooks can fill `answers` via `updatedInput`. Source: [Claude Code hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks#askuserquestion). |
| Codex / OpenAI app-server | `request_user_input` / `tool/requestUserInput` when exposed | OpenAI's app server documents `tool/requestUserInput` for 1-3 short questions and free-form `isOther` options. In Codex CLI, use `request_user_input` only when the active tool list and current collaboration mode both allow it; otherwise fall back to numbered text. Source: [Codex app-server reference](https://developers.openai.com/codex/app-server). |
| Conductor | Underlying agent primitive | Conductor runs Claude Code or Codex sessions; route to that agent's question primitive. Conductor Plan Mode exists for both, but Conductor is not a separate question API. Source: [Conductor agent modes](https://conductor.build/docs/concepts/agent-modes). |
| OpenCode | `question` tool | The built-in `question` tool asks during execution with header, question text, options, and custom answers; ensure `permission.question` is not denied. Source: [OpenCode tools](https://opencode.ai/docs/tools#question). |
| GitHub Copilot CLI | `ask_user` tool | Copilot CLI lists `ask_user` as "Ask the user a question" and `--no-ask-user` disables it. Use it when available; otherwise numbered text. Source: [Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference). |
| Gemini CLI | `ask_user` tool | Google codelab output lists `Ask User (ask_user)` in `/tools`; use it when present. Source: [Gemini CLI codelab](https://codelabs.developers.google.com/gemini-cli-hands-on). |
| Cursor CLI / ACP | `cursor/ask_question` when exposed | Cursor ACP documents `cursor/ask_question` as a blocking extension method; use it only inside hosts that expose that ACP method. Source: [Cursor ACP docs](https://cursor.com/docs/cli/acp#cursor-extension-methods). |
| Windsurf Cascade | Plan-mode interactive questions when in Plan Mode | Cascade Plan Mode can ask clarifying questions and present multiple options with an interactive interface. Outside that mode, fall back to numbered text unless a host tool is exposed. Source: [Cascade modes](https://docs.windsurf.com/windsurf/cascade/modes). |
| MCP server flows | `elicitation/create` | Use only when an MCP server is requesting user input through a client that supports elicitation. It is not a general assistant-to-user question primitive. Source: [MCP elicitation](https://modelcontextprotocol.io/specification/latest/client/elicitation). |
| Aider and unknown harnesses | Numbered text | If no structured primitive is visible, ask a plain numbered question and wait for the next user reply. |

### Portable fallback format

```markdown
Question: <one short question>
Recommended: <label> — <why>

1. <label> — <effect/tradeoff>
2. <label> — <effect/tradeoff>
3. <label> — <effect/tradeoff>
Other: reply with `other: <short answer>`
```

Use the option label from `handoff_gate.recommended`; do not assume the
recommended option is numbered `1` unless you deliberately rendered that label
as option 1 in this fallback.

Keep gates small: one decision by default, at most three questions when the
host primitive explicitly supports batching. Include a free-form `Other` path
when the host supports it; otherwise spell out the `other:` fallback in text.

## After the answer arrives

1. Normalize the answer to one option label or recognized free-text verb.
2. If the answer is ambiguous, ask one clarifying question; do not guess.
3. If the selected option has `dispatch: none`, stop with the relevant artifact path or pause status.
4. If the selected option has a `continue:` identifier, execute that in-skill action immediately.
5. If the selected option has a `dispatch:` command, immediately enter that skill with the exact command and context packet.
6. Do not re-run `/cheese` classification unless the selected option explicitly says to do so.

## Context payloads

Use context payloads when command-line flags would create an unstable mini-language. Payloads ride alongside the gate under the key `handoff_context:` so the downstream skill can tell them apart from the gate shape itself:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5"
  resolved_ids: [1, 3, 5]
```

Examples of when to attach a `handoff_context:` block:

- `/age -> /cure` selection ids travel as context, not as a `--select` flag.
- `/culture -> /cook` carries the compact contract that emerged from discussion.
- `/melt -> upstream skill` carries the interrupted operation and original skill invocation.

Keep payloads short and factual. If a payload would exceed a compact screenful, write or reference a `.cheese/.../<slug>.md` handoff artifact and pass the path instead.

## Flag propagation

Propagate `--hard` through every runnable downstream option while the flag is in scope. Propagate `--auto` inside documented auto-mode chains and inside `/cheese`'s autonomous-by-default dispatch path (see `skills/cheese/SKILL.md` § Escalation — tier-1 and tier-2 dispatches pre-select the auto variant and run it without a gate unless `--safe` is set).

Propagate `--safe` and `--open-pr` through every runnable downstream option while in scope. `--safe` re-introduces the gates that the autonomous default skips — the `/age` / `/affinage` cure-selection and `/cure`'s PR push. It only has meaning for skills that *have* such a gate to re-introduce: `/age`, `/affinage`, and `/cure`. It does **not** turn a `--auto` chain interactive (the two flags are opposites) — `/cook --auto` and `/press --auto` have no selection or push gate of their own, so they neither declare nor forward `--safe`; a `/cheese --safe` route that dispatches a `--auto` variant gates only `/cheese`'s own dispatch decision, then runs the chain headless. `--open-pr` rides all the way to the terminal `/cure`, authorizing a clean cure to open a *new* PR when none exists (the default only pushes an already-open one); inside the `--auto` chain it is threaded through each invocation (`/cook → /press → /age → /cure`).

Outside those autonomous paths, interactive gates must not add `--auto` unless the option explicitly says `--auto` and the user selected it. Inside them, the auto variant is the pre-selected recommended target by design — `--safe` is the user's opt-out to a gated flow, where the auto variant remains pre-selected but dispatch waits for confirmation.

## Standard forward-step menu

The forward command and its label vary per gate. Simple gates share one four-option shape — a forward step plus the standard tail (**Ship it**, **Checkpoint & stop**, **Stop**); gates with a richer *core* decision render that decision's options first, then append the same tail (see below):

- **\<forward verb\>** *(recommended)* — the plain forward command: one phase, interactive downstream (e.g. `/press <slug>`).
- **Ship it** — the forward command plus `--auto --open-pr`: run the rest of the pipeline headless and open (or push) the PR at the terminal cure (e.g. `/press <slug> --auto --open-pr`).
- **Checkpoint & stop** — `/wheypoint`: write a resumable handoff slug and pause, so a fresh context can resume via `/cheese --continue <slug>`.
- **Stop** — dispatch none; leave the pipeline paused with no checkpoint.

Propagate any in-scope `--hard` onto both runnable options (vanilla and **Ship it**). The four-option cap is why **Ship it** bundles `--auto` and `--open-pr` rather than offering them separately — `--open-pr` only acts at the terminal cure, so a standalone open-pr option at an upstream gate would not do anything until the chain reaches cure; it rides the headless chain instead.

When a gate carries a richer *core* decision (e.g. `/age`'s finding selection, or `/cure`'s push-vs-re-review), render that decision's options first, then append **Ship it**, **Checkpoint & stop**, and **Stop** as the standard tail. A gate-specific alternative that does not fit the four buttons (e.g. cook's "skip press, review now") stays as prose plus the free-form `Other` path rather than displacing a standard option.
