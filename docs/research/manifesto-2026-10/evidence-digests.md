# Evidence digests (2026-10-18)

Six read-only sub-agents read the wheypoint records, the wiki, the research
corpus, and skillz-that-grillz. This file keeps the facts the manifesto and
its review depend on, with the record or page each fact came from. Work ids
refer to `~/.local/share/cheese/paulnsorensen-easy-cheese/work/<work_id>/`.

## 1. The rebuild thread and its forks

| Work id | Latest revision | Status | Next | What it holds |
| --- | --- | --- | --- | --- |
| `rebuild-easy-cheese-from-scratch` | rev-c1a85e43507b (8) | ok | culture | 22 open questions, 2 decisions, 14 directives, 10-fork dossier |
| `easy-cheese-contracts-simplify` | rev-d4db1d5e6d96 (11) | ok | affinage PR#774 | gates-first cut; draft stack 772 to 774 |
| `wheypoint-contract-simplify` | rev-90cbbec9791d (2) | ok | mold | five ranked cuts; CLI 15 to about 7 verbs |
| `wheypoint-milknado-seam` | rev-df6756bd3d99 (11) | ok | affinage PR#735 | pointer coupling F-1 to F-4; stack 733 to 735 merged |
| `journey-workflow-coverage` | rev-525cb6ea725f (1) | gated | affinage PR#822 | 174 journeys, 14 skills, PRs 822 to 825 |
| `age-beyond-default` | rev-9679f12d9ab7 (1) | gated | mold | 12 forks F1 to F12 parked since 09-12 |
| `age-vs-thermo-nuclear-review` | rev-f7454afeb4b6 (5) | ok | affinage PR#808 | reframe as 13th dimension |
| `culture-altitudes` | rev-f5cbdffe1e61 (1) | ok | hold | altitude navigation inside ordinary Culture, PR #780 |

Lineage: contracts-simplify forked from rebuild at rev-c1a85e43507b;
wheypoint-contract-simplify forked from contracts-simplify; the seam record
forked from rebuild on 2026-09-27 (decision `d-f32437bf170c`).

### Directives recorded in the user's words

Rebuild record (`v-*` entries):

- "I like the pyz, and i like the idea of having schemas and code thats exported and shareable."
- "My philosophy is still to limit nondetermism by using code but mostly to save token cost."
- "But i wonder how much weve overbuilt and if all the skills still make sense at the end of ghe year 2026."
- "we want to use cheese schemas for the actual main artifacts of spec -> curdplan -> execution/eval loop"
- "i want to have a wya for agetns to keep the shape of a spec / ideas in place like with our front-end so we can stop reprinting words. like an active idea iwth diagrams etc."
- "we want an iterative -> talk through things, build pieces and keep molding/culturing in parallel - more of a free form stream. sometimes just doing a few line edits aren't worth invoking a cook - you know? how do we handle that"
- "before we jump to skills, i think let's define the workflows- can you list them?"
- "I think the ultimate goal is to have cheese flow operate out of a network of wheypoints, but have various gates to trigger behavior like a striated mold process depending on how big the change is, and of course catching and fixing issues with cook and age. The high level workflow ergonomics are hard to test for"
- "we'll probably fork the tilth part into our own and come up with a new set of items"

Contracts record:

- "I think we need to extremely simplify here"
- "There are fair amount of gates that mostly create difficulties, so I think those are the first to go. We can re-add them later."
- "The high-level things that drive us are clearly wheypoint as the backbone, then specs, implementation plans, delivery plans, review-results i guess."
- "I think  we want to try to unifiy this in a way that doesnt force us to go through a bespoke mold cook age cure workflow"
- "ontology of records, which may have verying degrees of specs and decisions (depending on the size) - prototypes, specs, reviews, whathaveyou, they all get cooked using a curd plan (which cna be as simple as inline, or omitted if its trivial)"
- "I'm leaning toward, at least from a schema standpoint, having separate spec, plan, and review contracts at the least. Whether they're in their own record or not I'm not sure."

Seam record:

- "we want wheypoint records to be a durable and linkable, and pluggable into milknado ideally (should we bolt milknado's engine onto the type?)"
- "I want it to be a seamless integration"

Journey record:

- "/goal all high level workflows should have a journey in an open pr"

## 2. Measured facts

