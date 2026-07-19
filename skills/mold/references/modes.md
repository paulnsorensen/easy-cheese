# The six modes of mold

Mold has no fixed entry point. Inspect the input shape and pick a starting mode. Announce the mode in one line. Low-confidence classifications default to **Explore**.

## Routing — input shape to starting mode

| Input shape | Start mode | Heuristic |
| --- | --- | --- |
| Stack trace, "X is broken/slow/flaky" | Diagnose | error markers, `file:line` refs, symptom verbs |
| File path, PR ref, existing spec in the durable spec corpus (resolver-owned; see `SKILL.md` Curdle) | Ground | concrete artifact exists; read it first |
| Half-baked design doc with signatures or schemas | Sketch | already has interfaces; refine them |
| "I want to add X" with concrete nouns | Bounds pass → Shape | run the bounds pass first (edges → goals/non-goals), then jump to options |
| "Should we do X? thinking about Y" | Bounds pass → Grill | bounds pass first, then stress-test the tentative plan |
| Vague noun, half-sentence, "thinking about" | Explore | no grounded artifact, no chosen direction |

**Front-loaded bounds pass.** Every row above selects a *secondary* mode. Regardless of input shape, mold opens with the mandatory bounds pass (`SKILL.md` Flow step 1 — an Explore-style edges → goals/non-goals round plus the per-round decision ledger) *before* this table's mode runs. The concrete-ask rows ("I want to add X", "Should we do X") therefore no longer skip straight past asking: the bounds pass fires first, then Shape/Grill takes the refined scope.

## Mode definitions

### Explore — intent extraction

**Job:** collapse ambiguity with high-leverage questions. Borrow the Job-To-Be-Done frame: Why Now, What This Unlocks, Who Has The Pain, Do Nothing. Use lettered options to compress decisions.

**Exit when:** a problem statement plus one concrete pain point is articulated.

### Ground — anti-hallucination

**Job:** anchor every claim to evidence — code, docs, prior research. When the user uses overloaded terms ("account", "session", "user"), pause and resolve with a canonical-term question. Terms resolved here are written to the session's durable glossary at `.cheese/glossary/<slug>.md` at the curdle atomic step (see `curdle.md` § Durable glossary), so downstream skills (`/cook`, `/age`, `/press`) can read them for naming consistency.

**On Ground entry:** resolve and load the project's cumulative domain model via `domain_model_target()` (`shared/scripts/paths.py`) — the read-probe cascade (consumer wiki, shape-matched via `list_corpora` and confirmed via `wiki_has_model` → tracked `docs/domain-model*` → `<project_corpus_root()>/domain-model*`), checked in full before any write: a wiki corpus that is merely *listed* does not win on its own — an existing file-store model wins over a wiki corpus with no confirmed model. It mirrors the `adr_target()` resolution *pattern* (`adr.md` § Resolution): dynamic, existing model always wins, and if the probe is unreachable degrade to "not loaded" and say so — never block Ground on it. The model is cross-session memory; the per-slug glossary is the branch-local handoff. When a user term conflicts with an existing model entry, **challenge immediately** ("the model defines X as …, you seem to mean Y — which is it?"). Challenges are LIVE here; writes to the model are deferred to the approval gate — curdle owns the write (see `curdle.md`), never inline during Ground.

**Invariant:** never say "I think the code does X" without a `cheez-search` call.

**Exit when:** every critical claim has a citation.

### Shape — option generation

**Job:** turn a grounded problem into 2+ candidate approaches with trade-offs. Always include **Do Nothing**. Present them as lettered options (`A/B/C/D`) for the user to pick — a consequential fork is theirs to choose, not yours to settle; give a one-line rationale per option, not a verdict. Validate Cycle any critical assumption behind an option.

**Exit when:** an option is picked (→ Sketch) or none survive (→ Explore).

### Sketch — interface lockdown

**Job:** lock modules, responsibilities, I/O contracts, and seams in pseudocode signatures. Before drafting, when the change touches more than one module or introduces a new public interface, run the shape check (`shape-check.md`) — signatures, callers (via `cheez-search`, i.e. `tilth_search kind: "callers"`), and `tilth_deps` blast radius — on the touched symbols so new seams fit existing convention and the impact is bounded. Print the shape-check summary block before any pseudocode. Single-module, internals-only sketches may skip the gate; note "shape check skipped: single-module change" instead.

**Acceptance notation (EARS):** for every public seam, emit acceptance criteria in EARS form: `WHEN <trigger> THE SYSTEM SHALL <response>`. If the trigger cannot be stated precisely (e.g. pure internal utilities), fall back to prose with a `[prose-fallback]` marker.

**Concrete-seam rule:** when a seam is small enough to write completely (a function body that fits in roughly 20 lines), write the full implementation rather than pseudocode. Reserve abbreviated signatures only for seams where the body is genuinely too large or depends on design unknowns not yet resolved in the dialogue.

**Exit when:** every public seam has a pseudocode signature or full implementation per the concrete-seam rule; every acceptance criterion is in EARS form (or marked `[prose-fallback]`); every cross-module call goes through public interfaces, not internals; shape-check verdict is recorded (or explicitly skipped per the gate above).

### Grill — adversarial clarification

**Job:** stress-test the chosen approach plus sketched interfaces. Each grilled item (any `[AGENT-DECIDED]` item or design decision) produces at most a **steelman + tension statement**, then a **user fork** — uphold / amend-as-proposed / user's own call — posed as lettered options (`A/B/C/D`); verdicts are never self-issued for items that change the design. Items where the steelman fails cleanly (grilling finds nothing) MAY be batch-reported as upheld; any item whose grilling produces an amendment MUST surface as a question before the amendment enters the ledger. Traverse decision branches and contract corners. Pause for a Validate Cycle when an unverified assumption surfaces.

**Exit when:** every branch and contract corner is touched and agent confidence ≥ user confidence.

### Diagnose — symptom inputs

**Job:** entry mode for stack traces and "X is broken". Phases:
`Build a Loop → Reproduce → Hypothesize (3–5 ranked, falsifiable) → Confirm root cause`.

**Phase 0 (Build a Loop)** is the core discipline — agree on a fast, deterministic, falsifiable feedback technique (failing test, curl/CLI script, headless browser, replay, bisection harness, differential loop) BEFORE chasing hypotheses. The chosen loop becomes the Reproduction block in the bug-shaped spec, so `/cook` can verify the fix against the same signal.

Diagnose is **diagnostic-only** — hand off to Shape ("what's the fix?") then Curdle emits a bug-shaped spec.

## User knobs (free-form interrupts)

`explore`, `ground`, `shape`, `sketch`, `grill`, `diagnose`, `validate <hypothesis>`, `prototype <question>`, `curdle`, `pause`, `enough`. Honour these immediately.

`prototype <question>` launches a Prototype Cycle (`prototype-cycle.md`): a
throwaway built in a hermetic sub-agent worktree to settle an ungrillable design
unknown, returning only the answer as a digest. The code is discarded; the answer
is the keeper.

## Uncertainty markers

| Marker | Meaning |
| --- | --- |
| `[?]` | Agent uncertain; needs validation |
| `[TBD]` | User uncertain; decision deferred |
| `[BLOCKED]` | External dependency unresolved |
| `[CONFLICT <id>]` | Codebase contradicts a stated assumption |
