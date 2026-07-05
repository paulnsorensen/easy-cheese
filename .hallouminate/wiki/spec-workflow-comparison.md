# Spec / brainstorm-to-spec workflow comparison

The takeaway up front: `/mold`, the older `spec.md` command, Matt Pocock's
`grill-with-docs`, and Superpowers' `brainstorming` skill have **independently
converged** on the same five moves — (1) interrogate one question at a time,
(2) always pair each question with a *recommended* answer, (3) ground claims
against the actual codebase before deciding, (4) enforce a hard approval gate
before any code, (5) emit a durable spec artifact that drives implementation.
They are siblings with the same DNA; the differences are about *where each
spends its rigor*.

This page captures a `/briesearch` comparison run (2026-06-13) so the next agent
shaping `/mold` doesn't re-research the field. Sources are cited inline by URL.

See also: [workflow-invariants](./workflow-invariants.md) (the cheese pipeline
and two-key handshake), [architecture](./architecture.md).

## Where each workflow spends its rigor

- **Matt Pocock** — *fidelity escape hatches.* When a question can't be answered
  by talk, drop into a throwaway `/prototype`, capture the answer (not the
  code), then resume grilling. Also unique in treating model-tier and
  context-window hygiene as first-class.
- **Superpowers (Jesse Vincent / obra)** — *enforceability.* The process is
  encoded as a Graphviz dot-graph inside the SKILL.md so the only legal exit
  node is `writing-plans`. Thesis: "Prose is documentation. Checklists and
  graphs are instructions."
- **`/mold`** — *anti-drift.* The agent-introduced-scope grep gate (every
  distinguishing noun in the spec must trace to a literal user message) is a
  mechanic **none of the others have**, plus the formal two-key handshake and
  shape-check blast-radius numbers.
- **`spec.md` (older home-grown cmd)** — *justification.* "Beat 0: Defend the
  Why" (JTBD, Why Now, Do Nothing) is a mandatory gate before design starts.

## Master comparison table

