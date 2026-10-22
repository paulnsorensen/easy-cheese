# easy-cheese manifesto review (2026-10-18)

> **Evidence, not decisions.** The canonical tenets and the owner's rulings
> live in `.hallouminate/wiki/easy-cheese-manifesto.md`. Section 2 (the
> simplest easy-cheese) and the skill keep, shrink, fold, park, and delete list
> are proposals; skill cuts are deferred. Section 5 (open forks) and section 7
> (suggested order) are superseded by the rulings of 2026-10-18 to 2026-10-22.
> Some facts below are stale against `main`: #776 landed schema 5, and
> #772 to #774 merged on 2026-10-15.

Read-only culture pass. Sources: the
rebuild record (rev 8), the contracts and wheypoint-contract records, the seam
record, the journey record, the age records, eleven older wheypoints, the
wiki (architecture, invariants, parity, ADR families, analytics, research),
the rebuild research cluster, four adjacent research clusters, and the
skillz-that-grillz repo and cheese dir. Six read-only sub-agents gathered the
evidence; this file holds the synthesis. The copied reports, measured facts,
diagrams, and record-level digests are in this directory.

## 1. Verdict per tenet

| # | Tenet | Verdict | Why |
|---|---|---|---|
| 1 | Research and grounding | Spot on, incomplete | The wiki rots as fast as the prose. Freshness needs a rule. |
| 2 | Diffusive shaping | Spot on, undecided | The Stream design answers it. Six forks block it. |
| 3 | Opinionated backbone | Spot on, wrong enforcement | Opinions live in prose. Prose adherence is about 1%. |
| 4 | Wheypoint network and wiki | Half right | The store is rich. The views and links are thin. |
| 5 | Reviewability | Spot on, least built | No review-time briefing exists. hard-cheese is a quiz, not a brief. |
| 6 | Predictable behavior | Spot on, mechanism changed | Typed gates were cut by your own decision. Typed exits stay. |
| 7 | Parallelism | Dream and data disagree | On by default, zero measured bursts. |
| 8 | Pluggability | Spot on, floor undefined | 85% of use runs on a harness with no sub-agents. |
| 9 | Determinism | Spot on, best executed | The decisions that matter most still leave no record. |
| 10 | skillz powered | Right, wrong order | Journeys grade behavior. Nothing grades altitude or mold. Simplify first. |
| 11 | Scalability | Spot on | Both failure modes measured. One rule fixes both. |
| 12 | UI native | Agree, over-invested | Canvas work dominates recent PRs while core forks sit open. |

## 2. The simplest easy-cheese that satisfies the recorded use cases

This is a synthesis of agent recommendations and your directives. Nothing here
is decided unless the manifesto lists it under "Already decided".

**Artifacts (four, plus the backbone).**

- Wheypoint record: continuity. Keep compare-and-set, protected entries,
  derived status, next_action, the exported schema, the pyz. Cut lineage
  copies, the dossier, the parent-digest chain, and 7 of 9 edge kinds (the
  five ranked moves in `wheypoint-contract-simplify`).
- Shape (spec): typed markdown with stable section ids, patched in place.
  The canvas renders it. The wiki page links to it.
- Plan (curd plan): omitted, inline, or full by a code-scored size. Delivery
  (PR grouping, branch, stack order) folds in as optional fields on pieces.
- Review: findings plus coverage. Diagnosis becomes a review kind.
- Eval result: deferred until a grader exists.

**Workflows (six).** Stream, Build, Review, Fix a bug, Land, Research. Shared
steps: publish, resume, spike, decision record. Design-then-build and
think-only fold into Stream. Skills map onto workflows, not the reverse.

**Skills (the measured core plus user-typed entries).**

- Keep: cook, age, cure, plate (most sessions); briesearch, affinage,
  wheypoint, pasteurize, melt (user-typed, distinct jobs).
- Shrink: mold becomes the shape doc, fork cards, and the promotion gate.
- Fold: culture becomes the "talk" move of Stream; altitude framing lives
  there (PR #780 already does this). press folds into cook per curd (PRs 786
  to 788 already do this).
- Re-purpose or park: hard-cheese becomes the review-time brief, or parks.
  easy-cheese-setup becomes a capability probe that routing reads.
- Delete: ultracook (move its two files cook still reads into
  cook/references).

**CLI.** One archive, or a few, not thirteen. Nested noun-verb surface
(47 shared entries collapse to 15). Keep the 77 deterministic verbs. Delete
the 17 verbs no prose references. Make the 13 routing verbs write a receipt.

