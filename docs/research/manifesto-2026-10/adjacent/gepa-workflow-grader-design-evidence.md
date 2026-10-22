---
slug: gepa-workflow-grader-design-evidence
created: 2026-10-03
confidence: speculating
parent: research/gepa-workflow-level-cheese-flow/gepa-workflow-level-cheese-flow.md
scope_excluded: harness location (the user will fork the tilth benchmark into easy-cheese with a new task set)
---

# Research: evidence for the open grader questions of a workflow-level GEPA loop

## Finding

**Q1. Staged or joint.** No source isolates local-only, global-only, and aligned optimization in one ablation.
The nearest evidence is a hybrid pattern: optimize one component against a local signal, then accept the change only when the global score rises.
Optimas works this way. It also re-fits the local reward after each accepted change[^optimas].
In MASS, block-level prompt optimization first gives about +6%, topology about +3%, and workflow prompts about +2%. The authors say that topology search without earlier prompt optimization must be avoided[^mass].
CANTANTE reports that copying the global score to every agent performs at the MIPROv2 level, below per-agent contrastive attribution[^cantante].
Optimas reports that local and global optima differ in details (retriever top-k 5 locally, 10 globally) but share their top-3 set[^optimas].

**Q2. Gate grading.** Offline replay of the pure gates is possible only when the gate inputs are saved, and today only press saves them.
`review_surface.score` returns a row count, not the numstat rows (`src/easy_cheese/shared/fanout/review_surface.py:102-132`).
Press keeps route and telemetry JSON but not the five readiness booleans (`skills/press/references/telemetry.md:44-68`, `src/easy_cheese/shared/gates.py:21-38`).
The Replay Gap paper used about 900 live rollouts over 6 paired runs. It saw 0 outcome flips in 359 same-model control forks, and FP8-served controls diverged on more than 90% of forks[^replay-gap].
Wheypoint `fork` copies decision state only. It copies no files, worktree, or commit (`src/easy_cheese/shared/wheypoint/fork.py:1-8`). `RepositoryProvenance(branch, commit)` is optional and set by the caller (`src/easy_cheese_schemas/contracts.py:3890-3898`).
Off-policy evaluation needs logged or estimable propensities for each decision[^dudik].

**Q3. Decisions as data.** Tier, leverage, and route have no schema field.
The leverage decision page says leverage lands in spec frontmatter (`.hallouminate/wiki/decisions/leverage-is-the-ceremony-axis.md:15`), but `MoldSpecFrontmatter` has no `leverage` field (`src/easy_cheese_schemas/contracts.py:2928-2951`).
The evidence on whether a required structured format changes the decision conflicts. "Let Me Speak Freely" reports that format limits degrade reasoning[^speak-freely]. A vendor rebuttal and a third-party replication find the effect depends on the model and on field order[^dottxt][^castillo].
No source measures how reliably an LLM extracts decisions from agent transcripts. Generic LLM annotation reached kappa > 0.70 on 25 of 34 constructs and struggled with abstract categories[^edm].
The OpenTelemetry GenAI agent span conventions are all still in Development status as of mid-2026[^otel].

**Q4. Ergonomics proxy.** Resume cost has a published method. Simulated users have a documented optimism bias.
Handoff Debt ran 724 takeover runs per successor model. It used fixed note fields (changed, evidence, uncertain, verify, rollback) and reports no ablation of individual fields[^handoff-debt].
A tau-bench study with 451 real users finds that LLM simulators are too cooperative and inflate agent success[^sim-gap].
The METR 2026 update calls its own observational estimate unreliable because of task withholding, dropout, and concurrent agents[^metr-update].
SWE-chat (about 18k real sessions) reports push-back in about 44% of turns and clarifying questions in 1.4% of turns, without validating these rates as quality signals[^swe-chat].
In the repo, `src/easy_cheese/shared/wheypoint/transcript.py:1-40` reads user text turns only, and the DuckDB analytics store is outside the repo and is labeled observational only.

