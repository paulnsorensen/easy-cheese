# The easy-cheese manifesto

Working copy. Owner: Paul Sorensen. Drafted 2026-10-18 from Paul's own words,
lightly edited. Each tenet carries an `Evidence` line that points at what the
repo, the wheypoints, and the research already measured. The edits that change
meaning are listed at the end so they can be accepted or rejected one by one.

## Already decided (do not re-litigate)

These come from recorded directives and decisions in the rebuild, contracts,
and seam wheypoints.

- Keep the pyz, and keep exported, shareable schemas and code.
- Use code to limit nondeterminism; the main goal is lower token cost.
- The wheypoint is the backbone. Specs, implementation plans, delivery plans,
  and review results are the high-level drivers.
- Gates were the first cut. Re-add a gate only on demonstrated need.
- Work must not have to pass through a bespoke mold, cook, age, cure chain.
- Define the workflows first, then map skills onto them.
- Wheypoint couples to milknado by pointer: shared schemas, separate stores.
- Fork the tilth benchmark into easy-cheese for a new task set.

## Tenets

### 1. Research and grounding on current data

Be it wiki or research, the model cannot be authoritative about the current
state of the world. We should always seek to learn the latest and newest
information. That includes our own wiki: a page without a date and a digest is
a guess, not a source.

Evidence: the wiki still says archives live on `main` (they moved to `dist`),
still counts ten `/age` dimensions (there are thirteen), and still describes a
`red_gate` import that was deleted. The rebuild record already re-pins stale
links at every resume.

### 2. Shape before build: Culture, Mold, Pasteurize, Prototype

We seek information and shape it. This is not a one-size-fits-all situation.
We should try to identify as many unknowns as possible to create clear
specifications for a full implementation. That may not happen in one shot, and
it may not be prototype-first. It is likely a collection of "diffusive" ways to
get there, and easy-cheese needs to support any of them with ease.

Evidence: the 10-03 session defined one `Stream` workflow (talk, inline edit,
or piece, against one shape doc with stable section ids) and five others
(Build, Review, Fix a bug, Land, Research). Mold today measures a median of
443 minutes and 320 tool calls, and 5 of 16 runs reached a spec write.

### 3. Cook, Age, Cure: the opinionated backbone

The entire backbone of the implementation engine can and should be opinionated
to reflect my experience and philosophies of how to make correct,
cost-effective software. This is the hardest part for LLMs versus humans.
Humans will (likely always) be able to view things at an altitude where LLMs
cannot see the logistical network of ideas that end up manifesting into code.
This needs to encapsulate those ideas without causing friction to the user.
The goal: once something is cooked, it should be up to spec, clean, properly
abstracted, and easy to change. An opinion that lives only in prose does not
hold. Each opinion is enforced by a code gate or graded by an eval.

Evidence: Claude follows about 1% of hedged numbered steps and skips them when
a degrade clause exists. The things that hold today are code: gate receipts,
the review-surface score, the severity formula. The chain costs a p50 of
3.4 hours and 129M cache-read tokens, and parent context growth is the largest
cost.

### 4. Context lives in a wheypoint network and LLM wikis

We will always need active context management. easy-cheese should write
context so that it is easy to connect ideas from any session. We can lean on
hallouminate for indexing, but there should be a good amount of tooling and
decision-making to store additional artifacts in a durable cheese path or in
the repo. I think we can do more here than we currently have. "More" means
better compiled views and better links between artifacts, not more fields on
the record.

Evidence: 49 work records exist under the durable cheese path. The continuity
kernel was built after a July context-loss incident deleted decisions. The
record today cannot pin a wiki page, an XDG artifact, or a milknado node, and
about 40% of its projection is metadata, lineage, or dossier.

### 5. Reviewability: manage comprehension debt

This is an emerging frontier of LLM-driven development where we have to
actively manage comprehension debt. I want to keep hard-cheese, but I also want
to enhance it so that by the time we get to code review, the user knows the
shape of everything, knows what to expect, and we present it that way. This
might include smart stacking of PRs with active comments and Mermaid.js
diagrams to justify why we built what we built. Reading code bare is going to
be extremely time-consuming, so we should come up with ways, or develop new
ways, to make integration of code much easier.

Evidence: reviews of 200 to 400 lines find 70 to 90% of defects; detection
falls to about 28% above 1,000 lines. Plate already picks stack topology by
cohesion. PR #753 (Mermaid for topology-changing commits) is open. Nothing
today produces a review-time briefing.

### 6. Predictable behavior

We have tried in the past to use strongly typed graphs to get agents to adhere
to exit types: permissive in what we accept, strict in what we produce.
Ultimately we want things to be reliable each time, scalable to the user's
skill (let them `/cheese` everything and we route it forever) without causing
friction. Cheese might be heavier than other flows, but it should ultimately be
extremely reliable. Typed exits stay. Typed gates between phases do not.

Evidence: 551 sessions and about 43k tool calls showed zero runtime validation
failures of agent payloads. The gate contracts "mostly create difficulties" and
are being removed in the draft stack 772 to 774.

### 7. Support parallelism

