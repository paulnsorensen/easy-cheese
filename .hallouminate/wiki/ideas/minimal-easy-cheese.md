# Minimal easy-cheese

Working discussion — 2026-10-18, updated 2026-10-22.
This page tests a simpler design against the [manifesto](../easy-cheese-manifesto.md).
The manifesto's rulings section records what the owner decided; this page keeps the proposals and the evidence.

## The smallest coherent shape

**One continuous work stream, two feedback loops, and one connected record of the work.**
This is a proposal, not a finding from the research.

The discovery loop gathers evidence, exposes unknowns, and shapes the next useful experiment or commitment.
Culture, Mold, Pasteurize, and Prototype are ways to do that work, not mandatory stations.

The delivery loop builds a bounded change, checks behavior and design, repairs defects, and prepares it for human integration.
Cook, Press, Age, Cure, Hard-cheese, and Plate provide those capabilities.
A task uses only the capabilities it needs.

Both loops update connected context.
Research, small edits, and ready implementation pieces can coexist without pretending every part of the problem is settled.
This directly answers the October 3 stream example.[^stream]

Keep the mechanism in three parts:

- **Skills own judgment and policy:** questions, exploration, decomposition, design review, and explanations.
- **The CLI owns mechanics:** validation, identities, revisions, links, stale-evidence detection, bounded execution bookkeeping, and artifact rendering.
- **Adapters supply capabilities:** the host, code intelligence, research, wiki search, optional Milknado, and optional UI.

This does not imply one executable, one universal schema, or one database.
The installed per-skill archive contract remains in force.[^bundles]

## What the record network owns

Wheypoint connects intent, decisions, open questions, evidence, work attempts, and artifact references.
Specifications describe desired behavior.
Plans describe work and dependencies.
Results describe observed outcomes.
A wiki keeps reusable knowledge; a search index helps retrieve it.

These are different authorities, even if some documents share a small envelope.
A graph link must not turn an old proposal into an approved requirement.
A successful parse must not turn an agent's claim into verified evidence.

Proposed context lifecycle: capture the useful change, link its sources, reconcile conflicts, then promote reusable knowledge.
Record supersession and the reason for it.
Retrieve the active work and relevant evidence, not every earlier transcript.
A cold-session recovery test should verify that important decisions survive.
Hallouminate remains optional; retrieval does not own the truth.

The existing Wheypoint–Milknado choice keeps shared schemas and separate stores.
Reopening that choice requires an explicit decision, not an incidental rewrite.[^seam]

## Coverage against recorded use cases

These rows describe required experiences, not a new sequence of mandatory phases.[^stream][^current][^brief]

| User task | Smallest path that preserves the intent |
| --- | --- |
| “Help me think” | Ground, discuss, record useful decisions and questions; do not create code or a full spec. |
| Research a current question | Retrieve relevant sources, expose conflicts and freshness, save the supported conclusion. |
| Request a waterfall specification | Expand discovery and specification depth; stop before implementation unless authorized. |
| Explore through a prototype | Build a reversible experiment; identify whether code is disposable or intended to survive. |
| Make a small, clear change | State the behavior, make the change, check it, and use proportionate review. |
| Fix a difficult bug | Reproduce, test the cause, add a regression check, fix, and verify the real boundary. |
| Discuss while ready pieces build | Pin each ready piece and its interfaces; continue discovery outside that commitment. |
| Run independent work in parallel | Give each worker clear ownership; validate dependencies and the integrated result. |
| Review existing work | Inspect the named revision and report evidence; do not assume permission to fix it. |
| Address PR feedback and CI | Triage, make authorized fixes, recheck, and update the existing publication. |
| Integrate a large change | Explain its shape; stack PRs when dependency order makes each layer easier to review. |
| Resume in another session | Recover current decisions, unresolved questions, artifact versions, and the next authorized move. |
| Work without optional tools or UI | Preserve core behavior; state any lost capability or assurance. |

The owner ruled on 2026-10-22: the in-flight piece finishes and a follow-up piece is queued; a change in direction cancels and resends it.
See [deterministic-fanout-sizing-005](../adr/deterministic-fanout-sizing-005.md).
The older fifteen-workflow map survives only as a summary in the sources recovered here.
The October record explicitly leaves its reconciliation with the six examples open.
This table is a coverage hypothesis, not proof that every historical workflow is accounted for.[^stream]

## Where the manifesto is strong, and where to sharpen it

These assistant proposals sharpen the manifesto without silently changing the owner's tenets.

- **Current, relevant evidence:** choose evidence that can answer the decision; freshness is not novelty for its own sake.
- **Comprehension as a result:** leave the user able to explain the structure, trade-offs, expected behavior, and remaining risks.
- **Whole-journey reliability:** verify the final environment, not only a valid handoff or successful router response.

**Grounding:** keep it, but seek the freshest relevant evidence, not novelty for its own sake.
A current code read may answer the question better than another web search.
METR's newer update explicitly limits what its older productivity result can tell us today.[^metr]