**Q5. Reflection side info.** The two GEPA reference evaluators disagree on what to pass.
The gskill SWE evaluator passes the problem (first 200 characters), the patch (first 500), the test output (first and last 500), the agent trace without truncation, and a status label (`f2p_failed`, `p2p_regression`, and others)[^gepa-repo].
The terminal-bench adapter passes the full message history and a one-line pass or fail reason, with no diff or test output[^gepa-repo].
The side-info ablation (about 6x fewer rollouts) used a non-coding dataset and gives no length guidance[^asi-paper].
STRACE reports that truncation and sliding windows "discard causally important evidence", and that causal extraction raised success from 42.5% to 58.5% on a formal-verification task[^strace].

**Q6. Judges.** Judges as optimization targets get hacked, and the reported mitigations anchor them to deterministic checks.
One study reports that a reference-free judge's pass rate rose from 0.72 to 0.94 while true accuracy stayed at 0.20. A three-family ensemble still accepted 55% of hacked answers. Making the judge commit its own answer first cut false positives from 71.9% to 1.2%[^judge-hack].
The step-rubric judge costs about 3x. Invented promises evaded it 82% of the time, and k=3 self-consistency "triples cost while improving nothing"[^traj-judge].
A 2026 paper recommends deterministic acceptance checks, frozen holdouts, and canary cases that treat a perfect score as suspect[^not-oracle].

**Mold grader.** No benchmark grades a spec by whether it recovers requirements held out from a merged PR.
The nearest designs are:
- Ambig-SWE: a simulated user holds the full issue and answers only from that issue. Interaction lifts performance by up to 74%[^ambig-swe].
- HumanEvalComm: degraded problems, scored by communication rate and good-question rate[^humanevalcomm].
- SWE-Bench Pro: each issue gets human-written requirements[^swe-pro].

A fixed implementer given a ground-truth plan improves pass@1. The evidence covers function-level tasks only[^self-plan].
LLM grading of ISO 29148 characteristics had high recall but low precision (precision 0.13-0.50 when independent)[^iso-llm].
The repo already has deterministic spec checks: `validate-spec` (`src/easy_cheese/skills/mold/validate_spec.py`), the typed `MoldSpecFrontmatter` and `TestContractRow` schemas (`src/easy_cheese_schemas/contracts.py:2928-2980`), and the goal-coverage rule in taste-test. No EARS validator exists.