| Fact | Value | Source |
| --- | --- | --- |
| Sessions per skill | age 968, cook 525, plate 131, cure 124, briesearch 122, cheese 88, affinage 76, mold 69, press 64, pasteurize 56, wheypoint 44, melt 43, culture 27, hard-cheese 1, easy-cheese-setup 0 | `rebuild/measured/f-01-session-usage.md` |
| Harness share | about 85% of skill loads from omp | same |
| Full chain, n=36 | p50 3.4 h cook to last load, 1,517 tool calls, 129M cache-read tokens, p90 about 7x | `rebuild/measured/f-02-pipeline-cost.md` |
| Cache-read share | 95% or more of all tokens | same |
| Rework | 26% of chains run two or more age rounds (max 13); 17 of 52 chains plate before any age; p50 6 reviewer spawns before plate | same |
| Age reviewers | 51 of 83 sessions ran zero reviewers; 73 ran one or two | `rebuild/measured/f-03-wiki-decisions.md` |
| Parallel bursts | 0 same-second bursts in 609 spawns; no age run with 3 or more reviewers | wiki `analytics/fanout-patterns-2026-09-10.md` |
| Mold cost | median 320 tool calls and 443 minutes; 5 of 16 runs reach a spec write | wiki `decisions/leverage-is-the-ceremony-axis.md` |
| Prose adherence | about 1% adherence to hedged numbered steps; Codex runs phase skills 2 to 4x cheaper | wiki `analytics/skill-adherence-2026-08-30.md` |
| Model tier | 91% of Claude dispatches passed no model, so `inherit` hid the tier | wiki `research/subagent-model-selection-portability.md` |
| Payload validation | zero runtime validation failures in 551 sessions, about 43k tool calls | wiki `adr/writer-view-boundary-simplification-001.md` |
| Fan-out stack | about 5,200 lines (run_fan 1,138; remediation 469; checkpoint 388; recovery 339; review_lock 650; workflow.py 2,235) | `rebuild/rebuild-easy-cheese-from-scratch.md` |
| Prose | 3,399 SKILL.md lines plus 11,760 reference lines; boilerplate repeats in 10 skills | `rebuild/session-2026-09-27-skills-schemas-cli.md` |
| Contracts | 22 registered; contracts.py 4,202 lines; compat.py 683 lines, no production caller | `rebuild/session-2026-10-03-workflows-stream.md` |
| Bundle verbs | 115 across 13 bundles; 77 deterministic, 13 routing, 8 render-only, 17 with no prose reference | same |
| Archives | 13 pyz, about 40 MB; mold carries 8.2 MB of canvas assets | same |
| Wheypoint size | about 9.2k shared LOC, 2.0k CLI, 14k tests; 40% of the projection is metadata, lineage, or dossier | `wheypoint-contract-simplify` record |
| Curd exhaustion | 5 of 6 curd dispatches exhausted context; estimates were systematically low | `.cheese/notes/deterministic-fanout-sizing-resume.md` |
| Review size effect | 70 to 90% defect detection at 200 to 400 lines; about 28% above 1,000 lines | wiki `research/language-reviewability-evidence.md` |
| Repo today | 16 skills; 15.6k markdown lines under skills/; 50.9k Python under src/; 77k test lines; 265 commits in 90 days; every phase skill touched 98 to 128 times | `git log`, `wc` on 2026-10-18 |
| Open PRs | 50 open; 26 older than one month | `gh pr list` on 2026-10-18 |

## 3. Decisions already on record

- Shape B (milknado imports easy-cheese-schemas at runtime): decided
  2026-08-28, not executed; conflicts with milknado ADR-003. Source:
  `graph-flow-schemas` record and `rebuild/session-2026-09-27-wheypoint-milknado-grounding.md`.
- Pointer coupling, shared schemas, separate stores: user selection
  2026-09-27 (seam record F-1). The merged SQLite store was rejected on lock
  and lifecycle grounds.
- Gates are the first cut (`d-c4f8f176780b`); candidates mold-cook-approval,
  mold-cook-handoff, cook-preparation-result, handoff-pointer,
  normalization-receipt, phase-contract.
- Three-layer removal stack published as draft PRs 772, 773, 774
  (`d-0622e1c5c45d`).
- Wheypoint simplification as a separate fourth PR through /mold
  (`d-2fe860d12162`). Branch `worktree/wheypoint-contract-simplify` carries
  schema-5 commits 256cd112 and b8cd77d6, unmerged.
- Keep WorkRef, WorkEdge, EdgeKind as schema exports (seam, 2026-09-27). The
  wheypoint-contract review two weeks later ranks EdgeKind 9 to 2 and the
  link, unlink, shape, backlinks verbs as cut moves.
- hard-cheese retained (wiki `adr/hard-cheese-retained-001.md`): retire only
  with consumer-population evidence; local telemetry can demote, not retire.
- Deterministic fan-out sizing (wiki `adr/deterministic-fanout-sizing-003.md`):
  judgment decides what a diff means; code decides how many agents look.
- Strict version equality, migration registry removed (wiki
  `adr/writer-view-boundary-simplification-001.md`).
- Age reframe dimension and third protected subject (PR #808; policy
  age-review-plan.v2).
