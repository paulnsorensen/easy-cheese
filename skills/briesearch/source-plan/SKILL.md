---
name: source-plan
description: Choose sources, preferred tools, and fallbacks before searching.
license: MIT
---

# /briesearch/source-plan

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Choose sources, preferred tools, and fallbacks before searching.

## Inputs

The user prompt plus any assumptions carried forward from earlier briesearch sub-skills.

## Instructions

1. Map each needed evidence type to a preferred tool and fallback.
2. State unavailable sources before collecting evidence.
3. Limit planned sources to those needed for the answer.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Current web facts | Tavily | generic web search or user-provided sources |
| Library/API docs | Context7 | repo docs, package docs, vendor pages |
| GitHub examples | `gh` or GitHub integration | web search scoped to GitHub, or skip with confidence note |
| Local patterns | Serena or LSP, `sg`, tilth | `ripgrep`, `find`, targeted reads |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

A concise research note, evidence bullets, confidence, and next step.

## Rules

- Cite or name evidence sources.
- Mark claims as unverified when evidence is weak.
