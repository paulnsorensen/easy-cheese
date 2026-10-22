---
slug: gepa-workflow-level-cheese-flow
created: 2026-10-03
confidence: speculating
related:
  - /home/paul/Dev/easy-cheese/.cheese/notes/rebuild-easy-cheese-from-scratch.md
  - /home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/cook-skill-optimization-loop.md
---

# Research: what a workflow-level GEPA loop for cheese flow could look like

## Finding

GEPA already accepts a candidate that is a dict of named text components, and it mutates one component per round by default (round-robin)[^gepa-paper][^dspy-gepa].
GEPA has no explicit credit-assignment algorithm. The reflection LM reads trajectories and feedback and does "implicit credit assignment"[^gepa-paper].
Workflow-level credit therefore depends on the side information that the evaluator returns.
A 2026 ablation reports 0.80 in 100 rollouts with side information against about 600 rollouts with a score only[^asi-paper].
The #728 tilth runner returns scores, the model, and guard names only. No transcript, diff, or failing test output reaches reflection.

The compound-system literature splits the problem into stages.
Optimas gives each component a local reward that must correlate with the global metric[^optimas].
MASS optimizes block-level prompts, then the topology, then workflow-level prompts[^mass].
No fetched source runs GEPA on a multi-stage workflow where several skill prompts and gate rules hand off to each other.

In easy-cheese, most shape-deciding gates that run after the spec are pure code: `select_mode` at `src/easy_cheese/shared/fanout/mode.py:31-54`, `age_route` at `src/easy_cheese/shared/fanout/age_route.py:357-370`, press readiness at `src/easy_cheese/shared/gates.py:21-38`, and the change-size score at `src/easy_cheese/shared/fanout/review_surface.py:22-132`.
The gates that decide the spec ceremony are prose and leave no record: mold tiers (`skills/mold/references/tiers.md:13-31`), leverage triggers (`skills/cheese/references/routing-policy.md:44-58`), and the /cheese route receipt (`skills/cheese/references/routing-receipt.md:10`).
The wheypoint revision chain, the `.cheese/<phase>/` handback preambles, and the press telemetry JSON together give a trajectory record that a grader can read.

Gate evaluation by log replay is unreliable. The Replay Gap paper reports that replay with a swapped decision "mispredicted every success-critical outcome", and it uses branching rollouts from a live fork instead[^replay-gap].
For ergonomics, Handoff Debt reports that context-bearing handoffs cut median agent events by 20-59% and prompt tokens by 42-63%, with smaller and model-dependent effects on solve rate[^handoff-debt].
HAS-Bench scores interaction cost, clarification quality, and control calibration as separate axes[^has-bench].

The measured cost of one full chain sets the constraint.
A cook-to-plate chain has a p50 of 3.4 hours and 129M cache-read tokens (rebuild wheypoint, notes section).
gskill uses 600 metric calls by default for one skill string[^gskill].
At that budget, end-to-end chains would cost about 2,040 agent-hours per optimize run (600 × 3.4 h, computed).