| Workflow | Maker | Brainstorm-first gate? | Question style | Codebase grounding | Approval mechanism | Artifact + path | Phase sequence | Distinguishing mechanic |
|---|---|---|---|---|---|---|---|---|
| **`/mold`** (cheese-flow) | this repo | Yes — no code, hands to `/cook` | One-at-a-time (Grill), lettered options (Explore), always recommends | Mandatory: `cheez-search` callers + `tilth_deps` shape-check, verdict low/med/high | **Two-key handshake** (explicit user verb + agent coherence checklist) | `.cheese/specs/<slug>.md` | Explore→Ground→Shape→Sketch→Grill→Diagnose→Curdle | **agent-introduced-scope grep gate**; blast-radius numbers gate Grill |
| **`spec.md`** (older home-grown) | this repo | Yes | Lettered A/B/C/D ("1A, 2C"), 3-6 round Q-research-Q loop | 4 parallel research agents in round 2 (cheez-search, Serena, GH) | Beat-0 "Defend the Why" gate; uncertainty markers | ~800-word prose spec, `.claude/specs/<slug>.md` + opt. GH issue | Beat 0 (Why) → Ask → Research → Summarize loop | **"Defend the Why"** (5 JTBD framing questions) as hard pre-gate |
| **Matt Pocock `grill-with-docs`** | Matt Pocock (aihero.dev) | Yes — grill before PRD | **One at a time, recommends each answer**, explores codebase instead of asking when it can | Challenges input against `CONTEXT.md` glossary; writes ADRs inline | Conversational; PRD synthesized at end via `/to-prd` | `CONTEXT.md` + ADRs → PRD → GH issues | Idea→Research→Prototype→Grill→PRD→Issues→Execute→QA | **`/prototype` escape hatch** for "ungrillable" questions; canonical-term challenge |
| **Superpowers `brainstorming`** | Jesse Vincent (obra) | **Hardest gate**: "Do NOT…take any implementation action until…user has approved" | One question per message, prefer multiple-choice | Step 1 explores files/docs/commits; 2-3 approaches w/ trade-offs | User approves each design section; spec self-review checklist | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (committed) | brainstorm→worktrees→writing-plans→execute(TDD)→review→finish | **dot-graph enforcement** — only legal exit node is `writing-plans` |
| **GitHub Spec Kit** | GitHub | No (constitution-first, not ideation) | Slash-command driven | Via constitution principles | Phase artifacts reviewed | `spec.md`/`plan.md`/`tasks.md` in `.specify/` | constitution→specify→plan→tasks→implement | **`constitution.md`** governing doc referenced by every phase |
| **AWS Kiro** | AWS | No | IDE prompt | IDE-integrated | Human approval gate between each phase | `requirements.md`/`design.md`/`tasks.md` | requirements→design→tasks→implement | **EARS notation** (`WHEN…THE SYSTEM SHALL…`) → property tests |
| **BMAD-METHOD** | bmad-code-org | **Yes** (`/bmad-brainstorming`) | Per-persona | Per-persona | Document-driven persona handoffs | `product-brief.md`/`PRD.md`/`architecture.md`/stories | brainstorm→PRD→architecture→stories→code | **19+ named agent personas** (Analyst/PM/Architect…) |
| **Taskmaster AI** | eyaltoledano | No | PRD-driven | `--research` web grounding | Dependency graph gates task order | `.taskmaster/` JSON tasks | PRD→parse→expand→next_task | **dependency-aware task graph** |
| **Agent OS v3** | Brian Casel (Builder Methods) | No (enhances plan mode) | Host agent's plan mode | **Standards discovery/injection** | Host plan-mode approval | `agent-os/product/*.md` | discover→inject→shape→implement | **standards management** (build to team conventions) |
| **OpenSpec** | Fission-AI | No (brownfield-first) | Slash commands | Delta-based | Three-phase state machine | `openspec/changes/` (proposal/specs/design/tasks) | propose→apply→archive | **strict propose→apply→archive state machine** |
| **Tessl** | Tessl (Guy Podjarny) | No | Dev- or AI-written spec | Spec Registry usage specs | Tests as hard guardrails | spec is source-of-truth; code is regenerable | define spec → agents code against spec+tests | **spec-as-source** (code stamped GENERATED, regenerable) — Framework closed beta as of mid-2026 |

## Deep dive — Matt Pocock

