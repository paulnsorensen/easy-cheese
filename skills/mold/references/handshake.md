# The two-key handshake

Curdle (artifact extraction) requires **both** keys. Neither is optional.

## User key

The user key shows explicit extraction intent: approval to write the spec. The direct form is `curdle`. `ship it`, `extract`, or `that's enough` have the same effect. A clear affirmative also turns the key when it directly answers an agent's extraction question. Examples include `ok let's go`, `sounds good`, and `go ahead`.

Judge the key by intent, never by spelling. Capitalization, surrounding whitespace, or punctuation never invalidate otherwise-clear approval. Never demand an exact respelling or a magic string. Do not infer the key from unrelated or ambiguous approval. Ask explicitly when the context does not establish that the user approves Curdle.

## Agent key — coherence self-check

Print this checklist and require every box checked before extraction (or an explicit `curdle anyway` override):

```
Coherence self-check before curdle:
- [ ] Problem statement: grounded, agreed
- [ ] Grounding recorded: a wiki probe result — citations or an explicit hallouminate-absent note — preceded the first structured question
- [ ] At least 2 options weighed (Do Nothing included)
- [ ] Chosen option grounded in codebase evidence
- [ ] Exploration delegated: evidence-heavy reads carry an explorer digest, or the parent-context fallback is recorded
- [ ] Interface sketches: Placement block complete (slice, spine step, public interface, private, crust delta, arrows)
- [ ] Cross-module calls go through public interfaces, not internals
- [ ] Identity nouns: each bound to a code referent or marked NEW ENTITY (an ALIAS must be resolved, not just noted)
- [ ] Non-goals audit: every bullet traces to a user-stated out-of-scope item or is marked [AGENT-INTRODUCED]
- [ ] Validate cycles: all launched cycles judged
- [ ] Chosen option Grilled (≥1 stress-test entry per major branch)
- [ ] Open questions all marked [TBD] / [BLOCKED] / [?] (none silent)
- [ ] Quality gates specified (≥1 runnable command)
- [ ] Reproduction loop captured if Diagnose ran (or [BLOCKED] if no loop is possible)
- [ ] Durable writes: ADR + domain-model targets resolved and the write, read-back, and completion-record protocol committed for the atomic step (or loud fallback noted)
- [ ] Fork taste test passed: fresh-context verdict covers every settled consequential decision before typed planning
- [ ] Spec format valid: validate-spec --strict exits 0 on the draft
```

If any box is unchecked, name it and propose the smallest move to fill it. The user can override with `curdle anyway`.

The last box — **Durable writes** — is a commitment checked before the handshake. It does not claim that the write already occurred. It confirms that the ADR + domain-model targets are resolved. It also locks in the write → read-back → completion-record protocol for the atomic-write step (`curdle.md` § Atomic write). The read-back verification and visible completion record occur during that step. Note the hallouminate-absent fallback clearly, never silently.

These checklist items match the gates in Mold's machine-readable gate model. See `gate-graph.md`. A passing `fork_taste_test_passed` verdict opens the typed planner stage. A stale, partial, contradictory, or blocker-bearing verdict keeps typed planning closed. A test compares this checklist with the model nodes. Edit both sources together. Render the flow with `python3 skills/mold/scripts/mold.pyz gate-graph`.

## Mandatory gates

These are not soft suggestions — Curdle hard-blocks until they are addressed:

- **Ground gate:** ≥1 Ground pass with a citation before Shape's options. Exception: pure greenfield (the agent must say so out loud).
- **Shape gate:** ≥1 Option block weighed (Do Nothing counts).
- **Sketch gate:** mandatory when the chosen option touches more than one module or introduces a new public interface. Skip only for trivial single-function changes (the agent must say so out loud).
- **Grill gate:** mandatory for high-blast-radius decisions. The shape check (`shape-check.md`) ranks blast radius `low | medium | high` from semantic caller search and `tilth_deps` when available. A `high` verdict — multi-module callers or more than five importers — makes Grill mandatory.
- **Open hypotheses:** any Validate Cycle launched but unjudged blocks Curdle unless the user accepts it as `[TBD]`.
- **Agent-introduced scope:** every distinguishing noun in the spec must trace to a user-typed mention or carry an approved scope-audit row. See the full procedure in § Agent-introduced scope below. Curdle is the single chokepoint because downstream skills trust the resulting frontmatter and do not re-block.
- **Entity-referent binding:** bind every identity noun to a code referent or mark it NEW ENTITY. Resolve each ALIAS; do not only note it. See the full procedure in § Entity-referent binding below.
- **Non-goals audit:** every `Non-goals` bullet traces to a user-stated out-of-scope item or is marked `[AGENT-INTRODUCED]`. Full procedure in § Non-goals audit below.
- **Fork taste test:** Require a fresh-context verdict before decomposition. The verdict must match the draft SHA256. It must cover each settled consequential decision exactly once. It cannot contain contradictions, orphaned decisions, unsupported assumptions, or acceptance gaps. When the ledger pins a `goal`, the draft's Problem statement must contain it unchanged, compared case- and whitespace-insensitively, or the verdict fails as `goal-drift`. Mold permits the initial verdict and two corrective rounds. A third failure stops the process.
- **Spec format gate:** Run `validate-spec --strict` on the draft before Curdle extracts it. The command must exit with status 0. Curdle writes only the current hardened format. It does not use the legacy read grace period.
- **UI surface classification:** every Mold-produced spec carries a provenance
  marker and an explicit `ui_surface` value under `gate_applicability`.
  `browser` requires an existing browser/E2E interface and outer seam for every
  Test Contract; `non-browser` is explicit and never inferred from prose;
  closed non-behavior work, including appearance-only, uses
  `not-applicable`. The taste and curd gates enforce this field without
  changing legacy specs.

## Scope audit table

The agent-introduced scope, non-goals, entity-referent, and follow-up audits below populate **one table, presented once, before the handshake**. Each row carries a default disposition. One confirm of the table approves every default except the rows marked `needs your verb`. A row needs its own explicit verb only when it fires a leverage trigger (`../../cheese/references/routing-policy.md` § Leverage triggers) or is an unresolved ALIAS / NEW ENTITY binding. A row fires a trigger when the term, bullet, or noun it names would itself fire one of the eight ids if kept: an auth knob fires `auth`, a new export fires `contract`, a new domain fires `new-slice`. Such a row renders `needs your verb` in its Default cell, and the confirm never covers it. The grep and semantic search that populate the rows still run; the per-row approval round does not.

```
Scope audit:
| # | Kind | Term / bullet / noun | Source | Default | Leverage |
| --- | --- | --- | --- | --- | --- |
| 1 | scope | <noun> | agent / citation | keep | — |
| 2 | non-goal | <bullet> | agent | keep | — |
| 3 | entity | <noun> | search | Bound <referent> | — |
| 4 | follow-up | <unit: member, member> | dialogue | non-goal only | — |
| 5 | scope | <noun> | citation | needs your verb | contract |
| 6 | entity | <noun> | search | needs your verb (ALIAS <referent>) | — |
Confirm the table to accept the defaults. Rows marked `needs your verb` block until you name a verb for each.
```

Curdle runs the table as the terminal backstop. It remains the single chokepoint that downstream skills trust (RC3).

## Agent-introduced scope

Before curdle, audit the draft spec for features the user did not type the name of.

Procedure:

1. Extract distinguishing nouns from the spec's `Approach`, `Decisions`, and `Interface sketches` blocks. Include proper-noun-like terms, library names, algorithm names, Greek parameter letters, config keys, and knobs.
2. For each noun, grep the prior user turns for a literal mention. Search only the user's typed messages, not agent or sub-agent output.
3. **Any noun with zero hits is agent-introduced.** Mark it `[AGENT-INTRODUCED]` inline in the draft and add a `scope` row to the scope audit table. Default `keep` when the noun restates the user's ask or binds to a code referent, `follow-up` when it names new work, `drop` otherwise.

4. **One confirm of the table approves the defaults.** A row that fires a leverage trigger needs its own verb: "keep <term>", "drop <term>", or "make <term> a follow-up". "Make <term> a follow-up" records a candidate within `Decided`. This choice does not create an issue or other artifact.
5. **When a direction is dropped**, whether the user typed the verb or confirmed a `drop` default, write a rejection record to `.cheese/.out-of-scope/<slug>-NNN.md`. A direction can be an approach, design knob, or named feature that the user declines. Use the format in `curdle.md` § Rejected-directions store. Do not make a rejected direction a follow-up candidate. Add explicit deferrals to the follow-up candidate set instead.
6. Do not silently promote a flagged term from a research citation into a design knob. This applies to briesearch sub-agent citations, fetched docs, and MCP results. The citation is evidence, not a mandate. See `skills/briesearch/references/synthesis.md` § Alternatives are open questions.

This gate exists because research sub-agents have historically over-synthesised. For example, a Tavily snippet mentioning "X or Y" became a shipped `[setting].knob = "x" | "y"` flag. The flag passed through curdle → cook although the user never typed the distinguishing noun. The grep heuristic detects this type of drift early.

Curdle is the single chokepoint for this gate. Downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block. Record approved-but-flagged terms in spec frontmatter as `agent_introduced_scope: [<term>, …]`. This record preserves the paper trail.

## Non-goals audit

`Non-goals` narrows scope — it removes work the user may have wanted without ever asking. That makes it the single most consequential lean, and the existing drift gates never audited it (they read only `Approach / Decisions / Interface sketches`). This gate guards it, as a sibling of Agent-introduced scope.

Procedure:

1. For each `Non-goals` bullet, grep prior user turns for a statement that puts the item out of scope. Search only the user's typed messages. Examples include "don't bother with X", "leave Y alone", and an explicit deferral.
2. **Any bullet with no such user statement is agent-introduced.** Mark it `[AGENT-INTRODUCED]` inline and add a `non-goal` row to the scope audit table with default `keep`. Non-goals that the bounds pass authored as `[AGENT-DECIDED]` are agent-introduced by definition and enter the table the same way. The user keeps, drops, or rewords it by confirming or editing the row.
3. Record approved-but-flagged non-goals in the same `agent_introduced_scope` frontmatter list, so the paper trail survives downstream.
4. Add every audited non-goal to the follow-up candidate set, including approved `[AGENT-INTRODUCED]` bullets. Candidate status preserves the scope boundary without accepting future work.

This audit is the `Non-goals audit` coherence gate. It is the `non_goals_audit` node in the gate model (`gate-graph.md`). Populate its rows as non-goals are proposed; present them once, in the scope audit table. Curdle reruns it as the terminal backstop and hard-blocks extraction until every bullet traces to the user or has an approved `[AGENT-INTRODUCED]` row.

## Follow-up disposition (inside the non-goals audit)

Before the two-key handshake, dispose of every follow-up candidate in one batch: the `follow-up` rows of the scope audit table. This process extends the existing `Non-goals audit` gate. It does not add or rename a gate. The default destination is **non-goal only**; every other destination is a user edit on the row.

1. Group related candidates into independently deliverable units. Each unit is one `follow-up` row whose cell lists its members; confirming the table accepts the grouping, and the user splits or merges by editing the row.
2. Search GitHub Issues and Hallouminate roadmap goals when discovery is available. A semantic match is surfaced on the row as a recommended `link #<id>`, not adopted as the default: the default destination stays non-goal only, and the user adopts the link by editing the row.
3. Recommend one destination per unit:
   - **non-goal only** — keep the scope boundary, create no follow-up artifact, and offer no action choice;
   - **GitHub Issue** — use for discrete, independently actionable work;
   - **roadmap goal** — use for coordinated, milestone-scale, or dependency-linked work;
   - **local issue draft** — use when publication is not desired or available.
