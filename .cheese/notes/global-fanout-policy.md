## Handoff slug

```
status: gated: forks 2 through 6 remain open; fork 7 closed and fork 1 reframed this session
next: mold
mode: single
artifact: none
session: claude:627465cf-63af-4470-a3fb-55a32edf483b
git: paulnsorensen/cheese-factory-refs@273585a3
created: 2026-07-28T06:15:59Z
parents: [global-fanout-policy, cheese-factory-refs]
baseline: none
BEFORE ANY DESIGN WORK, do two things in order: read the standing harness-agnostic constraint in the first Document section, then pull gh issue 313 into context and ingest it into the local hallouminate wiki. The playbook for this spec must account for issue 313, which no session has read yet. Fork 7 is closed. The currency inventory was rebuilt from source and the prior note's five-currency taxonomy was falsified.
```

## Document

### Standing constraint: this repo assumes nothing about the harness

The user issued this correction directly. It overrides prior sessions' reasoning and applies to every remaining fork.

easy-cheese ships to hosts that are not Claude Code. It must assume nothing on the other end of the harness. Concretely:

- `~/.claude/workflows/*.js` are **out of scope**. Do not edit them, do not design for them, and never treat their runtime behaviour as a safety net.
- Specifically falsified this session `<certain>`: the claim that uncapped dispatch sites are "backstopped by the harness at min(16, cores-2) concurrent and 1000 total". That reasoning is invalid for this repo. Any cap the design needs must be expressed inside the repo, in a form a harness-agnostic host can honour without a Claude-specific runtime.
- Workflow scripts may still be cited as evidence that a given unit exists, because they were written against the same problem. They are never cited as design targets, and never as a fallback.
- This is consistent with the locked decision that PR #314 closes and the workflow scripts extract to `paulnsorensen/dotfiles`. Those scripts are leaving.

A resumed session that starts reasoning about what the harness will do for us has drifted. Stop and re-read this section.

### Mandatory first action: gh issue 313

Not yet read by any session. Pull it into context, then ingest it into the local hallouminate wiki so it survives future context clears.

```
gh issue view 313 --repo paulnsorensen/easy-cheese --comments
```

Then write the distilled content into the repo wiki via hallouminate `add_markdown`, capturing the why rather than restating the issue body. The playbook this spec produces must take issue 313 into account, so read it before weighing any remaining fork.

### Goal

Produce one approved spec covering the machine's agent fan-out policy. Four parts: port dotfiles ADR-006 so `/cook` reviews at an Integrate barrier instead of per curd, build the `/pasteurize` fan pathway with instrumentation, reconcile the routing-policy documents and resolve their conflicting defaults, and re-derive every fan-out cap and heuristic rather than only the ones a prior note happened to list.

### State

**Done and verified this session.** Fork 7 is closed. The full currency inventory was rebuilt from source across three surfaces. External research is complete, with three cited reports on disk. Four prior claims were falsified and are corrected below.

**In flight.** The mold dialogue. Fork 2 has been weighed in prose with cited evidence but no decision was taken. Forks 1, 3, 4, 5 and 6 have had no weighing.

**Untouched.** No spec written. No branch cut. No ADR authored. No code changed. gh issue 313 unread.

### Corrections to the prior handoff

Verified this session. These supersede the prior note. Do not re-derive them.

1. **The environment claim is stale.** `<certain>` The branch is no longer one commit behind. `paulnsorensen/cheese-factory-refs` is at `273585a3`, identical to `origin/main`, zero ahead and zero behind. The stale-read hazard the prior note warned about is gone, so reading the working tree is now safe. The only dirty path is an untracked `.claude/` directory.

2. **"Roughly seventy numbers across five currencies" is wrong in both terms.** `<certain>` There are at least fifteen genuinely distinct units, catalogued below. The five-bucket taxonomy collapsed units that measure different things, and it had no slot at all for ordinal or categorical gates.

3. **"Four measured against thirteen unmeasured" is misleading.** `<certain>` There are three provenance tiers, not two. A test asserting a literal is a change-detector, not a derivation. Only `FILE_COST` is genuinely derived from data with computed headroom. See the provenance column below.

4. **"The one uncapped fan-out is milknado-fleet" undercounted.** `<certain>` There are at least four uncapped dispatch sites, all of them in workflow scripts and therefore out of scope per the standing constraint. Recorded below for completeness only.

