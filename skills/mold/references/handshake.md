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

These ten checklist items are the **gates** in mold's machine-readable gate model
(`references/gate-graph.md`). A test asserts the checklist items here equal the
model's gate nodes, so a gate cannot be silently dropped from this prose — edit
the two together. Render the flow with `mold.pyz gate-graph`.

## Mandatory gates

These are not soft suggestions — Curdle hard-blocks until they are addressed:

- **Ground gate:** ≥1 Ground pass with a citation before Shape's options. Exception: pure greenfield (the agent must say so out loud).
- **Shape gate:** ≥1 Option block weighed (Do Nothing counts).
- **Sketch gate:** mandatory when the chosen option touches more than one module or introduces a new public interface. Skip only for trivial single-function changes (the agent must say so out loud).
- **Grill gate:** mandatory for high-blast-radius decisions. The shape check (`shape-check.md`) ranks blast radius `low | medium | high` from a `cheez-search` callers query (`tilth_search kind: "callers"`) and `tilth_deps`. A `high` verdict — multi-module callers or more than five importers — makes Grill mandatory.
- **Open hypotheses:** any Validate Cycle launched but unjudged blocks Curdle unless the user accepts it as `[TBD]`.
- **Agent-introduced scope:** every distinguishing noun in the spec must trace to a user-typed mention or get per-term approval. Full procedure in § Agent-introduced scope below.

## Agent-introduced scope

Before curdle, audit the draft spec for features the user did not type the name of.

Procedure:

1. Extract distinguishing nouns from the spec's `Approach`, `Decisions`, and `Interface sketches` blocks — proper-noun-ish terms, library names, algorithm names, Greek letters used as parameters, config keys, knobs.
2. For each noun, grep the prior user turns of the conversation (the user's typed messages, not the agent's or sub-agents' output) for a literal mention.
3. **Any noun with zero hits is agent-introduced.** Mark it `[AGENT-INTRODUCED]` inline in the draft and present a short table:

   ```
   Agent-introduced scope check:
   | Term | First introduced by | Where in spec |
   | --- | --- | --- |
   | <noun> | <agent/sub-agent/citation> | <section> |
   ```

4. **The user must explicitly approve each row** before the handshake fires. Acceptable approvals: "yes keep <term>", "drop <term>", "make <term> a follow-up". Vague "looks good" is not approval.
5. If any flagged term came from a research citation (briesearch sub-agent, fetched doc, MCP result), it cannot be silently promoted into a design knob — the citation is evidence, not a mandate. See `skills/briesearch/references/synthesis.md` § Alternatives are open questions.

This gate exists because research sub-agents have historically over-synthesised: a Tavily snippet mentioning "X or Y" became a shipped `[setting].knob = "x" | "y"` flag, copied through curdle → cook without the user typing the distinguishing noun once. The grep heuristic catches that class of drift early.

Curdle is the single chokepoint for this gate. Downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block — record approved-but-flagged terms in spec frontmatter as `agent_introduced_scope: [<term>, …]` so the paper trail survives.

## Override semantics

`curdle anyway` overrides the agent key for one extraction. It does not disable future gates. The agent records the override and the unchecked items in the spec frontmatter so the human reviewer can see them. `curdle anyway` does **not** waive the Agent-introduced-scope gate — each flagged term still needs explicit per-term approval, since silent inclusion is the failure mode the gate exists to catch, and downstream skills will not re-check.

## Why both keys

The user knows their intent; the agent knows the dialogue's coherence. Either one alone produces drift — user-only writes incoherent specs; agent-only writes specs the user didn't actually want.
