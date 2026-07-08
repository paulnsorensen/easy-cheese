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
- [ ] Identity nouns: each bound to a code referent or marked NEW ENTITY (an ALIAS must be resolved, not just noted)
- [ ] Non-goals audit: every bullet traces to a user-stated out-of-scope item or is marked [AGENT-INTRODUCED]
- [ ] Validate cycles: all launched cycles judged
- [ ] Chosen option Grilled (≥1 stress-test entry per major branch)
- [ ] Open questions all marked [TBD] / [BLOCKED] / [?] (none silent)
- [ ] Quality gates specified (≥1 runnable command)
- [ ] Reproduction loop captured if Diagnose ran (or [BLOCKED] if no loop is possible)
```

If any box is unchecked, name it and propose the smallest move to fill it. The user can override with `curdle anyway`.

These twelve checklist items are the **gates** in mold's machine-readable gate model
(`gate-graph.md`). A test asserts the checklist items here equal the
model's gate nodes, so a gate cannot be silently dropped from this prose — edit
the two together. Render the flow with `mold.pyz gate-graph`.

## Mandatory gates

These are not soft suggestions — Curdle hard-blocks until they are addressed:

- **Ground gate:** ≥1 Ground pass with a citation before Shape's options. Exception: pure greenfield (the agent must say so out loud).
- **Shape gate:** ≥1 Option block weighed (Do Nothing counts).
- **Sketch gate:** mandatory when the chosen option touches more than one module or introduces a new public interface. Skip only for trivial single-function changes (the agent must say so out loud).
- **Grill gate:** mandatory for high-blast-radius decisions. The shape check (`shape-check.md`) ranks blast radius `low | medium | high` from a `cheez-search` callers query (`tilth_search kind: "callers"`) and `tilth_deps`. A `high` verdict — multi-module callers or more than five importers — makes Grill mandatory.
- **Open hypotheses:** any Validate Cycle launched but unjudged blocks Curdle unless the user accepts it as `[TBD]`.
- **Agent-introduced scope:** every distinguishing noun in the spec must trace to a user-typed mention or get per-term approval. Full procedure in § Agent-introduced scope below — Curdle is the single chokepoint, since downstream skills trust the resulting frontmatter and do not re-block.
- **Entity-referent binding:** every identity noun binds to a code referent or is marked NEW ENTITY; an ALIAS must be resolved, not just noted. Full procedure in § Entity-referent binding below.
- **Non-goals audit:** every `Non-goals` bullet traces to a user-stated out-of-scope item or is marked `[AGENT-INTRODUCED]`. Full procedure in § Non-goals audit below.

These audits — agent-introduced scope, entity-referent binding, and the non-goals audit (below) — fire **inline, per dialogue round**, not only terminally at Curdle: each runs the moment new scope is proposed and is surfaced in that round's decision ledger, so a lean is caught when it happens rather than reverse-engineered at the end. Curdle re-runs all three as the terminal backstop and stays the single chokepoint downstream skills trust (RC3).

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
5. **When the user explicitly drops a direction** — an approach, design knob, or named feature they decline — write a rejection record to `.cheese/.out-of-scope/<slug>-NNN.md` (format in `curdle.md` § Rejected-directions store). This makes direction-level rejections durable so `/cheese` can consult them before re-proposing the same direction in a later session. Deferrals ("make <term> a follow-up") are not direction rejections — route those to `.cheese/issues/`, not the out-of-scope store.
6. If any flagged term came from a research citation (briesearch sub-agent, fetched doc, MCP result), it cannot be silently promoted into a design knob — the citation is evidence, not a mandate. See `skills/briesearch/references/synthesis.md` § Alternatives are open questions.

This gate exists because research sub-agents have historically over-synthesised: a Tavily snippet mentioning "X or Y" became a shipped `[setting].knob = "x" | "y"` flag, copied through curdle → cook without the user typing the distinguishing noun once. The grep heuristic catches that class of drift early.

Curdle is the single chokepoint for this gate. Downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block — record approved-but-flagged terms in spec frontmatter as `agent_introduced_scope: [<term>, …]` so the paper trail survives.

## Non-goals audit

`Non-goals` narrows scope — it removes work the user may have wanted without ever asking. That makes it the single most consequential lean, and the existing drift gates never audited it (they read only `Approach / Decisions / Interface sketches`). This gate guards it, as a sibling of Agent-introduced scope.

Procedure:

1. For each `Non-goals` bullet, grep the prior user turns (the user's typed messages) for the user putting that item out of scope — a "don't bother with X", "leave Y alone", an explicit deferral.
2. **Any bullet with no such user statement is agent-introduced.** Mark it `[AGENT-INTRODUCED]` inline and present it for decision — the user must explicitly keep, drop, or reword it. A vague "looks good" is not approval.
3. Record approved-but-flagged non-goals in the same `agent_introduced_scope` frontmatter list, so the paper trail survives downstream.

This audit is the `Non-goals audit` coherence gate — the `non_goals_audit` node in the gate model (`gate-graph.md`). It fires **inline per round** as non-goals are proposed and again at Curdle as the terminal backstop, which hard-blocks extraction until every bullet traces to the user or is approved `[AGENT-INTRODUCED]`.

## Entity-referent binding

Before curdle, audit the draft for **identity/ownership-role nouns** — any noun the design treats as holding, owning, spanning, or claiming state or lifecycle (owner, run, session, claim-holder, coordinator, worker, lease, tenant, lock-holder, …). The trigger is the *role*, not a fixed word list: domain-specific identities are caught and plain value nouns (formats, algorithms, config knobs) are not flagged.

The mechanism is symbol search (`cheez-search`), one query per identity noun. The gate is *not* "did search find something" — it is a three-way verdict on what search returns:

| Search outcome | Verdict | Action |
| --- | --- | --- |
| Symbol whose shape matches the design's assumed role | **Bound** | record code referent + `file:line` citation |
| Symbol of a different shape/referent (aliasing) | **ALIAS** | state the divergence; resolve by renaming to the real entity or designing the intended one |
| No symbol | **NEW ENTITY** | add a spec section designing it |

Procedure:

1. Extract identity/ownership-role nouns from the spec's `Approach`, `Decisions`, and `Interface sketches` blocks.
2. `cheez-search` each noun and classify it `Bound` / `ALIAS` / `NEW ENTITY` per the table above.
3. Present the binding table inline in the draft — one row per identity-role noun:

   ```
   Entity-referent binding check:
   | design noun | code referent | citation | divergence note |
   | --- | --- | --- | --- |
   | run | ALIAS — make_run_id (one dispatch) | — | code `run` is one dispatch, not a session; design assumed a session spanning siblings (a search *hit* of the wrong shape) — state the divergence, rebind to the real entity |
   | session | NEW ENTITY | — | no symbol; the coordinator session the design needs must be designed |
   ```

4. **An unresolved binding hard-blocks curdle**, exactly as an unapproved `[AGENT-INTRODUCED]` noun does. A search *hit* is not resolution: if the design's usage diverges from the code's existing meaning of the same word, the aliasing must be stated and settled before extraction.

This gate is the referent-level sibling of Agent-introduced scope — that gate asks *did the user type this noun*, this one asks *does the code have it, with the assumed shape*. A fully handshook spec once declared its goal-claims "owned by the run/session" while the code's `run` was a single task dispatch, not a coordinator session; the aliased noun survived to a re-age blocker and a cure-pass-2 design decision that belonged in mold. Curdle is the single chokepoint; downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block — record bound and flagged nouns in frontmatter as `entity_referent_bindings: [{noun, verdict, referent, citation, note}, …]` (a list of binding records) so the referent and `file:line` citation the trail promises actually survive.

## Override semantics

`curdle anyway` overrides the agent key for one extraction. It does not disable future gates. The agent records the override and the unchecked items in the spec frontmatter so the human reviewer can see them. `curdle anyway` does **not** waive the Agent-introduced-scope gate — each flagged term still needs explicit per-term approval, since silent inclusion is the failure mode the gate exists to catch, and downstream skills will not re-check. The same holds for the **Entity-referent gate**: an unbound or aliased identity noun still blocks extraction under `curdle anyway`, since downstream skills trust the frontmatter bindings and do not re-derive them.

## Why both keys

The user knows their intent; the agent knows the dialogue's coherence. Either one alone produces drift — user-only writes incoherent specs; agent-only writes specs the user didn't actually want.
