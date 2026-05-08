# The six modes of mold

Mold has no fixed entry point. Inspect the input shape and pick a starting mode. Announce the mode in one line. Low-confidence classifications default to **Explore**.

## Routing — input shape to starting mode

| Input shape | Start mode | Heuristic |
| --- | --- | --- |
| Stack trace, "X is broken/slow/flaky" | Diagnose | error markers, `file:line` refs, symptom verbs |
| File path, PR ref, existing spec under `.cheese/specs/` | Ground | concrete artifact exists; read it first |
| Half-baked design doc with signatures or schemas | Sketch | already has interfaces; refine them |
| "I want to add X" with concrete nouns | Shape | named the thing → jump to options |
| "Should we do X? thinking about Y" | Grill | tentative plan exists → stress-test it |
| Vague noun, half-sentence, "thinking about" | Explore | no grounded artifact, no chosen direction |

## Mode definitions

### Explore — intent extraction

**Job:** collapse ambiguity with high-leverage questions. Borrow the Job-To-Be-Done frame: Why Now, What This Unlocks, Who Has The Pain, Do Nothing. Use lettered options to compress decisions.

**Exit when:** a problem statement plus one concrete pain point is articulated.

### Ground — anti-hallucination

**Job:** anchor every claim to evidence — code, docs, prior research. When the user uses overloaded terms ("account", "session", "user"), pause and resolve with a canonical-term question. Resolved terms get logged in the state file.

**Invariant:** never say "I think the code does X" without a `cheez-search` call.

**Exit when:** every load-bearing claim has a citation.

### Shape — option generation

**Job:** turn a grounded problem into 2+ candidate approaches with trade-offs. Always include **Do Nothing**. Recommend with one-line rationale. Validate Cycle any load-bearing assumption behind a recommendation.

**Exit when:** an option is picked (→ Sketch) or none survive (→ Explore).

### Sketch — interface lockdown

**Job:** lock modules, responsibilities, I/O contracts, and seams in pseudocode signatures. Before drafting, when the change touches more than one module or introduces a new public interface, run the shape check (`shape-check.md`) — signatures, callers (via `cheez-search`, i.e. `tilth_search kind: "callers"`), and `tilth_deps` blast radius — on the touched symbols so new seams fit existing convention and the impact is bounded. Print the shape-check summary block before any pseudocode. Single-module, internals-only sketches may skip the gate; note "shape check skipped: single-module change" instead.

**Exit when:** every public seam has a pseudocode signature; every cross-module call goes through public interfaces, not internals; shape-check verdict is recorded (or explicitly skipped per the gate above).

### Grill — adversarial clarification

**Job:** stress-test the chosen approach plus sketched interfaces. **One question at a time**, paired with the agent's recommended answer (recommendation is non-optional). Traverse decision branches and contract corners. Pause for a Validate Cycle when an unverified assumption surfaces.

**Exit when:** every branch and contract corner is touched and agent confidence ≥ user confidence.

### Diagnose — symptom inputs

**Job:** entry mode for stack traces and "X is broken". Phases:
`Build a Loop → Reproduce → Hypothesize (3–5 ranked, falsifiable) → Confirm root cause`.

**Phase 0 (Build a Loop)** is the core discipline — agree on a fast, deterministic, falsifiable feedback technique (failing test, curl/CLI script, headless browser, replay, bisection harness, differential loop) BEFORE chasing hypotheses. The chosen loop becomes the Reproduction block in the bug-shaped spec, so `/cook` can verify the fix against the same signal.

Diagnose is **diagnostic-only** — hand off to Shape ("what's the fix?") then Curdle emits a bug-shaped spec.

## User knobs (free-form interrupts)

`explore`, `ground`, `shape`, `sketch`, `grill`, `diagnose`, `validate <hypothesis>`, `curdle`, `pause`, `enough`. Honour these immediately.

## Uncertainty markers

| Marker | Meaning |
| --- | --- |
| `[?]` | Agent uncertain; needs validation |
| `[TBD]` | User uncertain; decision deferred |
| `[BLOCKED]` | External dependency unresolved |
| `[CONFLICT <id>]` | Codebase contradicts a stated assumption |
