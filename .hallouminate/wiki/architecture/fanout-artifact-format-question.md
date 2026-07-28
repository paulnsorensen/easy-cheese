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

## The question

Should today's fan-out artifact format — [handoff envelopes](../specs/cross-skill-work-contract.md)
plus prose fan-in reports, [curds file-disjoint by construction](../fanout-engine-entities.md) —
move toward a structured, provenance-carrying store (typed
entities/relations with source citations, a "blackboard") instead of, or
underneath, that prose?

## Current position: no

The `subagent-routing-overhaul` spec's position is **no** — fan-in
envelopes plus durable artifacts already cover *retrieval-shaped* sharing
(durable, cited, queryable via `ground`), curds are file-disjoint by
construction so they rarely need to chain facts across each other, and a
graph store is a deliberate non-goal. This issue exists to hold the
re-evaluation open rather than let the question get silently re-litigated
from scratch each time it comes up.

## The concrete trigger that would flip it

Multi-wave pipeline runs where wave-2 curds need structured facts that
wave-1 workers already discovered, and prose fan-in envelopes keep losing
them. The test is empirical, not aesthetic: instrument fan-in information
loss across a few real multi-wave runs — what did wave-2 re-derive that
wave-1 had already established? If instrumentation shows that loss, the
store earns its complexity (playbook Appendix C: "multi-doc, multi-hop
chaining" and "multi-agent shared state" are exactly the scenarios a graph
earns its keep for). If it doesn't, the answer stays no.

## Delineation against hallouminate

The wiki plus semantic `ground` already plays the playbook's "blackboard"
role for *retrieval-shaped* sharing — durable, cited, queryable, and this is
explicit in the dotfiles page's own "Local implications" section. The gap
under evaluation is narrower: *chaining* — facts that connect across
workers but never co-occur in one artifact, which retrieval by similarity
cannot surface regardless of how good the wiki gets. A structured store, if
ever adopted, would sit *underneath* the fan-in envelope as an additional
stage-contract, not replace hallouminate.

## Bearing on open fan-out policy questions

- **Additive fan-out (N workers, N findings) vs. exclusive fan-out (N
  debuggers, one hypothesis wins).** The playbook's resolution/assembly
  stages assume *additive* findings — entity resolution merges surface
  forms of the same fact, it does not arbitrate between mutually exclusive
  claims about what is true. It has no resolution mechanism for
  competing hypotheses; that is a different reconciliation shape (pick one,
  not merge all). Any adoption for `/age`-style additive fan-out would not
  transfer to a debugger-style exclusive fan-out without separate design.
- **Barrier-style review over a merged diff.** The playbook's model-tiering
  and precision-first-write guidance are about facts entering a *shared,
  durable* store across a long-lived multi-wave loop, not about a
  single-shot review pass over one already-merged diff. A barrier design
  that reviews once, post-merge, doesn't have the "workers write, orchestrator
  reads incrementally" shape the playbook is solving for — so the playbook
  neither blocks nor requires barrier-style review; it is largely silent on
  that axis. Nothing in the source document argues against reviewing a
  merged diff once.
- **Numbers cited from the playbook are all upstream generic claims** (see
  the dotfiles page for the model-tier table, the 90.2%-better/10–15×-cost
  multi-agent figure, and the resolution-block size of 50–100) — none of
  them are calibrated against this repo's fan-out sizing (`age_route.py`'s
  `n=1/2/5` ladder, `MIN_CURD_SURFACE=25`, `MAX_WAVE_SIZE=4`; see
  [age-fanout-router](./age-fanout-router.md) and
  [fanout-engine-entities](../fanout-engine-entities.md)). Treat them as
  external context, not as thresholds to import.

## Related

- [age-fanout-router](./age-fanout-router.md) — deterministic review
  fan-out sizing, the closest existing "N workers, reconcile" mechanism.
- [fanout-engine-entities](../fanout-engine-entities.md) — Curd, Wiring
  node, Curd block: today's file-disjoint decomposition artifacts.
- [cross-skill-work-contract](../specs/cross-skill-work-contract.md) — the
  versioned handoff envelope that is the closest existing analogue to a
  "stage contract."

_Source: GitHub issue #313 body + two PDF-extraction comments (Anthropic KG
playbook synthesis, independent, July 2026, not affiliated with or endorsed
by Anthropic) · Cross-checked against the dotfiles wiki ingest · Updated:
2026-07-27_