5. **Curd count and concurrent-agent count are distinct quantities.** `<certain>` `mode.py:36-40` reads only `len(curds)`, which has no ceiling anywhere. `curd_block.py:107-108` rejects any wave with more than `MAX_WAVE_SIZE` (4) slugs. Twelve curds is three waves of four, so the two numbers coincide only while curd count is at or below four. A sub-agent this session claimed they were the same integer by construction; that claim is wrong above four, and its own evidence table contradicted it.

### The currency inventory

Every unit in which a fan-out, dispatch, effort, or routing threshold is expressed, with where each comes from. Provenance tiers:

- **derived** means pinned against the frozen 30-commit fixture with measured headroom.
- **change-detected** means a test asserts the literal, so it cannot drift silently, but nothing justifies the value.
- **free-floating** means the test reads the constant symbolically, so any value passes and the number is unpinned in practice.
- **asserted** means stated in prose or config with no test at all.
- **out of scope** means it exists only in `~/.claude/workflows/`, recorded as evidence that the unit exists, never as a design input.

**Magnitude of work**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Weighted review-surface score | `age_route.py:90-92` `_SCORE_N2_FLOOR=60`, `_SCORE_N5_FLOOR=250`, `_HIGH_EFFORT_SCORE=900` | change-detected (`test_age_route.py:63-64,68,72,76,80,84`) |
| Same unit, two more thresholds | `mode.py:33` `DECOMPOSE_FIRST_THRESHOLD=250`; `pasteurize_route.py:26` `WIDE_RANGE_THRESHOLD=250` | **free-floating** (`test_mode.py:91-105`, `test_pasteurize_route.py:88-94` both read the symbol) |
| Score composition, files to attention-lines | `review_surface.py:23` `FILE_COST=8` | **derived**, safe range 7.33 to 9.11; minus ten percent breaks the pyramid test, plus ten percent passes |
| Score composition, per-path line weight | `review_surface.py:29-44` `DEFAULT_WEIGHTS` 0.0 / 0.25 / 1.0 | per-entry exercised (`test_review_surface.py:27-46`); the table is never asserted whole |
| Estimated edit lines, a declared estimate rather than a measurement | `curd_block.py:43` `MIN_CURD_SURFACE=25` | free-floating (`test_curd_block.py:24,225,232` symbolic) |
| Lines in one file | `preamble.md:69` roughly 800; `skill-authoring.md:38` roughly 80 to 150 for a SKILL.md body | asserted |
| Edit sites | `preamble.md:69` roughly 5 | asserted |
| Symbols touched | `mold/references/context-budget.md:15` more than 5 | asserted |
| Raw files changed, raw diff lines | `>15 files`, `>800 lines` | **out of scope and stale**, see the drift section |

**Partition and parallelism**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Curd count, the partition count, unbounded above | `mode.py:28` `PARALLEL_THRESHOLD=2` | change-detected (`test_mode.py:43` asserts the literal). Imported by `validate_decomposition.py:10` and `src/mold/curd-count.py:20`, and is the only shared value in the repo that cannot drift |
| Wave size, the concurrency cap | `curd_block.py:42` `MAX_WAVE_SIZE=4`, enforced at `curd_block.py:107-108` | change-detected with zero headroom (`test_curd_block.py:95-99` asserts the error text contains "4") |
| Review lens count | `age_route.py:99` `_TIER_ORDER=(1,2,5)`, promoting uncapped to a natural maximum of 9 (`age/SKILL.md:140`) | the tuple is never asserted by name, but the values 1, 2 and 5 are literal-pinned roughly twenty times in `test_age_route.py` |
| Debug agent count | eight constants at `pasteurize_route.py:29-50`, values 1, 2, 2, 3, 3, 3, 5 | six literal-pinned, two via symbol. The module docstring at `pasteurize_route.py:19-24` self-declares that every threshold is a reasoned guess, not a measurement |
| PR review comments, as a ladder bump trigger | `age_route.py:96` `_AFFINAGE_COMMENT_BUMP=10` | change-detected with zero headroom (`test_age_route.py:314-319`) |

