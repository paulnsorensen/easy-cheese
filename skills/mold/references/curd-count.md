# Curd count — recommendation driver

Runs after Curdle writes the spec, before the Handoff menu renders. Pushes the
parse-and-count work into a Python script so the recommendation is deterministic
and stays out of the conversation's token budget.

## What it answers

Gate applicability selects the immediate handoff. A `red-required` spec
recommends `/cut`; Cut's receipt then unlocks Cook. A closed
`not-applicable` spec and a legacy spec without a declaration recommend
`/cook`. Mold-produced specs are marked with `source: mold-handshake` or
`source: agent-mini-spec`; their `gate_applicability.ui_surface` is mandatory.
The digest also records the eventual Cook wave-plan mode: parallel curd
fan-out, a linear chain, or no mode hint.

The recommendation names the skill only. `--auto` remains a user-selected
menu choice, while the digest's `handoff.command` preserves the executable
automatic route when the user selects it.

A decomposition of `PARALLEL_THRESHOLD` (2) or more curds signals a parallel
Cook wave-plan; below that, high blast radius signals a linear chain. The
decomposer stays authoritative—the count is a pre-dispatch hint, not the mode
gate. `/ultracook` is retired as a top-level skill choice.

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
omit the flag; applicability still selects `/cut` or `/cook`, while
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

| Gate applicability | `recommended_skill` | `handoff` |
| --- | --- | --- |
| `red-required` | `/cut` | `command: ["/cut", "--auto", "<spec-path>"]` |
| closed `not-applicable` | `/cook` | `null` |
| no declaration (legacy) | `/cook` | `null` |

For a Mold provenance marker, the parser also requires
`ui_surface: browser | non-browser | not-applicable`. `browser` validates
both the interface and outer seam in every Test Contract; `non-browser` is
explicit and does not infer applicability from prose. The unmarked approved v1
spec and other legacy specs remain consumable by Cut without this field.
The independent Cook mode signal follows the curd count and blast radius:

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
  "recommended_skill": "/cut",
  "handoff": {
    "next": "cut",
    "command": ["/cut", "--auto", "<spec-path>"],
    "spec_ref": "<spec-path>",
    "metadata": {"gate_applicability": {"disposition": "red-required", "work_class": "behavior", "ui_surface": "non-browser"}}
  },
  "mode": "parallel",
  "rationale": "red-required outer gate precedes 7 candidate curds >= 2 threshold; parallel fan-out"
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
Mold must still read the spec's `gate_applicability` declaration and render the
same immediate route: `red-required` to Cut, closed `not-applicable` to Cook,
and legacy specs to Cook. Blast radius may supply the Cook mode hint. The
`--auto` form remains an explicit user menu choice. Say the degraded
substitution out loud.
