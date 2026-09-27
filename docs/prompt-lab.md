# Prompt laboratory

Development-only proxy for comparing Markdown prompts with a sequential, JSON-state evaluator.

## Install

Use Python 3.12 and install the pinned optional tools without installing the repository:

```bash
python3 scripts/prompt_lab.py validate tests/fixtures/prompt_lab/dataset.json
```

The requirements pin `gepa==0.1.4` and `openai==3.19.2`. Offline validation needs only Python. GEPA is an optimizer algorithm. DSPy is a framework that integrates GEPA with signatures and modules. This prototype calls GEPA directly because raw Markdown and a custom evaluator need no DSPy conversion.

## Paid evaluation

Set `OPENAI_API_KEY` and pass an explicit model. The tool never prints or stores the key.

```bash
export OPENAI_API_KEY=...
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/prompt_lab.py evaluate \
  --dataset tests/fixtures/prompt_lab/dataset.json --prompt baseline --split validation \
  --model gpt-4.1-mini --output-dir .context/prompt-lab/eval-01
```

Compare `--prompt baseline`, `--prompt current`, or a Markdown path. The current snapshot reads `skills/cheese/SKILL.md` and its classification reference. It is selected prompt context, not the complete installed skill.

Optimize one candidate with bounded GEPA calls:

```bash
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/prompt_lab.py optimize \
  --dataset tests/fixtures/prompt_lab/dataset.json --seed-prompt current \
  --model gpt-4.1-mini --output-dir .context/prompt-lab/opt-01 \
  --max-calls 64 --max-metric-calls 8
```

Evaluate the sealed holdout separately after optimization:

```bash
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/prompt_lab.py evaluate \
  --dataset tests/fixtures/prompt_lab/dataset.json --prompt .context/prompt-lab/opt-01/best_candidate.md \
  --split holdout --model gpt-4.1-mini --output-dir .context/prompt-lab/holdout-01
```

Every output directory must be new. Artifacts include hashes, model settings, repeat count, per-case checkpoints, failures, aggregate score, eligibility, call count, and provider token usage when available. `--max-calls` caps task and reflection requests; `--max-metric-calls` caps GEPA metric calls; `--max-output-tokens` bounds task and reflection responses. Increase the output-token bound if reflection truncates. These are call and token limits, not dollar guarantees.

## Limits and privacy

