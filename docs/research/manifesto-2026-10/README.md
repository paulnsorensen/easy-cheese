# Manifesto evidence bundle (2026-10-18)

This directory holds the research behind the easy-cheese tenets in
`.hallouminate/wiki/easy-cheese-manifesto.md`. The files in the table are
verbatim copies of reports from the durable cheese corpus at
`~/.local/share/cheese/paulnsorensen-easy-cheese/research/`. The corpus stays
the source of truth; this copy exists so the evidence travels with the repo
and with the pull request.

## What is here

| File | Source slug | Checked | sha256 (12) |
| --- | --- | --- | --- |
| `rebuild/rebuild-easy-cheese-from-scratch.md` | rebuild-easy-cheese-from-scratch | 2026-09-21 | `fb07226ecc46` |
| `rebuild/session-2026-09-27-skills-schemas-cli.md` | same | 2026-09-27 | `6e88233d3d6e` |
| `rebuild/session-2026-09-27-wheypoint-milknado-grounding.md` | same | 2026-09-27 | `4dd1e4560f6b` |
| `rebuild/session-2026-10-03-workflows-stream.md` | same | 2026-10-03 | `bd34fb1c2ec9` |
| `rebuild/measured/f-01-session-usage.md` | same, raw | 2026-09-21 | `526e0aa6938e` |
| `rebuild/measured/f-02-pipeline-cost.md` | same, raw | 2026-09-21 | `6ca08dd06cd8` |
| `rebuild/measured/f-03-wiki-decisions.md` | same, raw | 2026-09-21 | `bf3dac2f8c5b` |
| `rebuild/diagrams/1-stores-and-packages.svg` | same, diagrams | 2026-09-27 | `1b60e7230aab` |
| `rebuild/diagrams/2-work-graph.svg` | same | 2026-09-27 | `3b2d32264d1c` |
| `rebuild/diagrams/3-execution-loop.svg` | same | 2026-09-27 | `a48d7922b87d` |
| `rebuild/diagrams/4-wheypoint-record-shape.svg` | same | 2026-09-27 | `4f1b644bd737` |
| `rebuild/diagrams/5-coupling-a-pointer.svg` | same | 2026-09-27 | `4a60e349fc7f` |
| `rebuild/diagrams/6-coupling-b-merged.svg` | same | 2026-09-27 | `7f21d3054fe0` |
| `adjacent/context-compilation-work-records.md` | context-compilation-work-records | 2026-10-04 | `4c2435727283` |
| `adjacent/major-workflow-artifact-contracts.md` | major-workflow-artifact-contracts | 2026-10-04 | `896ca3074724` |
| `adjacent/gepa-workflow-level-cheese-flow.md` | gepa-workflow-level-cheese-flow | 2026-10-03 | `b7e72b02e9df` |
| `adjacent/gepa-workflow-grader-design-evidence.md` | gepa-workflow-grader-design-evidence | 2026-10-03 | `a99b0e341603` |

`evidence-digests.md` is new. It condenses what six read-only sub-agents
found in the wheypoint records, the wiki, and skillz-that-grillz on
2026-10-18. `manifesto-review.md` is the synthesis of that pass.

## What is not here

- The 44 raw page captures under `rebuild/raw/` (`a-*`, `b-*`, `c-*`, `d-*`,
  `e-*`, and the `*-calls.jsonl` ledgers). They are third-party page bodies
  and search digests. The main report cites them by file name.
- The `.dot` and `.png` forms of the six diagrams. The SVG is enough.
- The wheypoint work records themselves. They live under
  `~/.local/share/cheese/paulnsorensen-easy-cheese/work/<work_id>/` and are
  cited by work id and revision in `evidence-digests.md`.

## How to read it

1. Start with the canonical tenets and rulings in
   `.hallouminate/wiki/easy-cheese-manifesto.md`.
2. Read `manifesto-review.md` for the per-tenet verdicts and the research
   behind the rulings. Its proposals and fork list are evidence, not decisions.
3. Open `evidence-digests.md` for the record-level facts behind each claim.
4. Open the reports under `rebuild/` and `adjacent/` for the cited sources.

Citations inside the copied reports use the corpus layout (`raw/f-01-...`).
The `f-*` files are under `rebuild/measured/`; the others are not copied.