## Evidence

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| GEPA mutates one named component per round by default. The round-robin, all, and custom selectors exist. | raw/c-01-arxiv.md (Sec 3); DSPy GEPA API[^dspy-gepa][^gepa-paper] | paper, vendor docs | fetched 2026-10-03 | `certain` | |
| GEPA does credit assignment only implicitly, through reflection over trajectories and feedback. | raw/c-01-arxiv.md: "LLMs ... perform implicit credit assignment"[^gepa-paper] | paper | fetched 2026-10-03 | `certain` | |
| System-aware merge combines ancestors that "optimized disjoint sets of prompts" and gains about +2% overall, up to +5%. The paper says the merge schedule needs more study. | raw/c-01-arxiv.md (App. D.1, Obs. 5)[^gepa-paper] | paper | fetched 2026-10-03 | `certain` | Single source, but this source is authoritative for its own method. |
| Side information cuts rollouts by about 6x (0.80 in 100 against about 600 with a score only). | optimize_anything paper[^asi-paper] | paper | fetched 2026-10-03 | `speculating` | Single source. Retrieved through a summarizer. |
| The DSPy GEPA metric can return feedback for each predictor (`pred_name`, `pred_trace`). | DSPy GEPA API[^dspy-gepa] | vendor docs | fetched 2026-10-03 | `certain` | |
| gskill evolves one skills string and grades it on SWE-smith fail-to-pass tests. It defaults to 600 metric calls with a 200/50/100 split. | gskill guide[^gskill] | vendor docs | fetched 2026-10-03 | `certain` | |
| gskill skills raise Claude Code (Haiku 4.5) pass rates on the transfer repos. | gskill blog[^gskill-blog]; CAIS demo[^cais] | vendor blog, conference listing | fetched 2026-10-03 | `certain` | Both sources agree on the direction. |
| The Bleve transfer figure is 98.3% (blog) or 100% (CAIS), from 79.3%. | gskill blog[^gskill-blog]; CAIS demo[^cais] | vendor blog, conference listing | fetched 2026-10-03 | `don't know` | The sources disagree. |
| Evolved skills can overfit to the task style. | gskill blog: "more helpful for SWE-smith style tasks"[^gskill-blog] | vendor blog | fetched 2026-10-03 | `speculating` | Single source. |
| Unconstrained prompts grow past 5,000 characters and generalize worse. | Decagon blog[^decagon] | vendor blog | fetched 2026-10-03 | `speculating` | Single source. |
| Optimas uses one local reward per component that correlates with global performance, and reports +11.92%. | raw/d-01-arxiv-optimas.md; abstract[^optimas] | paper | fetched 2026-10-03 | `speculating` | Single source. Ablations not read. |
| MASS optimizes in stages: block prompts, then topology, then workflow prompts. | raw/d-02-arxiv-mass.md; abstract[^mass] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| Replaying logs with a swapped decision mispredicts outcomes. Branching rollouts with a same-model control fork isolate noise. | raw/d-05-arxiv-replay-gap.md; abstract[^replay-gap] | paper | fetched 2026-10-03 | `speculating` | Single source. The branching detail comes from a search snippet. The study evaluates model routing, not process gates. |
| Structured handoffs mainly cut resume cost (events and tokens), not solve rate. | raw/d-06-arxiv-handoff-debt.md; abstract[^handoff-debt] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| Human-agent benchmarks score interaction cost and control calibration separately from task success. | raw/d-09-misc.md; abstract[^has-bench]; tau-bench pass^k[^tau-bench] | paper | fetched 2026-10-03 | `speculating` | tau-bench dates from 2024. |
| Outcome-only judges miss silent faults (45% recall). Step-rubric judges reach 77% recall at 3x the cost. | raw/d-07-arxiv-trajectory-judge.md; abstract[^traj-judge] | paper | fetched 2026-10-03 | `speculating` | Single source. Synthetic non-coding environment. |
| Seeded-defect review benchmarks inject 1-3 bugs into real PRs and score precision and recall with an LLM judge. Iterative reviewers raise recall but add noise. | raw/d-08-qodo-and-crbench.md; pages[^qodo][^crbench] | vendor blog, paper | fetched 2026-10-03 | `speculating` | The vendor benchmark is not independent. CR-Bench was read only in part. |
| Shape gates after the spec are deterministic code and can be replayed offline. | `src/easy_cheese/shared/fanout/mode.py:31-54`, `src/easy_cheese/shared/fanout/age_route.py:357-370`, `src/easy_cheese/shared/gates.py:21-38` | repo code | live | `certain` | |
| Spec-ceremony gates (mold tier, leverage, route) are prose and write no record. | `skills/mold/references/tiers.md:13-31`, `skills/cheese/references/routing-policy.md:44-58`, `skills/cheese/references/routing-receipt.md:10` | repo code | live | `speculating` | Absence claim: the explorer checked these files and `.cheese/` writers only. |
| Wheypoint revisions carry a digest chain, transitions, typed edges, and fork lineage, so the kernel can rebuild a trajectory across sessions. | `src/easy_cheese_schemas/contracts.py:3976`, `src/easy_cheese_schemas/contracts.py:4177`, `src/easy_cheese_schemas/contracts.py:3750` | repo code | live | `certain` | |
| The #728 evaluator builds side info from scores, the model, and guard fields. Transcript, diff, and test output were not found in that dict. | PR #728 `scripts/agent_lab.py` evaluator, diff-relative ~L471-477[^pr728] | Git host | live | `speculating` | Absence is limited to the evaluator dict that the explorer read. |
| The #728 candidate and guards are hard-coded to cook (`REQUIRED_SKILL`, allowlist, build gate). | PR #728 `scripts/agent_lab_candidate.py` ~L659-666, `scripts/agent_lab_tilth.py` ~L1646[^pr728] | Git host | live | `certain` | Diff-relative line numbers. |
| A full chain costs p50 3.4 h and 129M cache-read tokens, with 6 reviewer spawns. | raw/r-01-rebuild-wheypoint.md#L65-67 (snapshot of the rebuild wheypoint) | repository knowledge | 2026-09-21 | `certain` | |

## Open questions