**Self-evaluation:** treat the core as an evidence-backed feedback loop, not a model approving its own work.
Tests, real system behavior, distinct review perspectives, and human decisions provide different kinds of feedback.
Older reasoning experiments found limits to intrinsic self-correction; they do not measure today's coding agents.[^correction]
Independent evaluators can also grade generously.[^harness]

**Human altitude:** preserve human authority over intent, trade-offs, and acceptance.
Do not make a claim about permanent model incapacity part of the architecture.
Make responsibilities, dependencies, alternatives, and likely change paths inspectable.

**Types:** require strict, versioned outputs at consequential boundaries.
Do not type every conversation move or infer semantic truth from schema validity.
Structured Outputs' format guarantee is not a correctness guarantee; that distinction is an inference from its published contract.[^structured]

**Parallelism:** preserve the capability, but earn each split through independence, risk, or useful perspective.
A multi-agent research result does not establish faster integrated coding.
Anthropic's report itself identifies this difference.[^parallel]

**Determinism:** offload stable mechanics.
Keep semantic judgments visible rather than hiding them behind deterministic scores.
The current Age router already separates semantic input from deterministic planning.[^age]

**Reviewability:** use a revision-bound change explanation, not decorative documentation.
Show intent, affected responsibilities, key alternatives, risks, evidence, and the decisions the human must understand.
Use diagrams or stacks only when they reduce that burden.
Hard-cheese stays the quiz; a separate review artifact supports understanding throughout the work ([hard-cheese-retained-002](../adr/hard-cheese-retained-002.md)).

**Optimization:** measure verified outcomes, cost, and user understanding.
Prevent the optimizer from changing its own success criteria or learning the holdout cases.
A private candidate patch is not approval to apply it.
The inspected skillz workflow already separates search, holdout comparison, and patch export.[^skillz]

## What is already discussed or stale

The root rebuild record remains exploratory.
Its graph links to contracts simplification, then Wheypoint-contract simplification.
The Milknado seam is a user-directed split without a recorded fork edge.[^records]

The September suggestion to park Hard-cheese was an agent proposal.
Today's explicit instruction keeps it.[^hard]
Older schema counts and public handoff descriptions no longer describe this checkout.
The current map records removed contracts and still warns that typed routes do not prove end-to-end adoption.[^contracts]

One small example of documentation drift remains: the Age router wiki lists twelve dimensions; current skill prose also lists “reframe.”
The current skill lists thirteen names.
This is evidence of a stale seam, not proof that all of cheese is stale.[^age][^age-source]

The checked local skillz tree contains the packaging, CLI, analytics, and optimization foundations.
An older wiki description of it as repository-plumbing skills is no longer sufficient.[^skillz]
The 2026-10-18 inspection found journey-coverage PRs #822–#825 open.
The handoff reports 174 proposed journey cases across 14 skills, with no live run.
Those are coverage plans, not reliability measurements.[^journeys]

## Next steps

On 2026-10-22 the owner chose to make the ruled changes first and measure after.
The earlier measure-first sequence (settle tenets, reconcile the journey map, baseline the current engine, then compare one simplification) no longer sets the order.
The accepted risk: no baseline of the current cook exists to compare the size heuristics against.

1. **Size-heuristics mold.**
   Define the size score, the grounding-plan section of the spec, mixed inline and dispatched pieces, the change-in-direction test, and the degrade path without sub-agents.
   See [deterministic-fanout-sizing-005](../adr/deterministic-fanout-sizing-005.md).
2. **Review-artifact mold.**
   Define its sections, its editor, and where it lands.
   See [hard-cheese-retained-002](../adr/hard-cheese-retained-002.md).
3. **Harness overlay.**
   Keep model names in one overlay and reject them elsewhere in shared skill text.
   See [codex-omp-portability-002](../adr/codex-omp-portability-002.md).
