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