One of the earliest things I thought was successful was ultracook: a way to
fan out many coder implementers to more quickly implement large swaths of
behavior. I still have dreams of plugging this into my milknado engine, but it
may not be needed. This should not be limited to coding. Reviews, especially
at altitude, should maybe behave like a double diamond: we cook some seams,
review others, and then refine until it is ready. Parallelism is a capacity
the engine offers when the size score asks for it, never a default.

Evidence: fan-out is on by default today, yet 609 spawns across 83 sessions
show zero same-second parallel bursts and no `/age` run with three or more
reviewers. The fan-out, remediation, checkpoint, and review-lock stack is about
5,200 lines. Five of six curd dispatches in one run exhausted their context.

### 8. Pluggability

Cheese is designed to be installed only via `npx skills`, so all of our
verbiage and tools need to predict and be flexible with whatever the user has.
We should keep this, and perhaps bias toward other cheese tools, but ultimately
support many forms of code intelligence, research, LLM wiki, and so on. The
floor is a harness with no sub-agents, no MCP, and no plan mode. Every workflow
must complete on the floor. Everything else is an accelerator.

Evidence: about 85% of skill loads come from omp, a Pi fork with no native
sub-agents or plan mode. The design-target fork (omp and Pi versus Claude
Code) has been open since 09-21.

### 9. Determinism: pack behavior into CLIs

This goes with predictable behavior, but I want as few tokens as possible
wasted on logic that can be offloaded to a CLI. There is obviously a tradeoff,
but we should always pack behavior into our CLIs to make cheese reliable and
as token-efficient as possible. Judgment decides what a change means. Code
decides what happens next, and every routing decision leaves a record.

Evidence: 115 bundle verbs across 13 bundles; 77 are deterministic, 13 route,
8 render, and 17 have no prose reference. Mold tier, leverage, and the
`/cheese` route are prose and leave no record, so they cannot be replayed or
graded.

### 10. skillz-that-grillz powered

I extracted all of my best libraries into paulnsorensen/skillz-that-grillz,
and I have dreams of explaining how cheese should work in journeys and evals
(we have some open PRs here) to allow models to ultimately refine cheese as it
changes and ages. A tenet without a grader is an opinion.

Evidence: 174 journey cases across 14 skills sit in PRs 822 to 825; every
contract carries draft status until you approve it.
The GEPA research says end-to-end fitness is infeasible (about 2,040 agent
hours per optimize run) and that no grader exists for mold, handoff quality,
or altitude. The only runtime link to skillz today is a build-time wedge pin at
a commit whose directory layout no longer exists upstream.

### 11. Scalability: minimum viable ceremony

If a user wants a full waterfall spec, we do it. If a user needs a bug fix, we
do NOT create nineteen Opus reviewer agents. We use the minimum viable amount
to achieve the goal. One rule, in code, with a receipt: ceremony is a function
of leverage, size, and context cost.

Evidence: both failure modes exist today. 17 of 52 chains plated before any
`/age`; 26% of chains ran two or more `/age` rounds, with a maximum of
thirteen. Routing policy sends any leverage trigger to full mold while the
tiers reference only rules out Quick.

### 12. UI-native ability, never required

A lot of the code we talk about is at a higher altitude than simple bug fixes.
We should have visual aids and web UIs that help even the most novice users
participate. But it is NOT required. The UI is a projection of the same typed
artifact the CLI reads. It never holds state the CLI cannot.

Evidence: the mold review canvas is at ADR 008 (shape views, pins, Excalidraw,
Mermaid) and adds 8.2 MB of assets to mold.pyz. The canvas validates no
feedback shape. Five of the last fifteen open PRs touch the canvas; four of
those fix test races.

## Edits that change meaning

Accept or reject each one.

1. Tenet 1 adds "including our own wiki" and the date-plus-digest rule.
2. Tenet 3 adds "enforced by a code gate or graded by an eval".
3. Tenet 4 defines "more" as compiled views and links, not record fields.
4. Tenet 6 splits typed exits (keep) from typed phase gates (cut), to match
   the gates-first-cut decision.
5. Tenet 7 states parallelism as a size-gated capacity, not a default.
6. Tenet 8 names the floor harness and calls everything else an accelerator.
7. Tenet 9 adds "every routing decision leaves a record".
8. Tenet 10 adds "a tenet without a grader is an opinion".
9. Tenet 11 adds the one-rule formulation.
10. Tenet 12 adds "the UI is a projection of the typed artifact".

## Sources

- In this repo: `docs/architecture/manifesto-evidence.md` (verdicts, the
  simplest cheese, open forks) and `docs/research/manifesto-2026-10/`
  (copied reports, measured facts, diagrams, record digests).
- Rebuild record and research: `~/.local/share/cheese/paulnsorensen-easy-cheese/work/rebuild-easy-cheese-from-scratch/` and `research/rebuild-easy-cheese-from-scratch/`.
- Contracts record: `work/easy-cheese-contracts-simplify/`, `work/wheypoint-contract-simplify/`.
- Seam record: `work/wheypoint-milknado-seam/`.
- Journeys: `work/journey-workflow-coverage/`, PRs 822 to 825.
- Age: `work/age-beyond-default/`, `work/age-vs-thermo-nuclear-review/`.
- Wiki: `.hallouminate/wiki/` (analytics, research, adr).