4. The user approves the destination by confirming the row's default or editing it. An edited destination also names the action: **create/link now** or **leave prepared**.
5. Record accepted units for Curdle. Keep rejected design directions in the rejection store. Do not add them to this batch.

The user approves grouping, splitting, semantic-match reuse, destination, and action choices by confirming the table's defaults or editing the rows. Mold settles none silently; every default is visible in the table. Omit this batch when no candidates exist. Preserve the current handshake and Curdle flow.

Record each candidate within `Decided` as `[FOLLOW-UP?]`. Include its summary, source, and rationale. A follow-up candidate is dialogue state only. It does not create an artifact or future commitment.

After both keys pass, Curdle writes local artifacts first. It then publishes approved follow-ups. It reconciles their state and references into the durable spec. It only then renders the implementation handoff.

## Entity-referent binding
Before curdle, audit the draft for **identity/ownership-role nouns**. These nouns identify roles that hold, own, span, or claim state or lifecycle. Examples include owner, run, session, claim-holder, coordinator, worker, lease, tenant, and lock-holder. The role triggers the audit, not a fixed word list. Flag domain-specific identities. Do not flag plain value nouns such as formats, algorithms, or config knobs.

The mechanism is semantic symbol search, one query per identity noun, following the [shared routing contract](../../cheese/references/code-intelligence-routing.md). The gate is *not* "did search find something" — it is a three-way verdict on what search returns:

