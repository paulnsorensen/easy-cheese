# Cure round 2: plate

Every finding from the plate review notes, the plate edge notes, and the hub notes.
`skill-review-cure.md` does not exist at HEAD.
The reconcile gate passes: ruff, typecheck, skill validation, and 45 area tests.

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-plate.md | high | Plate and `/gh` both claim pull request creation | deferred: owned by the `gh` skill, which is outside the plate area paths | — | `skills/plate/SKILL.md:5-8,18-22` keeps exclusive creation. `skill://gh:5-12` still routes creation |
| review-plate.md | high | `stack-tools` discards service-error evidence | applied | d7b66ec0 | `src/easy_cheese/skills/plate/stack_tools.py:61-95`; `tests/python/test_plate_runtime.py:274-303` |
| review-plate.md | high | The stack recovery test accepts a prohibited Git command | applied | 3b963978 | `tests/python/test_plate_contract.py:101-131` |
| review-plate.md | medium | The routing guard and mode table disagree on inspection | applied | 45598f90 | `skills/plate/SKILL.md:37-39` |
| review-plate.md | medium | New pull request mode conflicts with the one-reference rule | applied | 45598f90 | `skills/plate/SKILL.md:29,41-50` |
| review-plate.md | low | `SKILL.md` breaks the area prose rules | applied | 45598f90 | `skills/plate/SKILL.md:4-8,20,63,65,92,101,123` |
| review-plate.md | low | The generated command reference uses a second repository term | applied | f3b8c569 | `src/easy_cheese/skills/plate/commands.py:26-29`; `skills/plate/references/commands.md:7` |
| review-plate.md | low | `durable-writes.md` combines instructions | applied | aa80b223 | `skills/plate/references/durable-writes.md:3-4,39-40` |
| review-plate.md | low | `gh-stack.md` uses passive voice and compound instructions | applied | aa80b223 | `skills/plate/references/gh-stack.md:3-5,22-23,30-46,66-67,100` |
| review-plate.md | low | `ordinary-pr.md` breaks prose and list rules | applied | aa80b223 | `skills/plate/references/ordinary-pr.md:3,20,41,46,63` |
| review-plate.md | low | `stacks.md` breaks prose and term rules | applied | aa80b223 | `skills/plate/references/stacks.md:3-5,9,19,21,33,46,56` |
| review-plate.md | low | `topology.md` uses passive voice and compound instructions | applied | 0b3ffb93 | `skills/plate/references/topology.md:18,33,54` |
| review-plate.md | simplification | Say "load one reference at a time" | applied | 45598f90 | `skills/plate/SKILL.md:29` |
| review-plate.md | simplification | Remove `inspect` from the stack maintenance trigger | applied | 45598f90 | `skills/plate/SKILL.md:37-39` |
| review-plate.md | simplification | Move `test_plate_contract.py:307-345` to the Cook tests | rejected: the target file `tests/python/test_ultracook_skills.py` belongs to the `build` area | — | `tests/python/test_plate_contract.py:395-433` |
| review-plate.md | simplification | Keep `_http_status` and `_gh_stack_enablement` | applied | d7b66ec0 | `src/easy_cheese/skills/plate/stack_tools.py:57-95` |
| review-plate.md | simplification | Number `ordinary-pr.md:20` as step 7 | applied | aa80b223 | `skills/plate/references/ordinary-pr.md:20` |
| edge-cheese-plate.md | high | Publication flags can vanish before Plate | deferred: owned by `mold` and `pasteurize` | — | Plate accepts `--hard` at `skills/plate/SKILL.md:52` |
| edge-cheese-plate.md | high | The propagation tests check words, not commands | deferred: owned by `cheese`, which owns the route matrix | — | `skills/cheese/references/handoff-gate.md:56-75` |
| edge-cheese-plate.md | medium | The prose assigns `--open-pr` to two consumers | deferred: owned by `cheese` and `cure` | — | Plate documents no `--open-pr` input |
| edge-cheese-plate.md | medium | Plate does not define the hard-gate failure mode | applied | 45598f90 | `skills/plate/SKILL.md:56-65`; `tests/python/test_plate_contract.py:65-84` |
| edge-cook-plate.md | blocker | Cook auto mode grants publication without `--open-pr` | deferred: owned by `cook` | — | `skills/cook/references/auto-mode.md` |
| edge-cook-plate.md | high | The topology resolution has no typed storage contract | deferred: owned by `schemas` | — | `skills/plate/references/topology.md:66-70` persists `plate_layout` |
| edge-cook-plate.md | high | Plate rejects the complete Cook `pr_plan` | deferred: owned by `schemas`, which holds the canonical `PrPlan` | — | `src/easy_cheese/skills/plate/publication.py` reads the canonical model |
| edge-cook-plate.md | high | Cook assigns terminal Plate dispatch to two owners | deferred: owned by `cook` | — | `skills/cook/references/fan-pathway.md:320-322` |
| edge-cook-plate.md | medium | The tests inspect each side separately | applied on the Plate side | 0b3ffb93, 212782c7 | `tests/python/test_plate_contract.py:52-110,395-425` |
| edge-cure-plate.md | high | Cure writes tracked facts after Plate publishes | deferred: owned by `cure` | — | `skills/plate/SKILL.md:70-83` already requires every write first |
| edge-cure-plate.md | medium | The dispatch contract lacks paired tests | deferred: owned by `cure` for the producer half | — | `tests/python/test_plate_contract.py:426-434` |
| edge-plate-age.md | medium | The ownership edge has only Plate tests | applied | 212782c7 | `tests/python/test_plate_contract.py:395-425` |
| edge-plate-age.md | low | One Plate sentence contains two instructions | applied | 45598f90 | `skills/plate/SKILL.md:21` |
| edge-plate-cheese.md | high | The Plate summary in Cheese omits one trigger | deferred: owned by `cheese` | — | `skills/plate/references/topology.md:27-31` names both triggers |
| edge-plate-cheese.md | high | Plate does not handle the `Other` answer | applied | 0b3ffb93 | `skills/plate/references/topology.md:52-61` |
| edge-plate-cheese.md | high | The tests do not exercise the seam from both sides | applied on the Plate side | 0b3ffb93 | `tests/python/test_plate_contract.py:52-77` |
| edge-plate-cook.md | blocker | Cook drops the run identity that Plate requires | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:82-85`; `tests/python/test_plate_contract.py:80-96` |
| edge-plate-cook.md | high | The small-overlap path names an interface that does not exist | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:104-107` |
| edge-plate-cook.md | high | The mechanical overlap rule has no exact calculation | applied on the Plate side | 0b3ffb93 | `skills/plate/references/topology.md:87-97` |
| edge-plate-cook.md | medium | The tests do not exercise the seam from both sides | applied on the Plate side | 0b3ffb93 | `tests/python/test_plate_contract.py:79-96` |
| edge-plate-hard-cheese.md | blocker | A changed final state keeps an old PASS | deferred: owned by `hard-cheese` (`freshness_check.py`) | — | Plate now sends `tracked_diff_digest` at `skills/plate/references/durable-writes.md:58-70` |
| edge-plate-hard-cheese.md | high | Hard-cheese drops two required producer values | applied on the Plate side | 45598f90 | `skills/plate/references/durable-writes.md:58-70`; `tests/python/test_plate_contract.py:65-78` |
| edge-plate-hard-cheese.md | high | The gate outcome policy conflicts | applied on the Plate side | 45598f90 | `skills/plate/SKILL.md:56-65` |
| edge-plate-hard-cheese.md | high | The seam tests are one-sided and text-only | applied on the Plate side | 45598f90 | `tests/python/test_plate_contract.py:65-84` |
| hub-shared.md | ok | `plate -> shared` uses the shared manifest | no change needed | — | `src/easy_cheese/skills/plate/commands.py:8-34` |
| hub-schemas.md | — | No row for `plate` | no change needed | — | — |
| hub-build.md | — | No row for `plate` | no change needed | — | — |

