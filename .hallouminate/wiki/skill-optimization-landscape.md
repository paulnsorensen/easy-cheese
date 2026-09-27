# Skill optimization landscape — harnesses, task sources, and per-skill problems

Record of the 2026-09-26 sweep that answered "how do we auto-optimize our
skills against real-world problems". It lists every harness, benchmark,
research report, and handoff on this machine that bears on the question, so
the next session does not repeat the search. It then breaks the problem into
self-contained per-skill pieces and records the design intent for the pieces
that come last (`/mold`, skill routing).

Status: landscape and intent. No design decision is locked. PR #722 is the
only code.

## The one-line answer

PR #722 `scripts/agent_lab.py` is already the gskill shape: evolve a
SKILL.md with GEPA, run a real headless agent per task, grade by fail-to-pass
tests. It lacks real tasks, a real skill-loading path, and graders for
skills that have no test oracle. The tilth `benchmark/` harness already
supplies the runner, pinned real repos, fix tasks, budget caps, paired
statistics, and a graduation gate. Use it as the fitness function; keep the
GEPA loop, candidate export, holdout gate, and size gate in easy-cheese.

## External prior art

| Source | What it is | Take |
| --- | --- | --- |
| gskill (`github.com/itsmostafa/gskill`, documented as an official GEPA recipe) | SWE-smith tasks → static-analysis seed SKILL.md → `optimize_anything` loop → mini-SWE-agent in Docker → FAIL_TO_PASS grading | Right shape, wrong runtime: the agent in the loop is mini-SWE-agent; Claude Code is only a downstream consumer. Results (55→82% Jinja, 24→93% Bleve, Haiku 4.5 transfer 79→100%) are self-reported, no independent replication. |
| GEPA (`gepa-ai/gepa`, PyPI 0.1.4, arXiv 2507.19457) | `gepa.optimize` for a text dict; `optimize_anything` for arbitrary artifacts; `GEPAAdapter` = `evaluate` + `make_reflective_dataset`; budget via `max_metric_calls`; `reflection_lm` takes LiteLLM strings | Local reflection model is inferred, not documented. #722 sidesteps it by reflecting through `claude -p`. |
| Anthropic `claude plugin eval` | prompt + expected_output evals per skill | Trigger and trace checks, no outcome grader. `skills/plate/evals/evals.json` uses this shape. |

Full digest: `.cheese/research/gskill-gepa/gskill-gepa.md` (transient) —
promote if needed.

## Harnesses and benchmarks already on this machine