| Search outcome | Verdict | Action |
| --- | --- | --- |
| Symbol whose shape matches the design's assumed role | **Bound** | record code referent + `file:line` citation |
| Symbol of a different shape/referent (aliasing) | **ALIAS** | state the divergence; resolve by renaming to the real entity or designing the intended one |
| No symbol | **NEW ENTITY** | add a spec section designing it |

Procedure:

1. Extract identity/ownership-role nouns from the spec's `Approach`, `Decisions`, and `Interface sketches` blocks.
2. Search each noun and classify it `Bound` / `ALIAS` / `NEW ENTITY` per the table above.
3. Add one `entity` row per identity-role noun to the scope audit table. A `Bound` row needs no approval; an `ALIAS` or `NEW ENTITY` row blocks until resolved. The binding detail reads:

   ```
   Entity-referent binding check:
   | design noun | code referent | citation | divergence note |
   | --- | --- | --- | --- |
   | run | ALIAS — make_run_id (one dispatch) | — | code `run` is one dispatch, not a session; design assumed a session spanning siblings (a search *hit* of the wrong shape) — state the divergence, rebind to the real entity |
   | session | NEW ENTITY | — | no symbol; the coordinator session the design needs must be designed |
   ```

4. **An unresolved binding hard-blocks curdle**, exactly as an unapproved `[AGENT-INTRODUCED]` noun does. A search *hit* does not resolve the binding. Determine whether the design's usage differs from the code's existing meaning of the same word. If it differs, state and settle the aliasing before extraction.

