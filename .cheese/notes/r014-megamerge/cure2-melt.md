# Cure round 2 — melt

This note records every finding from the melt review notes.
It gives the state, the commit, and the evidence for each finding.

## Source notes

- `.cheese/notes/r014-megamerge/review-melt.md`
- `.cheese/notes/r014-megamerge/hub-shared.md` (row for `melt`)
- `.cheese/notes/r014-megamerge/hub-schemas.md` (no row for `melt`)
- `.cheese/notes/r014-megamerge/hub-build.md` (no row for `melt`)
- `.cheese/notes/r014-megamerge/skill-review-cure.md` (absent at this node)

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-melt.md | blocker | The format guide skips supported structural merges. | applied | `9d23b4db` | `skills/melt/references/cascade-stages.md:9-13`; test `tests/python/test_melt_prose_contract.py:15` |
| review-melt.md | blocker | The Melt handoff violates the shared gate contract. | applied | `89c6adb9` | `skills/melt/SKILL.md:212-276`; tests `tests/python/test_melt_prose_contract.py:50,68,77` |
| review-melt.md | high | The cascade depends on hidden Git configuration. | applied | `7d7856a1` | `skills/melt/SKILL.md:26-30,142-174`; test `tests/python/test_melt_prose_contract.py:25` |
| review-melt.md | low | The zdiff3 claim is too broad. | applied | `c6a324d5` | `skills/melt/SKILL.md:209-211` (zdiff3 bullet) |
| review-melt.md | simplification | Use `conflict-summary` as the only source for format support. | applied | `9d23b4db` | `skills/melt/references/cascade-stages.md:9-13` |
| review-melt.md | simplification | Replace the Handoff prose list with one structured gate record. | applied | `89c6adb9` | `skills/melt/SKILL.md:217-261` |
| review-melt.md | simplification | Use one preflight for the rerere and kdiff3 requirements. | applied | `7d7856a1` | `skills/melt/SKILL.md:144-154` |
| review-melt.md | simplification | Keep the five command wrappers. | no change | none | `src/easy_cheese/skills/melt/commands.py:10-59` already holds five decorated callables |
| review-melt.md | follow-up | Update the shared handoff gate contract for an incomplete Git operation. | deferred: owned by cheese | none | `skills/cheese/references/handoff-gate.md:207-218` |
| hub-shared.md | ok | `melt -> shared` command dispatch. | no change | none | `src/easy_cheese/skills/melt/commands.py:7-63` |

## Edge states after the cure

| Edge | State | Evidence |
| --- | --- | --- |
| `melt -> shared`: command declarations | ok | `src/easy_cheese/skills/melt/commands.py:7-59` |
| `melt -> shared`: command dispatch | ok | `src/easy_cheese/skills/melt/commands.py:62-63` |
| `melt -> cheese`: code inspection | ok | `skills/melt/SKILL.md:18-22` |
| `melt -> cheese`: handoff selection | ok | `skills/melt/SKILL.md:217-261` matches `skills/cheese/references/handoff-gate.md:56-75,207-218` |
| `melt -> plate`: publication | ok | `skills/melt/SKILL.md:243-252,269-273`; `/plate` owns every durable write |
| `build -> melt`: command references | ok | `skills/melt/references/commands.md` is unchanged; the manifest is unchanged |

## Disagreements

none

## STE100 status

compliant

## Follow-ups

- `cheese` must extend `skills/cheese/references/handoff-gate.md` for an incomplete Git operation.
  The contract must say when the standard tail becomes safe.
  Melt encodes this rule locally at `skills/melt/SKILL.md:269-273` until the shared contract states it.
- A later barrier node must rebuild the melt bundle. This node changed no bundled module.
