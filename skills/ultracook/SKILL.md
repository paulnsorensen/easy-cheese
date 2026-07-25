---
name: ultracook
description: Retired — /ultracook no longer exists as a standalone skill. Any /ultracook invocation resolves to /cook, which now owns the single implementation pathway (including the fan-out mechanics this skill used to run). Use /cook instead.
license: MIT
metadata: {dispatches-agents: false}
---

# /ultracook (retired)

`/ultracook` is retired as a top-level skill. Its mechanics — decompose, wave-fan curds, harvest, wire, post-merge review, plate — now live inside `/cook`'s single pathway, dispatched via `/cook --auto`, each phase still running as a fresh, isolated sub-agent context blind to the prior phase's reasoning. See [`../cook/SKILL.md`](../cook/SKILL.md)'s `## Fan pathway` section.

## Redirect

Any `/ultracook <spec> [flags]` invocation resolves to `/cook <spec> [flags]`. Carry `--open-pr`, `--resume <slug>`, and `--auto` forward verbatim — their semantics are unchanged, just hosted inside `/cook` now.

## What did not move

- `skills/ultracook/scripts/` and `skills/ultracook/references/` remain at their existing paths — nothing here vaporized. `/cook`'s fan-pathway prose points at these retained files by their current relative path (e.g. `../ultracook/scripts/ultracook.pyz`, `../ultracook/references/decomposer-prompt.md`) rather than duplicating or moving them.
- The manifest path stays `.cheese/ultracook/<slug>/manifest.yaml` for continuity — the identity of the skill that reads/writes it changed, not the path.
- `src/fanout/mode.py` and `src/fanout/curd_block.py` remain decomposer/fanout internals — `/cook`'s fan pathway calls them directly rather than through this retired skill.

If you are here because muscle memory typed `/ultracook`, run `/cook` with the same arguments.