## Evidence

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| Optimas accepts a local change only if global reward rises, and re-fits the local reward after each accepted change. | raw/a-01-arxiv.md; body excerpt[^optimas] | paper | fetched 2026-10-03 | `speculating` | Single source. Snippet-level extract. |
| Higher local-global alignment gives larger global gains. Local and global optima differ in detail. | raw/a-01-arxiv.md; body excerpt[^optimas] | paper | fetched 2026-10-03 | `speculating` | Tested on one component each, on two tasks. |
| MASS stage gains are about +6%, +3%, and +2%. Topology search without earlier prompt optimization is called something to avoid. | raw/a-01-arxiv.md; PDF excerpt[^mass] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| Copying the global score to every agent performs below per-agent contrastive attribution. | raw/a-01-arxiv.md; ablation excerpt[^cantante] | paper | fetched 2026-10-03 | `speculating` | Single source. Tested on MBPP, GSM8K, and HotpotQA. |
| Aggressive credit thresholds raise the risk of performance drift. | raw/a-01-arxiv.md; abstract[^credit-unify] | paper | fetched 2026-10-03 | `speculating` | Single source. The ablation tables were not retrieved. |
| No published ablation compares local-only, global-only, and aligned optimization. | raw/a-01-arxiv.md; searches listed below | paper | fetched 2026-10-03 | `speculating` | Absence is limited to the Optimas, MASS, GEPA, CANTANTE, TextGrad, and Trace sources that were checked. |
| Replay Gap used about 900 live rollouts and saw 0 flips in 359 control forks. FP8 controls diverged on more than 90% of forks. | raw/b-01-arxiv-otel-misc.md; body excerpt[^replay-gap] | paper | fetched 2026-10-03 | `speculating` | Single source. Fork count per decision and dollar cost were not found. |
| Off-policy evaluation reweights by logged or estimated action propensity. | raw/b-01-arxiv-otel-misc.md; search result[^dudik] | paper | fetched 2026-10-03 | `speculating` | The primary paper was not opened. |
| Pure gate inputs are mostly not saved. Only press keeps a route and telemetry record. | `src/easy_cheese/shared/fanout/review_surface.py:102-132`, `skills/press/references/telemetry.md:44-68`, `src/easy_cheese/shared/gates.py:21-38` | repo code | live | `speculating` | Absence claim. Whether the age route context JSON is kept was not verified. |
| Wheypoint fork copies decision state, not repository state. Commit provenance is optional and set by the caller. | `src/easy_cheese/shared/wheypoint/fork.py:1-8`, `src/easy_cheese_schemas/contracts.py:3890-3898` | repo code | live | `certain` | The module docstring states that fork writes only a child record. The fork code path was read and has no file or worktree copy. |
| Tier, leverage, and route have no schema field. The leverage decision page and the schema disagree. | `src/easy_cheese_schemas/contracts.py:2928-2951`, raw/f-01-leverage-decision.md#L15 (snapshot of the wiki decision page), `skills/mold/references/tiers.md:3-7` | repo code, repository knowledge | live | `speculating` | Absence is limited to the schema module and a search of `src/` for `leverage`. |
| A required output format can degrade reasoning. | raw/b-01-arxiv-otel-misc.md; abstract[^speak-freely] | paper | fetched 2026-10-03 | `speculating` | The sources disagree. See the next row. |
| The format effect depends on the model and the field order. | raw/b-01-arxiv-otel-misc.md; posts[^dottxt][^castillo] | vendor blog, blog | fetched 2026-10-03 | `don't know` | Contested. One source is a vendor. |
| OpenTelemetry GenAI agent spans are all still Development status. | raw/b-01-arxiv-otel-misc.md; repo listing[^otel] | vendor docs | fetched 2026-10-03 | `speculating` | Snippets only. |
| Handoff Debt: 724 takeover runs per model. Fixed note fields, no per-field ablation. | raw/c-01-arxiv.md; body summary[^handoff-debt] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| LLM-simulated users are too cooperative and inflate agent success against real users. | raw/c-01-arxiv.md; body summary[^sim-gap]; UserProxyBench[^userproxy] | paper | fetched 2026-10-03 | `speculating` | Two sources. Both are non-coding domains. |
| Observational productivity estimates carry selection and dropout confounders. | raw/c-01-arxiv.md; METR RCT[^metr-rct]; METR update[^metr-update] | paper, research org | fetched 2026-10-03 | `certain` | The organization is authoritative for its own study. |
| Real sessions show push-back in about 44% of turns and clarifying questions in 1.4%. | raw/c-01-arxiv.md; body summary[^swe-chat] | paper | fetched 2026-10-03 | `speculating` | Single source. The abstract variants differ (44% and 50%). |
| The gskill evaluator passes truncated problem, patch, and test output, plus the full agent trace and a status label. | raw/d-02-github-gepa.md; `swe_fitness_fn.py` L118-137[^gepa-repo] | repo code (upstream) | fetched 2026-10-03 | `certain` | |
| The terminal-bench adapter passes the full message history and a one-line failure reason. | raw/d-02-github-gepa.md; `terminal_bench_adapter.py` L198-217[^gepa-repo] | repo code (upstream) | fetched 2026-10-03 | `certain` | |
| Side info gives about 6x fewer rollouts on one non-coding dataset. The paper has no length guidance. | raw/d-01-arxiv.md; Sec 5.9[^asi-paper] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| Truncation can discard causally important evidence for reflective optimization. | raw/d-01-arxiv.md; abstract[^strace] | paper | fetched 2026-10-03 | `speculating` | Single source. Formal verification, not coding. |
| A reference-free judge can be hacked: pass rate 0.72 to 0.94 while true accuracy stays 0.20. Answer-first judging cut false positives from 71.9% to 1.2%. | raw/d-01-arxiv.md; abstract[^judge-hack] | paper | fetched 2026-10-03 | `speculating` | Single source. RL self-play on math. |
| A step-rubric judge costs about 3x, misses invented promises 82% of the time, and gains nothing from k=3 self-consistency. | raw/d-01-arxiv.md; body summary[^traj-judge] | paper | fetched 2026-10-03 | `speculating` | Single source. Synthetic support-desk environment. |
| Deterministic acceptance checks, frozen holdouts, and canaries are recommended over judge opinion. | raw/d-01-arxiv.md; abstract[^not-oracle] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| Ambig-SWE simulates a user who holds the full issue. Interaction lifts performance up to 74%. | raw/e-01-arxiv.md; body[^ambig-swe] | paper | fetched 2026-10-03 | `speculating` | Single source. |
| HumanEvalComm grades communication rate and good-question rate on degraded problems. | raw/e-01-arxiv.md; README[^humanevalcomm] | Git host | fetched 2026-10-03 | `speculating` | README only. |
| SWE-Bench Pro adds human-written requirements to each issue. | raw/e-01-arxiv.md; paper PDF[^swe-pro] | vendor paper | fetched 2026-10-03 | `speculating` | Single source. |
| A ground-truth plan raises a fixed implementer's pass@1. | raw/e-01-arxiv.md; body[^self-plan] | paper | fetched 2026-10-03 | `speculating` | Function-level tasks only. |
| LLM grading of ISO 29148 qualities has high recall and low precision. | raw/e-01-arxiv.md; body[^iso-llm] | paper | fetched 2026-10-03 | `speculating` | Single small study. No kappa. |
| No benchmark grades spec recovery of requirements held out from a merged PR. | raw/e-01-arxiv.md; searches listed below | paper | fetched 2026-10-03 | `speculating` | Absence is limited to the searches listed. |
| The repo has deterministic spec checks (`validate-spec`, typed frontmatter and test-contract schemas, goal coverage) but no EARS validator. | `src/easy_cheese/skills/mold/validate_spec.py`, `src/easy_cheese_schemas/contracts.py:2928-2980` | repo code | live | `speculating` | The EARS absence is limited to the mold skill and `src/`. |

