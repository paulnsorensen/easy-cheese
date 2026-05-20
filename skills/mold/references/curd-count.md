# Curd count — recommendation driver

Runs after Curdle writes the spec, before the Handoff menu renders. Pushes the
parse-and-count work into a Python script so the recommendation is deterministic
and stays out of the conversation's token budget.

## What it answers

Which downstream skill should hold the *(recommended)* slot in the Handoff menu —
`/cheese-factory`, `/ultracook`, `/cook --auto`, or `/cook`?

`/cheese-factory`'s own trigger is "decomposes into 5+ independent behavioural
curds". Below that count, the choice between `/cook`, `/cook --auto`, and
`/ultracook` is driven by the shape-check's blast-radius verdict.

## Procedure

After `curdle.md` writes the spec to disk, run the script and read the JSON
digest into context:

```bash
python3 skills/mold/scripts/curd-count.py .cheese/specs/<slug>.md \
  --blast-radius <low|medium|high>
```

Pass the `--blast-radius` value verbatim from the shape-check verdict line
(see `shape-check.md`). If shape-check was skipped or its verdict was `[?]`,
omit the flag — the recommendation will degrade to `/cook` for sub-threshold
specs.

## Signals counted

| Signal | Source in the spec |
| --- | --- |
| `goals` | Bullets under `## Goals` |
| `quality_gates` | Bullets under `## Quality gates` (also matches `## Acceptance criteria` for legacy specs) |
| `decisions` | Bullets under `## Decisions` (reported but not used in the rule) |

`candidate_curds = max(goals, quality_gates)`. Decisions are reported as a
sanity check — a spec with 8 decisions but 2 goals is usually one coherent
change with many tradeoffs, not 8 curds.

## Decision rule

The script only picks among the three skills that can hold the *(recommended)*
slot. `--auto` variants (`/cook --auto`, etc.) are user-opt-in alternatives
surfaced by the Handoff menu — the script never recommends them, because
"Never pre-select; auto mode is opt-in" is an existing mold rule.

| `candidate_curds` | `blast_radius` | Recommended |
| --- | --- | --- |
| ≥ 5 | any | `/cheese-factory` |
| < 5 | `high` | `/ultracook` |
| < 5 | `medium`, `low`, or unknown | `/cook` |

## Digest shape

```json
{
  "spec_path": ".cheese/specs/<slug>.md",
  "slug": "<slug>",
  "blast_radius": "high",
  "candidate_curds": 7,
  "signals": {"goals": 7, "quality_gates": 6, "decisions": 3},
  "threshold": 5,
  "decomposable": true,
  "recommended_skill": "/cheese-factory",
  "rationale": "7 candidate curds >= 5 threshold",
  "notes": [
    "Count is a signal, not a verdict.",
    "Confirm curd independence (criterion 4: file-disjoint) before dispatching /cheese-factory."
  ]
}
```

## Independence is the user's call

The script counts; it cannot verify that the candidate curds are file-disjoint
(`/cheese-factory`'s criterion 4) from spec text alone. Before dispatching
`/cheese-factory`, mold must confirm independence with the user — typically by
naming the file footprints captured in `## Interface sketches` and asking
whether any two candidate curds touch the same file. If they do, the recommended
slot should fall back to `/ultracook` even when the count clears the threshold.

## When tilth / Python is unavailable

The script depends only on the Python 3 stdlib. If the host has no `python3`,
mold falls back to the pre-script Handoff: blast-radius alone picks
`/ultracook` (high) or `/cook --auto`/`/cook` (low or medium), and
`/cheese-factory` appears in the option list with a manual "if this spec
decomposes into 5+ independent curds, pick this" tagline. The user makes the
call without a computed recommendation. Say the substitution out loud.