**Agent runway**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Turns | `registry.yaml` maxTurns 50 and 100; `turn-budget-guard.js:100-111` soft and hard at 40/50 and 75/100 | asserted config. The guard is the enforcing surface |
| Context tokens | `turn-budget-guard.js:97-98` 110k soft, 130k hard | measured against real transcript usage, the only other genuinely grounded currency |
| Context tokens, a second unrelated pair | `mold/references/context-budget.md:33-34` roughly 120k and 140k | asserted, and explicitly labelled not measured |
| Grace tool-calls | `turn-budget-guard.js:74` `CTX_GRACE_CALLS=3` | asserted |

**Loops**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Pipeline rounds | cure passes 2 (`cook/SKILL.md:262,265`), fix rounds 2 (`:271`), taste-test 2 (`:44`), fix attempts 3 (`pasteurize/SKILL.md:108,112`), hypothesis rounds 2 (`:224`), fork questions 3 (`mold/SKILL.md:21`) | asserted |
| Retry count | `curd.py:85` bound `0 <= retry_count <= 1`, an inline literal with no named constant | **fully unpinned**. Every fixture in every fan-out test sets `retry_count: 0`, so the upper bound is never exercised |
| Repro executions | `repro-rerun.py:30` `DEFAULT_RUNS=3`; `--runs 5` and "loop the trigger 100 times" at `pasteurize/SKILL.md:36,54,57` | the constant is value-pinned at `tests/pasteurize/python/test_repro_rerun.py:88-92`; the prose numbers are asserted |

**Units that are not counts at all**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Reproduction rate, a probability | `pasteurize/SKILL.md:44` above 50 percent is debuggable, 1 percent is not | asserted |
| Wall-clock | `gate-graph.py:205` a 30 second subprocess timeout; `pasteurize/SKILL.md:47` 30 seconds and 5 seconds for loop speed; `turn-budget-guard.js:65` `STALE_HOURS=6` | asserted |
| Characters | `preamble.md:69` roughly 4k for a dispatch prompt; `skill-authoring.md:23` 1024 for a Codex description; `query-planning.md:18` 400 for a Tavily query | asserted, and the 1024 is an external constraint |
| Bytes | `sub-agent-gate.md:9` roughly 2 KB digest ceiling; `turn-budget-guard.js:84` 5 MB log rotation; `:332` 256 KB tail read; `briesearch/references/context-isolation.md:10` 150K to 1M characters of raw fetch | asserted |
| Fetches, URLs, results | `context-isolation.md:19-20` more than 10 results, more than 3 URLs; `context-budget.md:13` three or more fetches, two or more search angles | asserted |

**Ordinal and categorical gates, which the five-bucket taxonomy had no slot for**

| Unit | Thresholds | Provenance |
| --- | --- | --- |
| Effort | low, medium, high at `age_route.py:181-187` and `validate_manifest.py:36` | change-detected via the score ladder tests |
| Model power | `validate_manifest.py:33-35` `POWER_RANK` cheap, default, powerful; floor-gated at `:244-270` | partially pinned. `test_validate_manifest.py:523-531` pins only that cheap is below powerful. The `default` tier is never tested and the rank integers are never asserted |
| Severity tier | medium-plus findings gate whether curds are marked dirty and re-run | asserted, and this is a genuine fan-out gate expressed in tiers rather than integers |
| SOLO quality score | `freshness-check.py:38-39` bounds 1 to 5, default pass floor 3 at `:168` | asserted |
| Bug shape | `pasteurize_route.py:52` five categories selecting among the eight debug-agent constants | change-detected through the route tests |
| CI class | `age_route.py:97` `_AFFINAGE_CI_BUMP_CLASSES` membership triggers an ordinal bump | partially pinned. `test_age_route.py:303-331` exercises failing, red, flaky and passing only |
| Topology, PR shape, phase | enums at `validate_manifest.py:37`, `validate_pr_plan.py`, `phase_decision.py:46-54` | schema-enforced |

**Conversion ratios, which are their own category**

`review_surface.py:23` `FILE_COST=8` converts files to attention-lines and is the only derived number in the repo. `turn-budget-guard.js:80` `BYTES_PER_TOKEN_ESTIMATE=4` converts bytes to tokens on the fallback path. `review_surface.py:29-44` `DEFAULT_WEIGHTS` converts a path glob to a per-line weight multiplier.

**Out of scope, recorded as evidence only**

The workflow scripts carry further units that have no in-repo equivalent: worker-pool lanes, batch and chunk sizes, item-gather limits, and a runtime-injected token budget object. Four dispatch sites in those scripts have no cap. None of this is a design input. See the standing constraint.