- Altitude navigation is part of ordinary Culture, not a mode
  (`culture-altitudes` `d-bea7b6c972d5`).
- Fork cards and Explain more in mold (PR #809; `mold-fork-questions`).

## 4. Open forks on record

From the rebuild record (22 open questions, condensed):

- Design-target harness: omp and Pi, or Claude Code.
- Fan-out stack: keep, or single-writer default.
- Spec phase: separate, lighter plan, or harness plan mode.
- Skill cut list; de-slop home (454 sessions outside the repo).
- Living-spec artifact: typed markdown with section ids, canvas, or wiki page.
- Which of 22 contracts survive; register spec, eval-result, artifact-ref.
- Canvas: feedback only, or editing surface.
- Build: own workflow, or a stream that starts ready.
- Promotion line to full mold; inline-edit line; edit under in-flight piece.
- Six-workflow list completeness versus the 15-workflow map.
- Which of 115 verbs stay, merge, or move to a nested noun-verb CLI.
- Grader design Q1 to Q6 plus the mold grader.

From the contracts record (12 open questions, condensed):

- One Record with typed entries, or separate Spec, Plan, Review contracts.
- Delivery plan as optional fields on Plan pieces.
- Public-contract survival test A, B, or C.
- Compiled context: projection (ADK) or ready queue (Beads).
- Plan weight: code-scored (Taskmaster) or agent choice (OpenSpec lite).
- Whether fan-out-bound contracts leave with the stack.
- Whether anything consumes schemas.easy-cheese.dev.

From age-beyond-default: F1 parallel dispatch, F2 n=1 verifier, F3 to F10
rubric ports, F11 benchmark, F12 ordering. Blocker: n>1 never ran in
parallel in 60 days; age and cure SKILL.md sit at 3,593 and 3,585 of 3,600
tokens.

## 5. Stale items found

- Wiki says archives are committed on `main`; PR #807 moved them to `dist`.
- Wiki `architecture.md` and `skill-parity-analysis.md` say ten age
  dimensions; there are thirteen after PR #808.
- Wiki `red-gate-environment-gotchas.md` describes a `red_gate` import
  removed in PR #560; five pages still mention RED-gate.
- 15 wiki pages wait on the contracts stack (contracts record follow-ups).
- `ground-check` cannot resolve `path:line` under a dot directory other than
  `.cheese` (`src/easy_cheese/skills/briesearch/ground_check.py:94`).
- Routing policy sends any leverage trigger to full mold; `tiers.md:19` only
  rules out Quick.
- `tools/wedge/pyproject.toml:8` pins skillz-that-grillz at a commit with a
  `lib/` layout; upstream now uses `packages/`.
- `compat.py:482-683` adapter has no production caller.
- `skills/ultracook/` redirect ships 410 to 681 reference lines that cook
  still reads.
- PRs 478 and 515 (typed handoff) are superseded by 772 to 774 (removes it).

## 6. skillz-that-grillz

- One published skill, `skillz`; libraries `wedge`, `fromargs`,
  `agent-session-analytics`; the `actions/wedge` GitHub Action.
- Journey spec approved 2026-10-10: `kind: journey`, hidden `brief`,
  simulated user, hybrid grader (command gate, then judge), budget 1000
  calls and 28,800 s, isolation check per turn.
- Autoimprove spec approved 2026-10-03: `evals/autoimprove.json` per skill,
  draft until the user approves; graders exact-json, judge, command, hybrid;
  GEPA pinned at 0.1.4; `claude --restricted -p`.
- Merged: #347 harder train journeys, #348 cases-too-easy stop and scaffold.
  Open: #352 to #359, none about journeys as a subject.
- easy-cheese's only dependency on skillz is the build-time wedge pin.

## 7. Research verdicts that bear on the tenets

- Every surveyed pack is spec-then-implement; none publishes a schema
  catalog or a separate adversarial-test phase
  (`rebuild/rebuild-easy-cheese-from-scratch.md`).
- Anthropic: multi-agent costs about 15x chat tokens and fits coding poorly;
  harness assumptions go stale as models improve.
- Code execution over MCP cut tokens 98.7%; programmatic tool calling 37%.
- Evidence for splitting spec from plan is stronger than for a standalone
  review artifact (`adjacent/major-workflow-artifact-contracts.md`).
- No surveyed source combines typed work records, per-task context
  compilation, and no fixed phases (`adjacent/context-compilation-work-records.md`).
- End-to-end GEPA fitness is infeasible at about 2,040 agent hours per run;
  gates are replayable only when inputs persist, and only press persists
  any; judges as targets get hacked (`adjacent/gepa-*.md`).
- Böckeler (martinfowler.com): "I'd rather review code than all these
  markdown files"; agents ignore spec instructions in large contexts.
