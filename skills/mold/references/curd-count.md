# Curd count — recommendation driver

Runs after Curdle writes the spec, before finalization. Pushes the parse-and-count
work into a Python script so the sizing signal is deterministic and stays out
of the conversation's token budget.

## What it answers

Curd-count reports candidate sizing and the recommended downstream skill. The
digest includes goal, quality-gate, and decision signals; landing metadata; and
an advisory Cook wave-plan mode. It has no handoff field and does not construct
an execution command. Finalization alone evaluates all required evidence and
publishes a canonical Cook handoff when the result is ready.

The recommendation names the skill only. The count is advisory sizing: it never
authorizes Cook, bypasses finalization, or turns a saved non-ready result into a
runnable handoff.

A decomposition of `PARALLEL_THRESHOLD` (2) or more curds signals a parallel
Cook wave-plan; below that, high blast radius signals a linear chain. The
decomposer stays authoritative—the count is a pre-dispatch hint, not the mode
gate. `/ultracook` is retired as a top-level skill choice.

## Procedure

After `curdle.md` writes the spec to disk, run the script and read the JSON
digest into context:

```bash
SPEC=$(python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>)
python3 skills/mold/scripts/mold.pyz curd-count "$SPEC" \
  --blast-radius <low|medium|high>
```

Pass the `--blast-radius` value verbatim from the shape-check verdict line
(see `shape-check.md`). If shape-check was skipped or its verdict was `[?]`,
omit the flag; the route stays `/cook`, while
sub-threshold specs receive no Cook mode hint.

## Signals counted

| Signal | Source in the spec |
| --- | --- |
| `goals` | Bullets under `## Goals` |
| `quality_gates` | Bullets under `## Quality gates` (also matches `## Acceptance criteria` for legacy specs) — reported, **not** counted |
| `decisions` | Bullets under `## Decisions` (reported but not used in the rule) |

`candidate_curds = goals` — only distinct behavioural goals drive the count.
`quality_gates` (acceptance criteria) and `decisions` are reported as signals
but deliberately excluded from the count: they are facets of one coherent
change, not independent file-disjoint curds. Counting acceptance criteria as
curds inflated the recommendation toward parallel fan-out for single coherent
refactors whose own criteria reference the same files (issue #111) — the more
thoroughly a spec was written, the more likely it mis-recommended fan-out.

## Decision rule

`recommended_skill` is always `/cook`; it is an advisory destination, not an
execution decision. Curd-count emits no handoff or command. The independent Cook
mode signal follows the curd count and blast radius:

| `candidate_curds` | `blast_radius` | `mode` |
| --- | --- | --- |
| ≥ 2 (`PARALLEL_THRESHOLD`) | any | `parallel` |
| < 2 | `high` | `linear` |
| < 2 | `medium`, `low`, or unknown | `null` |

## Digest shape

```json
{
  "spec_path": "<resolver-owned durable spec path for <slug>>",
  "slug": "<slug>",
  "blast_radius": "high",
  "candidate_curds": 7,
  "signals": {"goals": 7, "quality_gates": 6, "decisions": 3},
  "threshold": 2,
  "decomposable": true,
  "recommended_skill": "/cook",
  "mode": "parallel",
  "rationale": "7 candidate curds >= 2 threshold; parallel fan-out (advisory)"
}
```

## Independence is the user's call

The script counts; it cannot verify that the candidate curds are file-disjoint
(criterion 4) from spec text alone. Before a parallel wave-plan runs, mold
confirms independence with the user — typically by naming each curd's `scope`
from the typed `CurdPlan` (the planner derives file footprints from the
Placement block's `slice:` and `public interface:` lines plus the shape-check
importer list; `## Interface sketches` itself carries no file paths) and
asking whether any two candidate curds touch the same file. If they do, the decomposer folds the shared-file
curds back into the linear chain; the dispatched skill is `/cook` either way.

## When tilth / Python is unavailable

The script depends only on the Python 3 stdlib. If the host has no `python3`,
Mold may report the sizing signal manually: count the behavioural goals and
apply the blast-radius mode table. Finalization still owns readiness and
publishes any Cook handoff; do not substitute an execution command.