**Gates.** Receipts in code only: size score, leverage, route. Each leaves a
record so a grader can replay it. No gate contract between phases.

**Fan-out.** Single-writer cook by default. Fan opt-in when the size score
asks. milknado by pointer (decided 09-27). The harness Workflow tool is an
alternate executor, not a dependency.

**Stores.** Wiki in git. Work records and research under the durable cheese
path. `.cheese/` transient. ArtifactRef with `file:`, `xdg:`, `wiki:`, and
`milknado:` schemes. No SQLite merge.

**Evals.** Journeys per workflow (PRs 822 to 825). Seeded-defect benchmark for
age. Fail-to-pass for cook. Mold and altitude graders are open design work.

**UI.** The canvas renders the shape doc and returns pins and answers. It
never writes the spec.

## 3. Per tenet: discussed, research, challenge, open

### T1 Research and grounding

- Discussed: briesearch (122 sessions), brie-ground, researcher sub-agent,
  hallouminate grounding in mold and age, re-pin at resume
  (`d-2bfa3f20878c`).
- Research: Anthropic says harness assumptions go stale as models improve.
  The rebuild research run cost 46 searches, 24 extracts, 5 researcher
  spawns.
- Challenge: the tenet aims at the model. The wiki has the same defect. Pages
  describe a deleted `red_gate` import, ten dimensions, archives on `main`.
  Fifteen pages wait on the contracts stack. `ground-check` cannot resolve
  `path:line` under any dot directory except `.cheese`
  (`ground_check.py:94`).
- Open: who owns wiki freshness; whether post-PR write-back moves onto
  `/plate` (open follow-up in `post-pr-wiki-writeback.md`).

### T2 Diffusive shaping