This is an explicit proxy, not a tool or harness execution. It replays each scenario as user turns with prior model replies in history. Expected values and grading checks stay outside task prompts. Invalid JSON scores zero with diagnostics; provider failures stop loudly. The tiny curated suite is a pipeline smoke test, not a statistical quality claim. Only sanitized fixtures belong in this repository. Custom prompts are sent to the provider during paid evaluation. Review official [GEPA documentation](https://github.com/gepa-ai/gepa) and [DSPy documentation](https://dspy.ai/) for context; this prototype uses bare GEPA rather than DSPy or LiteLLM.


## Fixture acceptance table

| Family | Split | Proxy behavior |
| --- | --- | --- |
| Iterative authorization | train | Distinguishes prototype permission from publication permission. |
| Exceptions | train | Preserves both exceptions before removing scout only. |
| Relationship correction | validation | Switches from category grouping to dependency semantics. |
| Revision evidence | validation | Requires current-head CI and review evidence before merge readiness. |
| Checkpoint and deferral | holdout | Reuses a verified checkpoint and records explicit deferral without re-audit. |
| Cross-repo investigation | holdout | Retains evidence-based findings while staying cross-repository and harness-neutral. |

These cases test a small sequential proxy. They do not measure a general agent outcome or tool execution quality.

## Agent laboratory

`scripts/agent_lab.py` is the outcome-graded counterpart. It runs headless `claude -p` once per task inside a disposable copy of a fixture repository, injects the task's bug first, and grades the resulting tree with the task's own test command. The candidate Markdown is appended to the agent's system prompt. The agent, its tools, and its file edits are real; the tasks are small.

Tasks use the tilth benchmark shape: a prompt, one or more `original` to `mutated` string mutations, a `test_command` that fails while the bug is present, and optional required or forbidden reply strings. The committed fixture has one task per split against `tests/fixtures/prompt_lab/repo`.

```bash
python3 scripts/agent_lab.py validate tests/fixtures/prompt_lab/agent_tasks.json
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/agent_lab.py evaluate \
  --tasks tests/fixtures/prompt_lab/agent_tasks.json --prompt baseline --split validation \
  --model claude-haiku-4-5-20251001 --output-dir .context/agent-lab/eval-01 --max-budget-usd 0.25
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/agent_lab.py optimize \
  --tasks tests/fixtures/prompt_lab/agent_tasks.json --seed-prompt current \
  --model claude-haiku-4-5-20251001 --output-dir .context/agent-lab/opt-01 --max-runs 40 --max-metric-calls 8
```

`--prompt current` reads `skills/cook/SKILL.md`. `--max-runs` caps agent runs plus reflection calls; `--max-budget-usd` caps each single run through the CLI's own budget flag; `--timeout-seconds` bounds each run and each test command. Optimization evaluates the seed on train plus validation first and exports `best_candidate.md` only when the best candidate scores strictly higher. A run budget that ends early still writes `result.json` with the records so far. Pass `--keep-workspaces` to retain every agent workspace under the output directory for inspection.

The runner uses the session's Claude Code authentication and drops user and project settings, hooks, and MCP servers for each run. It passes `--dangerously-skip-permissions` because the workspace is disposable; never point it at a real checkout. Reflection also runs through `claude -p`, so no OpenAI key is needed for this path. Three synthetic tasks are a harness smoke test, not a quality claim; a real suite needs pinned external repositories like the tilth benchmark's fix tasks.

## Tilth runner

`agent_lab.py optimize --runner tilth` swaps the `claude -p` runner for tilth's own
`benchmark/run.py` harness and a real GEPA search over a `/cook` skill candidate (a
dict of repo-relative component paths: `skills/cook/SKILL.md`, its `references/*.md`,
and `src/easy_cheese/skills/cook/**/*.py`). Each unique candidate GEPA proposes gets
its own disposable `.claude-plugin` overlay, built with `candidate build`'s guard
pipeline (a token-budget check, then a build gate when the candidate touches code).
A guard violation scores as a fixed, always-dominated point; it never calls the
benchmark runner.

```bash
python3 scripts/agent_lab.py tasks mine --repo owner/name --out mined_tasks.json \
  --tilth-root /path/to/tilth
python3 scripts/agent_lab.py validate mined_tasks.json
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/agent_lab.py optimize \
  --runner tilth --tasks mined_tasks.json --model unused --seed current \
  --tilth-root /path/to/tilth --search-model haiku \
  --validation-model haiku --output-dir .context/agent-lab/tilth-opt-01 \
  --max-metric-calls 40
```

`tasks mine` pulls SHA-pinned fix tasks from a repository's merged pull requests and
gates each one on tilth's `benchmark/check_task.py` (the task must fail at its base
commit and pass at its head commit). It mines only lowercase Conventional Commit
`fix:` titles, and by default only pull requests whose author association is OWNER,
MEMBER, or COLLABORATOR; pass `--allow-untrusted-authors` to mine every merged pull
request regardless of author. The CLI output reports each dropped pull request's
number and reason under `drops`. A mined task set is untrusted input: `test_patch`
and `test_command` come from the source repository, so run `validate`, `optimize`,
and `graduate` against it only inside a sandboxed checkout, never against a real one.

`--search-model`, `--validation-model`, `--reflection-model`, and `graduate`'s
`--models` all take a tilth benchmark model alias (for example `haiku`, `sonnet`,
`sonnet5`, `opus`, `fable`), not a full model ID; `benchmark/run.py` rejects anything
else. `--search-model` runs train-split tasks; `--validation-model` runs
validation-split tasks; both accept a cheaper alias than the final holdout check.
`optimize`'s output is a Pareto front over `(correctness, -tokens)`, one candidate
directory per front member, plus `result.json`.

After optimization, grade a candidate against the seed on the sealed holdout split
with `graduate`:

```bash
uv run --no-project --with-requirements requirements/prompt-lab.txt python scripts/agent_lab.py graduate \
  --seed current --candidate .context/agent-lab/tilth-opt-01/candidates/<sha> \
  --holdout mined_tasks.json --tilth-root /path/to/tilth \
  --models sonnet,opus,fable \
  --output-dir .context/agent-lab/graduation-01
```

`--models` defaults to `sonnet,opus,fable` and rejects any set missing one of
those three aliases; graduation always grades a candidate at all three.

`graduate` promotes only when the candidate is non-dominated on every model and
strictly better on at least one axis on at least one model. A promotion writes
`best_candidate/` and `graduation.json` under `--output-dir`; a hold writes neither.
Every build runs inside a disposable `git worktree`, so the real checkout is never
written.