- Staged or joint? The options are to optimize each phase against a local grader first (Optimas, MASS), or to evolve the whole workflow dict against one end-to-end grade. `speculating`
- Which local grader belongs to each phase? Cook can use fail-to-pass (#728). Age can use seeded-defect precision and recall (the #722 follow-up). The evidence gives no grader for mold or for handoff quality. `speculating`
- How do we grade a gate? Choose between offline accuracy replay of the pure gate functions on recorded diffs, and branching rollouts that fork at the gate. A wheypoint `fork` could serve as the branch point. `speculating`
- Should the prose ceremony decisions (tier, leverage triggers, route) become recorded data so that a grader can score them? Or should a grader parse them from transcripts? `speculating`
- What is the ergonomics proxy? Choose among a simulated user (tau-bench style), observational session analytics (the existing DuckDB data, observational only), and Handoff-Debt-style resume cost (events and tokens to resume from a wheypoint). `speculating`
- Do we add a trajectory judge? A step-rubric judge catches silent faults at about 3x the cost. Outcome-only grading is cheaper but misses them. `speculating`
- Which side information reaches reflection? Options are transcript excerpts, failing test output, the diff, and the handback preamble. The ablation suggests this is the largest lever, even for cook alone. `speculating`
- Where does the workflow harness live? Choose between tilth `benchmark/` (the current decision for cook) and an easy-cheese replay harness that runs on wheypoint records. `speculating`

## Confidence

`speculating`: GEPA mechanics and local code are verified, but no source runs GEPA on a multi-stage workflow, and most 2026 evaluation sources are single-source.

## Next step

Run `/culture` on the open forks. It is the same next step as the rebuild wheypoint. After that, run `/mold` on the chosen shape. The cook loop spec lists /age, /mold, and routing graders as non-goals, so a workflow loop needs its own spec.

## Searched, empty

- Current web, Tavily and WebFetch, "GEPA multi-stage agent workflow skill prompts routing" → no primary run found. Only an FAQ snippet claims GEPA co-evolves routing logic.
- Current web, "GEPA CLAUDE.md AGENTS.md optimization" → nothing primary.
- Current web, "benchmark adaptive process ceremony / spec depth gate" → nothing. Router benchmarks cover model routing only.
- Current web, "pass^k review fix loop convergence" → anecdotal GitHub and blog sources only.
- Current web, "TerminalBenchAdapter GEPA results" → adapter listing only, no numbers.
- Current web, TextGrad and Trace/OptoPrime → not fetched (not covered).

## Verification log

- Explorer digests (local code and PR diffs) were read in session on 2026-10-03 against main `f06f5d77` and PR heads #722 and #728.
- raw/c-01-arxiv.md holds the GEPA paper text (arXiv 2507.19457). The researcher wrote notes for raw/d-01 through raw/d-09.
- Pages marked "summary" came through a small-model summarizer, so their quotes are close to the source but not verbatim.

## agent_resolution

| Work | Selected | Permissions | Isolation | Power | Effort |
| --- | --- | --- | --- | --- | --- |
| Local workflow gates and wheypoints | explorer | read-only | fresh-context | default | medium |
| PR #722 and #728 code | explorer | read-only | fresh-context | default | medium |
| GEPA internals | researcher | read-only | fresh-context | default | medium |
| Workflow-level evaluation literature | researcher | read-only | fresh-context | default | medium |

## References

[^gepa-paper]: https://arxiv.org/pdf/2507.19457 (fetched 2026-10-03).
[^dspy-gepa]: https://dspy.ai/api/optimizers/GEPA/overview/ (fetched 2026-10-03).
[^asi-paper]: https://arxiv.org/html/2605.19633v1 (fetched 2026-10-03).
[^gskill]: https://gepa-ai.github.io/gepa/guides/gskill (fetched 2026-10-03).
[^gskill-blog]: https://gepa-ai.github.io/gepa/blog/2026/02/18/automatically-learning-skills-for-coding-agents (fetched 2026-10-03).
[^cais]: https://caisconf.org/program/2026/demos/learning-skills-coding-agents (fetched 2026-10-03).
[^decagon]: https://decagon.ai/blog/optimizing-gepa-for-production (fetched 2026-10-03).
[^optimas]: https://arxiv.org/abs/2507.03041 (fetched 2026-10-03).
[^mass]: https://arxiv.org/abs/2502.02533 (fetched 2026-10-03).
[^replay-gap]: https://arxiv.org/abs/2608.08239 (fetched 2026-10-03).
[^handoff-debt]: https://arxiv.org/abs/2606.02875 (fetched 2026-10-03).
[^has-bench]: https://arxiv.org/abs/2607.04329 (fetched 2026-10-03).
[^tau-bench]: https://arxiv.org/abs/2406.12045 (fetched 2026-10-03).
[^traj-judge]: https://arxiv.org/abs/2609.00038 (fetched 2026-10-03).
[^qodo]: https://www.qodo.ai/blog/how-we-built-a-real-world-benchmark-for-ai-code-review/ (fetched 2026-10-03).
[^crbench]: https://arxiv.org/html/2603.11078v1 (fetched 2026-10-03).
[^pr728]: https://github.com/paulnsorensen/easy-cheese/pull/728 (fetched 2026-10-03).
