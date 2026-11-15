# Fan-out artifact format: the standing shared-store re-evaluation

Tracks issue [#313](https://github.com/paulnsorensen/easy-cheese/issues/313)
("Explore: provenance-carrying shared store for fan-out findings (KG
playbook) — change the artifact format?"), filed as the F2 follow-up from
the dotfiles `subagent-routing-overhaul` spec (2026-07-24). This page is the
easy-cheese-side record of the question and its current disposition — not a
restatement of the playbook doctrine, which lives in the dotfiles wiki
(`architecture/knowledge-graph-playbook.md`, ingested 2026-07-24, source-hash
`32c0769bb78d8fb7`; verified faithful against the source PDF text on
2026-07-27).

The disposition is still **no**. [ADR-005](../adr/deterministic-fanout-sizing-005.md)
(fork B) changes how cook picks its shape. It does not change this
disposition. See "Effect of ADR-005" below.

## The question

Should today's fan-out artifact format — [handoff envelopes](../specs/cross-skill-work-contract.md)
plus prose fan-in reports, with pieces kept file-disjoint (see
[fanout-engine-entities](../fanout-engine-entities.md)) — move toward a
structured, provenance-carrying store (typed entities and relations with
source citations, a "blackboard") instead of, or underneath, that prose?

## Current position: no

The `subagent-routing-overhaul` spec's position is **no**. Fan-in
envelopes plus durable artifacts already cover *retrieval-shaped* sharing
(durable, cited, queryable via `ground`). Disjoint pieces rarely need to
chain facts across each other. A graph store is a deliberate non-goal. This
issue holds the re-evaluation open, so nobody re-litigates the question from
scratch each time it comes up.

## The concrete trigger that would flip it

Multi-wave pipeline runs where wave-2 pieces need structured facts that
wave-1 workers already discovered, and prose fan-in envelopes keep losing
them. The test is empirical, not aesthetic: instrument fan-in information
loss across a few real multi-wave runs. Ask what wave-2 re-derived that
wave-1 had already established. If instrumentation shows that loss, the
store earns its complexity (playbook Appendix C: "multi-doc, multi-hop
chaining" and "multi-agent shared state" are exactly the scenarios a graph
earns its keep for). If it does not, the answer stays no.

## Effect of ADR-005

ADR-005 says cook has no fan-out default. Code-computed size heuristics
choose inline work, one fresh-context worker, or a parallel plan. Three
points show why the disposition holds:

- **The trigger is unchanged.** The flip condition is measured fan-in loss
  across waves. ADR-005 adds no such measurement. It chooses how many
  workers run, not what they exchange.
- **The "disjoint by construction" premise moves.** Earlier text relied on
  the Curd block to keep pieces file-disjoint. PR #672 removed the
  Curd-block parser. Disjointness of mixed inline and dispatched pieces is
  now open design work in ADR-005. If that design allows pieces to share
  files, re-check the "rarely chain facts" claim.
- **Fewer parallel runs make the trigger rarer.** A default of inline or one
  worker produces fewer multi-wave fan-outs than the old default. The
  local measurement already found no same-second parallel burst in 609
  spawns ([fanout-patterns-2026-09-10](../analytics/fanout-patterns-2026-09-10.md)).
  Multi-wave runs are the place to instrument first, and they are rare.

The research pages [fanout-gating-units-evidence](../research/fanout-gating-units-evidence.md)
and [schema-grounded-subagent-handoffs](../research/schema-grounded-subagent-handoffs.md)
reach the same conclusion from outside: a shared typed store pays off only
when facts chain across workers that never read the same files.

## Delineation against hallouminate

The wiki plus semantic `ground` already plays the playbook's "blackboard"
role for *retrieval-shaped* sharing — durable, cited, queryable. The dotfiles
page's own "Local implications" section says this. The gap under evaluation
is narrower: *chaining*. These are facts that connect across workers but
never co-occur in one artifact, which retrieval by similarity cannot surface
however good the wiki gets. A structured store, if ever adopted, would sit
*underneath* the fan-in envelope as an additional stage contract. It would
not replace hallouminate.

## Bearing on open fan-out policy questions

- **Additive fan-out (N workers, N findings) vs. exclusive fan-out (N
  debuggers, one hypothesis wins).** The playbook's resolution and assembly
  stages assume *additive* findings. Entity resolution merges surface forms
  of the same fact. It does not arbitrate between mutually exclusive claims.
  It has no mechanism for competing hypotheses, which need a different
  reconciliation shape (pick one, not merge all). Adopting the store for
  `/age`-style additive fan-out would not transfer to a debugger-style
  exclusive fan-out without separate design.
- **Barrier-style review over a merged diff.** The playbook's model-tiering
  and precision-first-write guidance cover facts entering a *shared,
  durable* store across a long-lived multi-wave loop. They do not cover a
  single-shot review of one merged diff. A barrier design that reviews once,
  post-merge, lacks the "workers write, orchestrator reads incrementally"
  shape the playbook solves for. The playbook neither blocks nor requires
  barrier-style review.
- **Playbook numbers are generic upstream claims.** The dotfiles page holds
  the model-tier table, the 90.2% gain with 10–15x cost figure, and the
  resolution-block size of 50–100. None of them is calibrated against this
  repo. The current review sizing is in [age-fanout-router](./age-fanout-router.md)
  (score bands and the `quick`, `normal`, and `deep` effort limits). Cook
  sizing is open design work in ADR-005. The earlier constants
  (`MIN_CURD_SURFACE`, `MAX_WAVE_SIZE`) no longer exist; see
  [ADR-004](../adr/deterministic-fanout-sizing-004.md) for that history.
  Treat the playbook numbers as external context, not as thresholds to
  import. For outside evidence on fan-out size, see
  [fanout-gating-units-evidence](../research/fanout-gating-units-evidence.md).

## Related

- [ADR-005](../adr/deterministic-fanout-sizing-005.md) — cook has no fan-out
  default; size heuristics decide the shape.
- [ADR-004](../adr/deterministic-fanout-sizing-004.md) — the earlier
  Curd-block size design, kept as history.
- [age-fanout-router](./age-fanout-router.md) — deterministic review
  fan-out sizing, the closest existing "N workers, reconcile" mechanism.
- [fanout-engine-entities](../fanout-engine-entities.md) — Curd and Wiring
  node: the decomposition vocabulary.
- [cross-skill-work-contract](../specs/cross-skill-work-contract.md) — the
  versioned handoff envelope, the closest existing analogue to a "stage
  contract."
- [fanout-gating-units-evidence](../research/fanout-gating-units-evidence.md)
  and [schema-grounded-subagent-handoffs](../research/schema-grounded-subagent-handoffs.md)
  — outside evidence on fan-out size and typed returns.

_Source: GitHub issue #313 body + two PDF-extraction comments (Anthropic KG
playbook synthesis, independent, July 2026, not affiliated with or endorsed
by Anthropic) · Cross-checked against the dotfiles wiki ingest and ADR-005 ·
Updated: 2026-11-15_
