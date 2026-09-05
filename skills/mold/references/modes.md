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

**Front-loaded bounds pass.** Every row above selects a *secondary* mode. Regardless of input shape, mold first runs the mandatory bounds pass from `SKILL.md` Flow step 1. This pass uses an Explore-style edges → goals/non-goals round and the per-round decision ledger. Run it *before* this table's mode. Therefore, concrete-ask rows ("I want to add X", "Should we do X") no longer skip asking. The bounds pass runs first. Then Shape/Grill receives the refined scope.

## Mode definitions

### Explore — intent extraction

**Job:** collapse ambiguity with high-leverage questions. Borrow the Job-To-Be-Done frame: Why Now, What This Unlocks, Who Has The Pain, Do Nothing. Use lettered options to compress decisions.

**Exit when:** the dialogue states one problem statement and one concrete pain point.

### Ground — anti-hallucination

**Job:** anchor every claim to evidence from code, docs, or prior research. When the user uses overloaded terms ("account", "session", "user"), pause and ask a canonical-term question. At the curdle atomic step, write resolved terms to the session's durable glossary at `.cheese/glossary/<slug>.md`. See `curdle.md` § Durable glossary. Downstream skills (`/cook`, `/age`, `/press`) can read these terms for naming consistency.

**On Ground entry:** resolve and load the project's cumulative domain model with `domain_model_target()` (`src/easy_cheese/shared/paths.py`). Complete the read-probe cascade before any write. First, probe the consumer wiki, shape-matched through `list_corpora` and confirmed through `wiki_has_model`. Then probe tracked `docs/domain-model*`, followed by `<project_corpus_root()>/domain-model*`. A listed wiki corpus does not win without a confirmed model. An existing file-store model wins over a wiki corpus without a confirmed model. The resolution mirrors the `adr_target()` *pattern* in `adr.md` § Resolution. It is dynamic, and the existing model always wins. If the probe is unreachable, degrade to "not loaded" and report it. Never block Ground because the probe is unreachable. The returned `wiki_reachable` provides this signal. `False` means no wiki probe occurred because no hook existed or the hook raised. In that case, announce "domain model not loaded from the wiki". Do not present the file-store result as the whole picture. The model is cross-session memory. The per-slug glossary is the branch-local handoff. **Challenge immediately** when a user term conflicts with an existing model entry. Ask: "the model defines X as …, you seem to mean Y — which is it?" Challenges are LIVE here. Defer model writes to the approval gate. Curdle owns the write; see `curdle.md`. Never write inline during Ground.

**Invariant:** never say "I think the code does X" without semantic source-code evidence gathered according to the [shared routing contract](../../cheese/references/code-intelligence-routing.md).

**Exit when:** every critical claim has a citation.

### Shape — option generation

**Job:** turn a grounded problem into 2+ candidate approaches with trade-offs. Always include **Do Nothing**. Present lettered options (`A/B/C/D`) for the user to select. The user chooses consequential forks; do not settle them. Give a one-line rationale for each option, not a verdict. Validate Cycle every critical assumption behind an option. Score options by the information they leave behind. Prefer the option that reduces the next maintainer's required knowledge or makes that knowledge more obvious.

**Exit when:** the user picks one option (→ Sketch). Return to Explore when no option survives.

### Sketch — interface lockdown

**Job:** lock modules, responsibilities, I/O contracts, and seams in pseudocode signatures. Run the shape check (`shape-check.md`) before drafting when the change touches multiple modules. Also run it before drafting when the change introduces a new public interface. Check signatures, semantic callers, and dependency blast radius for touched symbols. This check helps new seams follow existing conventions and bounds the impact. Print the shape-check summary block before any pseudocode. Single-module, internals-only sketches can skip the gate. Instead, note "shape check skipped: single-module change".

**Acceptance notation (EARS):** for every public seam, emit acceptance criteria in EARS form: `WHEN <trigger> THE SYSTEM SHALL <response>`. If the trigger cannot be stated precisely (e.g. pure internal utilities), fall back to prose with a `[prose-fallback]` marker.

**Concrete-seam rule:** a small seam has a complete function body of roughly 20 lines. For a small seam, write the full implementation instead of pseudocode. Use abbreviated signatures only when bodies are too large or depend on unresolved design unknowns.

**Exit when:** every public seam has a pseudocode signature or full implementation under the concrete-seam rule. Every acceptance criterion uses EARS form or has `[prose-fallback]`. Every cross-module call uses public interfaces, not internals. Record the shape-check verdict, or explicitly skip it under the gate above.

### Grill — adversarial clarification

**Job:** stress-test the chosen approach and sketched interfaces. Use **one grilled item per turn**, except for the clean-steelman batch below. For each `[AGENT-DECIDED]` item or design decision, produce at most a **steelman + tension statement**. Then present a **user fork**: uphold / amend-as-proposed / user's own call. Invoke the question primitive in [`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md). Use a real user turn. Do not render an `A/B/C/D` prose block and answer it yourself. Never self-issue verdicts for items that change the design. When the steelman fails cleanly and grilling finds nothing, you MAY batch-report items as upheld. When grilling produces an amendment, ask through the same primitive before adding the amendment to the ledger. Traverse decision branches and contract corners. Pause for a Validate Cycle when an unverified assumption appears.

**Exit when:** every branch and contract corner is touched and agent confidence ≥ user confidence.

### Diagnose — symptom inputs

**Job:** entry mode for stack traces and "X is broken". Phases:
`Build a Loop → Reproduce → Hypothesize (3–5 ranked, falsifiable) → Confirm root cause`.

**Phase 0 (Build a Loop)** is the core discipline. Agree on a fast, deterministic, falsifiable feedback technique BEFORE chasing hypotheses. Techniques include a failing test, curl/CLI script, headless browser, replay, bisection harness, or differential loop. The chosen loop becomes the Reproduction block in the bug-shaped spec. Thus, `/cook` can verify the fix against the same signal.

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
