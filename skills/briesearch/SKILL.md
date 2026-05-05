---
name: briesearch
description: This skill should be used whenever the user asks to research, look up, compare, or investigate something external to the immediate codebase — phrases like "research X", "look up the API for Y", "compare libraries", "what does the doc say about Z", "find examples of how to do W", "is this library maintained", or "before I implement, what's the right approach". Routes the question across library docs (Context7), web research (Tavily), local code patterns (cheez-search), and GitHub examples (gh), then synthesizes with explicit confidence. Use even when the user only mentions a library name without saying "research" — when in doubt, briesearch first so the spec or implementation is informed, not speculative.
license: MIT
---

# /briesearch

Use this skill when a technical question needs evidence before a decision: library behavior, current vendor docs, implementation patterns, or local precedent.

Do not use it for a single obvious file lookup or when the user already supplied enough evidence.

## Inputs

Accept the whole user prompt as the research question. If version, framework, repo scope, or decision criteria are missing and matter, ask one clarifying question; otherwise proceed with stated assumptions.

## Flow

1. Classify the question: library docs, current web facts, codebase pattern, GitHub example, comparison, or best practice.
2. State the source plan briefly, including unavailable sources and their fallbacks.
3. Gather only enough evidence to answer confidently.
4. Synthesize the answer with source notes and a confidence level.
5. Stop after research; do not implement the result unless the user separately asks.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Library/API docs | Context7 | package docs in the repo, README examples, then web search |
| Current web/vendor facts | Tavily | generic web search or cited vendor pages supplied by the user |
| Local code patterns | Serena or LSP, `sg` | `ripgrep`, `find`, targeted file reads |
| GitHub examples | `gh` or GitHub integration | web search scoped to GitHub, or skip with a confidence note |
| Structured JSON output | `jq` | careful manual inspection |

If a preferred tool is missing, say so once and continue with the fallback. Missing optional tools should lower confidence, not block the skill.

## Output

```markdown
## Research: <question>

### Answer
<concise synthesis>

### Evidence
- <source or file ref>: <finding>

### Confidence
<low|medium|high> — <why>

### Next step
<recommended skill or action, if any>
```

## Rules

- Commit to a source plan before collecting evidence.
- Do not pretend an unavailable source was checked.
- Prefer primary docs over blogs when both are available.
- Keep raw notes out of the response unless the user asks for them.