- Discussed: Stream mechanics (10-03), promotion line, inline gate, pieces
  cooked in their own worktree while molding continues, fork cards and
  Explain more (#809), altitude navigation in culture (#780),
  `/cook --prototype`.
- Research: every surveyed pack is spec-then-implement. Böckeler: "I'd rather
  review code than all these markdown files". OpenSpec is phase-free. Kiro
  Quick Spec keeps the same three files. Evidence for splitting spec from
  plan is stronger than for a standalone review artifact.
- Challenge: "identify as many unknowns as possible" is in tension with mold
  at 443 minutes median and 5 of 16 runs reaching a spec. Two ceremony rules
  conflict (routing-policy versus tiers.md:19). Culture, mold, pasteurize,
  and prototype are four skills today; the records describe them as four
  moves on one shape doc.
- Open: the six Stream forks (canvas role, build as workflow, promotion line,
  inline line, edit under in-flight piece, workflow list completeness).

### T3 Opinionated backbone

- Discussed: outer-TDD gates 001 to 005, `--auto` chain capped at two cure
  passes, deterministic sizing, taste-test lenses, 13 age dimensions
  (reframe added in #808), locked fix decisions (#667), sliced-bread
  reference in the global agent instructions, PRs 786 to 788 reshaping cook
  and press.
- Research: GitClear: refactoring moved from 21% to 3.8%, duplication up 81%.
  Codex runs phase skills 2 to 4 times cheaper than Claude on the same files.
- Challenge: the altitude you describe is the one thing no grader measures.
  The loop can spin (max 13 age rounds). The agent recommendation was to
  attack parent context growth before any other cost, and that is still
  undone. The 12 age-beyond-default forks have sat since 09-12 behind one
  blocker: n>1 has never run in parallel.
- Open: the altitude grader; the age-beyond-default ordering fork (F12).

### T4 Wheypoint network and wiki

- Discussed: continuity kernel ADRs 001 to 004, seam decisions F-1 to F-4,
  fork, link, shape, backlinks verbs (#733 to #735), the five ranked cuts
  (schema 5 on a branch, unmerged), context-compilation research, PR #764
  (wheel loop skill backed by wheypoints).
- Research: Google ADK frames context as a compiled view over typed events.
  Beads has ten edge kinds and a ready queue. No surveyed source combines
  typed records, per-task compilation, and no fixed phases.
- Challenge: the seam PRs built nine edge kinds and four verbs in late
  September. The wheypoint-contract review ranked most of them for deletion
  two weeks later. That is the over-iteration you fear, in one record.
  Work records are local and not in git, so "connect ideas from any session"
  only holds on one machine. The milknado adoption contract points at the
  non-authoritative `.cheese/notes` mirror.
- Open: compiled view (projection versus ready queue); which store is the
  share surface across machines; the wheypoint cut scope.

### T5 Reviewability

- Discussed: hard-cheese retained (ADR: retire only with consumer-population
  evidence), question targeting 001 to 003, canvas ADR 001 to 008, plate
  topology by cohesion, PR #753 Mermaid, language-reviewability evidence.
- Research: diff size dominates language choice. Author annotation of
  non-obvious changes raises detection.
- Challenge: hard-cheese gates the user with a quiz. The tenet asks for a
  brief: shape, expectations, why. Those are different artifacts. "Comprehension
  debt" appears in no record; this is a new framing. The cheapest native
  medium is the agent commenting on its own PR, and nothing does that.
- Open: what hard-cheese becomes; the brief format; whether stacking is
  driven by cohesion alone or by review budget (200 to 400 lines).

### T6 Predictable behavior

- Discussed: handback and handoff statuses, compiled TransitionRegistry,
  writer views, strict version equality (migration registry was empty since
  introduction), gates-first cut, stack 772 to 774.
- Research: Devin uses user-defined structured session output. No workflow
  converges on a universal Spec/Plan/Review schema.
- Challenge: 22 contracts, 115 verbs, and a 4,202-line contracts file did not
  buy predictability. Zero validation failures in 551 sessions means the
  schemas are either followed or too loose to matter. The unpredictability
  that hurts is prose adherence, and types do not fix that. Fewer, bigger
  contracts plus code routing plus evals is the path.
- Open: record ontology (you lean separate Spec, Plan, Review); embed versus
  link; the public-contract survival test.

### T7 Parallelism

- Discussed: ultracook retired into the cook fan pathway, fan on by default,
  agent recommendation single-writer default, milknado by pointer, Shape B
  decided 08-28 and never executed, milknado ADR-003 conflict, the harness
  Workflow tool and milknado-worker agent in this harness.
- Research: Anthropic: multi-agent costs about 15 times chat tokens and fits
  coding poorly. Review fan-out: `/age` n=5 is "on paper only".
- Challenge: before any milknado wiring, run one fan and one single-writer
  cook on the same spec and measure. Five of six curd dispatches exhausted
  context because curds were too large; a `MAX_CURD_SURFACE` was proposed and
  never built. Your double-diamond idea is new and already half-built by PRs
  786 to 788 (press per curd).
- Open: the fan-out fork (F2, open since 09-21); whether milknado or the
  harness Workflow tool is the executor; `MAX_CURD_SURFACE`.

### T8 Pluggability

- Discussed: portability is the design center, one shared portability
  reference, harness-neutral `cheap|default|powerful` model tiers, OMP paths
  broken as written (`CLAUDE_SKILL_DIR`), hard-cheese kept for external
  consumers.
- Research: Claude Code ships native `/code-review`, plan mode, PR follow-up.
  Copilot reads AGENTS.md from the PR head. Pi has no sub-agents or plan
  mode. SKILL.md portability is disputed and has no primary spec.
- Challenge: on 85% of sessions, tenets 7 and 2 (background pieces) silently
  no-op. "Predict what the user has" should be code: a capability probe at
  session start, stored, read by routing. 91% of Claude dispatches passed no
  model, so the tier was hidden.
- Open: the design-target harness fork.

### T9 Determinism

- Discussed: verb inventory, nested CLI, single archive, routing in code,
  deterministic sizing ("judgment decides what a diff means; code decides how
  many agents look at it").
- Research: code execution over MCP cut tokens 98.7%; programmatic tool
  calling cut 37%.
- Challenge: tier, leverage, and route are prose with no record. The GEPA
  grader research says gates are replayable only when inputs persist, and
  only press persists any. This is the precondition for tenet 10.
- Open: single archive versus thirteen; nested CLI; which routing verbs
  write receipts.

### T10 skillz-that-grillz powered

- Discussed: journeys (approved spec 10-10, merged #347 and #348), autoimprove
  contract (`evals/autoimprove.json`, draft until approved), hybrid grader,
  GEPA 0.1.4, `claude -p --restricted`, 174 journeys in PRs 822 to 825, GEPA
  workflow research with seven open grader forks, the cook optimization loop
  blocked by a run.py contract mismatch.
- Research: judges as optimization targets get hacked (pass rate 0.72 to
  0.94 while true accuracy stayed 0.20). Side info gives about 6 times fewer
  rollouts. LLM-simulated users are too cooperative.
- Challenge: the research itself says do not start the optimizer before the
  fan-out and cut-list forks settle. Journeys take hours per run. The wedge
  pin points at a `lib/` layout that skillz no longer has.
- Open: graders Q1 to Q6 plus mold; first live journey run and budget; the
  wedge pin.

### T11 Scalability

- Discussed: mold tiers, leverage-is-the-ceremony-axis, sizing ladder
  n in {1, 2, 5}, inline gate as risk plus size plus context cost.
- Challenge: the two-rule conflict is exactly the bug this tenet forbids.
- Open: the inline-edit line; the promotion line.

### T12 UI native

- Discussed: canvas ADR 001 to 008, living-spec fork (typed markdown source,
  canvas projection), feedback-only leaning, PR #810 tailnet host.
- Challenge: the canvas renders hand-authored JSON, not the spec. It stores
  any JSON object. Four of the last fifteen open PRs fix canvas test races.
- Open: canvas role fork.

## 4. Hard look: stale and over-iterated

1. Mold. 128 commits in 90 days. 3,076 Python lines plus 8.2 MB canvas
   assets. Median 443 minutes, 31% reach a spec. Two conflicting ceremony
   rules. Four of the last fifteen open PRs fix canvas test races.
2. Contracts. 22 to 19 in flight. contracts.py is 4,202 lines. compat.py is
   683 lines with no production caller. Stack 772 to 774 has been draft since
   10-04. The wheypoint cut (schema 5) sits on a branch and contradicts seam
   PRs merged two weeks earlier.
3. Fan-out stack. About 5,200 lines, on by default, zero measured parallel
   bursts, repeated fix PRs.
4. Wiki staleness. Archives on `main` versus `dist`; ten versus twelve versus
   thirteen dimensions; deleted `red_gate` import; fifteen pages pending.
5. Open PR debt. 50 open PRs; 26 older than a month. Some are superseded by
   later decisions: #478 and #515 (typed handoff) versus 772 to 774 (removes
   it); #571 (retire overlap ratchet); #526 and #533 (wiki docs).
6. Skill prose. 15.6k markdown lines under `skills/`. Every phase skill was
   touched 98 to 128 times in 90 days. About 30 lines of boilerplate repeat
   in ten skills, so every cross-cutting edit ripples through all of them.
7. Residue. ultracook redirect plus 410 to 681 reference lines cook still
   reads. hard-cheese: one local session. easy-cheese-setup: zero sessions.
8. skillz pin. `tools/wedge/pyproject.toml:8` pins a commit with a `lib/`
   layout; upstream moved to `packages/`.
9. milknado. Shape B decided 08-28, never executed. ADR-003 conflicts. The
   local checkout was 24 commits stale when the seam was grounded.
10. Age. Thirteen dimensions; the benchmark covers eight; nothing verifies at
    n=1; twelve forks parked since 09-12.

## 5. Needs more clarity (consolidated open forks)

| Id | Fork | Open since | Your recorded lean |
|---|---|---|---|
| A | Design-target harness: omp and Pi, or Claude Code | 09-21 | omp and Pi first |
| B | Fan-out default: single-writer or keep the stack | 09-21 | single-writer |
| C | Record ontology: one Record with typed entries, or Spec, Plan, Review contracts; embed or link | 10-04 | separate contracts |
| D | Stream mechanics: six forks | 10-03 | listed in rebuild record |
| E | Skill cut list | 09-21 | none recorded |
| F | Grader design: Q1 to Q6 plus mold grader; first live journey run | 10-03 | fork tilth benchmark (decided) |
| G | Wheypoint cut scope: which of five moves | 10-14 | none recorded |
| H | CLI shape: one archive or thirteen; nested noun-verb | 09-27 | none recorded |
| I | Reviewability artifact: what hard-cheese becomes; brief format | new | keep hard-cheese |
| J | milknado: execute Shape B; amend ADR-003 | 08-28 | pointer coupling (decided) |

## 6. New on 2026-10-18 (not in any record)

- "Comprehension debt" as the name for the reviewability problem.
- Review as a double diamond: cook some seams, review others, refine.
- PR stacks with active comments and Mermaid as the justification layer.
- "Let them `/cheese` everything and we route it forever."
- "Diffusive" paths from idea to implementation.
- UI for the most novice users, explicitly optional.
- The wedge pin drift (found today, not raised by you).

## 7. Suggested order

1. Decide A, B, and C. Every other fork depends on at least one of them.
2. Land 772 to 774 and the wheypoint cut, or close them. Two weeks of draft
   is decision debt.
3. Apply the one ceremony rule in code with a receipt. This resolves the
   routing-policy versus tiers conflict and makes tier, leverage, and route
   gradeable.
4. Flip fan-out to opt-in. Run one fan versus single-writer measurement.
5. Define the review-time brief. Decide what hard-cheese becomes.
6. Approve the journey contracts. Run one live journey per workflow.
7. Then, and only then, start the optimizer.