| Asset | Location | State | Reuse |
| --- | --- | --- | --- |
| tilth `benchmark/` | `/home/paul/Dev/tilth/benchmark/` (`run.py`, `paired.py`, `stats.py`, `pricing.yaml`, `graduation/evaluate.py`, `tasks/*.py`) | Working. 26+ tasks, 11 `capability = "fix"`, pinned gin/express/fastapi/ripgrep; `claude -p`, `codex exec`, `opencode run`; `--setting-sources ""`, `--mcp-config`, `--max-budget-usd`; paired-bootstrap cost-per-correct; 243-row $30 runs on record | **Fitness function.** A candidate skill is one more mode. Needs a `skills_dir` overlay (~20 lines). |
| tilth ADR-006 (`tilth-list-orient-view`) | `/home/paul/Dev/tilth-jahala/.cheese/notes/tilth-list-orient-view.md` | A prototype branch failed the benchmark merge gate (14/18 vs 11/18) and was parked | Precedent: no benchmark win, no merge. |
| `tilth-sonnet5-cost-attribution` | `/home/paul/Dev/tilth/.cheese/notes/` | Cost is the fixed MCP prefix (~5k tokens/cell, cache-written per fresh session), not per-call output | Run candidates at Haiku, validate winners at Sonnet/Opus/Fable. |
| PR #722 `agent_lab.py` / `prompt_lab.py` | branch `paulnsorensen/dspy-prompt-tests` (CI green, open) | 3 synthetic `calc.py` tasks; candidate appended to system prompt; settings, hooks, MCP dropped | Keep the GEPA loop, export rule, holdout split, budget caps. Replace the runner. |
| /age seeded-defect benchmark | XDG corpus `benchmark/age/<run>/results/age/*.json` (20 runs, CR-Bench fields `hits/noise/precision/recall/snr`) | Harness removed in PR #669; results format survives | Reuse the result schema for the /age grader. |
| hallouminate agent-bench | remote branches `paulnsorensen/agent-bench-tier0`, `-pilot` | Paired-arm wiki-vs-baseline; never run live | Pattern only. |
| cheez-wiki `agent-benchmarking`, `benchmark-ci-gates`, `code-quality-benchmarks` | `/home/paul/Dev/cheez-wiki/.hallouminate/wiki/projects/` | Design pages: the disqualifier test (harness must run the real agent with our skills and MCP), PR gate 5–15 tasks <$3 <10 min diff-aware, weekly 4–5 arm matrix, copeca and Harbor pass, SlopCodeBench-style erosion metric | CI shape and the slop guard. |
| Research `seeded-defect-review-benchmark-cost` (2026-09-12) | XDG corpus `research/` | No drop-in corpus exists; LLM-judge scoring with CR-Bench buckets is settled and cheap; telemetry cannot see misses | Grader design for /age. |
| `age-beyond-default` (gated/mold) | XDG corpus `work/age-beyond-default`; wiki `research/review-dimensions-prompt-comparison.md`, `review-fanout-policy-comparison.md` | Forks F1–F12; F11 = measurement harness; blocker: age and cure SKILL.md at 3593/3585 of 3600 tokens | F11 is the /age grader. |
| Session analytics DuckDB | `~/.cache/dotfiles/session-analytics/sessions.duckdb` (2.3 GB; `raw_entries`, `skill_invocations`, `agent_spawns`, `tool_uses`, …) | Observational only; full-table JSON scans OOM at 7 GB — filter on `cwd` and `timestamp` first, or use the `duckdb-expert` packs | Trend signal and reflection material, never fitness. |
| `wgs-audit-brief` / `wgs-audit-report` | `.cheese/notes/` | writing-great-skills rubric audit of 18 skills (duplication 18/18, sediment 4/18, no-ops 5/18) | A static text-quality grader for candidates. |
| `skills/{briesearch,cook,mold}/references/evals.md` | repo | Should/should-not-trigger lists and trace checks; manual today | Mechanical trace checks for the briesearch grader. |
| dotfiles `global-instruction-tightening` (PR #985) | dotfiles corpus | Analytics-driven manual rewrite: 2,248 → 898 tokens | The human version of the loop we want to automate. |

## Real-world task sources (no hand authoring)

1. Mine merged `fix:` PRs with test changes on easy-cheese, tilth,
   hallouminate: task = `{repo, base_sha, prompt = issue or PR body,
   test_command = the PR's tests}`. The existing "mutation must fail before
   the agent runs" check already proves fail-at-base / pass-at-head.
2. tilth's 11 fix tasks and 15 locate/trace tasks (already pinned).
3. Session failures captured as tasks: one command records `repo, HEAD sha,
   prompt, what correct looks like`. The `evals.md` failure-mode lists are
   the taxonomy.
4. Session analytics stays a trend signal.

## Per-skill problems that are self-contained

Each row is one optimization problem with its own task source, grader, and
fitness. They do not depend on each other. `/age` and `/cook` must look at
real code, never the toy fixture.

| Skill | Task | Grader | Fitness | Notes |
| --- | --- | --- | --- | --- |
| `/cook` | Mined fix PRs + tilth fix tasks on pinned real repos | Fail-to-pass test command | Paired cost-per-correct vs seed; token-budget gate; erosion delta on the diff | Grade the diff quality too, or GEPA learns slop. |
| `/age` | The same mined PRs presented as the buggy diff (pre-fix tree + the PR's own change reversed, or a planted defect per overlap area) | LLM judge, CR-Bench buckets Bug Hit / Valid Suggestion / Noise → recall, precision, SNR | Recall on the injected bug with precision floor | Result schema exists from the #669 runs. Also grade the unchanged 5 age-only dimensions. |
| `/cure` | An /age report with selected findings on a real diff | Tests pass, finding resolved, no unrelated hunks | Pass rate and diff scope | Shares the /cook runner. |
| `/press` | A cooked diff with a known weak test | Does press add a test that fails on the seeded regression | Regression caught yes/no | Cheap once /cook tasks exist. |
| `/briesearch` | The 13 durable research reports as references plus fresh questions from real sessions | Mechanical trace checks from `references/evals.md` (plan before routing, routing block, claim table, confidence cap, raw on disk) plus judge on claim coverage against the reference report | Trace-check pass count plus coverage | Must also test the smart route: ground locally (wiki, `/culture` state) and in code (tilth) before web. |
| `/plate` | `claude plugin eval` shape already in `skills/plate/evals/evals.json` | Expected-output judge | Trigger and behavior | Cheapest first target for the trigger grader. |
| Trigger evals (all skills) | Should/should-not lists in `evals.md` | Did the skill fire | Precision and recall of invocation | Runs through `claude -p` with the candidate installed. |

Deferred, record intent only:

- `/mold`: harder because the oracle is a human-approved spec and the
  dialogue is interactive. Intent: replay recorded mold dialogues (the XDG
  `specs/` corpus has 46 approved specs with provenance) and grade the
  produced spec against the approved one on entities, gates, and
  non-goals. Design after the outcome-graded skills work.
- Skill routing (`/cheese`): harder because the oracle is "which skill
  should have run". Intent: derive routing tasks from session analytics
  (`skill_invocations` with the user's first turn) and grade the route
  choice. Design last; it depends on the per-skill graders.

## Harness gaps to close before optimizing anything real


User direction (2026-09-26): the loops optimize for maximal results and
for token size, and they may create and edit the packaged CLIs. Three
consequences:

- **Two objectives, not one.** Fitness is a vector: outcome (correct,
  bug hit, trace pass) and tokens spent (cache-read included, per the
  rebuild measurements where cache-read is 95% of all tokens). GEPA is a
  Pareto optimizer, so keep both dimensions in the score instead of
  collapsing them; the tilth harness already reports cost-per-correct,
  which is the same trade expressed in dollars. Promote a candidate only
  when it is not dominated on either axis by the seed.
- **The candidate is the whole skill, code included.** A candidate is
  `SKILL.md`, `references/*.md`, and `src/easy_cheese/skills/<skill>/`
  (the Python that builds into `skills/<skill>/scripts/<skill>.pyz`). The
  reflection step may move prose into code, add a subcommand, or delete a
  reference; that is the code-over-prose directive from the rebuild
  exercise applied by the optimizer. A code candidate must pass
  `just bundle` and the skill's own tests before it earns an agent run, so
  the fitness function runs the build and test gate first and scores a
  broken build as 0 without spending inference.
- **Token accounting needs the harness, not the transcript.** Count
  tokens from `claude -p --output-format json` usage (the tilth runner
  already records `model_usage` per cell), split into skill-load tokens
  (SKILL.md plus loaded references) and run tokens, so the optimizer can
  see when a shorter skill costs more turns.


- Install the candidate as a skill in the disposable workspace
  (`.claude/skills/<name>/`), not as a system-prompt append, so discovery,
  `references/*.md`, and sub-agent dispatch are graded.
- Multi-component candidates: `SKILL.md` plus each `references/*.md` as
  separate GEPA components.
- Token-budget gate from `validate_skills.py` scores 0. See
  [skill-size-budget](./skill-size-budget.md).
- Do not drop MCP wholesale: tilth is part of the skill contract. The tilth
  harness already handles `--mcp-config`.
- Models: run candidates at Haiku for volume; validate the winner at Sonnet,
  and at Opus or Fable when the user wants the promoted skill measured on
  the models that actually run it. Budget per optimize: ~30 tasks × 8 metric
  calls ≈ 240 runs.
- Promotion rule: the graduation gate decides, not the optimizer. Same as
  tilth ADR-006.

## Related redesign threads (found by the same sweep)

These sessions and records discuss rebuilding the CLI and the skill pack.
They constrain what a skill optimizer targets.

| Thread | Where | What it decided or left open |
| --- | --- | --- |
| Rebuild from scratch (2026-09-21, session `66a38ed6`) | `.cheese/notes/rebuild-easy-cheese-from-scratch.md`; XDG `research/rebuild-easy-cheese-from-scratch/` | Directives: keep the pyz; keep exported schemas and code; code limits nondeterminism to cut tokens; test whether the pack is overbuilt. Measured: age 968, cook 525, plate 131, cure 124 sessions; ~30 skills ≤4 loads in 60 days; ~85% of loads from omp; p50 chain 3.4 h and 129M cache-read tokens. Six forks open, next `/culture`. |
| Rewrite summary (2026-09-23, session `01564f36`) | transcript only; the worktree is gone | Found exactly one local rebuild session. Named the moat: compiled per-skill CLI, exported schema catalog (21 contract URIs), artifact machinery. |
| CLI rebuild (2026-09-24, session `63656582`) | XDG `specs/wheypoint-cli.md`; worktree `easy-cheese-cli-rebuild-3ae768` | "Anything is on the table." A shared CLI layer at `src/easy_cheese/cli/`, wheypoint first, machine-wide handoff discovery. Shipped as fromargs (#724, #725) and `wheypoint list --scope machine` (#719). |
| Enforceable skill boundaries (2026-08-24) | worktree `easy-cheese-cli-rebuild-3ae768/.cheese/specs/enforceable-skill-boundaries.md` + glossary + issues F001/F002 | One bundle per skill, `@bundle_command`, `HandoffPointer`, `NormalizationReceipt`, `contract migrate/accept/publish`. Mold → Cook slice first. |
| Skill parity (2026-06) | [skill-parity-analysis](./skill-parity-analysis.md) | Struck list — do not re-litigate without re-checking. |
| Global instruction tightening (2026-09-15) | dotfiles PR #985 | Analytics-driven prose cut; the same method applies to skills. |

Not found in the scope checked (Claude, Codex, omp logs since 2026-07-15; a
2.3 GB DuckDB scan hit the memory limit, so the JSONL grep is the source):
the Sep 6–7 "we overbuild in never-ending mold sessions" session that the
Sep 23 summary cites. Locate it by date if needed.

## Suggested order

1. Merge #722 as the loop; treat its `ClaudeRunner` as throwaway.
2. `skills_dir` overlay in tilth `benchmark/run.py` modes.
3. `agent_lab tasks mine <repo>` from merged fix PRs; import tilth's tasks.
4. Install-as-skill injection, multi-component candidates, size gate,
   erosion guard.
5. `/cook` first, then `/age` via the seeded-diff grader, then
   `/briesearch` via trace checks, then trigger evals for every skill.
6. Weekly holdout eval routine (PR #570 sketches the job); `optimize` stays
   manual and budgeted.
7. `/mold` and routing last.