## Open questions

- Q1: Do we use Optimas-style local search with a global acceptance gate, MASS-style block-first staging, or CANTANTE-style per-phase contrastive attribution? `speculating`
- Q2: Do we record gate inputs (numstat rows, curd list, readiness booleans, base commit) so pure gates can be replayed offline? Or do we fork live with a pinned commit and same-model control forks? Or do we add logged propensities (randomized gates) for off-policy evaluation? `speculating`
- Q3: Do we add schema fields for tier, leverage, and route? If so, does the reasoning come before the decision field? Or do we extract from transcripts and measure extraction agreement first? `speculating`
- Q4: Is the ergonomics signal the resume cost from a wheypoint, a simulated user calibrated against real sessions, or observational analytics with known confounders? `speculating`
- Q5: Do we use a gskill-style bounded side info (truncated test output and patch plus status), a terminal-bench-style full history, or a causal extract (STRACE)? `speculating`
- Q6: Does a judge serve only as side info for reflection, or as a scored objective? If scored, do we use answer-first judging, hidden anchors, or canaries? `speculating`
- Mold: Do we grade specs downstream (a fixed implementer's pass rate on the spec), by hidden-requirement recovery against a simulated user (Ambig-SWE), by question quality (HumanEvalComm), or by deterministic structure checks (`validate-spec`)? `speculating`

## Confidence

`speculating`: Local code and GEPA upstream code are verified. Most external claims rest on a single 2025-2026 paper, often read at abstract or summary level, and key ablations (Q1, Q6 in coding) are missing.

## Next step

Run `/culture` on these forks. Then run `/mold` on a workflow-grader spec that includes the forked benchmark task set.

## Searched, empty

- Current web, "Goodhart proxy misalignment local metric prompt optimization compound" (2 queries) → no relevant result.
- Current web, Optimas local-only against global-only ablation → not in the retrieved extract.
- Current web, GEPA per-module against whole-system feedback ablation → none found.
- Current web, LLM extraction of decisions from agent transcripts, agreement rates → none found.
- Current web, router-specific off-policy evaluation and human-labeled tier oracles → none found.
- Current web, LangGraph and OpenAI Agents SDK decision tracing → not verified.
- Current web, coding-specific simulated-user fidelity against real users → none found.
- Current web, EARS conformance checkers, Smella, Paska → none found.
- Current web, hidden-requirement recovery from merged PRs → none found.
- Current web, reflection-context length threshold → none found.
- Current web, direct evidence of judge hacking inside GEPA or DSPy loops → adjacent evidence only.

## Verification log

- Five researchers and one explorer ran on 2026-10-03. The raw notes are in raw/a-01 through raw/e-01.
- The GEPA upstream code was read from a depth-1 clone (raw/d-02-github-gepa.md).
- Most arXiv claims came through WebFetch summaries or query-reranked extracts, so their quotes are close to the source but not verbatim.
- Local citations refer to main `f06f5d77`.

## agent_resolution

| Work | Selected | Permissions | Isolation | Power | Effort |
| --- | --- | --- | --- | --- | --- |
| Staged and joint optimization | researcher | read-only | fresh-context | default | medium |
| Gate grading and decision logging | researcher | read-only | fresh-context | default | medium |
| Ergonomics proxies | researcher | read-only | fresh-context | default | medium |
| Side info and judges | researcher | read-only | fresh-context | default | medium |
| Spec-quality graders | researcher | read-only | fresh-context | default | medium |
| Local gate, fork, and spec seams | explorer | read-only | fresh-context | default | medium |

## References

[^optimas]: https://arxiv.org/html/2507.03041v3 (fetched 2026-10-03).
[^mass]: https://arxiv.org/pdf/2502.02533 (fetched 2026-10-03).
[^cantante]: https://arxiv.org/html/2605.13295v1 (fetched 2026-10-03).
[^credit-unify]: https://arxiv.org/html/2605.30227v1 (fetched 2026-10-03).
[^replay-gap]: https://arxiv.org/html/2608.08239 (fetched 2026-10-03).
[^dudik]: https://arxiv.org/abs/1103.4601 (fetched 2026-10-03) [unverified].
[^speak-freely]: https://arxiv.org/abs/2408.02442 (fetched 2026-10-03).
[^dottxt]: https://blog.dottxt.ai/say-what-you-mean.html (fetched 2026-10-03).
[^castillo]: https://dylancastillo.co/posts/say-what-you-mean-sometimes.html (fetched 2026-10-03).
[^edm]: https://educationaldatamining.org/wp-content/uploads/2026/proceedings/2026.EDM.full-papers/2026.EDM.full-papers.21.pdf (fetched 2026-10-03).
[^otel]: https://github.com/open-telemetry/semantic-conventions-genai (fetched 2026-10-03).
[^handoff-debt]: https://arxiv.org/html/2606.02875 (fetched 2026-10-03).
[^sim-gap]: https://arxiv.org/html/2603.11245v1 (fetched 2026-10-03).
[^userproxy]: https://arxiv.org/html/2609.38043v1 (fetched 2026-10-03).
[^metr-rct]: https://arxiv.org/abs/2507.09089 (fetched 2026-10-03).
[^metr-update]: https://metr.org/blog/2026-02-24-uplift-update (fetched 2026-10-03).
[^swe-chat]: https://arxiv.org/html/2604.20779v1 (fetched 2026-10-03).
[^gepa-repo]: https://github.com/gepa-ai/gepa (fetched 2026-10-03).
[^asi-paper]: https://arxiv.org/html/2605.19633 (fetched 2026-10-03).
[^strace]: https://arxiv.org/abs/2607.07702 (fetched 2026-10-03).
[^judge-hack]: https://arxiv.org/abs/2607.05904 (fetched 2026-10-03).
[^traj-judge]: https://arxiv.org/html/2609.00038 (fetched 2026-10-03).
[^not-oracle]: https://arxiv.org/abs/2609.02246 (fetched 2026-10-03).
[^ambig-swe]: https://arxiv.org/html/2502.13069v2 (fetched 2026-10-03).
[^humanevalcomm]: https://github.com/jie-jw-wu/human-eval-comm (fetched 2026-10-03).
[^swe-pro]: https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20(9).pdf (fetched 2026-10-03) [unverified].
[^self-plan]: https://arxiv.org/html/2303.06689v5 (fetched 2026-10-03).
[^iso-llm]: https://arxiv.org/html/2408.10886v1 (fetched 2026-10-03).
