# Cure round 2: pasteurize

This note records every finding from the pasteurize review notes.
It gives the state, the commit, and the evidence for each finding.

## Findings

| # | Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | review-pasteurize.md | blocker | `debug-tag-sweep` cannot certify a clean repository. | applied | `70550468` | `src/easy_cheese/skills/pasteurize/debug_tag_sweep.py:77-91,122-170`; `skills/pasteurize/SKILL.md:240-253`; `tests/pasteurize/python/test_debug_tag_sweep.py:224-407` |
| 2 | review-pasteurize.md | blocker | The rerun verdict cannot confirm the expected failure. | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:102-170`; `tests/pasteurize/python/test_repro_rerun.py:117-196` |
| 3 | review-pasteurize.md | blocker | The handoff cannot meet the canonical phase contract. | partly applied | `053be9c6` | `skills/pasteurize/SKILL.md:332-363`. The template now parses. The phase registration is `deferred: owned by schemas` — see Disagreements. |
| 4 | review-pasteurize.md | high | The skill looks for specifications in the wrong store. | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:39-40` |
| 5 | review-pasteurize.md | high | `repro-rerun` has no execution timeout. | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:49-99,126-143`; `tests/pasteurize/python/test_repro_rerun.py:199-230` |
| 6 | review-pasteurize.md | high | The frontmatter does not identify user triggers. | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:3-10` |
| 7 | review-pasteurize.md | medium | The bundle ships an unused fan-out command. | rejected | (none) | `tests/python/test_fanout_sizing_docs.py:229-270` asserts the fan-out table and its constants. Removal needs an edit in a test file outside this area. |
| 8 | review-pasteurize.md | medium | The skill lacks the required discipline section. | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:18-36` |
| 9 | review-pasteurize.md | low | The fan-out table omits the exact score of 250. | deferred | (none) | `tests/python/test_fanout_sizing_docs.py:232-233` asserts the literal `score < 250` and `score > 250`. The fix needs an edit outside this area. |
| 10 | review-pasteurize.md | STE100 | `SKILL.md` uses `signal` and `loop` for one meaning. | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:85-86` |
| 11 | review-pasteurize.md | STE100 | `SKILL.md` gives two Claude commands in one sentence. | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:153-154` |
| 12 | review-pasteurize.md | STE100 | `references/commands.md` uses `lanes`. | applied | `ad804f64` | `skills/pasteurize/references/commands.md:8` |
| 13 | review-pasteurize.md | STE100 | `references/commands.md` uses `N` and `repro`. | applied | `ad804f64` | `skills/pasteurize/references/commands.md:9` |
| 14 | edge-affinage-pasteurize.md | blocker | The reproduction command can confirm the wrong claim. | applied | `eafcb9ea` | `src/easy_cheese/skills/pasteurize/repro_rerun.py:102-117`; `tests/pasteurize/python/test_repro_rerun.py:120-129` |
| 15 | edge-affinage-pasteurize.md | high | Pasteurize cannot return an investigation verdict to Affinage. | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:48-81` |
| 16 | edge-affinage-pasteurize.md | medium | Tests do not exercise the seam from either side. | partly applied | `eafcb9ea` | The consumer side has expectation tests. The Affinage producer test is `deferred: owned by affinage`. |
| 17 | edge-affinage-pasteurize.md | STE100 | Affinage prose violations. | deferred | (none) | `deferred: owned by affinage` |
| 18 | edge-cheese-pasteurize.md | high | Pasteurize drops `--open-pr` and `--hard`. | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:65-72` |
| 19 | edge-cheese-pasteurize.md | high | Pasteurize cannot write its handoff through the canonical writer. | partly applied | `053be9c6` | The preamble now matches the parser. The registry entry is `deferred: owned by schemas`. |
| 20 | edge-cheese-pasteurize.md | high | Pasteurize uses a stop status for outcomes that it routes. | applied | `053be9c6` | `skills/pasteurize/SKILL.md:111-112,353-363,401-404` |
| 21 | edge-cheese-pasteurize.md | high | Tests do not exercise the Cheese seam. | deferred | (none) | The transition test needs the phase registry entry from row 19. |
| 22 | edge-cheese-pasteurize.md | medium | Pasteurize defines no consumer for `wiki_hits`. | applied | `0e5f359b` | `skills/pasteurize/SKILL.md:74-77` |
| 23 | edge-cheese-pasteurize.md | STE100 | Cheese prose violations. | deferred | (none) | `deferred: owned by cheese` |
| 24 | edge-cheese-pasteurize.md | STE100 | `SKILL.md:39,142,204` violations. | applied | `67cf8c20` | `skills/pasteurize/SKILL.md:99-103,217-218,285` |
| 25 | edge-cook-pasteurize.md | high | Cook cannot consume the documented Pasteurize slug. | applied on the Cook side | `a2b7ccd4` | `cure2-cook.md:52` records the Cook fix. This side keeps `.cheese/pasteurize/<slug>.md` and names the output contract at `skills/pasteurize/SKILL.md:327-367`. |
| 26 | edge-cook-pasteurize.md | high | Pasteurize cannot emit the required canonical handoff. | partly applied | `053be9c6` | Same as row 19. |
| 27 | edge-cook-pasteurize.md | medium | Tests cover only the Cook side of the dispatch. | deferred | (none) | The seam test needs the phase registry entry from row 19. |
| 28 | edge-cook-pasteurize.md | STE100 | Cook prose violations. | deferred | (none) | `deferred: owned by cook` |
| 29 | hub-shared.md | medium | The generated route command treats `--help` as a file path. | deferred | (none) | `deferred: owned by shared`. The fix belongs to `json_command` in `src/easy_cheese/shared/`. |
| 30 | hub-schemas.md | high | Cheese does not consume the full phase registry. | deferred | (none) | `deferred: owned by cheese and schemas` |
| 31 | hub-build.md | — | No row names `pasteurize`. | not applicable | (none) | `hub-build.md` lists only `wheypoint -> build`. |

`skill-review-cure.md` does not exist in this worktree.

## Disagreements

- **The Pasteurize phase registration.** `edge-cook-pasteurize.md` assigns the
  fix to Pasteurize. `cure2-cheese.md:47` assigns the same fix to `schemas`.
  The compiled registry lives at
  `src/easy_cheese_schemas/_compiled_phase_registry.py`, and its declaration
  test lives at `tests/schemas/python/test_phase_contracts.py:34-38`. Both
  files sit outside the `pasteurize` area paths. I kept the typed schema
  contract as the owner and deferred the registration to `schemas`. This side
  now emits a preamble that the shared parser reads correctly, so the fix
  reduces to adding `skills/pasteurize/phase-contract.yaml` and recompiling.

- **The exact score of 250 (row 9) and the dormant route command (row 7).**
  `review-pasteurize.md` asks for `<= 250` and for the removal of
  `pasteurize-route`. `tests/python/test_fanout_sizing_docs.py` asserts the
  literal `score < 250` string and the complete fan-out table. That test file
  is in no area path list. I kept the current prose, because a truthful fix
  needs a matching test change outside this area.

## Scope note

The area path list names four files. Two blockers and one high have their root
cause in `src/easy_cheese/skills/pasteurize/repro_rerun.py` and
`src/easy_cheese/skills/pasteurize/debug_tag_sweep.py`. No other area owns
those modules, and no other cure node reads these notes. I therefore treated
the complete `src/easy_cheese/skills/pasteurize/` package and
`tests/pasteurize/` as this area.

## Follow-ups

- Add `skills/pasteurize/phase-contract.yaml` and recompile the phase registry.
- Add the Pasteurize row to `tests/schemas/python/test_phase_contracts.py`.
- Add a seam test for the Cheese dispatch, the Pasteurize handoff, and the Cook
  resume.
- Add an Affinage producer test for the investigation request.
- Add help handling to `json_command` in `src/easy_cheese/shared/`.
- Change `tests/python/test_fanout_sizing_docs.py` to accept `score <= 250`,
  then correct the fan-out table.
- Remove `pasteurize-route` and its shared policy when the fan-out test moves
  with it.
- Rebuild `skills/pasteurize/scripts/pasteurize.pyz` at the integration
  barrier. The bundle tests in `tests/pasteurize/python/` run against the
  archive, and this node did not rebuild it.