This gate is the referent-level sibling of Agent-introduced scope. That gate asks *did the user type this noun*. This gate asks *does the code have it, with the assumed shape*. One example shows why the gate exists. A fully handshook spec declares its goal-claims "owned by the run/session". The code's `run` names one task dispatch, not a coordinator session. The aliased noun then reaches a re-age blocker and a cure-pass-2 design decision that belongs in Mold. Curdle is the single chokepoint. Downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block. Record bound and flagged nouns in frontmatter as `entity_referent_bindings: [{noun, verdict, referent, citation, note}, …]`. Use a list of binding records. Preserve the referent and promised `file:line` citation in this record.

## Override semantics

`curdle anyway` overrides the agent key for one extraction. It does not disable future gates. Record the override and unchecked items in the spec frontmatter. This record lets the human reviewer see them. `curdle anyway` does **not** waive the scope audit table's leverage rows or its unresolved bindings. It accepts every other default. The gate prevents silent inclusion, and downstream skills do not re-check. Under `curdle anyway`, an unbound or aliased identity noun still blocks extraction. Downstream skills trust the frontmatter bindings and do not re-derive them.

## Why both keys

The user knows their intent; the agent knows the dialogue's coherence. Either one alone produces drift — user-only writes incoherent specs; agent-only writes specs the user didn't actually want.