### Confirmed drift, all of it in scope except where noted

1. **A deployed script gates fan-out on a rule the owning skill repudiates.** `<certain>` `cheese-factory.js:614-615` reads "Thresholds from /age SKILL.md section scale threshold" and gates on `files_changed > 15 || lines_changed > 800`. `skills/age/SKILL.md:129` states that `/age` sizes its own fan-out via the age router "rather than a size-only threshold". Duplicated verbatim at `move-my-cheese.js:266` with no shared import. Both copies are out of scope for editing, but this is the strongest available evidence for what duplicated thresholds do on this machine, and it is the decisive argument in fork 2.
2. **Two of the three literal 250s were never pinned to 250.** `<certain>` No test file imports more than one of the three owning modules, so a cross-check is structurally impossible today. `DECOMPOSE_FIRST_THRESHOLD` and `WIDE_RANGE_THRESHOLD` can be changed to any value with zero test failures.
3. **`registry.yaml` disagrees with its enforcing guard.** `<certain>` `agents/registry.yaml:206` declares `worktree-content-digest: maxTurns: 30`, but `turn-budget-guard.js` has no key for that type, so the enforced cap is the default 50. Every other type that appears in both tables matches.
4. **The literal 250 appears in no workflow script.** `<certain>` That drift is Python-only, narrower than the prior note implied.

### Locked decisions

Carried forward unchanged from the prior note, plus one added this session. Implement them. Do not re-open them.

- **PR #314 closes, and the workflow scripts extract to `paulnsorensen/dotfiles` via a new ticket on that repo. DO NOT RE-OPEN THIS.** The user was asked twice and gave the identical answer both times. New evidence about this decision belongs in the spec, not in another question.
- **This knowingly reverses ADR-4, and the spec must record that.** `<certain>` `adr/subagent-routing-overhaul.md:42-43` describes the migration that PR #314 implements. The spec must author a new ADR superseding ADR-4 with the reversal and its rationale. ADR-4's stated reason was that the workflow drifted from the skills once already; the reversal should say why that risk is now acceptable.
- **Part (iii) is reconciliation, not authoring.** The policy page exists. The work is updating its stale `## Current state` block and resolving conflicting defaults across the policy documents.
- **Agenda 7 is instrumentation only.** The `/pasteurize` pathway emits its routing decision and outcome to a durable log so the eight constants become calibratable later. No fixture capture now.
- **Scope covers every fan-out cap and heuristic**, not only the ones a prior note listed.
- **Agenda item 1 resolves downstream of the #314 decision.** Retirement of `cheese-factory.js` is off the table; it lives on in dotfiles.
- **Both in-repo `/cheese-factory` references get deleted** (`skills/cook/SKILL.md:55` and `skills/cheese/references/routing-policy.md:16`), going out with the port rather than separately. `pasteurize_route.py` is kept and wired rather than cut. `/age`'s merged score ladder is not up for redesign.
- **New, added this session: the harness-agnostic constraint** in the first Document section is locked. It is a user directive, not a design preference.

### Fork 7, closed this session

**Resolution: one source of truth per unit, instrument the count currency, and write the repo's existing conversion rule down as policy.** The question was never unify-versus-tune. It was one-source-of-truth versus many.

The rule the repo already implements, in two places `<certain>`:

- `review_surface.py:21-23` converts files to attention-lines where the conversion is sound, and pins it against the fixture.
- `mode.py:44-46` refuses to convert score into a parallelism decision, on the stated ground that "score alone proves nothing about file-disjointness, so blind parallel fan-out is never safe at any size".

That is unify-where-sound and refuse-where-not, already in the code. The spec's job is to state it and apply it consistently.

Supporting external evidence, with full reports on disk:

- No shipped agent framework gates fan-out on input magnitude. All gate on runtime budget. `<certain>` across Anthropic, OpenAI Agents SDK, LangGraph, CrewAI and AutoGen, each checked against a resolving primary doc.
- Linear scalarization provably cannot reach concave regions of the Pareto front, so collapsing genuinely different objectives into one score destroys information structurally (Lin et al., NeurIPS 2019). `<certain>` The more distinct units the inventory finds, the stronger this gets.
- Unify-on-one-number is supported where one measured scalar drives one decision, as with SRE error budgets. `<certain>`
- Instrument-first has convergent support from three independent self-tuning lineages, DB2 STMM, JVM ergonomics and BBR. `<certain>` BBR is also the counter-example to collapsing everything, since it kept two control parameters rather than one.
- Anthropic's own engineering post states that multi-agent is a poor fit for coding, and their reported win was on breadth-first research. `<certain>` that this is what it asserts. Cognition's follow-up states that the narrow pattern works when writes stay single-threaded, which is what ADR-006's barrier design does. `<speculative>` on generalisation, but it belongs in the ADR as rationale.

