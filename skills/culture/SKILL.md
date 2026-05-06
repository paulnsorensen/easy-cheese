---
name: culture
description: This skill should be used when the user wants to think out loud, rubber-duck a design, walk through trade-offs, or explore an ambiguous problem WITHOUT producing files, code, or specs — phrases like "let's talk through X", "rubber duck this with me", "I'm trying to decide between A and B", "help me think about Y", "what would happen if we…", "/culture". Hard invariant — culture never writes to production files, never commits, never opens PRs. Output is conversation, not artifacts. Use when the user wants shared mental model first; if the dialogue reveals real work to do, recommend `/mold` (fuzzy → spec) or `/cook` (clear ask → code) and stop. Before `/mold` or `/cook`.
license: MIT
---

# /culture

Use this skill for free-form technical thinking when the desired output is shared understanding, not files, commits, specs, or PRs.

Do not use it when the user wants a written spec (`/mold`), implementation (`/cook`), review (`/age`), or external evidence gathering (`/briesearch`).

## Hard invariant

`/culture` does not write production files, commit changes, open PRs, or mutate project state. If the conversation reveals that something should be built or written, stop and recommend the next skill.

## Flow

1. Restate the question or tension in one sentence.
2. Identify assumptions, constraints, and decision criteria.
3. Explore trade-offs and likely blast radius.
4. Use evidence only when it helps the conversation; avoid deep research unless the user asks.
5. End with a compact summary, open questions, and a `## Handoff` prompt (see below).

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Quick code orientation | code-review-graph via cheez-search, Serena or LSP, `sg` | `ripgrep`, file tree, targeted reads only after MCP/semantic paths cannot answer |
| Visualizing diffs or examples | `delta` | plain `git diff` |
| External sanity check | `/briesearch` | clearly mark as an assumption |

Missing optional tools should not interrupt the conversation. Keep tool use light; this is a thinking session.

## Output

Return a short conversational summary:

- Current understanding
- Trade-offs or options
- Open questions

## Handoff

When the conversation reveals real work, ask via `AskUserQuestion` which downstream to run. Default options (pick at most two of these plus a stop):

- **Run /mold** *(recommended when the idea is still fuzzy)* — converge on a spec.
- **Run /cook** *(recommended when the ask is clear and unambiguous)* — implement directly.
- **Pause** — keep the dialogue in head; no further action.

`/briesearch` is offered only when the conversation hit a factual gap that external docs could close. `/age` is never the next step from culture — review needs a diff to look at.

## Rules

- No writes, no commits, no PRs.
- Ask one useful question at a time when the user is exploring.
- Prefer clarity over completeness.
