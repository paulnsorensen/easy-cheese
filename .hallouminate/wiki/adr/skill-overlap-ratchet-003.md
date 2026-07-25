
# ADR: Compare semantic overlap against explicit reference topology

The analyzer keeps document references, collapsed skill ownership, and semantic similarity as distinct graph views; slash-command mentions are not invocation edges.

## Decision record

### ADR-003: Typed graph views without inferred invocation edges [status: accepted]

- **Context:** Existing repository tests already define document-reference edges as Markdown links plus backticked relative paths. Skill-command mentions can represent actual handoffs, examples, comparisons, or incidental prose. Mixing these meanings would make graph distance ambiguous.[^1]
- **Decision:** Build a directed document graph from the existing reference grammar, derive a collapsed-skill graph from manifest ownership, and build a symmetric semantic graph from exact and above-threshold overlap. Classify each semantic finding by direct links, directed and undirected distance, component membership, and same-skill ownership.
- **Alternatives:** Use semantic scores without graph context; merge document and invocation edges; add a separately typed invocation graph in the first release.
- **Consequences:** Findings can distinguish overlong linked restatements from disconnected candidates for canonical shared references. Workflow semantics remain outside the initial job until an explicit invocation grammar is designed.

Related: [[skill-overlap-ratchet-002]], [[skill-overlap-ratchet-004]].

[^1]: `tests/python/ref_extraction.py:1-30`; `tests/python/test_reference_resolution.py:64-73`; `.claude-plugin/plugin.json:3-22`