### Decision dossier

**Fork 1: `MAX_WAVES` against ADR-3, now partly a taxonomy artifact.** ADR-3 resolved "waves cap concurrency at 4; no hard curd ceiling" (`adr/subagent-routing-overhaul.md:33-35`). Since curd count and wave size are now confirmed to be distinct quantities, `MAX_WAVES` conflicts with ADR-3 only if the two are treated as one currency. Options: reverse ADR-3 and add a hard cap; honour ADR-3 and make cook's gate display projected dispatch count and token cost so the human gates on cost; or drop the item. Reversing adds a second underived integer beside `MAX_WAVE_SIZE`. Honouring ADR-3 leaves the mold-approval and cook gates as the designed brake, which survive the pointer deletion untouched. Prior leaning: the user selected `MAX_WAVES` as in scope before ADR-3 surfaced.

**Fork 2: who fans the lenses. Weighed in prose this session, no decision taken.** The constraint is tool-level, not policy `<certain>`: `age/SKILL.md:68` states that fan-out requires `/age` not itself be a sub-agent because "a sub-agent cannot spawn sub-agents", and the `reviewer` role denies the `Agent` tool in `registry.yaml`. `cook/SKILL.md:99` dispatches `reviewer(age)` per curd, pinning every per-curd age to `n=1`. ADR-006 moves review to the barrier over the whole merged diff, which is the largest score in the run and would return `n=5` or higher, so the port creates exactly one review that most deserves fan-out and hands it the dispatch shape that forbids it.

Two facts narrow the fork. The string `Integrate` appears nowhere in `skills/cook/SKILL.md` `<certain>`, so the barrier is unbuilt in the native path and this is a greenfield decision. And `cook/SKILL.md:100`'s post-merge chain `press -> age -> cure -> age` carries no agent-type annotation, unlike line 99, so the post-merge age's dispatch level is currently unspecified. That ambiguity is a defect to fix under either option.

Option A, `/cook` dispatches N lens reviewers itself, can be priced exactly: `age-fanout.js` is 257 lines doing precisely that, and it duplicates seams 2, 3, 4 and 6 outside `/age`. Seam 4 applies the dimension-boundaries table's fifteen tiebreaker rules; seam 6 is a per-finding verifier with confirm, downgrade and escalate semantics. Option A means two copies of that logic, and the drift record above shows what that produces on this machine.

Option B, `/age` gains an orchestrator-called mode, is cheaper than the prior note priced it. The seam sequence at `age/SKILL.md:159-171` is already written entirely in orchestrator terms, and nothing in it requires that orchestrator be a user-invoked `/age`. Only the seam 1 predicate at line 68 binds it, so option B is plausibly a predicate change rather than a contract rewrite.

Both options pay the same cost, which the prior note missed: `/cook`'s orchestrator absorbs packet assembly, reconciliation over N workers' full finding rows (seam 3 line 166 is explicit that these are not digests and the size ceiling does not apply), and the verifier pass, while also managing the fan run.

A third option exists. The constraint is that the fanning level needs the `Agent` tool, not that it must be the top-level orchestrator. A dedicated review-orchestrator role holding `Agent` would keep `/cook`'s context clean and `/age`'s seams single-copy. It is blocked on the open question below.

Agent leaning `<speculative>`: option B reframed as a predicate change, because the seams are already authored for it and option A is the shape with a documented drift record. But settle the nesting question first.

**Fork 3: finding-to-curd routing.** ADR-006 routes barrier findings back to owning curds by file. Each curd already declares `files` as a required key in `src/fanout/curd_block.py`, so the data exists; the open item is confirming the manifest carries it through harvest. The fail-closed rule, marking all curds dirty when the barrier reports medium-plus with no per-curd routing, is stated in ADR-006 and is worth porting as a rule. No prior leaning.

