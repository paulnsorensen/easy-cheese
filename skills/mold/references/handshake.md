# The two-key handshake

Curdle (artifact extraction) requires **both** keys. Neither is optional.

## User key

The user must say one of: `curdle`, `ship it`, `extract`, `that's enough`. **Never inferred.**

A vague "ok let's go" or "sounds good" is not the user key. Ask explicitly.

## Agent key — coherence self-check

Print this checklist and require every box checked before extraction (or an explicit `curdle anyway` override):

```
Coherence self-check before curdle:
- [ ] Problem statement: grounded, agreed
- [ ] At least 2 options weighed (Do Nothing included)
- [ ] Chosen option grounded in codebase evidence
- [ ] Interface sketches: every public seam has a pseudocode signature
- [ ] Cross-module calls go through public interfaces, not internals
- [ ] Validate cycles: all launched cycles judged
- [ ] Chosen option Grilled (≥1 stress-test entry per major branch)
- [ ] Open questions all marked [TBD] / [BLOCKED] / [?] (none silent)
- [ ] Quality gates specified (≥1 runnable command)
- [ ] Reproduction loop captured if Diagnose ran (or [BLOCKED] if no loop is possible)
```

If any box is unchecked, name it and propose the smallest move to fill it. The user can override with `curdle anyway`.

## Mandatory gates

These are not soft suggestions — Curdle hard-blocks until they are addressed:

- **Ground gate:** ≥1 Ground pass with a citation before Shape's options. Exception: pure greenfield (the agent must say so out loud).
- **Shape gate:** ≥1 Option block weighed (Do Nothing counts).
- **Sketch gate:** mandatory when the chosen option touches more than one module or introduces a new public interface. Skip only for trivial single-function changes (the agent must say so out loud).
- **Grill gate:** mandatory for high-blast-radius decisions. The shape check (`shape-check.md`) ranks blast radius `low | medium | high` from a `cheez-search` callers query (`tilth_search kind: "callers"`) and `tilth_deps`. A `high` verdict — multi-module callers or more than five importers — makes Grill mandatory.
- **Open hypotheses:** any Validate Cycle launched but unjudged blocks Curdle unless the user accepts it as `[TBD]`.

## Override semantics

`curdle anyway` overrides the agent key for one extraction. It does not disable future gates. The agent records the override and the unchecked items in the spec frontmatter so the human reviewer can see them.

## Why both keys

The user knows their intent; the agent knows the dialogue's coherence. Either one alone produces drift — user-only writes incoherent specs; agent-only writes specs the user didn't actually want.