Public skill set: `github.com/mattpocock/skills`. End-to-end model is:
Idea → Research (`research.md`) → Prototype → Grill → PRD → Kanban (GH issues) →
Execute → QA (<https://www.aihero.dev/my-7-phases-of-ai-development>).

Two mechanics worth stealing:

1. **`grill-with-docs`** — literal prompt:
   > "Interview me relentlessly about every aspect of this plan until we reach a
   > shared understanding. Walk down each branch of the design tree, resolving
   > dependencies between decisions one-by-one. For each question, provide your
   > recommended answer. Ask the questions one at a time. If a question can be
   > answered by exploring the codebase, explore the codebase instead."
   (github.com/mattpocock/skills/blob/main/skills/engineering/grill-with-docs/SKILL.md)
   The `-with-docs` variant adds glossary discipline: when your term conflicts
   with `CONTEXT.md`, it calls it out and proposes a canonical term, writing
   ADRs inline. **Nearly identical to `/mold`'s Grill + Ground canonical-term
   resolution** — independent convergence.
2. **`/prototype` as a grilling escape hatch** — on an "ungrillable" question
   (UI feel, ambiguous state model) stop talking and build a throwaway: either a
   tiny terminal app for a state machine/reducer, or several switchable UI
   variations on one route. The keeper is *the answer*, captured in an
   ADR/NOTES.md, not the code; then resume grilling
   (<https://www.aihero.dev/skills-prototype>;
   <https://www.aihero.dev/things-people-get-wrong-with-grill-me-and-grill-with-docs>).
   `/mold` has no equivalent — Diagnose builds a reproduction loop, but there is
   no "build to resolve a design unknown" branch.

Sharp opinions (talk transcript, finance.biggo.com/podcast/e7209c094224b09c):
pure spec-to-code degrades fast ("first passable, third was garbage" — software
entropy); **codebase quality is the ceiling** on agent output (Ousterhout deep
modules); use a *smart* model for grilling and a smaller one for implementation;
never clear context just to write the PRD ("throwing away all your design
work"); keep grilling under ~120k tokens (the model "dumb zone"). Work is sliced
into vertical "tracer bullet" issues (cross-layer, not horizontal) forming a DAG
for parallel agent execution. The "design tree" concept cites Brooks' *The
Design of Design*; ubiquitous language cites Evans' *DDD*.

Other published skills (June 2026): `grill-with-docs`, `grill-me`,
`domain-model` (now the recommended front-of-workflow step), `to-prd`,
`to-issues`, `prototype`, `handoff`, `tdd`, `improve-codebase-architecture`,
`triage`, `zoom-out`, `diagnose`.

## Deep dive — Superpowers (Jesse Vincent / obra)

The `brainstorming` skill is the **hardest pre-implementation gate** reviewed:
> "Do NOT invoke any implementation skill, write any code, scaffold any project,
> or take any implementation action until you have presented a design and the
> user has approved it."
(raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md).
A one-liner utility goes through the same gate as a platform — there's a named
anti-pattern section, "This Is Too Simple To Need A Design."

The 9 steps: explore context → (optional visual companion, requires consent) →
ask clarifying questions **one at a time, prefer multiple-choice** → propose 2-3
approaches with a recommendation → present design in sections, approve each →
write `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (committed) → 4-item
spec self-review → user reviews file → invoke `writing-plans`.

Distinguishing insight: **enforceability through structure**. In v4.3.0 Jesse +
Claude found prose descriptions of good process were being rationalized away. The
fix wasn't better prose — it was encoding the process as a numbered checklist
plus a Graphviz dot-graph *inside the SKILL.md*, where the only exit node from
the brainstorm subgraph is `writing-plans`
(blog.fsck.com/agent-blog/2026/02/12/superpowers-v4-3-0). Stated principle:
"Prose is documentation. Checklists and graphs are instructions."

Full pipeline: `brainstorm → using-git-worktrees → writing-plans →
executing-plans | subagent-driven-development → (TDD red/green per task) →
requesting-code-review → finishing-a-development-branch`. The plan from
`writing-plans` carries a fixed header (Goal / Architecture / Tech Stack) and an
agentic-worker instruction; tasks are TDD red→green and handed to a fresh
subagent per task (recommended) or inline execution.

Design philosophy (blog.fsck.com/2025/10/09/superpowers): "If Claude thinks
you're trying to start a project or task, it should default into talking through
a plan with you before it starts down the path of implementation."

## How the two home-grown skills relate

`spec.md` and `/mold` are the **same lineage** — `spec.md` reads like an earlier
parallel design that `/mold` refined:

- `spec.md`'s "Beat 0: Defend the Why" (JTBD / Why Now / Do Nothing) → survives
  as `/mold`'s **Explore mode** JTBD frame and the mandatory "Do Nothing always
  included" in Shape.
- `spec.md`'s lettered A/B/C/D options → `/mold` keeps lettered options in
  Explore.
- `spec.md`'s round-2 parallel research agents → `/mold`'s Validate Cycle +
  sub-agent context gate (now budgeted: 2 `/briesearch` calls per session).
- `spec.md`'s `[?]` / `[TBD]` / `[BLOCKED]` markers → carried verbatim into
  `/mold`, plus a new `[CONFLICT]`.

What `/mold` **adds** that `spec.md` lacks: the two-key handshake
(`skills/mold/references/handshake.md`), shape-check blast-radius numbers gating
Grill (`skills/mold/references/shape-check.md`), the agent-introduced-scope grep
  gate, and a computed handoff (`curd-count` → `/cook` or `/ultracook`, linear
  vs parallel mode). What `spec.md` has that `/mold` softened: the explicit
~800-word / 2-minute-read prose target and optional GitHub-issue emission.

## Where `/mold` is ahead — and what it could borrow

**Ahead of all 10 tools:** the agent-introduced-scope grep gate is unique. No
one else greps prior user turns to catch the "Tavily snippet → shipped config
knob" drift (`skills/mold/references/handshake.md` § Agent-introduced scope). The
shape-check producing *arguable numbers* (caller count, importer count) rather
than a guessed verdict is also stronger than anyone's grounding step.

**Borrow candidates** (open questions, not mandates — alternatives raised by
sources):

- Matt Pocock's **`/prototype` escape hatch** — a "build to resolve a design
  unknown, then resume" branch `/mold` lacks.
- Superpowers' **dot-graph hard exit** — encoding `/mold`'s gates as a
  machine-readable graph rather than a prose checklist, since Jesse's whole
  v4.3.0 finding was that prose gates get rationalized past.
- **EARS-style acceptance notation** (Kiro) for the spec's Acceptance section to
  make criteria test-generable.

## Other widely-used spec tools (survey)

- **GitHub Spec Kit** (github/spec-kit, MIT) — constitution → specify → plan →
  tasks → implement; `constitution.md` at `.specify/memory/constitution.md`
  governs every phase; `[P]` marks parallel tasks; agent-agnostic.
- **AWS Kiro** (kiro.dev, proprietary IDE, July 2025) — requirements.md (EARS) →
  design.md → tasks.md → implement; human approval gate per phase; hooks are
  event-driven quality automations; IDE-locked (Code OSS).
- **BMAD-METHOD** (bmad-code-org, 40k+ stars, MIT) — brainstorm-first via
  `/bmad-brainstorming`; 19+ agent personas (Analyst → PM → Architect → PO/SM →
  Developer); document-driven handoffs; "epic sharding" splits PRDs.
- **Taskmaster AI** (eyaltoledano/claude-task-master, 25k+ stars) — PRD →
  `parse_prd` → dependency-aware hierarchical tasks in `.taskmaster/`;
  `next_task` respects the graph; main/research/fallback model tiers.
- **Agent OS v3** (buildermethods.com, Brian Casel, Jan 2026) — discover →
  inject → shape (via host plan mode) → implement; v3 delegates spec-writing to
  the host agent and focuses on standards discovery/injection.
- **OpenSpec** (Fission-AI/OpenSpec) — strict propose → apply → archive state
  machine; `openspec/specs/` is source-of-truth, `changes/` holds proposals;
  brownfield-first; `openspec validate --strict`.
- **Tessl** (tessl.io, Guy Podjarny / ex-Snyk) — spec-as-source: code is
  regenerable output stamped `GENERATED FROM SPEC`; Spec Registry has 10k+ OSS
  usage specs; Framework was closed/private beta as of mid-2026.

Further reading: Martin Fowler / Birgitta Böckeler, "Understanding Spec-Driven
Development: Kiro, spec-kit, and Tessl" (martinfowler.com, 15 Oct 2025).

## Confidence & gaps

High overall. Matt Pocock and Superpowers claims are from primary SKILL.md files
and the authors' own blogs/transcripts; `/mold` and `spec.md` were read
directly. Gaps: Pocock's `domain-model` / `to-issues` / `tdd` skill internals
weren't fetched; Superpowers' exact v5.x spec-review loop (inline checklist vs.
subagent) is unconfirmed; Tessl's workflow is closed-beta and unverifiable;
OpenSpec star count is from a secondary source.