**Fork 4: what replaces `clean_complete`.** `cook/SKILL.md:102` short-circuits a curd when its first age reports `next: done`, skipping cure and the final age. With no per-curd age that signal disappears. Options: the taste-test inherits the role, or the short-circuit goes away. No prior leaning.

**Fork 5: the `/pasteurize` seam shape.** `/age` has six seams. Pasteurize reconciles competing hypotheses rather than accumulating findings, so its reconciliation seam is a different problem: N debuggers proposing mutually exclusive causes against N reviewers contributing additive rows. Decide whether the packet and worker seams are reusable as-is. `fanout-fanin-discipline.md:44` prescribes fan-in for competing hypotheses "by disconfirming evidence, not voting". No prior leaning.

**Fork 6: repo split.** The policy reconciliation belongs in dotfiles; the barrier and the pathway belong in easy-cheese; the #314 closure and its extraction ticket span both. One spec with two PRs keeps the coupling visible but cannot be plated as a single branch; two specs split the coupling across artifacts that can drift apart. No prior leaning.

### Open questions and blockers

1. **gh issue 313 is unread.** It gates the playbook. Resolve first.
2. **Is level-2 agent nesting forbidden by the harness itself, or only by every registry leaf denying the `Agent` tool?** `<don't know>` This determines whether fork 2's third option exists. The answer must be established in a harness-agnostic way, per the standing constraint: even if one host permits nesting, the design cannot require it.
3. Forks 1 through 6 above.
4. Agenda 5, the `phase_decision.py` table rewrite, is mechanical and needs no fork. Both tables are pure and unit-tested, and the rewrite follows from fork 2.

### Artifacts

- `.cheese/research/fanout-currencies-frameworks/`, what shipped frameworks gate on.
- `.cheese/research/fanout-currencies-empirical/`, measured evidence on agent counts and diminishing returns.
- `.cheese/research/fanout-currencies-priorart/`, the unify-versus-separate dividing line.
- `.cheese/notes/cheese-factory-refs.md`, the grandparent note.
- The prior revision of this note is at `/tmp/global-fanout-policy.bak.md` for this session only.
- https://github.com/paulnsorensen/easy-cheese/issues/313, unread, gates the playbook.
- https://github.com/paulnsorensen/easy-cheese/pull/351, merged at `273585a3`.
- https://github.com/paulnsorensen/easy-cheese/pull/314, open, to be closed per the locked decision. Branch `paulnsorensen/cook-subagent-routing-overhaul`, head `30ab148807aa9c511c5e7d67160a81a004fc68d4`. Its copies are ahead of the dotfiles ones and the extraction ticket needs those additions plus the `{1,4,10}` to `{1,2,5}` reconciliation.
- `/Users/paul/Dev/dotfiles/.hallouminate/wiki/adr/subagent-routing-overhaul.md` and `adr/cheese-factory-workflow.md`, with ADR-006 at lines 40 to 45.
- `/Users/paul/Dev/dotfiles/.hallouminate/wiki/architecture/{subagent-routing-policy,fanout-fanin-discipline,subagent-turn-budgets}.md`.
- `/Users/paul/Dev/dotfiles/agents/{preamble.md,registry.yaml,lib/turn-budget-guard.js}`.
- Durable spec path for this slug resolves to `/Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/global-fanout-policy.md`. Nothing is written there yet.

Read dotfiles from `/Users/paul/Dev/dotfiles`, verified at `276dbc1`. Do not read `/Users/paul/conductor/workspaces/dotfiles/baku`, which is stale and caused a falsified claim in an earlier session.

### Suggested skills

Read gh issue 313 and ingest it into the wiki first. Then re-enter `/mold` on this slug, resuming at Shape. Fork 2 has been weighed and needs only a decision plus the nesting question settled. Then take forks 1, 3, 4, 5 and 6 in that order. The mold contract requires prose weighing with cited evidence before any structured question, and forks 1, 3, 4, 5 and 6 have had none.

### Environment

Workspace `/Users/paul/conductor/workspaces/easy-cheese/bissau`, branch `paulnsorensen/cheese-factory-refs` at `273585a3`, identical to `origin/main`, zero ahead and zero behind. The only dirty path is an untracked `.claude/` directory. Target branch is `origin/main`. The port itself wants a fresh branch off main. Cross-repo work touches `/Users/paul/Dev/dotfiles`. No secrets involved.
