# Curd count — recommendation driver

Runs after Curdle writes the spec, before the Handoff menu renders. Pushes the
parse-and-count work into a Python script so the recommendation is deterministic
and stays out of the conversation's token budget.

## What it answers

Whether to recommend `/cook` for the *(recommended)* slot in the Handoff
menu, and which internal wave-plan **mode** to signal alongside it: parallel
curd fan-out or the linear chain. `/cook` is the uniform recommendation —
`/ultracook` is retired as a top-level skill choice.

`/cook --auto` is a user-opt-in alternative the menu always offers in the
non-decomposable low/medium branch, but it is never a *recommended* pick: per
existing mold rules, "Never pre-select; auto mode is opt-in" — so the script
does not consider it.

A decomposition of `PARALLEL_THRESHOLD` (2) or more curds signals a parallel
wave-plan; below that, the choice between plain `/cook` and a linear-mode
`/cook` is driven by the shape-check's blast-radius verdict. The decomposer
stays authoritative — the count is a pre-dispatch hint, not the mode gate.

## Procedure

After `curdle.md` writes the spec to disk, run the script and read the JSON
digest into context:

```bash
SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)
python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz curd-count "$SPEC" \
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

The script always recommends `/cook` for the *(recommended)* slot and names
the internal `mode` signal alongside it. `--auto` variants (`/cook --auto`,
etc.) are user-opt-in alternatives surfaced by the Handoff menu — the script
never recommends them, because "Never pre-select; auto mode is opt-in" is an
existing mold rule.

| `candidate_curds` | `blast_radius` | `recommended_skill` (always `/cook`) | `mode` |
| --- | --- | --- | --- |
| ≥ 2 (`PARALLEL_THRESHOLD`) | any | `/cook` | `parallel` |
| < 2 | `high` | `/cook` | `linear` |
| < 2 | `medium`, `low`, or unknown | `/cook` | `null` |

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
  "rationale": "7 candidate curds >= 2 threshold; parallel fan-out",
  "notes": [
    "Count is a signal, not a verdict.",
    "candidate_curds = goals only; acceptance-criteria / quality-gate count does not drive it (issue #111).",
    "Confirm curd independence (criterion 4: file-disjoint) before /cook fans out in parallel waves."
  ]
}
```

## Independence is the user's call

The script counts; it cannot verify that the candidate curds are file-disjoint
(criterion 4) from spec text alone. Before a parallel wave-plan runs, mold
confirms independence with the user — typically by naming the file footprints
captured in `## Interface sketches` and asking whether any two candidate
curds touch the same file. If they do, the decomposer folds the shared-file
curds back into the linear chain; the dispatched skill is `/cook` either way.

## When tilth / Python is unavailable

The script depends only on the Python 3 stdlib. If the host has no `python3`,
mold falls back to the pre-script Handoff: blast-radius alone recommends
`/cook` and signals a parallel or linear wave-plan (high blast radius signals
linear mode; low or medium recommends `/cook` with no mode) for the
*(recommended)* slot, and a parallel wave-plan appears in the option list
with a manual "if this spec decomposes into 2+ independent curds, the
decomposer will fan it out" tagline. `/cook --auto` stays where it always
lives — as a user-opt-in alternative in the non-decomposable low/medium menu,
never the recommended pick. Say the substitution out loud.