4. **Record links.**
   Add digest-pinned links from the Wheypoint record to Spec, Plan, and Review artifacts, then revisit further record cuts (issue #843).
5. **Journeys and the grader (fork F).**
   Run after the tilth benchmark work.
   Pin the task, revision, model, tools, and live-call budget before each run.

Routing-only tests remain useful, but do not establish successful downstream work.[^evals][^journeys]
Do not remove guards or weaken success criteria to make a change look better.

## Decisions still needed

- Which workflows exist: the six from the October 3 session, or a reconciliation with the lost fifteen? This waits for the skill cuts (fork E).
- What evidence makes a piece ready to leave discovery and enter implementation? The size-heuristics mold owns part of this.
- What counts as a change in direction for an in-flight piece, and does code or the agent detect it?
- One archive or thirteen (fork H)?

The available evidence does not show that a wholesale rewrite improves quality or total delivery cost.[^initial]

## Evidence boundary

This minimal-core discussion summarizes a bounded discovery pass, not every historical conversation.
Four Sol specialists investigated the records, current architecture, and primary research.
The project search returned 13 store records and 40 legacy notes; all 13 records were inspected.
Of 30 unparseable notes, three were read and 27 received title-only triage.
Of ten parseable notes, one was read and nine received title-only triage.
The older fifteen-workflow enumeration remains missing, so use-case coverage is still provisional.

The connected record chain is:

| Record | Inspected revision | Meaning |
| --- | --- | --- |
| `rebuild-easy-cheese-from-scratch` | `rev-c1a85e43507b` | Exploratory root; no wholesale rewrite approval. |
| `easy-cheese-contracts-simplify` | `rev-d4db1d5e6d96` | Recorded child; selected contract cuts. |
| `wheypoint-contract-simplify` | `rev-90cbbec9791d` | Recorded grandchild; #776 (`ff7509bc`, merged 2026-10-15) landed the schema-5 cuts; further cuts wait on issue #843. |
| `wheypoint-milknado-seam` | `rev-df6756bd3d99` | Related split without a recorded fork edge; shared schemas and separate stores. |
| `journey-workflow-coverage` | `rev-525cb6ea725f` | Related coverage handoff; proposed cases, not live results. |

Private Wheypoint IDs and XDG citations preserve provenance, but a public clone cannot resolve them.
Raw transcripts and local session reports are not part of this publication.
The reviewable visual is `docs/architecture/easy-cheese-working-direction.html`.
Open that self-contained file locally; GitHub displays its source rather than rendering the page.
The visual summarizes this proposal and does not replace the evidence or approve a rewrite.

## Sources

[^brief]: Owner's 2026-10-18 request, T3 thread `b8d02190-bff6-4f67-a1b1-25faf8f2ebc7`; checkpoint `easy-cheese-rewrite-manifesto`.
[^stream]: XDG research `rebuild-easy-cheese-from-scratch/session-2026-10-03-workflows-stream.md:40-90`.
[^current]: `skills/cook/SKILL.md:19-30,67-110`; `skills/cook/references/prototype-mode.md:1-20,72-93`; `skills/culture/SKILL.md:9-33`.
[^bundles]: [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md); `AGENTS.md:27-64`.
[^seam]: Wheypoint `wheypoint-milknado-seam@rev-df6756bd3d99`, decisions `d-3d74c2d7aadf` and `d-0282e93e168d`.
[^metr]: [METR study update](https://metr.org/blog/2026-02-24-uplift-update/), published 2026-02-24, retrieved 2026-10-18.
[^correction]: [Huang et al., ICLR 2024](https://arxiv.org/html/2310.01798v2), revised 2024-03-14, retrieved 2026-10-18.
[^harness]: [Anthropic harness-design report](https://www.anthropic.com/engineering/harness-design-long-running-apps), retrieved 2026-10-18; vendor experience, not general proof.
[^structured]: [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api), published 2024-08-06, retrieved 2026-10-18.
[^parallel]: [Anthropic multi-agent research report](https://www.anthropic.com/engineering/multi-agent-research-system), retrieved 2026-10-18; vendor-specific research evaluation.
[^age]: [Age fan-out router](../architecture/age-fanout-router.md), lines 11-32.
[^age-source]: `skills/age/SKILL.md:86-91`, checkout `1371af898da52e000e9c7c7a5579c35b7aeecb3a`.
[^skillz]: Local checkout of `paulnsorensen/skillz-that-grillz`, clean revision `e7be9f9b43853a3385eb699ada2cf8f06094377c`: `README.md:10-40,64-74`, `pyproject.toml:17-32`, `skills/skillz/references/experiments.md:13-27,50-61`. Remote equality was not checked.
[^records]: Wheypoints `rebuild-easy-cheese-from-scratch@rev-c1a85e43507b`, `easy-cheese-contracts-simplify@rev-d4db1d5e6d96`, `wheypoint-contract-simplify@rev-90cbbec9791d`; list/show/log inspected 2026-10-18.
[^hard]: XDG research `rebuild-easy-cheese-from-scratch/session-2026-09-27-skills-schemas-cli.md:52-62`; owner's current instruction: “I want to keep hard-cheese.”
[^contracts]: [Workflow contract map](../architecture/workflow-contract-map.md), lines 8-18,46-64,147-180; source corroboration in `src/easy_cheese/shared/phase_routes.py:16-46`, `skills/age/SKILL.md:235-242`, `skills/cure/SKILL.md:53-61`.
[^journeys]: Wheypoint `journey-workflow-coverage`, dated 2026-10-17; [PR #822](https://github.com/paulnsorensen/easy-cheese/pull/822), [PR #823](https://github.com/paulnsorensen/easy-cheese/pull/823), [PR #824](https://github.com/paulnsorensen/easy-cheese/pull/824), [PR #825](https://github.com/paulnsorensen/easy-cheese/pull/825), metadata checked 2026-10-18. Counts and no-live-run status come from the handoff, not an independent suite run.
[^evals]: [Anthropic agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), retrieved 2026-10-18.
[^initial]: XDG research `rebuild-easy-cheese-from-scratch/rebuild-easy-cheese-from-scratch.md:5-9,96-112`.

_Source: owner's 2026-10-18 brief and publication request; owner rulings of 2026-10-18 to 2026-10-22; assistant synthesis; cited records and research · Updated: 2026-10-22._