## Disagreements

- `edge-cheese-plate.md` says that `--open-pr` reaches Plate. `skills/plate/SKILL.md` accepts only `--hard`.
  I kept the Plate contract and left `--open-pr` with `/cure`. The typed dispatch chain already ends at `/plate [--hard]`.
- `edge-plate-cook.md` names `worktree_harvest(branch, onto=run_branch)`. The shared module exposes the `worktree harvest` command.
  I kept the bundled command surface, because it exists at HEAD.

## STE100 status

compliant for every prose file in the plate area.

- `skills/plate/references/topology.md:40` keeps `prompt: How should this work be plated for review?`.
  This line is quoted transport material. The rule keeps quoted material unchanged.

## Follow-ups

- `gh` must give pull request creation to Plate and keep inspection and administration.
- `cook` must preserve `--open-pr` only when the invocation contains it. `cook` must add `run_branch` to `repair_dispatch`.
- `mold` and `pasteurize` must forward every in-scope publication flag.
- `cheese` must name both topology question triggers. `cheese` must add a route matrix test.
- `cure` must move its post-pull-request write-back before it dispatches Plate.
- `hard-cheese` must consume `artifacts`, `tracked_diff_digest`, and `gate`. It must bind freshness to the reviewed state.
- `schemas` must add `plate_layout` to the canonical `PrPlan`. It must add a typed topology record.
